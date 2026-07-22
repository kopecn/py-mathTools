"""Step 2 solver for the third-order (jerk-limited) position interface:
computes the profile that reaches the target at an EXACT prescribed
duration (time synchronization) -- the synchronization workhorse used to
line multiple DOFs up on a common trajectory duration.

Faithful port of ``SWIFT_MATH/OTG/position/PositionThirdOrderStep2.swift``
(~1,900 lines; the single largest file in the OTG port). See
``.claude/specs/otg.md`` §Internal fidelity requirements 2, 4, 5 and
``.claude/action-plan/39-otg-position-third-step2.md``.

**No alias-mutation hazard.** Unlike ``PositionThirdOrderStep1``
(``steps/position_third_order_step1.py``), this class does not accumulate a
``validProfiles`` list of saved candidates: every ``time*`` method takes and
mutates the single caller-owned ``Profile`` directly (an ``inout profile``
in Swift), trying its candidate branches in sequence and returning ``True``
on the first one that passes ``Profile.check_with_timing``. This is
architecturally identical to ``VelocityThirdOrderStep2``
(``steps/velocity_third_order.py``) -- no ``copy.deepcopy`` is needed
anywhere in this file.

**Dropped debug logging.** The Swift ``timeVel`` method guards a large
block of ``print(...)`` calls behind a hardcoded ``let debugTimeVel =
false`` -- permanently dead, developer-only tracing, not part of the
algorithm. Those prints are not ported (there is nothing to preserve:
``debugTimeVel`` is never ``true``); every branch, root search, and Newton
step they wrap around is preserved exactly.

**Dead branch, ported anyway.** ``timeNoneSmooth`` (Swift) /
``_time_none_smooth`` (here) is never called from ``getProfile`` in the
Swift source (grep-confirmed) -- ported anyway per otg.md design
constraint 2, mirroring ``PositionThirdOrderStep1``'s ``*_two_step``
precedent.

**Source quirk preserved verbatim.** ``timeAcc0``'s second ``do`` block is
labeled ``// UDUD`` in the Swift source but its ``checkWithTiming`` call
actually passes ``.UDDU`` -- a mismatched comment, not a bug in the
executed logic. Ported as literally written (``ControlSigns.UDDU``), not
"corrected" to match the comment, per otg.md's "translate mechanically;
do not restructure" rule.

**No ``_ieee754_div`` in this file.** otg.md §Internal fidelity requirement
4 only routes a division through the IEEE-754-semantics helper where a
*failing test* has shown a genuine Swift-``Double``-zero-denominator
hazard is reachable (see ``position_third_order_step1.py``'s
``_time_all_none_acc0_acc1``). No such case surfaced while developing this
chunk's test suite (three analytic cases at three prescribed-duration
scale factors each, plus a below-optimal negative case); every ``/`` here
is a plain Python division. If a future oracle/regression case reaches a
genuine zero denominator, add the helper then, scoped to that one site.
"""

from __future__ import annotations

import math

from math_tools.functional.roots import (
    evaluate_polynomial,
    polynomial_derivative,
    polynomial_monic_derivative,
    shrink_interval,
    solve_cubic,
    solve_quartic_monic,
)
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile

__all__: list[str] = []

#: Swift module-private ``tolerance`` constant (``PositionThirdOrderStep2.swift``
#: line 10) -- distinct from ``functional.roots``' ``POLYNOMIAL_TOLERANCE``
#: and from ``Profile``'s own epsilon constants.
_TOLERANCE = 1e-14

#: Swift ``Double.ulpOfOne`` (machine epsilon for float64).
_ULP = 2.220446049250313e-16


def _pow2(x: float) -> float:
    """Swift ``private func pow2(_:)`` -- squares ``x``."""
    return x * x


def _ieee754_sqrt(x: float) -> float:
    """IEEE 754 square root (Swift/C ``Double`` ``sqrt`` semantics): a
    negative argument silently yields ``nan`` -- never a crash. Python's
    ``math.sqrt`` raises ``ValueError`` on a negative argument instead,
    which diverges from the Swift source whenever a candidate branch's
    discriminant goes negative for a physically infeasible prescribed
    duration (below the Step1 time-optimal minimum) -- exactly the
    scenario this chunk's "below-optimal duration is infeasible" test
    exercises (see ``otg.md`` §Internal fidelity requirement 4's
    ``_ieee754_div`` precedent, the same principle applied to ``sqrt``).
    Swift silently propagates the resulting ``nan`` into ``profile.t[...]``,
    which then fails ``Profile.check``'s precision comparisons (``nan``
    comparisons are always false) rather than crashing; reproduced here
    explicitly.

    Unlike ``_ieee754_div`` (below) -- and unlike otg.md's own scoping note
    for division, which is deliberately NOT a blanket rule -- this helper
    IS used at every ``sqrt`` call site in this file rather than only the
    literal one the negative-duration test first tripped over. Once that
    test proved the hazard reachable, tracing it turned up a *cascade*:
    ``get_profile`` tries well over a dozen candidate branches in
    sequence for an infeasible (too-short) prescribed duration, and a
    negative discriminant is the generic, expected way each of those
    branches' algebra signals "no real solution here" -- not a rare
    degenerate root the way a zero denominator is for ``_ieee754_div``'s
    documented site. Patching sites one Newton-recursion at a time (this
    file has ~30 ``sqrt`` calls) would not change the outcome, only the
    number of iterations; wrapping every ``sqrt`` in this file (and only
    this file -- otg.md design constraint 4's per-site scoping still
    applies elsewhere) is the minimal change that matches the actually
    demonstrated failure mode. See ``39-otg-position-third-step2.md``'s
    Resolution notes for the full account.
    """
    if x < 0.0:
        return math.nan
    return math.sqrt(x)


def _ieee754_div(numerator: float, denominator: float) -> float:
    """IEEE 754 float division (Swift/C ``Double`` ``/`` semantics):
    ``0.0/0.0`` is ``nan``, ``x/0.0`` (``x != 0``) is a signed infinity --
    never a crash. Python's ``/`` operator raises ``ZeroDivisionError`` on
    any zero denominator instead. Matches
    ``steps/position_third_order_step1.py``'s identical helper (otg.md
    §Internal fidelity requirement 4); applied here ONLY at the specific
    site(s) this chunk's below-optimal-duration test showed reachable --
    unlike ``_ieee754_sqrt`` above, this is NOT a blanket replacement of
    every ``/`` in this file.
    """
    if denominator != 0.0:
        return numerator / denominator
    if numerator == 0.0:
        return math.nan
    return math.copysign(math.inf, numerator) * math.copysign(1.0, denominator)


class PositionThirdOrderStep2:
    """Mathematical equations for Step 2 in third-order position interface:
    time synchronization."""

    def __init__(
        self,
        tf: float,
        p0: float,
        v0: float,
        a0: float,
        pf: float,
        vf: float,
        af: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        self.p0 = p0
        self.v0 = v0
        self.a0 = a0
        self.tf = tf
        self.pf = pf
        self.vf = vf
        self.af = af
        self._v_max = v_max
        self._v_min = v_min
        self._a_max = a_max
        self._a_min = a_min
        self._j_max = j_max

        # Pre-calculated expressions.
        self.pd = pf - p0
        self.tf_p2 = tf * tf
        self.tf_p3 = self.tf_p2 * tf
        self.tf_p4 = self.tf_p2 * self.tf_p2

        self.vd = vf - v0
        self.vd_p2 = self.vd * self.vd
        self.v0_p2 = v0 * v0
        self.vf_p2 = vf * vf

        self.ad = af - a0
        self.ad_p2 = self.ad * self.ad
        self.a0_p2 = a0 * a0
        self.af_p2 = af * af

        self.a0_p3 = a0 * self.a0_p2
        self.a0_p4 = self.a0_p2 * self.a0_p2
        self.a0_p5 = self.a0_p3 * self.a0_p2
        self.a0_p6 = self.a0_p4 * self.a0_p2
        self.af_p3 = af * self.af_p2
        self.af_p4 = self.af_p2 * self.af_p2
        self.af_p5 = self.af_p3 * self.af_p2
        self.af_p6 = self.af_p4 * self.af_p2

        self.j_max_p2 = j_max * j_max

        self.g1 = -self.pd + tf * v0
        self.g2 = -2 * self.pd + tf * (v0 + vf)

        #: Swift declares ``minimize_jerk: Bool = false`` but never reads it
        #: -- dead field, ported for fidelity per otg.md design constraint 2.
        self.minimize_jerk = False

    def _time_acc0_acc1_vel(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        """Profile UDDU, Solution 1 / Profile UDUD."""
        if (2 * (a_max - a_min) + self.ad) / j_max < self.tf:
            h1 = (
                _ieee754_sqrt(
                    (
                        self.a0_p4
                        + self.af_p4
                        - 4 * self.a0_p3 * (2 * a_max + a_min) / 3
                        - 4 * self.af_p3 * (a_max + 2 * a_min) / 3
                        + 2 * (self.a0_p2 - self.af_p2) * a_max * a_max
                        + (4 * self.a0 * a_max - 2 * self.a0_p2)
                        * (
                            self.af_p2
                            - 2 * self.af * a_min
                            + (a_min - a_max) * a_min
                            + 2 * j_max * (a_min * self.tf - self.vd)
                        )
                        + 2 * self.af_p2 * (a_min * a_min + 2 * j_max * (a_max * self.tf - self.vd))
                        + 4
                        * j_max
                        * (
                            2 * a_min * (self.af * self.vd + j_max * self.g1)
                            + (a_max * a_max - a_min * a_min) * self.vd
                            + j_max * self.vd_p2
                        )
                        + 8 * a_max * self.j_max_p2 * (self.pd - self.tf * self.vf)
                    )
                    / (a_max * a_min)
                    + 4 * self.af_p2
                    + 2 * self.a0_p2
                    + (4 * self.af + a_max - a_min) * (a_max - a_min)
                    + 4 * j_max * (a_min - a_max + j_max * self.tf - 2 * self.af) * self.tf
                )
                * abs(j_max)
                / j_max
            )

            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = (
                -(
                    self.af_p2
                    - self.a0_p2
                    + 2 * a_max * a_max
                    + a_min * (a_min - 2 * self.ad - 3 * a_max)
                    + 2 * j_max * (a_min * self.tf - self.vd)
                )
                + a_min * h1
            ) / (2 * (a_max - a_min) * j_max)
            profile.t[2] = a_max / j_max
            profile.t[3] = (a_min - a_max + h1) / (2 * j_max)
            profile.t[4] = -a_min / j_max
            profile.t[5] = self.tf - (
                profile.t[0]
                + profile.t[1]
                + profile.t[2]
                + profile.t[3]
                + 2 * profile.t[4]
                + self.af / j_max
            )
            profile.t[6] = profile.t[4] + self.af / j_max

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.ACC0_ACC1_VEL,
            ):
                return True

        # Profile UDUD
        if (-self.a0 + 4 * a_max - self.af) / j_max < self.tf:
            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = (
                3 * (self.a0_p4 + self.af_p4)
                - 4 * (self.a0_p3 + self.af_p3) * a_max
                - 4 * self.af_p3 * a_max
                + 24 * (self.a0 + self.af) * a_max * a_max * a_max
                - 6 * (self.af_p2 + self.a0_p2) * (a_max * a_max - 2 * j_max * self.vd)
                + 6 * self.a0_p2 * (self.af_p2 - 2 * self.af * a_max - 2 * a_max * j_max * self.tf)
                - 12
                * a_max
                * a_max
                * (2 * a_max * a_max - 2 * a_max * j_max * self.tf + j_max * self.vd)
                - 24 * self.af * a_max * j_max * self.vd
                + 12 * self.j_max_p2 * (2 * a_max * self.g1 + self.vd_p2)
            ) / (
                12
                * a_max
                * j_max
                * (
                    self.a0_p2
                    + self.af_p2
                    - 2 * (self.a0 + self.af) * a_max
                    + 2 * (a_max * a_max - a_max * j_max * self.tf + j_max * self.vd)
                )
            )
            profile.t[2] = a_max / j_max
            profile.t[3] = (
                -self.a0_p2
                - self.af_p2
                + 2 * a_max * (self.a0 + self.af - 2 * a_max)
                - 2 * j_max * self.vd
            ) / (2 * a_max * j_max) + self.tf
            profile.t[4] = profile.t[2]
            profile.t[5] = self.tf - (
                profile.t[0]
                + profile.t[1]
                + profile.t[2]
                + profile.t[3]
                + 2 * profile.t[4]
                - self.af / j_max
            )
            profile.t[6] = profile.t[4] - self.af / j_max

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDUD,
                ReachedLimits.ACC0_ACC1_VEL,
            ):
                return True

        return False

    def _time_acc1_vel(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        """Profile UDDU / Profile UDUD."""
        ph1uddu = (
            self.a0_p2
            + self.af_p2
            - a_min * (self.a0 + 2 * self.af - a_min)
            - 2 * j_max * (self.vd - a_min * self.tf)
        )
        ph2uddu = (
            2 * a_min * (j_max * self.g1 + self.af * self.vd)
            - a_min * a_min * self.vd
            + j_max * self.vd_p2
        )
        ph3uddu = (
            self.af_p2 + a_min * (a_min - 2 * self.af) - 2 * j_max * (self.vd - a_min * self.tf)
        )

        polynom_uddu = [
            (2 * (2 * self.a0 - a_min)) / j_max,
            (4 * self.a0_p2 + ph1uddu - 3 * self.a0 * a_min) / self.j_max_p2,
            (2 * self.a0 * ph1uddu) / (self.j_max_p2 * j_max),
            (
                3 * (self.a0_p4 + self.af_p4)
                - 4 * (self.a0_p3 + 2 * self.af_p3) * a_min
                + 6 * self.af_p2 * (a_min * a_min - 2 * j_max * self.vd)
                + 12 * j_max * ph2uddu
                + 6 * self.a0_p2 * ph3uddu
            )
            / (12 * self.j_max_p2 * self.j_max_p2),
        ]

        t_min_uddu = -self.a0 / j_max
        t_max_uddu = min(
            (self.tf + 2 * a_min / j_max - (self.a0 + self.af) / j_max) / 2,
            (a_max - self.a0) / j_max,
        )

        roots_uddu = sorted(solve_quartic_monic(*polynom_uddu))
        for t0 in roots_uddu:
            if t0 < t_min_uddu or t0 > t_max_uddu:
                continue
            t = t0

            # Single Newton step (regarding pd).
            if abs(self.a0 + j_max * t) > 16 * _ULP:
                h0 = j_max * t * t
                orig = (
                    -self.pd
                    + (
                        3 * (self.a0_p4 + self.af_p4)
                        - 8 * self.af_p3 * a_min
                        - 4 * self.a0_p3 * a_min
                        + 6 * self.af_p2 * (a_min * a_min + 2 * j_max * (h0 - self.vd))
                        + 6
                        * self.a0_p2
                        * (
                            self.af_p2
                            - 2 * self.af * a_min
                            + a_min * a_min
                            + 2 * a_min * j_max * (-2 * t + self.tf)
                            + 2 * j_max * (5 * h0 - self.vd)
                        )
                        + 24
                        * self.a0
                        * j_max
                        * t
                        * (
                            self.a0_p2
                            + self.af_p2
                            - 2 * self.af * a_min
                            + a_min * a_min
                            + 2 * j_max * (a_min * (-t + self.tf) + h0 - self.vd)
                        )
                        - 24 * self.af * a_min * j_max * (h0 - self.vd)
                        + 12
                        * j_max
                        * (a_min * a_min * (h0 - self.vd) + j_max * (h0 - self.vd) * (h0 - self.vd))
                    )
                    / (24 * a_min * self.j_max_p2)
                    + h0 * (self.tf - t)
                    + self.tf * self.v0
                )
                deriv = (self.a0 + j_max * t) * (
                    (self.a0_p2 + self.af_p2) / (a_min * j_max)
                    + (a_min - self.a0 - 2 * self.af) / j_max
                    + (4 * self.a0 * t + 2 * h0 - 2 * self.vd) / a_min
                    + 2 * self.tf
                    - 3 * t
                )
                t -= orig / deriv

            h1 = (
                -(
                    (self.a0_p2 + self.af_p2) / 2
                    + j_max * (-self.vd + 2 * self.a0 * t + j_max * t * t)
                )
                / a_min
            )

            profile.t[0] = t
            profile.t[1] = 0.0
            profile.t[2] = self.a0 / j_max + t
            profile.t[3] = self.tf - (h1 - a_min + self.a0 + self.af) / j_max - 2 * t
            profile.t[4] = -a_min / j_max
            profile.t[5] = (h1 + a_min) / j_max
            profile.t[6] = profile.t[4] + self.af / j_max

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.ACC1_VEL,
            ):
                return True

        # Profile UDUD
        ph1udud = (
            self.a0_p2
            - self.af_p2
            + (2 * self.af - self.a0) * a_max
            - a_max * a_max
            - 2 * j_max * (self.vd - a_max * self.tf)
        )
        ph2udud = a_max * a_max + 2 * j_max * self.vd
        ph3udud = self.af_p2 + ph2udud - 2 * a_max * (self.af + j_max * self.tf)
        ph4udud = 2 * a_max * j_max * self.g1 + a_max * a_max * self.vd + j_max * self.vd_p2

        polynom = [
            (4 * self.a0 - 2 * a_max) / j_max,
            (4 * self.a0_p2 - 3 * self.a0 * a_max + ph1udud) / self.j_max_p2,
            (2 * self.a0 * ph1udud) / (self.j_max_p2 * j_max),
            (
                3 * (self.a0_p4 + self.af_p4)
                - 4 * (self.a0_p3 + 2 * self.af_p3) * a_max
                - 24 * self.af * a_max * j_max * self.vd
                + 12 * j_max * ph4udud
                - 6 * self.a0_p2 * ph3udud
                + 6 * self.af_p2 * ph2udud
            )
            / (12 * self.j_max_p2 * self.j_max_p2),
        ]

        t_min = -self.a0 / j_max
        t_max = min((self.tf + self.ad / j_max - 2 * a_max / j_max) / 2, (a_max - self.a0) / j_max)

        roots = sorted(solve_quartic_monic(*polynom))
        for t in roots:
            if t > t_max or t < t_min:
                continue

            h1 = (
                (self.a0_p2 - self.af_p2) / 2
                + self.j_max_p2 * t * t
                - j_max * (self.vd - 2 * self.a0 * t)
            ) / a_max

            profile.t[0] = t
            profile.t[1] = 0.0
            profile.t[2] = t + self.a0 / j_max
            profile.t[3] = self.tf + (h1 + self.ad - a_max) / j_max - 2 * t
            profile.t[4] = a_max / j_max
            profile.t[5] = -(h1 + a_max) / j_max
            profile.t[6] = profile.t[4] - self.af / j_max

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDUD,
                ReachedLimits.ACC1_VEL,
            ):
                return True

        return False

    def _time_acc0_vel(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        if self.tf < max((-self.a0 + a_max) / j_max, 0.0) + max(a_max / j_max, 0.0):
            return False

        ph1 = (
            12
            * j_max
            * (
                -a_max * a_max * self.vd
                - j_max * self.vd_p2
                + 2 * a_max * j_max * (-self.pd + self.tf * self.vf)
            )
        )

        # Profile UDDU
        polynom_uddu = [
            (2 * a_max) / j_max,
            (
                self.a0_p2
                - self.af_p2
                + 2 * self.ad * a_max
                + a_max * a_max
                + 2 * j_max * (self.vd - a_max * self.tf)
            )
            / self.j_max_p2,
            0.0,
            -(
                -3 * (self.a0_p4 + self.af_p4)
                + 4 * (self.af_p3 + 2 * self.a0_p3) * a_max
                - 12 * self.a0 * a_max * (self.af_p2 - 2 * j_max * self.vd)
                + 6 * self.a0_p2 * (self.af_p2 - a_max * a_max - 2 * j_max * self.vd)
                + 6
                * self.af_p2
                * (a_max * a_max - 2 * a_max * j_max * self.tf + 2 * j_max * self.vd)
                + ph1
            )
            / (12 * self.j_max_p2 * self.j_max_p2),
        ]

        t_min_uddu = -self.af / j_max
        t_max_uddu = min(self.tf - (2 * a_max - self.a0) / j_max, -a_min / j_max)

        roots_uddu = sorted(solve_quartic_monic(*polynom_uddu))
        for t0 in roots_uddu:
            if t0 < t_min_uddu or t0 > t_max_uddu:
                continue
            t = t0

            # Single Newton step (regarding pd).
            if t > _ULP:
                h1 = j_max * t * t + self.vd
                orig = (
                    -3 * (self.a0_p4 + self.af_p4)
                    + 4 * (self.af_p3 + 2 * self.a0_p3) * a_max
                    - 24 * self.af * a_max * self.j_max_p2 * t * t
                    - 12 * self.a0 * a_max * (self.af_p2 - 2 * j_max * h1)
                    + 6 * self.a0_p2 * (self.af_p2 - a_max * a_max - 2 * j_max * h1)
                    + 6
                    * self.af_p2
                    * (a_max * a_max - 2 * a_max * j_max * self.tf + 2 * j_max * h1)
                    - 12
                    * j_max
                    * (
                        a_max * a_max * h1
                        + j_max * h1 * h1
                        + 2
                        * a_max
                        * j_max
                        * (self.pd + j_max * t * t * (t - self.tf) - self.tf * self.vf)
                    )
                ) / (24 * a_max * self.j_max_p2)
                deriv = (
                    -t
                    * (
                        self.a0_p2
                        - self.af_p2
                        + 2 * a_max * (self.ad - j_max * self.tf)
                        + a_max * a_max
                        + 3 * a_max * j_max * t
                        + 2 * j_max * h1
                    )
                    / a_max
                )
                t -= orig / deriv

            h1uddu = ((self.a0_p2 - self.af_p2) / 2 + j_max * (j_max * t * t + self.vd)) / a_max

            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = (h1uddu - a_max) / j_max
            profile.t[2] = a_max / j_max
            profile.t[3] = self.tf - (h1uddu + self.ad + a_max) / j_max - 2 * t
            profile.t[4] = t
            profile.t[5] = 0.0
            profile.t[6] = self.af / j_max + t

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.ACC0_VEL,
            ):
                return True

        # Profile UDUD
        polynom = [
            (-2 * a_max) / j_max,
            -(
                self.a0_p2
                + self.af_p2
                - 2 * (self.a0 + self.af) * a_max
                + a_max * a_max
                + 2 * j_max * (self.vd - a_max * self.tf)
            )
            / self.j_max_p2,
            0.0,
            (
                3 * (self.a0_p4 + self.af_p4)
                - 4 * (self.af_p3 + 2 * self.a0_p3) * a_max
                + 6 * self.a0_p2 * (self.af_p2 + a_max * a_max + 2 * j_max * self.vd)
                - 12 * self.a0 * a_max * (self.af_p2 + 2 * j_max * self.vd)
                + 6
                * self.af_p2
                * (a_max * a_max - 2 * a_max * j_max * self.tf + 2 * j_max * self.vd)
                - ph1
            )
            / (12 * self.j_max_p2 * self.j_max_p2),
        ]

        t_min = self.af / j_max
        t_max = min(self.tf - a_max / j_max, a_max / j_max)

        roots = sorted(solve_quartic_monic(*polynom))
        for t0 in roots:
            if t0 < t_min or t0 > t_max:
                continue
            t = t0

            # Single Newton step (regarding pd).
            h1ududpd = j_max * t * t - self.vd
            orig = -(
                3 * (self.a0_p4 + self.af_p4)
                - 4 * (2 * self.a0_p3 + self.af_p3) * a_max
                + 24 * self.af * a_max * self.j_max_p2 * t * t
                - 12 * self.a0 * a_max * (self.af_p2 - 2 * j_max * h1ududpd)
                + 6 * self.a0_p2 * (self.af_p2 + a_max * a_max - 2 * j_max * h1ududpd)
                + 6 * self.af_p2 * (a_max * a_max - 2 * j_max * (self.tf * a_max + h1ududpd))
                + 12
                * j_max
                * (
                    -a_max * a_max * h1ududpd
                    + j_max * h1ududpd * h1ududpd
                    - 2
                    * a_max
                    * j_max
                    * (-self.pd + j_max * t * t * (t - self.tf) + self.tf * self.vf)
                )
            ) / (24 * a_max * self.j_max_p2)
            deriv = (
                t
                * (
                    self.a0_p2
                    + self.af_p2
                    - 2 * j_max * h1ududpd
                    - 2 * (self.a0 + self.af + j_max * self.tf) * a_max
                    + a_max * a_max
                    + 3 * a_max * j_max * t
                )
                / a_max
            )
            t -= orig / deriv

            h1udud = ((self.a0_p2 + self.af_p2) / 2 + j_max * (self.vd - j_max * t * t)) / a_max

            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = (h1udud - a_max) / j_max
            profile.t[2] = a_max / j_max
            profile.t[3] = self.tf - (h1udud - self.a0 - self.af + a_max) / j_max - 2 * t
            profile.t[4] = t
            profile.t[5] = 0.0
            profile.t[6] = -(self.af / j_max) + t

            if profile.check_with_timing(
                self.tf,
                j_max,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDUD,
                ReachedLimits.ACC0_VEL,
            ):
                return True

        return False

    def _time_vel(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        tz_min = max(0.0, -self.a0 / j_max)
        tz_max = min((self.tf - self.a0 / j_max) / 2, (a_max - self.a0) / j_max)

        # Profile UDDU
        if (
            abs(self.v0) < _ULP
            and abs(self.a0) < _ULP
            and abs(self.vf) < _ULP
            and abs(self.af) < _ULP
        ):
            polynom = [1.0, -self.tf / 2, 0.0, self.pd / (2 * j_max)]
            roots = sorted(solve_cubic(*polynom))

            for t0 in roots:
                if t0 > self.tf / 4:
                    continue
                t = t0

                # Single Newton step (regarding pd).
                if t > _ULP:
                    orig = -self.pd + j_max * t * t * (self.tf - 2 * t)
                    deriv = 2 * j_max * t * (self.tf - 3 * t)
                    t -= orig / deriv

                profile.t[0] = t
                profile.t[1] = 0.0
                profile.t[2] = t
                profile.t[3] = self.tf - 4 * t
                profile.t[4] = t
                profile.t[5] = 0.0
                profile.t[6] = t

                if profile.check_with_timing(
                    self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.VEL
                ):
                    return True

        else:
            p1 = self.af_p2 - 2 * j_max * (
                -2 * self.af * self.tf + j_max * self.tf_p2 + 3 * self.vd
            )
            ph1 = self.af_p3 - 3 * self.j_max_p2 * self.g1 - 3 * self.af * j_max * self.vd
            ph2 = (
                self.af_p4
                + 8 * self.af_p3 * j_max * self.tf
                + 12
                * j_max
                * (
                    3 * j_max * self.vd_p2
                    - self.af_p2 * self.vd
                    + 2 * self.af * j_max * (self.g1 - self.tf * self.vd)
                    - 2 * self.j_max_p2 * self.tf * self.g1
                )
            )
            ph3 = self.a0 * (self.af - j_max * self.tf)
            ph4 = j_max * (-self.ad + j_max * self.tf)

            # Find root of 5th order polynom.
            polynom5 = [0.0] * 6
            polynom5[0] = 1.0
            polynom5[1] = (
                15 * self.a0_p2
                + self.af_p2
                + 4 * self.af * j_max * self.tf
                - 16 * ph3
                - 2 * j_max * (j_max * self.tf_p2 + 3 * self.vd)
            ) / (4 * ph4)
            polynom5[2] = (
                29 * self.a0_p3
                - 2 * self.af_p3
                - 33 * self.a0 * ph3
                + 6 * self.j_max_p2 * self.g1
                + 6 * self.af * j_max * self.vd
                + 6 * self.a0 * p1
            ) / (6 * j_max * ph4)
            polynom5[3] = (
                61 * self.a0_p4
                - 76 * self.a0_p2 * ph3
                - 16 * self.a0 * ph1
                + 30 * self.a0_p2 * p1
                + ph2
            ) / (24 * self.j_max_p2 * ph4)
            polynom5[4] = (
                self.a0
                * (
                    7 * self.a0_p4
                    - 10 * self.a0_p2 * ph3
                    - 4 * self.a0 * ph1
                    + 6 * self.a0_p2 * p1
                    + ph2
                )
            ) / (12 * self.j_max_p2 * j_max * ph4)
            polynom5[5] = (
                7 * self.a0_p6
                + self.af_p6
                - 12 * self.a0_p4 * ph3
                + 48 * self.af_p3 * self.j_max_p2 * self.g1
                - 8 * self.a0_p3 * ph1
                - 72
                * self.j_max_p2
                * j_max
                * (
                    j_max * self.g1 * self.g1
                    + self.vd_p2 * self.vd
                    + 2 * self.af * self.g1 * self.vd
                )
                - 6 * self.af_p4 * j_max * self.vd
                + 36 * self.af_p2 * self.j_max_p2 * self.vd_p2
                + 9 * self.a0_p4 * p1
                + 3 * self.a0_p2 * ph2
            ) / (144 * self.j_max_p2 * self.j_max_p2 * ph4)

            deriv5 = polynomial_monic_derivative(polynom5)
            dderiv5 = polynomial_derivative(deriv5)

            # Solve 4th-order derivative analytically.
            d_extremas = sorted(solve_quartic_monic(deriv5[1], deriv5[2], deriv5[3], deriv5[4]))

            tz_current = tz_min

            def check_root_uddu(t0: float) -> bool:
                # Single Newton step (regarding pd).
                t = t0

                h1pd = _ieee754_sqrt(
                    (self.a0_p2 + self.af_p2) / (2 * self.j_max_p2)
                    + (2 * self.a0 * t + j_max * t * t - self.vd) / j_max
                )
                orig = -self.pd - (
                    2 * self.a0_p3
                    + 4 * self.af_p3
                    + 24 * self.a0 * j_max * t * (self.af + j_max * (h1pd + t - self.tf))
                    + 6 * self.a0_p2 * (self.af + j_max * (2 * t - self.tf))
                    + 6 * (self.a0_p2 + self.af_p2) * j_max * h1pd
                    + 12 * self.af * j_max * (j_max * t * t - self.vd)
                    + 12
                    * self.j_max_p2
                    * (j_max * t * t * (h1pd + t - self.tf) - self.tf * self.v0 - h1pd * self.vd)
                ) / (12 * self.j_max_p2)
                deriv_newton = -(self.a0 + j_max * t) * (
                    3 * (h1pd + t) - 2 * self.tf + (self.a0 + 2 * self.af) / j_max
                )
                if (
                    not math.isnan(orig)
                    and not math.isnan(deriv_newton)
                    and abs(deriv_newton) > _ULP
                ):
                    t -= orig / deriv_newton

                if t > self.tf or math.isnan(t):
                    return False

                h1 = _ieee754_sqrt(
                    (self.a0_p2 + self.af_p2) / (2 * self.j_max_p2)
                    + (t * (2 * self.a0 + j_max * t) - self.vd) / j_max
                )

                profile.t[0] = t
                profile.t[1] = 0.0
                profile.t[2] = t + self.a0 / j_max
                profile.t[3] = self.tf - 2 * (t + h1) - (self.a0 + self.af) / j_max
                profile.t[4] = h1
                profile.t[5] = 0.0
                profile.t[6] = h1 + self.af / j_max

                return profile.check_with_timing(
                    self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.VEL
                )

            for tz0 in d_extremas:
                if tz0 >= tz_max:
                    continue
                tz = tz0
                orig = evaluate_polynomial(deriv5, tz)
                if abs(orig) > _TOLERANCE:
                    tz -= orig / evaluate_polynomial(dderiv5, tz)

                val_new = evaluate_polynomial(polynom5, tz)
                dderiv_val = evaluate_polynomial(dderiv5, tz)

                if abs(val_new) < 64 * abs(dderiv_val) * _TOLERANCE:
                    if check_root_uddu(tz):
                        return True
                elif evaluate_polynomial(polynom5, tz_current) * val_new < 0:
                    if check_root_uddu(shrink_interval(polynom5, tz_current, tz)):
                        return True
                tz_current = tz

            val_max = evaluate_polynomial(polynom5, tz_max)
            val_current = evaluate_polynomial(polynom5, tz_current)

            if val_current * val_max < 0:
                if check_root_uddu(shrink_interval(polynom5, tz_current, tz_max)):
                    return True
            elif abs(val_max) < 8 * _ULP:
                if check_root_uddu(tz_max):
                    return True

        # Profile UDUD
        ph1 = self.af_p2 - 2 * j_max * (2 * self.af * self.tf + j_max * self.tf_p2 - 3 * self.vd)
        ph2 = self.af_p3 - 3 * self.j_max_p2 * self.g1 + 3 * self.af * j_max * self.vd
        ph3 = 2 * j_max * self.tf * self.g1 + 3 * self.vd_p2
        ph4 = (
            self.af_p4
            - 8 * self.af_p3 * j_max * self.tf
            + 12
            * j_max
            * (
                j_max * ph3
                + self.af_p2 * self.vd
                + 2 * self.af * j_max * (self.g1 - self.tf * self.vd)
            )
        )
        ph5 = self.af + j_max * self.tf

        # Find root of 6th order polynom.
        polynom6 = [0.0] * 7
        polynom6[0] = 1.0
        polynom6[1] = (5 * self.a0 - ph5) / j_max
        polynom6[2] = (39 * self.a0_p2 - ph1 - 16 * self.a0 * ph5) / (4 * self.j_max_p2)
        polynom6[3] = (55 * self.a0_p3 - 33 * self.a0_p2 * ph5 - 6 * self.a0 * ph1 + 2 * ph2) / (
            6 * self.j_max_p2 * j_max
        )
        polynom6[4] = (
            101 * self.a0_p4
            + ph4
            - 76 * self.a0_p3 * ph5
            - 30 * self.a0_p2 * ph1
            + 16 * self.a0 * ph2
        ) / (24 * self.j_max_p2 * self.j_max_p2)
        polynom6[5] = (
            self.a0
            * (
                11 * self.a0_p4
                + ph4
                - 10 * self.a0_p3 * ph5
                - 6 * self.a0_p2 * ph1
                + 4 * self.a0 * ph2
            )
        ) / (12 * self.j_max_p2 * self.j_max_p2 * j_max)
        polynom6[6] = (
            11 * self.a0_p6
            - self.af_p6
            - 12 * self.a0_p5 * ph5
            - 48 * self.af_p3 * self.j_max_p2 * self.g1
            - 9 * self.a0_p4 * ph1
            + 72
            * self.j_max_p2
            * j_max
            * (j_max * self.g1 * self.g1 - self.vd_p2 * self.vd - 2 * self.af * self.g1 * self.vd)
            - 6 * self.af_p4 * j_max * self.vd
            - 36 * self.af_p2 * self.j_max_p2 * self.vd_p2
            + 8 * self.a0_p3 * ph2
            + 3 * self.a0_p2 * ph4
        ) / (144 * self.j_max_p2 * self.j_max_p2 * self.j_max_p2)

        deriv6 = polynomial_monic_derivative(polynom6)
        dderiv6 = polynomial_monic_derivative(deriv6)

        dd_tz_current = tz_min
        dd_tz_intervals: list[tuple[float, float]] = []

        dd_extremas = sorted(solve_quartic_monic(dderiv6[1], dderiv6[2], dderiv6[3], dderiv6[4]))

        for tz0 in dd_extremas:
            if tz0 >= tz_max:
                continue
            tz = tz0
            orig = evaluate_polynomial(dderiv6, tz)
            if abs(orig) > _TOLERANCE:
                tz -= orig / evaluate_polynomial(polynomial_derivative(dderiv6), tz)

            eval_current = evaluate_polynomial(deriv6, dd_tz_current)
            eval_tz = evaluate_polynomial(deriv6, tz)
            product = eval_current * eval_tz

            if product < 0:
                dd_tz_intervals.append((dd_tz_current, tz))
            dd_tz_current = tz

        final_eval_current = evaluate_polynomial(deriv6, dd_tz_current)
        final_eval_max = evaluate_polynomial(deriv6, tz_max)
        final_dd_product = final_eval_current * final_eval_max

        if final_dd_product < 0:
            dd_tz_intervals.append((dd_tz_current, tz_max))

        tz_current = tz_min

        def check_root_udud(t0: float) -> bool:
            # Double Newton step (regarding pd).
            t = t0
            h1pd = _ieee754_sqrt(
                (self.af_p2 - self.a0_p2) / (2 * self.j_max_p2)
                - ((2 * self.a0 + j_max * t) * t - self.vd) / j_max
            )
            orig = (
                -self.pd
                + (self.af_p3 - self.a0_p3 + 3 * self.a0_p2 * j_max * (self.tf - 2 * t))
                / (6 * self.j_max_p2)
                + (2 * self.a0 + j_max * t) * t * (self.tf - t)
                + (j_max * h1pd - self.af) * h1pd * h1pd
                + self.tf * self.v0
            )
            deriv_newton = (
                (self.a0 + j_max * t)
                * (2 * (self.af + j_max * self.tf) - 3 * j_max * (h1pd + t) - self.a0)
                / j_max
            )

            t -= orig / deriv_newton

            h1pd = _ieee754_sqrt(
                (self.af_p2 - self.a0_p2) / (2 * self.j_max_p2)
                - ((2 * self.a0 + j_max * t) * t - self.vd) / j_max
            )
            orig = (
                -self.pd
                + (self.af_p3 - self.a0_p3 + 3 * self.a0_p2 * j_max * (self.tf - 2 * t))
                / (6 * self.j_max_p2)
                + (2 * self.a0 + j_max * t) * t * (self.tf - t)
                + (j_max * h1pd - self.af) * h1pd * h1pd
                + self.tf * self.v0
            )
            if abs(orig) > 1e-9:
                deriv_newton = (
                    (self.a0 + j_max * t)
                    * (2 * (self.af + j_max * self.tf) - 3 * j_max * (h1pd + t) - self.a0)
                    / j_max
                )
                t -= orig / deriv_newton

            h1 = _ieee754_sqrt(
                (self.af_p2 - self.a0_p2) / (2 * self.j_max_p2)
                - ((2 * self.a0 + j_max * t) * t - self.vd) / j_max
            )

            # Calculate times first, validate BEFORE assigning, to prevent
            # corrupting the shared profile on failure.
            t0v = t
            t1v = 0.0
            t2v = t + self.a0 / j_max
            t3v = self.tf - 2 * (t + h1) + self.ad / j_max
            t4v = h1
            t5v = 0.0
            t6v = h1 - self.af / j_max

            if t0v < 0 or t2v < 0 or t3v < 0 or t4v < 0 or t6v < 0:
                return False

            profile.t[0] = t0v
            profile.t[1] = t1v
            profile.t[2] = t2v
            profile.t[3] = t3v
            profile.t[4] = t4v
            profile.t[5] = t5v
            profile.t[6] = t6v

            return profile.check_with_timing(
                self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.VEL
            )

        for lo, hi in dd_tz_intervals:
            tz = shrink_interval(deriv6, lo, hi)

            if tz >= tz_max:
                continue

            p_val = evaluate_polynomial(polynom6, tz)
            dderiv_val = evaluate_polynomial(dderiv6, tz)
            threshold = 64 * abs(dderiv_val) * _TOLERANCE

            if abs(p_val) < threshold:
                if check_root_udud(tz):
                    return True
            else:
                val_current = evaluate_polynomial(polynom6, tz_current)
                product = val_current * p_val

                if product < 0:
                    if check_root_udud(shrink_interval(polynom6, tz_current, tz)):
                        return True
            tz_current = tz

        final_udud_val_current = evaluate_polynomial(polynom6, tz_current)
        final_udud_val_max = evaluate_polynomial(polynom6, tz_max)
        final_udud_product = final_udud_val_current * final_udud_val_max

        if final_udud_product < 0:
            if check_root_udud(shrink_interval(polynom6, tz_current, tz_max)):
                return True

        return False

    def _time_acc0_acc1(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        if abs(self.a0) < _ULP and abs(self.af) < _ULP:
            h1 = (
                2 * a_min * self.g1
                + self.vd_p2
                + a_max * (2 * self.pd + a_min * self.tf_p2 - 2 * self.tf * self.vf)
            )
            h2 = (a_max - a_min) * (-a_min * self.vd + a_max * (a_min * self.tf - self.vd))

            jf = h2 / h1
            profile.t[0] = a_max / jf
            profile.t[1] = (-2 * a_max * h1 + a_min * a_min * self.g2) / h2
            profile.t[2] = profile.t[0]
            profile.t[3] = 0.0
            profile.t[4] = -a_min / jf
            profile.t[5] = self.tf - (2 * profile.t[0] + profile.t[1] + 2 * profile.t[4])
            profile.t[6] = profile.t[4]

            return profile.check_with_timing(
                self.tf,
                jf,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.ACC0_ACC1,
                j_max=j_max,
            )

        # UDDU
        h1 = _ieee754_sqrt(
            144
            * _pow2(
                (a_max - a_min) * (-a_min * self.vd + a_max * (a_min * self.tf - self.vd))
                - self.af_p2 * (a_max * self.tf - self.vd)
                + 2 * self.af * a_min * (a_max * self.tf - self.vd)
                + self.a0_p2 * (a_min * self.tf + self.v0 - self.vf)
                - 2 * self.a0 * a_max * (a_min * self.tf - self.vd)
            )
            + 48
            * self.ad
            * (
                3 * self.a0_p3
                - 3 * self.af_p3
                + 12 * a_max * a_min * (-a_max + a_min)
                + 4 * self.af_p2 * (a_max + 2 * a_min)
                + self.a0
                * (
                    -3 * self.af_p2
                    + 8 * self.af * (a_min - a_max)
                    + 6 * (a_max * a_max + 2 * a_max * a_min - a_min * a_min)
                )
                + 6 * self.af * (a_max * a_max - 2 * a_max * a_min - a_min * a_min)
                + self.a0_p2 * (3 * self.af - 4 * (2 * a_max + a_min))
            )
            * (
                2 * a_min * self.g1
                + self.vd * self.vd
                + a_max * (2 * self.pd + a_min * self.tf * self.tf - 2 * self.tf * self.vf)
            )
        )

        jf = -(
            3 * self.af_p2 * a_max * self.tf
            - 3 * self.a0_p2 * a_min * self.tf
            - 6 * self.ad * a_max * a_min * self.tf
            + 3 * a_max * a_min * (a_min - a_max) * self.tf
            + 3 * (self.a0_p2 - self.af_p2) * self.vd
            + 6 * self.vd * (self.af * a_min - self.a0 * a_max)
            + 3 * (a_max * a_max - a_min * a_min) * self.vd
            + h1 / 4
        ) / (
            6
            * (
                2 * a_min * self.g1
                + self.vd * self.vd
                + a_max * (2 * self.pd + a_min * self.tf_p2 - 2 * self.tf * self.vf)
            )
        )
        profile.t[0] = (a_max - self.a0) / jf
        profile.t[1] = (
            self.a0_p2
            - self.af_p2
            + 2 * self.ad * a_min
            - 2
            * (
                a_max * a_max
                - 2 * a_max * a_min
                + a_min * a_min
                + a_min * jf * self.tf
                - jf * self.vd
            )
        ) / (2 * (a_max - a_min) * jf)
        profile.t[2] = a_max / jf
        profile.t[3] = 0.0
        profile.t[4] = -a_min / jf
        profile.t[5] = self.tf - (
            profile.t[0] + profile.t[1] + profile.t[2] + 2 * profile.t[4] + self.af / jf
        )
        profile.t[6] = profile.t[4] + self.af / jf

        if profile.check_with_timing(
            self.tf,
            jf,
            v_max,
            v_min,
            a_max,
            a_min,
            ControlSigns.UDDU,
            ReachedLimits.ACC0_ACC1,
            j_max=j_max,
        ):
            return True

        return False

    def _time_acc1(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        # Case UDDU
        h0uddu = (
            _ieee754_sqrt(
                self.j_max_p2
                * (
                    self.a0_p4
                    + self.af_p4
                    - 4 * self.af_p3 * j_max * self.tf
                    + 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
                    - 4 * self.a0_p3 * (self.af - j_max * self.tf)
                    + 6 * self.a0_p2 * (self.af - j_max * self.tf) * (self.af - j_max * self.tf)
                    + 24 * self.af * self.j_max_p2 * self.g1
                    - 4
                    * self.a0
                    * (
                        self.af_p3
                        - 3 * self.af_p2 * j_max * self.tf
                        + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
                    )
                    - 12 * self.j_max_p2 * (-self.vd_p2 + j_max * self.tf * self.g2)
                )
                / 3
            )
            / j_max
        )
        h1_uddu_sol1 = _ieee754_sqrt(
            (
                self.a0_p2
                + self.af_p2
                - 2 * self.a0 * self.af
                - 2 * self.ad * j_max * self.tf
                + 2 * h0uddu
            )
            / self.j_max_p2
            + self.tf_p2
        )

        profile.t[0] = -(
            self.a0_p2
            + self.af_p2
            + 2 * self.a0 * (j_max * self.tf - self.af)
            - 2 * j_max * self.vd
            + h0uddu
        ) / (2 * j_max * (-self.ad + j_max * self.tf))
        profile.t[1] = 0.0
        profile.t[2] = (self.tf - h1_uddu_sol1) / 2 - self.ad / (2 * j_max)
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = h1_uddu_sol1
        profile.t[6] = self.tf - (profile.t[0] + profile.t[2] + profile.t[5])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC1
        ):
            return True

        # Case UDUD
        h0udud = (
            _ieee754_sqrt(
                self.j_max_p2
                * (
                    self.a0_p4
                    + self.af_p4
                    + 4 * (self.af_p3 - self.a0_p3) * j_max * self.tf
                    + 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
                    + 6 * self.a0_p2 * (self.af + j_max * self.tf) * (self.af + j_max * self.tf)
                    + 24 * self.af * self.j_max_p2 * self.g1
                    - 4
                    * self.a0
                    * (
                        self.a0_p2 * self.af
                        + self.af_p3
                        + 3 * self.af_p2 * j_max * self.tf
                        + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
                    )
                    + 12 * self.j_max_p2 * (self.vd_p2 + j_max * self.tf * self.g2)
                )
                / 3
            )
            / j_max
        )
        h1udud = _ieee754_sqrt(
            (
                self.a0_p2
                + self.af_p2
                - 2 * self.a0 * self.af
                + 2 * self.ad * j_max * self.tf
                + 2 * h0udud
            )
            / self.j_max_p2
            + self.tf_p2
        )

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = -(
            self.a0_p2
            + self.af_p2
            - 2 * self.a0 * self.af
            + 2 * j_max * (self.vd - self.a0 * self.tf)
            + h0udud
        ) / (2 * j_max * (self.ad + j_max * self.tf))
        profile.t[3] = 0.0
        profile.t[4] = self.ad / (2 * j_max) + (self.tf - h1udud) / 2
        profile.t[5] = h1udud
        profile.t[6] = self.tf - (profile.t[5] + profile.t[4] + profile.t[2])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.ACC1
        ):
            return True

        # Case UDDU, Solution 2
        h0a = (
            self.a0_p3
            - self.af_p3
            - 3 * self.a0_p2 * a_min
            + 3 * a_min * a_min * (self.a0 + j_max * self.tf)
            + 3 * self.af * a_min * (-a_min - 2 * j_max * self.tf)
            - 3 * self.af_p2 * (-a_min - j_max * self.tf)
            - 3 * self.j_max_p2 * (-2 * self.pd - a_min * self.tf_p2 + 2 * self.tf * self.vf)
        )
        h0b = (
            self.a0_p2
            + self.af_p2
            - 2 * (self.a0 + self.af) * a_min
            + 2 * (a_min * a_min - j_max * (-a_min * self.tf + self.vd))
        )
        h0c = (
            self.a0_p4
            + 3 * self.af_p4
            - 4 * (self.a0_p3 + 2 * self.af_p3) * a_min
            + 6 * self.a0_p2 * a_min * a_min
            + 6 * self.af_p2 * (a_min * a_min - 2 * j_max * self.vd)
            + 12
            * j_max
            * (2 * a_min * j_max * self.g1 - a_min * a_min * self.vd + j_max * self.vd_p2)
            + 24 * self.af * a_min * j_max * self.vd
            - 4
            * self.a0
            * (
                self.af_p3
                - 3 * self.af * a_min * (-a_min - 2 * j_max * self.tf)
                + 3 * self.af_p2 * (-a_min - j_max * self.tf)
                + 3
                * j_max
                * (
                    -a_min * a_min * self.tf
                    + j_max * (-2 * self.pd - a_min * self.tf_p2 + 2 * self.tf * self.vf)
                )
            )
        )
        h1_uddu_sol2 = abs(j_max) / j_max * _ieee754_sqrt(4 * h0a * h0a - 6 * h0b * h0c)
        h2 = 6 * j_max * h0b

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = (2 * h0a + h1_uddu_sol2) / h2
        profile.t[3] = -(
            self.a0_p2
            + self.af_p2
            - 2 * (self.a0 + self.af) * a_min
            + 2 * (a_min * a_min + a_min * j_max * self.tf - j_max * self.vd)
        ) / (2 * j_max * (self.a0 - a_min - j_max * profile.t[2]))
        profile.t[4] = (self.a0 - a_min) / j_max - profile.t[2]
        profile.t[5] = self.tf - (
            profile.t[2] + profile.t[3] + profile.t[4] + (self.af - a_min) / j_max
        )
        profile.t[6] = (self.af - a_min) / j_max

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC1
        ):
            return True

        # Case UDUD, Solution 1
        h0a_udud = (
            -self.a0_p3
            + self.af_p3
            + 3 * (self.a0_p2 - self.af_p2) * a_max
            - 3 * self.ad * a_max * a_max
            - 6 * self.af * a_max * j_max * self.tf
            + 3 * self.af_p2 * j_max * self.tf
            + 3
            * j_max
            * (
                a_max * a_max * self.tf
                + j_max * (-2 * self.pd - a_max * self.tf_p2 + 2 * self.tf * self.vf)
            )
        )
        h0b_udud = (
            self.a0_p2 - self.af_p2 + 2 * self.ad * a_max + 2 * j_max * (a_max * self.tf - self.vd)
        )
        h0c_udud = (
            self.a0_p4
            + 3 * self.af_p4
            - 4 * (self.a0_p3 + 2 * self.af_p3) * a_max
            + 6 * self.a0_p2 * a_max * a_max
            - 24 * self.af * a_max * j_max * self.vd
            + 12
            * j_max
            * (2 * a_max * j_max * self.g1 + j_max * self.vd_p2 + a_max * a_max * self.vd)
            + 6 * self.af_p2 * (a_max * a_max + 2 * j_max * self.vd)
            - 4
            * self.a0
            * (
                self.af_p3
                + 3 * self.af * a_max * (a_max - 2 * j_max * self.tf)
                - 3 * self.af_p2 * (a_max - j_max * self.tf)
                + 3
                * j_max
                * (
                    a_max * a_max * self.tf
                    + j_max * (-2 * self.pd - a_max * self.tf_p2 + 2 * self.tf * self.vf)
                )
            )
        )
        h1_udud_sol1 = (
            abs(j_max) / j_max * _ieee754_sqrt(4 * h0a_udud * h0a_udud - 6 * h0b_udud * h0c_udud)
        )
        h2_udud = 6 * j_max * h0b_udud

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = -(2 * h0a_udud + h1_udud_sol1) / h2_udud
        profile.t[3] = 2 * h1_udud_sol1 / h2_udud
        profile.t[4] = (a_max - self.a0) / j_max + profile.t[2]
        profile.t[5] = self.tf - (
            profile.t[2] + profile.t[3] + profile.t[4] + (-self.af + a_max) / j_max
        )
        profile.t[6] = (-self.af + a_max) / j_max

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.ACC1
        ):
            return True

        return False

    def _time_acc0(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        # UDUD
        h1 = _ieee754_sqrt(
            self.ad_p2 / (2 * self.j_max_p2)
            - self.ad * (a_max - self.a0) / self.j_max_p2
            + (a_max * self.tf - self.vd) / j_max
        )

        profile.t[0] = (a_max - self.a0) / j_max
        profile.t[1] = self.tf - self.ad / j_max - 2 * h1
        profile.t[2] = h1
        profile.t[3] = 0.0
        profile.t[4] = (self.af - a_max) / j_max + h1
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.NONE
        ):
            return True

        # NOTE (source quirk, preserved verbatim): the Swift comment above
        # this block says "// UDUD" but the actual checkWithTiming call
        # passes .UDDU -- see this module's docstring.
        h0a = (
            -self.a0_p2 + self.af_p2 - 2 * self.ad * a_max + 2 * j_max * (a_max * self.tf - self.vd)
        )
        h0b = (
            self.a0_p3
            + 2 * self.af_p3
            - 6 * self.af_p2 * a_max
            - 3 * self.a0_p2 * (self.af - j_max * self.tf)
            - 3 * self.a0 * a_max * (a_max - 2 * self.af + 2 * j_max * self.tf)
            - 3
            * j_max
            * (
                j_max * (-2 * self.pd + a_max * self.tf_p2 + 2 * self.tf * self.v0)
                + a_max * (a_max * self.tf - 2 * self.vd)
            )
            + 3 * self.af * (a_max * a_max + 2 * a_max * j_max * self.tf - 2 * j_max * self.vd)
        )
        h0 = abs(j_max) * _ieee754_sqrt(4 * h0b * h0b - 18 * h0a * h0a * h0a)
        h1b = 3 * j_max * h0a

        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = (
            -self.a0_p3
            + self.af_p3
            + self.af_p2 * (-6 * a_max + 3 * j_max * self.tf)
            + self.a0_p2 * (-3 * self.af + 6 * a_max + 3 * j_max * self.tf)
            + 6 * self.af * (a_max * a_max - j_max * self.vd)
            + 3 * self.a0 * (self.af_p2 - 2 * (a_max * a_max + j_max * self.vd))
            - 6 * j_max * (a_max * (a_max * self.tf - 2 * self.vd) + j_max * self.g2)
        ) / h1b
        profile.t[2] = -(self.ad + h0 / h1b) / (2 * j_max) + self.tf / 2 - profile.t[1] / 2
        profile.t[3] = h0 / (j_max * h1b)
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[0] + profile.t[1] + profile.t[2] + profile.t[3])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # a3 != 0

        # UDDU Solution 1
        h0a_2 = (
            self.a0_p3
            + 2 * self.af_p3
            - 6 * (self.af_p2 + a_max * a_max) * a_max
            - 6 * (self.a0 + self.af) * a_max * j_max * self.tf
            + 9 * a_max * a_max * (self.af + j_max * self.tf)
            + 3 * self.a0 * a_max * (-2 * self.af + 3 * a_max)
            + 3 * self.a0_p2 * (self.af - 2 * a_max + j_max * self.tf)
            - 6 * self.j_max_p2 * self.g1
            + 6 * (self.af - a_max) * j_max * self.vd
            - 3 * a_max * self.j_max_p2 * self.tf_p2
        )
        h0b_2 = (
            self.a0_p2
            + self.af_p2
            + 2
            * (a_max * a_max - (self.a0 + self.af) * a_max + j_max * (self.vd - a_max * self.tf))
        )
        h1_2 = abs(j_max) / j_max * _ieee754_sqrt(4 * h0a_2 * h0a_2 - 18 * h0b_2 * h0b_2 * h0b_2)
        h2_2 = 6 * j_max * h0b_2

        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = self.ad / j_max - 2 * profile.t[0] - (2 * h0a_2 - h1_2) / h2_2 + self.tf
        profile.t[2] = -(2 * h0a_2 + h1_2) / h2_2
        profile.t[3] = (2 * h0a_2 - h1_2) / h2_2
        profile.t[4] = self.tf - (profile.t[0] + profile.t[1] + profile.t[2] + profile.t[3])
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            return True

        return False

    def _time_none(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        if abs(self.v0) < _ULP and abs(self.a0) < _ULP and abs(self.af) < _ULP:
            h1 = _ieee754_sqrt(self.tf_p2 * self.vf_p2 + _pow2(4 * self.pd - self.tf * self.vf))
            jf = 4 * (4 * self.pd - 2 * self.tf * self.vf + h1) / self.tf_p3

            profile.t[0] = self.tf / 4
            profile.t[1] = 0.0
            profile.t[2] = 2 * profile.t[0]
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = profile.t[0]

            if profile.check_with_timing(
                self.tf,
                jf,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.NONE,
                j_max=j_max,
            ):
                return True

        if abs(self.a0) < _ULP and abs(self.af) < _ULP:
            # Profiles with a3 != 0, Solution UDDU: first acc, then constant.
            polynom = [
                -2 * self.tf,
                2 * self.vd / j_max + self.tf_p2,
                4 * (self.pd - self.tf * self.vf) / j_max,
                (self.vd_p2 + j_max * self.tf * self.g2) / self.j_max_p2,
            ]
            roots = sorted(solve_quartic_monic(*polynom))
            for t0 in roots:
                t = t0
                if t > self.tf / 2 or t > (a_max - self.a0) / j_max:
                    continue

                # Single Newton step (regarding pd).
                h1 = (j_max * t * (t - self.tf) + self.vd) / (j_max * (2 * t - self.tf))
                h2 = (2 * j_max * t * (t - self.tf) + j_max * self.tf_p2 - 2 * self.vd) / (
                    j_max * (2 * t - self.tf) * (2 * t - self.tf)
                )
                orig = (
                    -2 * self.pd
                    + 2 * self.tf * self.v0
                    + h1 * h1 * j_max * (self.tf - 2 * t)
                    + j_max * self.tf * (2 * h1 * t - t * t - (h1 - t) * self.tf)
                ) / 2
                deriv = (j_max * self.tf * (2 * t - self.tf) * (h2 - 1)) / 2 + h1 * j_max * (
                    self.tf - (2 * t - self.tf) * h2 - h1
                )
                t -= orig / deriv

                profile.t[0] = t
                profile.t[1] = 0.0
                profile.t[2] = (j_max * t * (t - self.tf) + self.vd) / (j_max * (2 * t - self.tf))
                profile.t[3] = self.tf - 2 * t
                profile.t[4] = t - profile.t[2]
                profile.t[5] = 0.0
                profile.t[6] = 0.0

                if profile.check_with_timing(
                    self.tf,
                    j_max,
                    v_max,
                    v_min,
                    a_max,
                    a_min,
                    ControlSigns.UDDU,
                    ReachedLimits.NONE,
                ):
                    return True

        # UDUD T 0246
        h0 = (
            _ieee754_sqrt(
                2
                * self.j_max_p2
                * (
                    2
                    * _pow2(
                        self.a0_p3
                        - self.af_p3
                        - 3 * self.af_p2 * j_max * self.tf
                        + 9 * self.af * self.j_max_p2 * self.tf_p2
                        - 3 * self.a0_p2 * (self.af + j_max * self.tf)
                        + 3 * self.a0 * _pow2(self.af + j_max * self.tf)
                        + 3
                        * self.j_max_p2
                        * (8 * self.pd + j_max * self.tf_p3 * self.tf - 8 * self.tf * self.vf)
                    )
                    - 3
                    * (
                        self.a0_p2
                        + self.af_p2
                        - 2 * self.af * j_max * self.tf
                        - 2 * self.a0 * (self.af + j_max * self.tf)
                        - j_max * (j_max * self.tf_p2 + 4 * self.v0 - 4 * self.vf)
                    )
                    * (
                        self.a0_p4
                        + self.af_p4
                        + 4 * self.af_p3 * j_max * self.tf
                        + 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
                        - 3 * self.j_max_p2 * self.j_max_p2 * self.tf_p2 * self.tf_p2
                        - 4 * self.a0_p3 * (self.af + j_max * self.tf)
                        + 6 * self.a0_p2 * _pow2(self.af + j_max * self.tf)
                        - 12
                        * self.af
                        * self.j_max_p2
                        * (8 * self.pd + j_max * self.tf_p3 * self.tf - 8 * self.tf * self.v0)
                        + 48 * self.j_max_p2 * self.vd_p2
                        + 48 * self.j_max_p2 * j_max * self.tf * self.g2
                        - 4
                        * self.a0
                        * (
                            self.af_p3
                            + 3 * self.af_p2 * j_max * self.tf
                            - 9 * self.af * self.j_max_p2 * self.tf_p2
                            - 3
                            * self.j_max_p2
                            * (8 * self.pd + j_max * self.tf_p3 * self.tf - 8 * self.tf * self.vf)
                        )
                    )
                )
            )
            / j_max
        )
        h1 = (
            12
            * j_max
            * (
                -self.a0_p2
                - self.af_p2
                + 2 * self.af * j_max * self.tf
                + 2 * self.a0 * (self.af + j_max * self.tf)
                + j_max * (j_max * self.tf_p2 + 4 * self.v0 - 4 * self.vf)
            )
        )
        h2 = (
            -4 * self.a0_p3
            + 4 * self.af_p3
            + 12 * self.a0_p2 * self.af
            - 12 * self.a0 * self.af_p2
            + 48 * self.j_max_p2 * self.pd
            + 12 * (self.a0_p2 - self.af_p2) * j_max * self.tf
            - 24 * self.j_max_p2 * self.tf * (self.v0 + self.vf)
            + 24 * self.ad * j_max * self.vd
        )
        h3 = 2 * self.a0_p3 - 2 * self.af_p3 - 6 * self.a0_p2 * self.af + 6 * self.a0 * self.af_p2

        profile.t[0] = (
            h3
            - 48 * self.j_max_p2 * (self.tf * self.vf - self.pd)
            - 6 * (self.a0_p2 + self.af_p2) * j_max * self.tf
            + 12 * self.a0 * self.af * j_max * self.tf
            + 6 * (self.a0 + 3 * self.af + j_max * self.tf) * self.tf_p2 * self.j_max_p2
            - h0
        ) / h1
        profile.t[1] = 0.0
        profile.t[2] = (h2 + h0) / h1
        profile.t[3] = 0.0
        profile.t[4] = (-h2 + h0) / h1
        profile.t[5] = 0.0
        profile.t[6] = (
            -h3
            + 48 * self.j_max_p2 * (self.tf * self.v0 - self.pd)
            - 6 * (self.a0_p2 + self.af_p2) * j_max * self.tf
            + 12 * self.a0 * self.af * j_max * self.tf
            + 6 * (self.af + 3 * self.a0 + j_max * self.tf) * self.tf_p2 * self.j_max_p2
            - h0
        ) / h1

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.NONE
        ):
            return True

        # Profiles with a3 != 0, Solution UDDU: T 0234
        ph1 = self.af + j_max * self.tf

        polynom_0234 = [
            -2 * (self.ad + j_max * self.tf) / j_max,
            2
            * (self.a0_p2 + self.af_p2 + j_max * (self.af * self.tf + self.vd) - 2 * self.a0 * ph1)
            / self.j_max_p2
            + self.tf_p2,
            2
            * (
                self.a0_p3
                - self.af_p3
                - 3 * self.af_p2 * j_max * self.tf
                + 3 * self.a0 * ph1 * (ph1 - self.a0)
                - 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
            )
            / (3 * self.j_max_p2 * j_max),
            (
                self.a0_p4
                + self.af_p4
                + 4 * self.af_p3 * j_max * self.tf
                - 4 * self.a0_p3 * ph1
                + 6 * self.a0_p2 * ph1 * ph1
                + 24 * self.j_max_p2 * self.af * self.g1
                - 4
                * self.a0
                * (
                    self.af_p3
                    + 3 * self.af_p2 * j_max * self.tf
                    + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
                )
                + 6 * self.j_max_p2 * self.af_p2 * self.tf_p2
                + 12 * self.j_max_p2 * (self.vd_p2 + j_max * self.tf * self.g2)
            )
            / (12 * self.j_max_p2 * self.j_max_p2),
        ]
        t_min_0234 = self.ad / j_max
        t_max_0234 = min((a_max - self.a0) / j_max, (self.ad / j_max + self.tf) / 2)

        roots_0234 = sorted(solve_quartic_monic(*polynom_0234))
        for t_root in roots_0234:
            t_m = t_root
            if t_m < t_min_0234 or t_m > t_max_0234:
                continue

            # Single Newton step (regarding pd).
            h0n = j_max * (2 * t_m - self.tf) - self.ad
            h1n = (
                self.ad_p2
                - 2 * self.af * j_max * t_m
                + 2 * self.a0 * j_max * (t_m - self.tf)
                + 2 * j_max * (j_max * t_m * (t_m - self.tf) + self.vd)
            ) / (2 * j_max * h0n)
            h2n = (
                -self.ad_p2
                + 2 * self.j_max_p2 * (self.tf_p2 + t_m * (t_m - self.tf))
                + (self.a0 + self.af) * j_max * self.tf
                - self.ad * h0n
                - 2 * j_max * self.vd
            ) / (h0n * h0n)

            orig = (
                -self.a0_p3
                + self.af_p3
                + 3 * self.ad_p2 * j_max * (h1n - t_m)
                + 3 * self.ad * self.j_max_p2 * (h1n - t_m) * (h1n - t_m)
                - 3 * self.a0 * self.af * self.ad
                + 3
                * self.j_max_p2
                * (
                    self.a0 * self.tf_p2
                    - 2 * self.pd
                    + 2 * self.tf * self.v0
                    + h1n * h1n * j_max * (self.tf - 2 * t_m)
                    + j_max * self.tf * (2 * h1n * t_m - t_m * t_m - (h1n - t_m) * self.tf)
                )
            ) / (6 * self.j_max_p2)

            deriv = (h0n * (-self.ad + j_max * self.tf) * (h2n - 1)) / (2 * j_max) + h1n * (
                -self.ad + j_max * (self.tf - h1n) - h0n * h2n
            )

            t_m -= orig / deriv

            profile.t[0] = t_m
            profile.t[1] = 0.0
            profile.t[2] = (
                self.ad_p2
                + 2
                * j_max
                * (-self.a0 * self.tf - self.ad * t_m + j_max * t_m * (t_m - self.tf) + self.vd)
            ) / (2 * j_max * (-self.ad + j_max * (2 * t_m - self.tf)))
            profile.t[3] = self.ad / j_max + self.tf - 2 * t_m
            profile.t[4] = self.tf - (t_m + profile.t[2] + profile.t[3])
            profile.t[5] = 0.0
            profile.t[6] = 0.0

            if profile.check_with_timing(
                self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        # T 3456
        h1_3456 = 3 * j_max * (self.ad_p2 + 2 * j_max * (self.a0 * self.tf - self.vd))
        h2_3456 = self.ad_p2 + 2 * j_max * (self.a0 * self.tf - self.vd)
        h0_3456 = (
            _ieee754_div(
                _ieee754_sqrt(
                    4
                    * _pow2(
                        2 * (self.a0_p3 - self.af_p3)
                        - 6 * self.a0_p2 * (self.af - j_max * self.tf)
                        + 6 * self.j_max_p2 * self.g1
                        + 3
                        * self.a0
                        * (
                            2 * self.af_p2
                            - 2 * j_max * self.af * self.tf
                            + self.j_max_p2 * self.tf_p2
                        )
                        + 6 * self.ad * j_max * self.vd
                    )
                    - 18 * h2_3456 * h2_3456 * h2_3456
                ),
                h1_3456,
            )
            * abs(j_max)
            / j_max
        )

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = _ieee754_div(
            self.af_p3
            - self.a0_p3
            + 3 * (self.af_p2 - self.a0_p2) * j_max * self.tf
            - 3 * self.ad * (self.a0 * self.af + 2 * j_max * self.vd)
            - 6 * self.j_max_p2 * self.g2,
            h1_3456,
        )
        profile.t[4] = (self.tf - profile.t[3] - h0_3456) / 2 - self.ad / (2 * j_max)
        profile.t[5] = h0_3456
        profile.t[6] = (self.tf - profile.t[3] + self.ad / j_max - h0_3456) / 2

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # T 2346
        ph1_2346 = (
            self.ad_p2
            + 2 * (self.af + self.a0) * j_max * self.tf
            - j_max * (j_max * self.tf_p2 + 4 * self.vd)
        )
        ph2_2346 = j_max * self.tf_p2 * self.g1 - self.vd * (
            -2 * self.pd - self.tf * self.v0 + 3 * self.tf * self.vf
        )
        ph3_2346 = (
            5 * self.af_p2
            - 8 * self.af * j_max * self.tf
            + 2 * j_max * (2 * j_max * self.tf_p2 - self.vd)
        )
        ph4_2346 = (
            self.j_max_p2 * self.tf_p4
            - 2 * self.vd_p2
            + 8 * j_max * self.tf * (-self.pd + self.tf * self.vf)
        )
        ph5_2346 = (
            5 * self.af_p4
            - 8 * self.af_p3 * j_max * self.tf
            - 12 * self.af_p2 * j_max * (j_max * self.tf_p2 + self.vd)
            + 24
            * self.af
            * self.j_max_p2
            * (-2 * self.pd + j_max * self.tf_p3 + 2 * self.tf * self.vf)
            - 6 * self.j_max_p2 * ph4_2346
        )
        ph6_2346 = (
            -self.vd_p2
            + j_max * self.tf * (-2 * self.pd + 3 * self.tf * self.v0 - self.tf * self.vf)
            - self.af * self.g2
        )

        poly1_2346 = -(
            4 * (self.a0_p3 - self.af_p3)
            - 12 * self.a0_p2 * (self.af - j_max * self.tf)
            + 6
            * self.a0
            * (
                2 * self.af_p2
                - 2 * self.af * j_max * self.tf
                + j_max * (j_max * self.tf_p2 - 2 * self.vd)
            )
            + 6 * self.af * j_max * (3 * j_max * self.tf_p2 + 2 * self.vd)
            - 6
            * self.j_max_p2
            * (-4 * self.pd + j_max * self.tf_p3 - 2 * self.tf * self.v0 + 6 * self.tf * self.vf)
        ) / (3 * j_max * ph1_2346)

        poly2_2346 = -(
            -self.a0_p4
            - self.af_p4
            + 4 * self.a0_p3 * (self.af - j_max * self.tf)
            + self.a0_p2
            * (
                -6 * self.af_p2
                + 8 * self.af * j_max * self.tf
                - 4 * j_max * (j_max * self.tf_p2 - self.vd)
            )
            + 2 * self.af_p2 * j_max * (j_max * self.tf_p2 + 2 * self.vd)
            - 4
            * self.af
            * self.j_max_p2
            * (-3 * self.pd + j_max * self.tf_p3 + 2 * self.tf * self.v0 + self.tf * self.vf)
            + self.j_max_p2
            * (
                self.j_max_p2 * self.tf_p4
                - 8 * self.vd_p2
                + 4 * j_max * self.tf * (-3 * self.pd + self.tf * self.v0 + 2 * self.tf * self.vf)
            )
            + 2
            * self.a0
            * (
                2 * self.af_p3
                - 2 * self.af_p2 * j_max * self.tf
                + self.af * j_max * (-3 * j_max * self.tf_p2 - 4 * self.vd)
                + self.j_max_p2
                * (
                    -6 * self.pd
                    + j_max * self.tf_p3
                    - 4 * self.tf * self.v0
                    + 10 * self.tf * self.vf
                )
            )
        ) / (self.j_max_p2 * ph1_2346)

        poly3_2346 = -(
            self.a0_p5
            - self.af_p5
            + self.af_p4 * j_max * self.tf
            - 5 * self.a0_p4 * (self.af - j_max * self.tf)
            + 2 * self.a0_p3 * ph3_2346
            + 4 * self.af_p3 * j_max * (j_max * self.tf_p2 + self.vd)
            + 12 * self.j_max_p2 * self.af * ph6_2346
            - 2
            * self.a0_p2
            * (
                5 * self.af_p3
                - 9 * self.af_p2 * j_max * self.tf
                - 6 * self.af * j_max * self.vd
                + 6 * self.j_max_p2 * (-2 * self.pd - self.tf * self.v0 + 3 * self.tf * self.vf)
            )
            - 12 * self.j_max_p2 * j_max * ph2_2346
            + self.a0 * ph5_2346
        ) / (3 * self.j_max_p2 * j_max * ph1_2346)

        poly4_2346 = -(
            -self.a0_p6
            - self.af_p6
            + 6 * self.a0_p5 * (self.af - j_max * self.tf)
            - 48 * self.af_p3 * self.j_max_p2 * self.g1
            + 72
            * self.j_max_p2
            * j_max
            * (j_max * self.g1 * self.g1 + self.vd_p2 * self.vd + 2 * self.af * self.g1 * self.vd)
            - 3 * self.a0_p4 * ph3_2346
            - 36 * self.af_p2 * self.j_max_p2 * self.vd_p2
            + 6 * self.af_p4 * j_max * self.vd
            + 4
            * self.a0_p3
            * (
                5 * self.af_p3
                - 9 * self.af_p2 * j_max * self.tf
                - 6 * self.af * j_max * self.vd
                + 6 * self.j_max_p2 * (-2 * self.pd - self.tf * self.v0 + 3 * self.tf * self.vf)
            )
            - 3 * self.a0_p2 * ph5_2346
            + 6
            * self.a0
            * (
                self.af_p5
                - self.af_p4 * j_max * self.tf
                - 4 * self.af_p3 * j_max * (j_max * self.tf_p2 + self.vd)
                + 12 * self.j_max_p2 * (-self.af * ph6_2346 + j_max * ph2_2346)
            )
        ) / (18 * self.j_max_p2 * self.j_max_p2 * ph1_2346)

        polynom_2346 = [poly1_2346, poly2_2346, poly3_2346, poly4_2346]
        t_max_2346 = (self.a0 - a_min) / j_max

        roots_2346 = sorted(solve_quartic_monic(*polynom_2346))
        for t_root in roots_2346:
            t_m = t_root
            if t_m > t_max_2346:
                continue

            # Single Newton step (regarding pd).
            h1n = self.ad_p2 / 2 + j_max * (
                self.af * t_m + (j_max * t_m - self.a0) * (t_m - self.tf) - self.vd
            )
            h2n = -self.ad + j_max * (self.tf - 2 * t_m)
            h3n = _ieee754_sqrt(h1n)
            orig = (
                (
                    self.af_p3
                    - self.a0_p3
                    + 3 * self.af * j_max * t_m * (self.af + j_max * t_m)
                    + 3 * self.a0_p2 * (self.af + j_max * t_m)
                    - 3
                    * self.a0
                    * (
                        self.af_p2
                        + 2 * self.af * j_max * t_m
                        + self.j_max_p2 * (t_m * t_m - self.tf_p2)
                    )
                    + 3
                    * self.j_max_p2
                    * (
                        -2 * self.pd
                        + j_max * t_m * (t_m - self.tf) * self.tf
                        + 2 * self.tf * self.v0
                    )
                )
                / (6 * self.j_max_p2)
                - h3n * h3n * h3n / (j_max * abs(j_max))
                + ((-self.ad - j_max * t_m) * h1n) / self.j_max_p2
            )
            deriv = (
                6 * j_max * h2n * h3n / abs(j_max)
                + 2 * (-self.ad - j_max * self.tf) * h2n
                - 2
                * (
                    3 * self.ad_p2
                    + self.af * j_max * (8 * t_m - 2 * self.tf)
                    + 4 * self.a0 * j_max * (-2 * t_m + self.tf)
                    + 2 * j_max * (j_max * t_m * (3 * t_m - 2 * self.tf) - self.vd)
                )
            ) / (4 * j_max)

            t_m -= orig / deriv

            h1_sol2 = _ieee754_sqrt(
                2 * self.ad_p2
                + 4
                * j_max
                * (self.ad * t_m + self.a0 * self.tf + j_max * t_m * (t_m - self.tf) - self.vd)
            ) / abs(j_max)

            # Solution 2 with aPlat
            profile.t[0] = 0.0
            profile.t[1] = 0.0
            profile.t[2] = t_m
            profile.t[3] = self.tf - 2 * t_m - self.ad / j_max - h1_sol2
            profile.t[4] = h1_sol2 / 2
            profile.t[5] = 0.0
            profile.t[6] = self.tf - (t_m + profile.t[3] + profile.t[4])

            if profile.check_with_timing(
                self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        # Profiles with a3 != 0, Solution UDUD: T 0124
        ph0_0124 = -2 * self.pd - self.tf * self.v0 + 3 * self.tf * self.vf
        ph1_0124 = -self.ad + j_max * self.tf
        ph2_0124 = j_max * self.tf_p2 * self.g1 - self.vd * ph0_0124
        ph3_0124 = 5 * self.af_p2 + 2 * j_max * (
            2 * j_max * self.tf_p2 - self.vd - 4 * self.af * self.tf
        )
        ph4_0124 = (
            self.j_max_p2 * self.tf_p4
            - 2 * self.vd_p2
            + 8 * j_max * self.tf * (-self.pd + self.tf * self.vf)
        )
        ph5_0124 = (
            5 * self.af_p4
            - 8 * self.af_p3 * j_max * self.tf
            - 12 * self.af_p2 * j_max * (j_max * self.tf_p2 + self.vd)
            + 24
            * self.af
            * self.j_max_p2
            * (-2 * self.pd + j_max * self.tf_p3 + 2 * self.tf * self.vf)
            - 6 * self.j_max_p2 * ph4_0124
        )
        ph6_0124 = -self.vd_p2 + j_max * self.tf * (
            -2 * self.pd + 3 * self.tf * self.v0 - self.tf * self.vf
        )
        ph7_0124 = 3 * self.j_max_p2 * ph1_0124 * ph1_0124

        poly1_0124 = (4 * self.af * self.tf - 2 * j_max * self.tf_p2 - 4 * self.vd) / ph1_0124
        poly2_0124 = (
            -2 * (self.a0_p4 + self.af_p4)
            + 8 * self.af_p3 * j_max * self.tf
            + 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
            + 8 * self.a0_p3 * (self.af - j_max * self.tf)
            - 12 * self.a0_p2 * (self.af - j_max * self.tf) * (self.af - j_max * self.tf)
            - 12
            * self.af
            * self.j_max_p2
            * (-self.pd + j_max * self.tf_p3 - 2 * self.tf * self.v0 + 3 * self.tf * self.vf)
            + 2
            * self.a0
            * (
                4 * self.af_p3
                - 12 * self.af_p2 * j_max * self.tf
                + 9 * self.af * self.j_max_p2 * self.tf_p2
                - 3 * self.j_max_p2 * (2 * self.pd + j_max * self.tf_p3 - 2 * self.tf * self.vf)
            )
            + 3
            * self.j_max_p2
            * (
                self.j_max_p2 * self.tf_p4
                + 4 * self.vd_p2
                - 4 * j_max * self.tf * (self.pd + self.tf * self.v0 - 2 * self.tf * self.vf)
            )
        ) / ph7_0124
        poly3_0124 = (
            -self.a0_p5
            + self.af_p5
            - self.af_p4 * j_max * self.tf
            + 5 * self.a0_p4 * (self.af - j_max * self.tf)
            - 2 * self.a0_p3 * ph3_0124
            - 4 * self.af_p3 * j_max * (j_max * self.tf_p2 + self.vd)
            + 12 * self.af_p2 * self.j_max_p2 * self.g2
            - 12 * self.af * self.j_max_p2 * ph6_0124
            + 2
            * self.a0_p2
            * (
                5 * self.af_p3
                - 9 * self.af_p2 * j_max * self.tf
                - 6 * self.af * j_max * self.vd
                + 6 * self.j_max_p2 * ph0_0124
            )
            + 12 * self.j_max_p2 * j_max * ph2_0124
            + self.a0
            * (
                -5 * self.af_p4
                + 8 * self.af_p3 * j_max * self.tf
                + 12 * self.af_p2 * j_max * (j_max * self.tf_p2 + self.vd)
                - 24
                * self.af
                * self.j_max_p2
                * (-2 * self.pd + j_max * self.tf_p3 + 2 * self.tf * self.vf)
                + 6 * self.j_max_p2 * ph4_0124
            )
        ) / (j_max * ph7_0124)
        poly4_0124 = -(
            self.a0_p6
            + self.af_p6
            - 6 * self.a0_p5 * (self.af - j_max * self.tf)
            + 48 * self.af_p3 * self.j_max_p2 * self.g1
            - 72
            * self.j_max_p2
            * j_max
            * (j_max * self.g1 * self.g1 + self.vd_p2 * self.vd + 2 * self.af * self.g1 * self.vd)
            + 3 * self.a0_p4 * ph3_0124
            - 6 * self.af_p4 * j_max * self.vd
            + 36 * self.af_p2 * self.j_max_p2 * self.vd_p2
            - 4
            * self.a0_p3
            * (
                5 * self.af_p3
                - 9 * self.af_p2 * j_max * self.tf
                - 6 * self.af * j_max * self.vd
                + 6 * self.j_max_p2 * ph0_0124
            )
            + 3 * self.a0_p2 * ph5_0124
            - 6
            * self.a0
            * (
                self.af_p5
                - self.af_p4 * j_max * self.tf
                - 4 * self.af_p3 * j_max * (j_max * self.tf_p2 + self.vd)
                + 12
                * self.j_max_p2
                * (self.af_p2 * self.g2 - self.af * ph6_0124 + j_max * ph2_0124)
            )
        ) / (6 * self.j_max_p2 * ph7_0124)

        polynom_0124 = [poly1_0124, poly2_0124, poly3_0124, poly4_0124]

        roots_0124 = sorted(solve_quartic_monic(*polynom_0124))
        for t in roots_0124:
            if t > self.tf or t > (a_max - self.a0) / j_max:
                continue

            h1_0124 = _ieee754_sqrt(
                self.ad_p2 / (2 * self.j_max_p2)
                + (self.a0 * (t + self.tf) - self.af * t + j_max * t * self.tf - self.vd) / j_max
            )

            profile.t[0] = t
            profile.t[1] = self.tf - self.ad / j_max - 2 * h1_0124
            profile.t[2] = h1_0124
            profile.t[3] = 0.0
            profile.t[4] = self.ad / j_max + h1_0124 - t
            profile.t[5] = 0.0
            profile.t[6] = 0.0

            if profile.check_with_timing(
                self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDUD, ReachedLimits.NONE
            ):
                return True

        # 3-step profile (aka UZD), sometimes missed because of numerical
        # errors: T 012
        h1_uzd = _ieee754_sqrt(
            -self.ad_p2
            + j_max * (2 * (self.a0 + self.af) * self.tf - 4 * self.vd + j_max * self.tf_p2)
        ) / abs(j_max)

        profile.t[0] = (self.tf - h1_uzd + self.ad / j_max) / 2
        profile.t[1] = h1_uzd
        profile.t[2] = (self.tf - h1_uzd - self.ad / j_max) / 2
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # 3-step profile (aka UZU), sometimes missed because of numerical
        # errors.
        polynom_uzu = [
            self.ad_p2,
            self.ad_p2 * self.tf,
            (self.a0_p2 + self.af_p2 + 10 * self.a0 * self.af) * self.tf_p2
            + 24 * (self.tf * (self.af * self.v0 - self.a0 * self.vf) - self.pd * self.ad)
            + 12 * self.vd_p2,
            -3
            * self.tf
            * (
                (self.a0_p2 + self.af_p2 + 2 * self.a0 * self.af) * self.tf_p2
                - 4 * self.vd * (self.a0 + self.af) * self.tf
                + 4 * self.vd_p2
            ),
        ]
        roots_uzu = sorted(solve_cubic(*polynom_uzu))
        for t in roots_uzu:
            if t > self.tf:
                continue

            jf = self.ad / (self.tf - t)

            profile.t[0] = _ieee754_div(
                2 * (self.vd - self.a0 * self.tf) + self.ad * (t - self.tf), 2 * jf * t
            )
            profile.t[1] = t
            profile.t[2] = 0.0
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = self.tf - (profile.t[0] + profile.t[1])

            if profile.check_with_timing(
                self.tf,
                jf,
                v_max,
                v_min,
                a_max,
                a_min,
                ControlSigns.UDDU,
                ReachedLimits.NONE,
                j_max=j_max,
            ):
                return True

        # 3-step profile (aka UDU), sometimes missed because of numerical
        # errors.
        profile.t[0] = (
            self.ad_p2 / j_max
            + 2 * (self.a0 + self.af) * self.tf
            - j_max * self.tf_p2
            - 4 * self.vd
        ) / (4 * (self.ad - j_max * self.tf))
        profile.t[1] = 0.0
        profile.t[2] = -self.ad / (2 * j_max) + self.tf / 2
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[0] + profile.t[2])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        return False

    def _time_none_smooth(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        """Never called from :meth:`get_profile` in the Swift source either
        -- ported anyway per otg.md design constraint 2 (see this module's
        docstring)."""
        # Solution: h0/h1
        h0 = self.ad_p2 + 2 * j_max * (self.a0 * self.tf - self.vd)
        h1a = (
            2 * (self.a0_p3 - self.af_p3)
            - 6 * self.a0_p2 * (self.af - j_max * self.tf)
            + 6 * self.j_max_p2 * (-self.pd + self.tf * self.v0)
            + 6 * self.a0 * self.af_p2
            + 3 * self.a0 * j_max * (j_max * self.tf_p2 - 2 * self.vd)
            + 6 * self.af * j_max * (self.vd - self.tf * self.a0)
        )
        h1 = _ieee754_sqrt(4 * h1a * h1a - 18 * h0 * h0 * h0) * abs(j_max) / j_max

        profile.t[0] = 0.0
        profile.t[1] = (
            -self.a0_p3
            + self.af_p3
            + 3 * (self.af_p2 - self.a0_p2) * j_max * self.tf
            - 3 * self.a0 * self.af * self.ad
            - 6 * j_max * self.ad * self.vd
            - 6 * self.j_max_p2 * (-2 * self.pd + self.tf * (self.v0 + self.vf))
        ) / (3 * j_max * h0)
        profile.t[2] = (
            4 * (self.a0_p3 - self.af_p3)
            + 6 * self.j_max_p2 * self.a0 * self.tf_p2
            + 12 * self.a0 * self.af * self.ad
            + 12
            * j_max
            * (j_max * (self.tf * self.v0 - self.pd) + self.ad * (self.vd - self.a0 * self.tf))
            - h1
        ) / (6 * j_max * h0)
        profile.t[3] = h1 / (3 * j_max * h0)
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[1] + profile.t[2] + profile.t[3])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # Solution: h0/h0b/h1a
        h0_2 = self.ad_p2 + 2 * j_max * (self.vd - self.af * self.tf)
        h0b_2 = self.af_p3 - 3 * self.j_max_p2 * (
            self.af * self.tf_p2 + 2 * (self.pd - self.tf * self.vf)
        )
        h1a_2 = self.a0_p3 + 3 * self.a0 * self.af * self.ad - h0b_2
        h1_2 = (
            _ieee754_sqrt(
                4 * h1a_2 * h1a_2
                - 6
                * h0_2
                * (
                    self.a0_p4
                    + self.af_p4
                    - 4 * self.a0_p3 * self.af
                    + 6 * self.a0_p2 * self.af_p2
                    + 12
                    * self.j_max_p2
                    * (self.vd_p2 - 2 * self.af * (self.pd - self.tf * self.v0))
                    - 4 * self.a0 * h0b_2
                )
            )
            * abs(j_max)
            / j_max
        )

        profile.t[0] = -(2 * h1a_2 + h1_2) / (6 * j_max * h0_2)
        profile.t[1] = h1_2 / (3 * j_max * h0_2)
        profile.t[2] = profile.t[0] - (self.af - self.a0) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = self.tf - (profile.t[0] + profile.t[1] + profile.t[2])
        profile.t[6] = 0.0

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # Solution 3
        h0_3 = (
            _ieee754_sqrt(
                3
                * (
                    self.a0_p4
                    + self.af_p4
                    - 4 * self.af_p3 * j_max * self.tf
                    + 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
                    - 4 * self.a0_p3 * (self.af - j_max * self.tf)
                    + 6 * self.a0_p2 * (self.af - j_max * self.tf) * (self.af - j_max * self.tf)
                    + 24 * self.af * self.j_max_p2 * (-self.pd + self.tf * self.v0)
                    - 4
                    * self.a0
                    * (
                        self.af_p3
                        - 3 * self.af_p2 * j_max * self.tf
                        + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
                    )
                    - 12
                    * self.j_max_p2
                    * (
                        -self.vd_p2
                        + j_max * self.tf * (-2 * self.pd + self.tf * (self.v0 + self.vf))
                    )
                )
            )
            * abs(j_max)
            / j_max
        )
        h1_3 = (
            _ieee754_sqrt(
                3
                * (
                    3 * self.a0_p2
                    + 3 * self.af_p2
                    - 6 * self.a0 * self.af
                    - 6 * self.ad * j_max * self.tf
                    + 3 * self.j_max_p2 * self.tf_p2
                    - 2 * h0_3
                )
            )
            * abs(j_max)
            / j_max
        )

        profile.t[0] = (
            -3 * (self.a0_p2 + self.af_p2)
            + 6 * self.a0 * self.af
            + 6 * j_max * (self.vd - self.a0 * self.tf)
            + h0_3
        ) / (6 * j_max * (-self.ad + j_max * self.tf))
        profile.t[1] = 0.0
        profile.t[2] = (3 * j_max * self.tf - 3 * self.ad - h1_3) / (6 * j_max)
        profile.t[3] = h1_3 / (3 * j_max)
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[0] + profile.t[2] + profile.t[3])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # Solution 2
        h0_4 = 6 * (self.ad_p2 + 2 * self.af * j_max * self.tf - 2 * j_max * self.vd)
        h1a_4 = 2 * (
            self.a0_p3
            - self.af_p3
            + 3 * self.a0 * self.af * self.ad
            + 6 * self.j_max_p2 * (self.pd - self.tf * self.vf)
            + 3 * self.j_max_p2 * self.af * self.tf_p2
        )
        h1_4 = (
            _ieee754_sqrt(
                h1a_4 * h1a_4
                - h0_4
                * (
                    self.a0_p4
                    - 4 * self.a0_p3 * self.af
                    + 6 * self.a0_p2 * self.af_p2
                    + self.af_p4
                    + 24 * self.af * self.j_max_p2 * (-self.pd + self.tf * self.v0)
                    + 12 * self.j_max_p2 * self.vd_p2
                    - 4
                    * self.a0
                    * (
                        self.af_p3
                        - 3 * self.af * self.j_max_p2 * self.tf_p2
                        + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
                    )
                )
            )
            * abs(j_max)
            / j_max
        )
        h2_4 = (
            4 * self.a0_p3
            - 4 * self.af_p3
            + 12 * self.a0 * self.af * self.ad
            - 12 * self.j_max_p2 * (self.pd - self.tf * self.vf)
            - 6 * self.j_max_p2 * self.af * self.tf_p2
            + 12 * self.ad * j_max * (self.vd - self.af * self.tf)
        )
        h3_4 = j_max * h0_4

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = (h1a_4 + h1_4) / h3_4
        profile.t[3] = -(h2_4 + h1_4) / h3_4
        profile.t[4] = (h2_4 - h1_4) / h3_4
        profile.t[5] = self.tf - (profile.t[2] + profile.t[3] + profile.t[4])
        profile.t[6] = 0.0

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        # Solution 1
        term1 = self.a0_p4 + self.af_p4 - 4 * self.af_p3 * j_max * self.tf
        term2 = 6 * self.af_p2 * self.j_max_p2 * self.tf_p2
        term3 = -4 * self.a0_p3 * (self.af - j_max * self.tf)
        term4 = 6 * self.a0_p2 * (self.af - j_max * self.tf) * (self.af - j_max * self.tf)
        term5 = 24 * self.af * self.j_max_p2 * (-self.pd + self.tf * self.v0)
        term6 = (
            -4
            * self.a0
            * (
                self.af_p3
                - 3 * self.af_p2 * j_max * self.tf
                + 6 * self.j_max_p2 * (-self.pd + self.tf * self.vf)
            )
        )
        term7 = (
            -12
            * self.j_max_p2
            * (-self.vd_p2 + j_max * self.tf * (-2 * self.pd + self.tf * (self.v0 + self.vf)))
        )

        h0_5 = (
            _ieee754_sqrt((term1 + term2 + term3 + term4 + term5 + term6 + term7) / 3)
            * abs(j_max)
            / j_max
        )
        h1_5 = (
            _ieee754_sqrt(
                self.ad_p2 - 2 * self.ad * j_max * self.tf + self.j_max_p2 * self.tf_p2 + 2 * h0_5
            )
            * abs(j_max)
            / j_max
        )

        profile.t[0] = -(self.ad_p2 + 2 * j_max * (self.a0 * self.tf - self.vd) + h0_5) / (
            2 * j_max * (-self.ad + j_max * self.tf)
        )
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = (-self.ad + j_max * self.tf - h1_5) / (2 * j_max)
        profile.t[5] = h1_5 / j_max
        profile.t[6] = self.tf - (profile.t[0] + profile.t[4] + profile.t[5])

        if profile.check_with_timing(
            self.tf, j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            return True

        return False

    def get_profile(self, profile: Profile) -> bool:
        # Set the profile target values and initial state -- these are used
        # by check()/check_with_timing() to validate the generated
        # trajectory.
        profile.pf = self.pf
        profile.vf = self.vf
        profile.af = self.af
        profile.p[0] = self.p0
        profile.v[0] = self.v0
        profile.a[0] = self.a0

        # Test all cases to get ones that match. However we should guess
        # which one is correct and try them first...
        up_first = self.pd > self.tf * self.v0
        v_max = self._v_max if up_first else self._v_min
        v_min = self._v_min if up_first else self._v_max
        a_max = self._a_max if up_first else self._a_min
        a_min = self._a_min if up_first else self._a_max
        j_max = self._j_max if up_first else -self._j_max

        if self._time_acc0_acc1_vel(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_vel(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc0_vel(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc1_vel(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc0_acc1_vel(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_vel(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_acc0_vel(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_acc1_vel(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_acc0_acc1(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc0(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc1(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_none(profile, v_max, v_min, a_max, a_min, j_max):
            return True

        if self._time_acc0_acc1(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_acc0(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_acc1(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        if self._time_none(profile, v_min, v_max, a_min, a_max, -j_max):
            return True

        return False
