"""Step 1 solver for the third-order (jerk-limited) position interface:
computes the time-optimal profile.

Faithful port of ``SWIFT_MATH/OTG/position/PositionThirdOrderStep1.swift``
(~850 lines; class/method names and branch structure preserved
mechanically -- the largest/most complex step solver in the OTG port). See
``.claude/specs/otg.md`` §Internal fidelity requirements 1, 2, 4, 5 and
``.claude/action-plan/38-otg-position-third-step1.md``.

**Struct-value-copy semantics.** ``Profile`` is a Python class (reference
type); Swift's ``Profile`` is a struct (value type). This file has the
richest set of alias-mutation hazards in the OTG port so far (see
``steps/velocity_third_order.py`` and ``steps/position_second_order.py``
for the simpler precedents this follows):

- ``_time_all_vel`` and ``_time_acc0_acc1`` each fetch ONE local
  ``profile`` copy at the top and reuse it, unmutated-between-checks, for
  up to four/two sequential solution attempts within the same call (e.g.
  ``_time_all_vel``'s ACC0_ACC1_VEL / ACC1_VEL / ACC0_VEL / VEL cases all
  overwrite the same ``profile.t`` array in turn, even after an earlier
  attempt in the *same call* already succeeded and was "saved" with
  ``return_after_found=False``). Every ``validProfiles[profileCount] =
  profile`` save point is ported as ``self.valid_profiles[self._profile_count]
  = copy.deepcopy(profile)`` so a later attempt's mutations to the shared
  local ``profile`` cannot retroactively corrupt an earlier saved
  candidate -- the initial ``profile = copy.deepcopy(self.valid_profiles[
  self._profile_count])`` fetch is included for the same defensive
  reason/consistency with those two precedent files, even though (unlike
  the saves) it is not independently load-bearing.
- ``_time_all_none_acc0_acc1`` is the one NEW pattern in this port: its
  three ``for`` loops (NONE / ACC0 / ACC1 roots) call ``self._add_profile()``
  on every success and, when NOT returning immediately, explicitly
  re-fetch ``profile = self.valid_profiles[self._profile_count]`` before
  continuing to the next root -- this ports the Swift source's own
  explicit "BUG FIX: Get fresh profile reference to prevent corrupting
  previously added profile" comments verbatim. The re-fetch is a *plain*
  reference reassignment (no ``copy.deepcopy``): it points ``profile`` at
  the freshly ``set_boundary``-initialized next slot (untouched by any
  save), so nothing is aliased with previously-saved state; only the save
  itself (``self.valid_profiles[self._profile_count] = copy.deepcopy(profile)``)
  needs to sever the alias, exactly as in the two methods above.
- ``_time_acc1_vel_two_step``/``_time_acc0_two_step``/``_time_vel_two_step``/
  ``_time_none_two_step`` are "only for numerical issues" (Swift's own
  comment) and, per a source-tree grep, are **never called from
  ``getProfile``** -- dead code in the Swift source too. Ported anyway
  (otg.md design constraint 2: "if a Swift branch looks dead, port it
  anyway and note it"). Each is architecturally like
  ``VelocityThirdOrderStep2``'s "no copy needed" methods (a single
  ``profile`` mutated directly, always returning on the first success), so
  no alias hazard exists within them -- deep copies are still applied at
  every save for uniformity with the rest of this file, not because they
  are load-bearing here.
- ``get_profile``'s "trivial zero" special case (``v0``, ``a0``, and ``pd``
  all ~0) faithfully reproduces an apparent Swift quirk: ``var p =
  validProfiles[profileCount]`` is passed to ``timeAllSingleStep(&p, ...)``
  by ``inout``, and on success only ``profileCount += 1`` runs --
  ``validProfiles[profileCount]`` itself is never reassigned from ``p``.
  In Swift's struct semantics this discards ``p``'s computed
  ``j``/``p``/``v``/``a``/``direction``/``limits``/``control_signs``
  fields, leaving the slot with only its ``set_boundary`` state (this
  doesn't affect correctness for the reachable inputs: the case is only
  entered when ``v0``, ``a0``, ``pd`` are all ~0, so
  ``_time_all_single_step`` always finds the trivial *all-zero-``t``*
  solution here, which is exactly what an unmutated, freshly-``set_boundary``
  slot already has). Ported as ``p = copy.deepcopy(self.valid_profiles[
  self._profile_count])`` with no write-back, reproducing the same
  discard rather than "fixing" it.
"""

from __future__ import annotations

import copy
import math
import sys

from math_tools.functional.roots import solve_quartic_monic
from math_tools.otg.block import Block, Interval
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile
from math_tools.otg.steps.position_third_order_step2 import _ieee754_sqrt

__all__: list[str] = []

#: Swift ``Double.ulpOfOne`` (machine epsilon for float64) -- used for the
#: "vf/af/v0/a0/pd essentially zero" guards in ``get_profile`` and
#: ``_time_all_single_step``. Matches ``steps/velocity_third_order.py``'s
#: identical module-private convention (this is NOT
#: ``functional.roots.EPS16``).
_ULP = sys.float_info.epsilon

#: Swift ``Double.leastNormalMagnitude`` (smallest positive normalized
#: float64, ~2.2250738585072014e-308) -- used for the near-zero guards in
#: ``get_profile``, ``_time_all_single_step``, and
#: ``_time_all_none_acc0_acc1``'s Newton-refinement root guards. Distinct
#: from ``_ULP`` above (both are used in this Swift file, unlike the
#: single-constant velocity/position-second-order files).
_LEAST_NORMAL_MAGNITUDE = sys.float_info.min


def _ieee754_div(numerator: float, denominator: float) -> float:
    """IEEE 754 float division (Swift/C ``Double`` ``/`` semantics):
    ``0.0/0.0`` is ``nan``, ``x/0.0`` (``x != 0``) is a signed infinity --
    never a crash. Python's ``/`` operator raises ``ZeroDivisionError`` on
    any zero denominator instead, which diverges from the Swift source at
    the ``t == 0`` degenerate quartic-root case in
    ``_time_all_none_acc0_acc1``'s NONE loop (a legitimate
    ``insertIfPositive``-returned root when the polynomial's constant term
    is zero -- see ``t_min_none == 0`` in ``get_profile``'s rest-to-rest
    tests). Swift silently propagates the resulting nan/inf into
    ``profile.t[0]``, which then fails ``profile.check``'s precision
    comparisons (nan/inf comparisons are always false) rather than
    crashing; reproduced here explicitly since Python has no implicit
    equivalent for this operator.
    """
    if denominator != 0.0:
        return numerator / denominator
    if numerator == 0.0:
        return math.nan
    return math.copysign(math.inf, numerator) * math.copysign(1.0, denominator)


class PositionThirdOrderStep1:
    """Mathematical equations for Step 1 in the third-order (jerk-limited)
    position interface: extremal (time-optimal) profiles."""

    def __init__(
        self,
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
        self.v0 = v0
        self.a0 = a0
        self.vf = vf
        self.af = af
        self._v_max = v_max
        self._v_min = v_min
        self._a_max = a_max
        self._a_min = a_min
        self._j_max = j_max

        # Pre-calculated expressions.
        self.pd = pf - p0
        self.v0_p2 = v0 * v0
        self.vf_p2 = vf * vf
        self.a0_p2 = a0 * a0
        self.af_p2 = af * af
        self.a0_p3 = a0 * self.a0_p2
        self.a0_p4 = self.a0_p2 * self.a0_p2
        self.af_p3 = af * self.af_p2
        self.af_p4 = self.af_p2 * self.af_p2
        self.j_max_p2 = j_max * j_max

        # Max 5 valid profiles + 1 spare for numerical issues. Separate
        # instances, not shared references (`[Profile()] * 6` would create
        # multiple references to the SAME object).
        self.valid_profiles: list[Profile] = [Profile() for _ in range(6)]
        self._profile_count = 0

    def _add_profile(self) -> None:
        self._profile_count += 1
        if self._profile_count < len(self.valid_profiles):
            self.valid_profiles[self._profile_count].set_boundary(
                self.valid_profiles[self._profile_count - 1]
            )

    def _reset_profiles(self) -> None:
        self._profile_count = 0

    def _has_profiles(self) -> bool:
        return self._profile_count > 0

    def _time_all_vel(
        self,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
        return_after_found: bool,
    ) -> None:
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        # ACC0_ACC1_VEL
        # NOTE: this profile type explicitly uses aMax/aMin in the formulas
        # below, so it inherently respects acceleration limits. No
        # additional checking needed.
        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = (self.a0_p2 / 2 - a_max * a_max - j_max * (self.v0 - v_max)) / (
            a_max * j_max
        )
        profile.t[2] = a_max / j_max
        profile.t[3] = (
            3 * (self.a0_p4 * a_min - self.af_p4 * a_max)
            + 8
            * a_max
            * a_min
            * (self.af_p3 - self.a0_p3 + 3 * j_max * (self.a0 * self.v0 - self.af * self.vf))
            + 6 * self.a0_p2 * a_min * (a_max * a_max - 2 * j_max * self.v0)
            - 6 * self.af_p2 * a_max * (a_min * a_min - 2 * j_max * self.vf)
            - 12
            * j_max
            * (
                a_max
                * a_min
                * (a_max * (self.v0 + v_max) - a_min * (self.vf + v_max) - 2 * j_max * self.pd)
                + (a_min - a_max) * j_max * v_max * v_max
                + j_max * (a_max * self.vf_p2 - a_min * self.v0_p2)
            )
        ) / (24 * a_max * a_min * self.j_max_p2 * v_max)
        profile.t[4] = -a_min / j_max
        profile.t[5] = -(self.af_p2 / 2 - a_min * a_min - j_max * (self.vf - v_max)) / (
            a_min * j_max
        )
        profile.t[6] = profile.t[4] + self.af / j_max

        if profile.check(
            j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0_ACC1_VEL
        ):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            if return_after_found:
                return

        # ACC1_VEL
        # BUG FIX: this profile type calculates times based only on vMax
        # and jMax for the acceleration phase, without explicitly
        # constraining to aMax/aMin. We need to check whether the
        # resulting peak acceleration in the acceleration phase would
        # violate limits. The deceleration phase explicitly uses aMin, so
        # it's automatically constrained.
        t_acc0 = _ieee754_sqrt(self.a0_p2 / (2 * self.j_max_p2) + (v_max - self.v0) / j_max)
        a_peak_acc0 = j_max * t_acc0

        # Check whether the peak is within [aMin, aMax] (handles both UP
        # and DOWN directions).
        a_limit_min = min(a_min, a_max)
        a_limit_max = max(a_min, a_max)

        if a_limit_min <= a_peak_acc0 <= a_limit_max:
            # Acceleration-phase peak is within limits. The deceleration
            # phase uses aMin directly, so it's automatically constrained.
            # Generate the profile.
            profile.t[0] = t_acc0 - self.a0 / j_max
            profile.t[1] = 0.0
            profile.t[2] = t_acc0
            profile.t[3] = (
                -3 * self.af_p4
                + 8 * a_min * (self.af_p3 - self.a0_p3)
                + 24 * a_min * j_max * (self.a0 * self.v0 - self.af * self.vf)
                - 6 * self.af_p2 * (a_min * a_min - 2 * j_max * self.vf)
                + 12
                * j_max
                * (
                    2 * a_min * j_max * self.pd
                    + a_min * a_min * (self.vf + v_max)
                    + j_max * (v_max * v_max - self.vf_p2)
                    + a_min * t_acc0 * (self.a0_p2 - 2 * j_max * (self.v0 + v_max))
                )
            ) / (24 * a_min * self.j_max_p2 * v_max)
            profile.t[4] = -a_min / j_max
            profile.t[5] = -(self.af_p2 / 2 - a_min * a_min - j_max * (self.vf - v_max)) / (
                a_min * j_max
            )
            profile.t[6] = profile.t[4] + self.af / j_max

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC1_VEL
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return

        # ACC0_VEL
        t_acc1 = _ieee754_sqrt(self.af_p2 / (2 * self.j_max_p2) + (v_max - self.vf) / j_max)

        # BUG FIX: check whether the peak acceleration would exceed limits
        # (preserve sign!).
        a_peak_acc1_acc0vel = j_max * t_acc1

        if a_limit_min <= a_peak_acc1_acc0vel <= a_limit_max:
            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = (self.a0_p2 / 2 - a_max * a_max - j_max * (self.v0 - v_max)) / (
                a_max * j_max
            )
            profile.t[2] = a_max / j_max
            profile.t[3] = (
                3 * self.a0_p4
                + 8 * a_max * (self.af_p3 - self.a0_p3)
                + 24 * a_max * j_max * (self.a0 * self.v0 - self.af * self.vf)
                + 6 * self.a0_p2 * (a_max * a_max - 2 * j_max * self.v0)
                - 12
                * j_max
                * (
                    -2 * a_max * j_max * self.pd
                    + a_max * a_max * (self.v0 + v_max)
                    + j_max * (v_max * v_max - self.v0_p2)
                    + a_max * t_acc1 * (-self.af_p2 + 2 * (self.vf + v_max) * j_max)
                )
            ) / (24 * a_max * self.j_max_p2 * v_max)
            profile.t[4] = t_acc1
            profile.t[5] = 0.0
            profile.t[6] = t_acc1 + self.af / j_max

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0_VEL
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return

        # VEL
        # BUG FIX: re-check tAcc0 and tAcc1 for the VEL profile (they were
        # calculated earlier). Peak accelerations: a_peak_acc0 (already
        # calculated), a_peak_acc1 (need t_acc1).
        t_acc1_vel = _ieee754_sqrt(self.af_p2 / (2 * self.j_max_p2) + (v_max - self.vf) / j_max)
        a_peak_acc1_vel = j_max * t_acc1_vel

        # Check whether both phases respect limits (directional check, not
        # abs!). a_limit_min/max were already calculated above for
        # ACC1_VEL.
        if (
            a_limit_min <= a_peak_acc0 <= a_limit_max
            and a_limit_min <= a_peak_acc1_vel <= a_limit_max
        ):
            profile.t[0] = t_acc0 - self.a0 / j_max
            profile.t[1] = 0.0
            profile.t[2] = t_acc0
            profile.t[3] = (
                (self.af_p3 - self.a0_p3) / (3 * self.j_max_p2 * v_max)
                + (
                    self.a0 * self.v0
                    - self.af * self.vf
                    + (self.af_p2 * t_acc1_vel + self.a0_p2 * t_acc0) / 2
                )
                / (j_max * v_max)
                - (self.v0 / v_max + 1.0) * t_acc0
                - (self.vf / v_max + 1.0) * t_acc1_vel
                + self.pd / v_max
            )

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.VEL
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return

    def _time_acc0_acc1(
        self,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
        return_after_found: bool,
    ) -> None:
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        h1 = (
            3 * (self.af_p4 * a_max - self.a0_p4 * a_min)
            + a_max
            * a_min
            * (
                8 * (self.a0_p3 - self.af_p3)
                + 3 * a_max * a_min * (a_max - a_min)
                + 6 * a_min * self.af_p2
                - 6 * a_max * self.a0_p2
            )
            + 12
            * j_max
            * (
                a_max * a_min * ((a_max - 2 * self.a0) * self.v0 - (a_min - 2 * self.af) * self.vf)
                + a_min * self.a0_p2 * self.v0
                - a_max * self.af_p2 * self.vf
            )
        ) / (3 * (a_max - a_min) * self.j_max_p2)

        h1 += (
            4
            * (a_max * self.vf_p2 - a_min * self.v0_p2 - 2 * a_min * a_max * self.pd)
            / (a_max - a_min)
        )

        if h1 >= 0:
            h1 = _ieee754_sqrt(h1) / 2

            h2 = (
                self.a0_p2 / (2 * a_max * j_max)
                + (a_min - 2 * a_max) / (2 * j_max)
                - self.v0 / a_max
            )
            h3 = (
                -self.af_p2 / (2 * a_min * j_max)
                - (a_max - 2 * a_min) / (2 * j_max)
                + self.vf / a_min
            )

            # UDDU: Solution 2
            if h2 > h1 / a_max and h3 > -h1 / a_min:
                profile.t[0] = (-self.a0 + a_max) / j_max
                profile.t[1] = h2 - h1 / a_max
                profile.t[2] = a_max / j_max
                profile.t[3] = 0.0
                profile.t[4] = -a_min / j_max
                profile.t[5] = h3 + h1 / a_min
                profile.t[6] = profile.t[4] + self.af / j_max

                if profile.check(
                    j_max,
                    v_max,
                    v_min,
                    a_max,
                    a_min,
                    ControlSigns.UDDU,
                    ReachedLimits.ACC0_ACC1,
                    True,
                ):
                    self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                    self._add_profile()
                    if return_after_found:
                        return

            # UDDU: Solution 1
            if h2 > -h1 / a_max and h3 > h1 / a_min:
                profile.t[0] = (-self.a0 + a_max) / j_max
                profile.t[1] = h2 + h1 / a_max
                profile.t[2] = a_max / j_max
                profile.t[3] = 0.0
                profile.t[4] = -a_min / j_max
                profile.t[5] = h3 - h1 / a_min
                profile.t[6] = profile.t[4] + self.af / j_max

                if profile.check(
                    j_max,
                    v_max,
                    v_min,
                    a_max,
                    a_min,
                    ControlSigns.UDDU,
                    ReachedLimits.ACC0_ACC1,
                    True,
                ):
                    self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                    self._add_profile()

    def _time_all_none_acc0_acc1(
        self,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
        return_after_found: bool,
    ) -> None:
        # BUG FIX (Swift source comment): reassigned (not just read once)
        # so a fresh reference can be grabbed after add_profile() advances
        # to a new slot -- see this module's docstring.
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        # NONE UDDU / UDUD strategy
        h2_none = (self.a0_p2 - self.af_p2) / (2 * j_max) + (self.vf - self.v0)
        h2_p2 = h2_none * h2_none
        t_min_none = (self.a0 - self.af) / j_max
        t_max_none = (a_max - a_min) / j_max

        polynom_none = [
            0.0,
            -2 * (self.a0_p2 + self.af_p2 - 2 * j_max * (self.v0 + self.vf)) / self.j_max_p2,
            4
            * (self.a0_p3 - self.af_p3 + 3 * j_max * (self.af * self.vf - self.a0 * self.v0))
            / (3 * j_max * self.j_max_p2)
            - 4 * self.pd / j_max,
            -h2_p2 / self.j_max_p2,
        ]

        h3_acc0 = (self.a0_p2 - self.af_p2) / (2 * a_max * j_max) + (self.vf - self.v0) / a_max
        t_min_acc0 = (a_max - self.af) / j_max
        t_max_acc0 = (a_max - a_min) / j_max

        h0_acc0 = (
            3 * (self.af_p4 - self.a0_p4)
            + 8 * (self.a0_p3 - self.af_p3) * a_max
            + 24 * a_max * j_max * (self.af * self.vf - self.a0 * self.v0)
            - 6 * self.a0_p2 * (a_max * a_max - 2 * j_max * self.v0)
            + 6 * self.af_p2 * (a_max * a_max - 2 * j_max * self.vf)
            + 12
            * j_max
            * (
                j_max * (self.vf_p2 - self.v0_p2 - 2 * a_max * self.pd)
                - a_max * a_max * (self.vf - self.v0)
            )
        )
        h2_acc0 = -self.af_p2 + a_max * a_max + 2 * j_max * self.vf

        polynom_acc0 = [
            -2 * a_max / j_max,
            h2_acc0 / self.j_max_p2,
            0.0,
            h0_acc0 / (12 * self.j_max_p2 * self.j_max_p2),
        ]

        h3_acc1 = (
            -(self.a0_p2 + self.af_p2) / (2 * j_max * a_min)
            + a_min / j_max
            + (self.vf - self.v0) / a_min
        )
        t_min_acc1 = (a_min - self.a0) / j_max
        t_max_acc1 = (a_max - self.a0) / j_max

        h0_acc1 = (
            (self.a0_p4 - self.af_p4) / 4
            + 2 * (self.af_p3 - self.a0_p3) * a_min / 3
            + (self.a0_p2 - self.af_p2) * a_min * a_min / 2
            + j_max
            * (
                self.af_p2 * self.vf
                + self.a0_p2 * self.v0
                + 2 * a_min * (j_max * self.pd - self.a0 * self.v0 - self.af * self.vf)
                + a_min * a_min * (self.v0 + self.vf)
                + j_max * (self.v0_p2 - self.vf_p2)
            )
        )
        h2_acc1 = self.a0_p2 - self.a0 * a_min + 2 * j_max * self.v0

        polynom_acc1 = [
            2 * (2 * self.a0 - a_min) / j_max,
            (5 * self.a0_p2 + a_min * (a_min - 6 * self.a0) + 2 * j_max * self.v0) / self.j_max_p2,
            2 * (self.a0 - a_min) * h2_acc1 / (self.j_max_p2 * j_max),
            h0_acc1 / (self.j_max_p2 * self.j_max_p2),
        ]

        polynom_acc0_min = [
            polynom_acc0[0] + 4 * t_min_acc0,
            polynom_acc0[1] + (3 * polynom_acc0[0] + 6 * t_min_acc0) * t_min_acc0,
            polynom_acc0[2]
            + (2 * polynom_acc0[1] + (3 * polynom_acc0[0] + 4 * t_min_acc0) * t_min_acc0)
            * t_min_acc0,
            polynom_acc0[3]
            + (
                polynom_acc0[2]
                + (polynom_acc0[1] + (polynom_acc0[0] + t_min_acc0) * t_min_acc0) * t_min_acc0
            )
            * t_min_acc0,
        ]

        polynom_acc0_has_solution = (
            polynom_acc0_min[0] < 0
            or polynom_acc0_min[1] < 0
            or polynom_acc0_min[2] < 0
            or polynom_acc0_min[3] <= 0
        )

        polynom_acc1_has_solution = any(c < 0 for c in polynom_acc1) or polynom_acc1[3] <= 0

        # Solve quartic polynomial roots.
        roots_none = sorted(solve_quartic_monic(*polynom_none))
        roots_acc0 = sorted(solve_quartic_monic(*polynom_acc0)) if polynom_acc0_has_solution else []
        roots_acc1 = sorted(solve_quartic_monic(*polynom_acc1)) if polynom_acc1_has_solution else []

        # Process roots for NONE.
        for t_root in roots_none:
            t = t_root
            if not (t_min_none <= t <= t_max_none):
                continue
            if t > _LEAST_NORMAL_MAGNITUDE:
                h1 = j_max * t * t
                orig = (
                    -h2_p2 / (4 * j_max * t)
                    + h2_none * (self.af / j_max + t)
                    + (
                        4 * self.a0_p3
                        + 2 * self.af_p3
                        - 6 * self.a0_p2 * (self.af + 2 * j_max * t)
                        + 12 * (self.af - self.a0) * j_max * self.v0
                        + 3 * self.j_max_p2 * (-4 * self.pd + (h1 + 8 * self.v0) * t)
                    )
                    / (12 * self.j_max_p2)
                )
                deriv = h2_none + 2 * self.v0 - self.a0_p2 / j_max + h2_p2 / (4 * h1) + (3 * h1) / 4
                t -= orig / deriv

            h0 = _ieee754_div(h2_none, 2 * j_max * t)
            profile.t[0] = h0 + t / 2 - self.a0 / j_max
            profile.t[1] = 0.0
            profile.t[2] = t
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = -h0 + t / 2 + self.af / j_max

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return
                # BUG FIX: get a fresh profile reference to prevent
                # corrupting the previously added profile.
                profile = self.valid_profiles[self._profile_count]

        # Process ACC0 roots.
        for t_root in roots_acc0:
            t = t_root
            if not (t_min_acc0 <= t <= t_max_acc0):
                continue
            if t > _LEAST_NORMAL_MAGNITUDE:
                h1 = j_max * t
                orig = h0_acc0 / (12 * self.j_max_p2 * t) + t * (h2_acc0 + h1 * (h1 - 2 * a_max))
                deriv = 2 * (h2_acc0 + h1 * (2 * h1 - 3 * a_max))
                t -= orig / deriv

            profile.t[0] = (-self.a0 + a_max) / j_max
            profile.t[1] = h3_acc0 - 2 * t + j_max / a_max * t * t
            profile.t[2] = t
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = (self.af - a_max) / j_max + t

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return
                # BUG FIX: get a fresh profile reference to prevent
                # corrupting the previously added profile.
                profile = self.valid_profiles[self._profile_count]

        # Process ACC1 roots.
        for t_root in roots_acc1:
            t = t_root
            if not (t_min_acc1 <= t <= t_max_acc1):
                continue
            if t > _LEAST_NORMAL_MAGNITUDE:
                h5 = self.a0_p3 + 2 * j_max * self.a0 * self.v0
                h1 = j_max * t
                orig = (
                    -(
                        h0_acc1 / 2
                        + h1
                        * (
                            h5
                            + self.a0 * (a_min - 2 * h1) * (a_min - h1)
                            + self.a0_p2 * (5 * h1 / 2 - 2 * a_min)
                            + a_min * a_min * h1 / 2
                            + j_max * (h1 / 2 - a_min) * (h1 * t + 2 * self.v0)
                        )
                    )
                    / j_max
                )
                deriv = (a_min - self.a0 - h1) * (h2_acc1 + h1 * (4 * self.a0 - a_min + 2 * h1))
                t -= min(orig / deriv, t)

                h1 = j_max * t
                orig = (
                    -(
                        h0_acc1 / 2
                        + h1
                        * (
                            h5
                            + self.a0 * (a_min - 2 * h1) * (a_min - h1)
                            + self.a0_p2 * (5 * h1 / 2 - 2 * a_min)
                            + a_min * a_min * h1 / 2
                            + j_max * (h1 / 2 - a_min) * (h1 * t + 2 * self.v0)
                        )
                    )
                    / j_max
                )
                if abs(orig) > 1e-9:
                    deriv = (a_min - self.a0 - h1) * (h2_acc1 + h1 * (4 * self.a0 - a_min + 2 * h1))
                    t -= orig / deriv

                    h1 = j_max * t
                    orig = (
                        -(
                            h0_acc1 / 2
                            + h1
                            * (
                                h5
                                + self.a0 * (a_min - 2 * h1) * (a_min - h1)
                                + self.a0_p2 * (5 * h1 / 2 - 2 * a_min)
                                + a_min * a_min * h1 / 2
                                + j_max * (h1 / 2 - a_min) * (h1 * t + 2 * self.v0)
                            )
                        )
                        / j_max
                    )
                    if abs(orig) > 1e-9:
                        deriv = (a_min - self.a0 - h1) * (
                            h2_acc1 + h1 * (4 * self.a0 - a_min + 2 * h1)
                        )
                        t -= orig / deriv

            profile.t[0] = t
            profile.t[1] = 0.0
            profile.t[2] = (self.a0 - a_min) / j_max + t
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = h3_acc1 - (2 * self.a0 + j_max * t) * t / a_min
            profile.t[6] = (self.af - a_min) / j_max

            if profile.check(
                j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC1, True
            ):
                self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
                self._add_profile()
                if return_after_found:
                    return
                # BUG FIX: get a fresh profile reference to prevent
                # corrupting the previously added profile.
                profile = self.valid_profiles[self._profile_count]

    def _time_acc1_vel_two_step(
        self, v_max: float, v_min: float, a_max: float, a_min: float, j_max: float
    ) -> None:
        """Only for numerical issues (Swift ``timeAcc1VelTwoStep``); never
        called from :meth:`get_profile` in the Swift source either -- a
        source-tree grep confirms it, ported anyway per otg.md design
        constraint 2."""
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = self.a0 / j_max
        profile.t[3] = -(
            3 * self.af_p4
            - 8 * a_min * (self.af_p3 - self.a0_p3)
            - 24 * a_min * j_max * (self.a0 * self.v0 - self.af * self.vf)
            + 6 * self.af_p2 * (a_min * a_min - 2 * j_max * self.vf)
            - 12
            * j_max
            * (
                2 * a_min * j_max * self.pd
                + a_min * a_min * (self.vf + v_max)
                + j_max * (v_max * v_max - self.vf_p2)
                + a_min * self.a0 * (self.a0_p2 - 2 * j_max * (self.v0 + v_max)) / j_max
            )
        ) / (24 * a_min * self.j_max_p2 * v_max)
        profile.t[4] = -a_min / j_max
        profile.t[5] = -(self.af_p2 / 2 - a_min * a_min + j_max * (v_max - self.vf)) / (
            a_min * j_max
        )
        profile.t[6] = profile.t[4] + self.af / j_max

        if profile.check(
            j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC1_VEL
        ):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()

    def _time_acc0_two_step(
        self, v_max: float, v_min: float, a_max: float, a_min: float, j_max: float
    ) -> None:
        """Never called from :meth:`get_profile` in the Swift source
        either -- ported anyway per otg.md design constraint 2."""
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        # Two-step profile
        profile.t[0] = 0.0
        profile.t[1] = (self.af_p2 - self.a0_p2 + 2 * j_max * (self.vf - self.v0)) / (
            2 * self.a0 * j_max
        )
        profile.t[2] = (self.a0 - self.af) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

        # Three-step profile - removed pf
        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = (
            self.a0_p2 + self.af_p2 - 2 * a_max * a_max + 2 * j_max * (self.vf - self.v0)
        ) / (2 * a_max * j_max)
        profile.t[2] = (-self.af + a_max) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

        # Three-step profile - removed aMax
        h0 = 3 * (self.af_p2 - self.a0_p2 + 2 * j_max * (self.v0 + self.vf))
        h2 = (
            self.a0_p3
            + 2 * self.af_p3
            + 6 * self.j_max_p2 * self.pd
            + 6 * (self.af - self.a0) * j_max * self.vf
            - 3 * self.a0 * self.af_p2
        )

        discriminant_numerator = 2 * (
            2 * h2 * h2
            + h0
            * (
                self.a0_p4
                - 6 * self.a0_p2 * (self.af_p2 + 2 * j_max * self.vf)
                + 8
                * self.a0
                * (self.af_p3 + 3 * self.j_max_p2 * self.pd + 3 * self.af * j_max * self.vf)
                - 3
                * (
                    self.af_p4
                    + 4 * self.af_p2 * j_max * self.vf
                    + 4 * self.j_max_p2 * (self.vf_p2 - self.v0_p2)
                )
            )
        )

        h1 = _ieee754_sqrt(discriminant_numerator) * abs(j_max) / j_max

        profile.t[0] = (
            4 * self.af_p3
            + 2 * self.a0_p3
            - 6 * self.a0 * self.af_p2
            + 12 * self.j_max_p2 * self.pd
            + 12 * (self.af - self.a0) * j_max * self.vf
            + h1
        ) / (2 * j_max * h0)

        profile.t[1] = -h1 / (j_max * h0)

        profile.t[2] = (
            -4 * self.a0_p3
            - 2 * self.af_p3
            + 6 * self.a0_p2 * self.af
            + 12 * self.j_max_p2 * self.pd
            - 12 * (self.af - self.a0) * j_max * self.v0
            + h1
        ) / (2 * j_max * h0)

        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

        # Three-step profile - t = (aMax - aMin) / jMax
        t = (a_max - a_min) / j_max

        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = (
            (self.a0_p2 - self.af_p2) / (2 * a_max * j_max)
            + (self.vf - self.v0 + j_max * t * t) / a_max
            - 2 * t
        )
        profile.t[2] = t
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = (self.af - a_min) / j_max

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

    def _time_vel_two_step(
        self, v_max: float, v_min: float, a_max: float, a_min: float, j_max: float
    ) -> None:
        """Never called from :meth:`get_profile` in the Swift source
        either -- ported anyway per otg.md design constraint 2."""
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        h1 = _ieee754_sqrt(self.af_p2 / (2 * self.j_max_p2) + (v_max - self.vf) / j_max)

        # Four-step profile: Solution 3/4
        profile.t[0] = -self.a0 / j_max
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = (
            (self.af_p3 - self.a0_p3) / (3 * self.j_max_p2 * v_max)
            + (self.a0 * self.v0 - self.af * self.vf + (self.af_p2 * h1) / 2) / (j_max * v_max)
            - (self.vf / v_max + 1.0) * h1
            + self.pd / v_max
        )
        profile.t[4] = h1
        profile.t[5] = 0.0
        profile.t[6] = h1 + self.af / j_max

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.VEL):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

        # Four-step profile: Alternative
        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = self.a0 / j_max
        profile.t[3] = (
            (self.af_p3 - self.a0_p3) / (3 * self.j_max_p2 * v_max)
            + (self.a0 * self.v0 - self.af * self.vf + (self.af_p2 * h1 + self.a0_p3 / j_max) / 2)
            / (j_max * v_max)
            - (self.v0 / v_max + 1.0) * self.a0 / j_max
            - (self.vf / v_max + 1.0) * h1
            + self.pd / v_max
        )
        profile.t[4] = h1
        profile.t[5] = 0.0
        profile.t[6] = h1 + self.af / j_max

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.VEL):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

    def _time_none_two_step(
        self, v_max: float, v_min: float, a_max: float, a_min: float, j_max: float
    ) -> None:
        """Never called from :meth:`get_profile` in the Swift source
        either -- ported anyway per otg.md design constraint 2."""
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        # Two step
        h0 = (
            _ieee754_sqrt((self.a0_p2 + self.af_p2) / 2 + j_max * (self.vf - self.v0))
            * abs(j_max)
            / j_max
        )
        profile.t[0] = (h0 - self.a0) / j_max
        profile.t[1] = 0.0
        profile.t[2] = (h0 - self.af) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

        # Single step
        profile.t[0] = (self.af - self.a0) / j_max
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check(j_max, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            return

    def _time_all_single_step(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> bool:
        """Only for the zero-limits case."""
        del j_max  # unused in the Swift source too -- profile.check is
        # always called with a hardcoded 0.0 jerk, never this parameter.
        if abs(self.af - self.a0) > _LEAST_NORMAL_MAGNITUDE:
            return False

        profile.t = [0.0] * 7

        if abs(self.a0) > _LEAST_NORMAL_MAGNITUDE:
            q = _ieee754_sqrt(2 * self.a0 * self.pd + self.v0_p2)

            # Solution 1
            profile.t[3] = (-self.v0 + q) / self.a0
            if profile.t[3] >= 0.0 and profile.check(
                0.0, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

            # Solution 2
            profile.t[3] = -(self.v0 + q) / self.a0
            if profile.t[3] >= 0.0 and profile.check(
                0.0, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        elif abs(self.v0) > _ULP:
            profile.t[3] = self.pd / self.v0
            if profile.check(
                0.0, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        elif abs(self.pd) < _ULP:
            if profile.check(
                0.0, v_max, v_min, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        return False

    def get_profile(self, input_profile: Profile, block: Block) -> bool:
        # Zero-limits special case.
        if self._j_max == 0.0 or self._a_max == 0.0 or self._a_min == 0.0:
            p = copy.deepcopy(block.p_min)
            p.set_boundary(input_profile)

            if self._time_all_single_step(
                p, self._v_max, self._v_min, self._a_max, self._a_min, self._j_max
            ):
                block.p_min = p
                block.t_min = p.t_sum[-1] + p.brake.duration + p.accel.duration
                if abs(self.v0) > _LEAST_NORMAL_MAGNITUDE or abs(self.a0) > _LEAST_NORMAL_MAGNITUDE:
                    block.a = Interval(block.t_min, math.inf)
                return True
            return False

        self._reset_profiles()
        self.valid_profiles[self._profile_count].set_boundary(input_profile)

        if abs(self.vf) < _ULP and abs(self.af) < _ULP:
            v_max = self._v_max if self.pd >= 0 else self._v_min
            v_min = self._v_min if self.pd >= 0 else self._v_max
            a_max = self._a_max if self.pd >= 0 else self._a_min
            a_min = self._a_min if self.pd >= 0 else self._a_max
            j_max = self._j_max if self.pd >= 0 else -self._j_max

            # Special case: when v0, a0, and pd are all essentially zero.
            if abs(self.v0) < _ULP and abs(self.a0) < _ULP and abs(self.pd) < _ULP:
                # For the trivial case where we're already at the target,
                # try time_all_single_step first.
                p = copy.deepcopy(self.valid_profiles[self._profile_count])
                if self._time_all_single_step(p, v_max, v_min, a_max, a_min, j_max):
                    self._profile_count += 1
                else:
                    self._time_all_none_acc0_acc1(v_max, v_min, a_max, a_min, j_max, True)
            else:
                # There is no blocked interval when vf==0 && af==0, so
                # return after the first found profile.
                self._time_all_vel(v_max, v_min, a_max, a_min, j_max, True)
                if self._has_profiles():
                    success, _ = Block.calculate_block(
                        block, self.valid_profiles, self._profile_count
                    )
                    return success

                self._time_all_none_acc0_acc1(v_max, v_min, a_max, a_min, j_max, True)

            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success

            # Try profiles one by one and exit early if found.
            directions = [
                (v_max, v_min, a_max, a_min, j_max),
                (v_max, v_min, a_max, a_min, j_max),
                (v_max, v_min, a_max, a_min, j_max),
                (v_min, v_max, a_min, a_max, -j_max),
                (v_min, v_max, a_min, a_max, -j_max),
                (v_min, v_max, a_min, a_max, -j_max),
            ]

            for d_v_max, d_v_min, d_a_max, d_a_min, d_j_max in directions:
                self._time_all_vel(d_v_max, d_v_min, d_a_max, d_a_min, d_j_max, True)
                if self._has_profiles():
                    success, _ = Block.calculate_block(
                        block, self.valid_profiles, self._profile_count
                    )
                    return success

                self._time_all_none_acc0_acc1(d_v_max, d_v_min, d_a_max, d_a_min, d_j_max, True)
                if self._has_profiles():
                    success, _ = Block.calculate_block(
                        block, self.valid_profiles, self._profile_count
                    )
                    return success

                self._time_acc0_acc1(d_v_max, d_v_min, d_a_max, d_a_min, d_j_max, True)
                if self._has_profiles():
                    success, _ = Block.calculate_block(
                        block, self.valid_profiles, self._profile_count
                    )
                    return success

        else:
            # General search for profiles. Prioritize profiles with proper
            # limit handling to avoid acceleration violations.
            self._time_all_vel(
                self._v_max, self._v_min, self._a_max, self._a_min, self._j_max, False
            )
            self._time_all_vel(
                self._v_min, self._v_max, self._a_min, self._a_max, -self._j_max, False
            )
            self._time_acc0_acc1(
                self._v_max, self._v_min, self._a_max, self._a_min, self._j_max, False
            )
            self._time_acc0_acc1(
                self._v_min, self._v_max, self._a_min, self._a_max, -self._j_max, False
            )
            self._time_all_none_acc0_acc1(
                self._v_max, self._v_min, self._a_max, self._a_min, self._j_max, False
            )
            self._time_all_none_acc0_acc1(
                self._v_min, self._v_max, self._a_min, self._a_max, -self._j_max, False
            )

        success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
        return success
