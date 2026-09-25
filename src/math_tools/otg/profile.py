"""Per-DOF kinematic profile: the hot data structure OTG step solvers fill.

Faithful port of ``SWIFT_MATH/OTG/Profile.swift`` (~715 lines; method and
branch structure preserved mechanically). See ``.claude/specs/otg.md``
§Internal fidelity requirements 1, 4, 5 and
``.claude/action-plan/33-otg-profile.md``.

All kinematic stepping goes through
:func:`math_tools.functional.roots.integrate_jerk` -- never a fresh
constant-jerk integration (otg.md §Internal fidelity requirement 1). Every
Swift ``for i in 0..<7`` loop that advances ``p``/``v``/``a`` (with or
without a nonzero jerk term) is the same closed-form step, so it is ported
as a call to ``integrate_jerk(t[i], p[i], v[i], a[i], j[i])`` throughout,
including the "second-order" and "first-order" interfaces where the Swift
source inlines the ``j == 0`` special case by hand.

``brake``/``accel`` are the real ``math_tools.otg.brake.BrakeProfile``
(chunk 34, ``otg/brake.py``): chunk 33 originally stood these in with a
module-private ``_DeferredBrakeProfile`` dataclass because ``brake.py``
didn't exist yet; chunk 34 landed it and this module now imports the real
type directly (see ``33-otg-profile.md``'s Resolution notes for the
original deferral and ``34-otg-block-brake-bound.md``'s Resolution notes
for the reconciliation).

``check_position_extremum``/``check_step_for_position_extremum``'s ``ext``
parameter stays typed against the module-private structural
:class:`~typing.Protocol` :class:`_PositionExtremumSink` (``min``, ``max``,
``t_min``, ``t_max`` floats) rather than importing
``math_tools.otg.bound.Bound`` directly -- chunk 34's real ``Bound`` has
those exact field names (its own design constraint), so it satisfies this
Protocol structurally without an import edge from this module to
``bound.py``. ``33-otg-profile.md``'s Resolution notes explicitly permit
the Protocol to "stay indefinitely"; kept as-is per
``34-otg-block-brake-bound.md``'s Resolution notes for the same reason.
"""

from __future__ import annotations

import math
import sys
from typing import Protocol, overload

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.brake import BrakeProfile
from math_tools.otg.enums import ControlSigns, Direction, ReachedLimits

__all__ = ["Profile"]

# Profile.swift's own private module constants (transcribed verbatim). These
# are NOT functional.roots.EPS16/POLYNOMIAL_* -- Profile.swift defines its
# own distinct tolerances, separate from the polynomial-root kernel's.
_V_EPS = 1e-12
_A_EPS = 1e-12
_J_EPS = 1e-12
_P_PRECISION = 1e-8
_V_PRECISION = 1e-8
_A_PRECISION = 1e-10
_T_PRECISION = (
    1e-12  # Declared but unused in the Swift source too; ported for fidelity.
)
_T_MAX = 1e12

#: Swift ``Double.ulpOfOne`` (machine epsilon for float64) -- used (not
#: ``EPS16``) everywhere Profile.swift compares against "effectively zero".
_ULP = sys.float_info.epsilon

# Reached-limits sets used by ``check`` (otg.md's ReachedLimits.NONE is the
# common case where none of these apply; kept as module-level tuples so the
# branch conditions below read like the Swift ``||`` chains they replace).
_ZERO_TIME_VEL_LIMITS = (
    ReachedLimits.ACC0_ACC1_VEL,
    ReachedLimits.ACC0_VEL,
    ReachedLimits.ACC1_VEL,
    ReachedLimits.VEL,
)
_ZERO_TIME_ACC0_LIMITS = (ReachedLimits.ACC0, ReachedLimits.ACC0_ACC1)
_ZERO_TIME_ACC1_LIMITS = (ReachedLimits.ACC1, ReachedLimits.ACC0_ACC1)
_ZERO_ACC_AT_VEL_LIMITS = (
    ReachedLimits.ACC0_ACC1_VEL,
    ReachedLimits.ACC0_ACC1,
    ReachedLimits.ACC0_VEL,
    ReachedLimits.ACC1_VEL,
    ReachedLimits.VEL,
)


class _PositionExtremumSink(Protocol):
    """Structural stand-in for ``math_tools.otg.bound.Bound`` (chunk 34),
    kept intentionally rather than importing ``Bound`` directly (see this
    module's docstring).

    :meth:`Profile.check_position_extremum` and
    :meth:`Profile.check_step_for_position_extremum` only mutate these four
    float attributes, so any object shaped like this -- including the real
    ``Bound``, whose fields are named identically per
    ``34-otg-block-brake-bound.md``'s design constraints -- satisfies it
    structurally without this module importing ``bound.py``.
    """

    min: float
    max: float
    t_min: float
    t_max: float


class Profile:
    """A single-DOF kinematic profile: position, velocity, acceleration, jerk.

    Fixed-length arrays, never resized (otg.md §Internal fidelity
    requirement 1): ``t``/``t_sum``/``j`` (7 elements), ``a``/``v``/``p`` (8
    elements, one boundary value per phase transition plus the initial
    state).
    """

    def __init__(self) -> None:
        self.t: list[float] = [0.0] * 7
        self.t_sum: list[float] = [0.0] * 7
        self.j: list[float] = [0.0] * 7
        self.a: list[float] = [0.0] * 8
        self.v: list[float] = [0.0] * 8
        self.p: list[float] = [0.0] * 8

        # Brake sub-profiles (math_tools.otg.brake.BrakeProfile, chunk 34).
        self.brake: BrakeProfile = BrakeProfile()
        self.accel: BrakeProfile = BrakeProfile()

        # Target (final) kinematic state.
        self.pf: float = 0.0
        self.vf: float = 0.0
        self.af: float = 0.0

        self.limits: ReachedLimits = ReachedLimits.NONE
        self.direction: Direction = Direction.DOWN
        self.control_signs: ControlSigns = ControlSigns.UDDU

    # MARK: - Equality

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Profile):
            return NotImplemented
        return (
            self.t == other.t
            and self.t_sum == other.t_sum
            and self.j == other.j
            and self.a == other.a
            and self.v == other.v
            and self.p == other.p
            and self.brake == other.brake
            and self.accel == other.accel
            and self.pf == other.pf
            and self.vf == other.vf
            and self.af == other.af
            and self.limits == other.limits
            and self.direction == other.direction
            and self.control_signs == other.control_signs
        )

    # MARK: - Third-order velocity interface

    def check_for_velocity(
        self,
        jf: float,
        a_max: float,
        a_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
    ) -> bool:
        if self.t[0] < 0:
            return False

        self.t_sum[0] = self.t[0]
        for i in range(6):
            if self.t[i + 1] < 0:
                return False
            self.t_sum[i + 1] = self.t_sum[i] + self.t[i + 1]

        if limits == ReachedLimits.ACC0 and self.t[1] < _ULP:
            return False

        if self.t_sum[-1] > _T_MAX:
            return False

        if control_signs == ControlSigns.UDDU:
            self.j = [
                jf if self.t[0] > 0 else 0.0,
                0.0,
                -jf if self.t[2] > 0 else 0.0,
                0.0,
                -jf if self.t[4] > 0 else 0.0,
                0.0,
                jf if self.t[6] > 0 else 0.0,
            ]
        else:
            self.j = [
                jf if self.t[0] > 0 else 0.0,
                0.0,
                -jf if self.t[2] > 0 else 0.0,
                0.0,
                jf if self.t[4] > 0 else 0.0,
                0.0,
                -jf if self.t[6] > 0 else 0.0,
            ]

        for i in range(7):
            self.p[i + 1], self.v[i + 1], self.a[i + 1] = integrate_jerk(
                self.t[i], self.p[i], self.v[i], self.a[i], self.j[i]
            )

        self.control_signs = control_signs
        self.limits = limits

        self.direction = Direction.UP if a_max > 0 else Direction.DOWN
        a_upp_lim = (a_max if self.direction == Direction.UP else a_min) + _A_EPS
        a_low_lim = (a_min if self.direction == Direction.UP else a_max) - _A_EPS

        return (
            abs(self.v[-1] - self.vf) < _V_PRECISION
            and abs(self.a[-1] - self.af) < _A_PRECISION
            and self.a[1] >= a_low_lim
            and self.a[3] >= a_low_lim
            and self.a[5] >= a_low_lim
            and self.a[1] <= a_upp_lim
            and self.a[3] <= a_upp_lim
            and self.a[5] <= a_upp_lim
        )

    def check_for_velocity_with_timing(
        self,
        tf: float,
        jf: float,
        a_max: float,
        a_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        *,
        j_max: float | None = None,
    ) -> bool:
        """``checkForVelocityWithTiming`` (both Swift overloads collapsed).

        ``tf`` is accepted (matching the Swift signature) but unused in
        every branch, exactly as in the Swift source. ``j_max`` collapses
        the two-overload/three-overload split: omit it for the plain
        ``checkForVelocityWithTiming(tf, jf, aMax, aMin, controlSigns,
        limits)`` overload; pass it for the ``jMax``-guarded overload.
        """
        del tf
        if j_max is not None and not (abs(jf) < abs(j_max) + _J_EPS):
            return False
        return self.check_for_velocity(jf, a_max, a_min, control_signs, limits)

    def set_boundary_for_velocity(
        self,
        p0_new: float,
        v0_new: float,
        a0_new: float,
        vf_new: float,
        af_new: float,
    ) -> None:
        self.a[0] = a0_new
        self.v[0] = v0_new
        self.p[0] = p0_new
        self.af = af_new
        self.vf = vf_new

    # MARK: - Second-order velocity interface

    def check_for_second_order_velocity(
        self,
        a_up: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
    ) -> bool:
        if self.t[1] < 0.0:
            return False

        self.t_sum = [
            0.0,
            self.t[1],
            self.t[1],
            self.t[1],
            self.t[1],
            self.t[1],
            self.t[1],
        ]
        if self.t_sum[-1] > _T_MAX:
            return False

        self.j = [0.0] * 7
        self.a = [0.0, a_up if self.t[1] > 0 else 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, self.af]
        for i in range(7):
            self.p[i + 1], self.v[i + 1], _ = integrate_jerk(
                self.t[i], self.p[i], self.v[i], self.a[i], 0.0
            )

        self.control_signs = control_signs
        self.limits = limits

        self.direction = Direction.UP if a_up > 0 else Direction.DOWN

        return abs(self.v[-1] - self.vf) < _V_PRECISION

    def check_for_second_order_velocity_with_timing(
        self,
        tf: float,
        a_up: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        *,
        a_max: float | None = None,
        a_min: float | None = None,
    ) -> bool:
        """``checkForSecondOrderVelocityWithTiming`` (both overloads collapsed).

        Pass ``a_max``/``a_min`` together for the bound-checked overload;
        omit both for the plain delegating overload.
        """
        del tf
        if a_max is not None and a_min is not None:
            if not (a_min - _A_EPS < a_up < a_max + _A_EPS):
                return False
        return self.check_for_second_order_velocity(a_up, control_signs, limits)

    # MARK: - Third-order position interface

    def check(
        self,
        jf: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        set_limits: bool = False,
    ) -> bool:
        if self.t[0] < 0:
            return False

        self.t_sum[0] = self.t[0]
        for i in range(6):
            if self.t[i + 1] < 0:
                return False
            self.t_sum[i + 1] = self.t_sum[i] + self.t[i + 1]

        if limits in _ZERO_TIME_VEL_LIMITS and self.t[3] < _ULP:
            return False

        if limits in _ZERO_TIME_ACC0_LIMITS and self.t[1] < _ULP:
            return False

        if limits in _ZERO_TIME_ACC1_LIMITS and self.t[5] < _ULP:
            return False

        if self.t_sum[-1] > _T_MAX:
            return False

        if control_signs == ControlSigns.UDDU:
            self.j = [
                jf if self.t[0] > 0 else 0.0,
                0.0,
                -jf if self.t[2] > 0 else 0.0,
                0.0,
                -jf if self.t[4] > 0 else 0.0,
                0.0,
                jf if self.t[6] > 0 else 0.0,
            ]
        else:
            self.j = [
                jf if self.t[0] > 0 else 0.0,
                0.0,
                -jf if self.t[2] > 0 else 0.0,
                0.0,
                jf if self.t[4] > 0 else 0.0,
                0.0,
                -jf if self.t[6] > 0 else 0.0,
            ]

        self.direction = Direction.UP if v_max > 0 else Direction.DOWN
        v_upp_lim = (v_max if self.direction == Direction.UP else v_min) + _V_EPS
        v_low_lim = (v_min if self.direction == Direction.UP else v_max) - _V_EPS

        for i in range(7):
            self.p[i + 1], self.v[i + 1], self.a[i + 1] = integrate_jerk(
                self.t[i], self.p[i], self.v[i], self.a[i], self.j[i]
            )

            if limits in _ZERO_ACC_AT_VEL_LIMITS and i == 2:
                self.a[3] = 0.0
                if self.t[2] > _ULP:
                    self.j[2] = (self.a[3] - self.a[2]) / self.t[2]

            if set_limits:
                if limits == ReachedLimits.ACC1 and i == 2:
                    self.a[3] = a_min
                    if self.t[2] > _ULP:
                        self.j[2] = (self.a[3] - self.a[2]) / self.t[2]

                if limits == ReachedLimits.ACC0_ACC1:
                    if i == 0:
                        self.a[1] = a_max
                        if self.t[0] > _ULP:
                            self.j[0] = (self.a[1] - self.a[0]) / self.t[0]
                    if i == 4:
                        self.a[5] = a_min
                        if self.t[4] > _ULP:
                            self.j[4] = (self.a[5] - self.a[4]) / self.t[4]

            if i > 1 and self.a[i + 1] * self.a[i] < -_ULP:
                v_a_zero = self.v[i] - (self.a[i] * self.a[i]) / (2 * self.j[i])
                if v_a_zero > v_upp_lim or v_a_zero < v_low_lim:
                    return False

        self.control_signs = control_signs
        self.limits = limits

        a_upp_lim = (a_max if self.direction == Direction.UP else a_min) + _A_EPS
        a_low_lim = (a_min if self.direction == Direction.UP else a_max) - _A_EPS

        p_check = abs(self.p[-1] - self.pf) < _P_PRECISION
        v_check = abs(self.v[-1] - self.vf) < _V_PRECISION
        a_check = abs(self.a[-1] - self.af) < _A_PRECISION

        a_lim_check = (
            self.a[1] >= a_low_lim
            and self.a[3] >= a_low_lim
            and self.a[5] >= a_low_lim
            and self.a[1] <= a_upp_lim
            and self.a[3] <= a_upp_lim
            and self.a[5] <= a_upp_lim
        )

        v_lim_check = (
            self.v[3] <= v_upp_lim
            and self.v[4] <= v_upp_lim
            and self.v[5] <= v_upp_lim
            and self.v[6] <= v_upp_lim
            and self.v[3] >= v_low_lim
            and self.v[4] >= v_low_lim
            and self.v[5] >= v_low_lim
            and self.v[6] >= v_low_lim
        )

        return p_check and v_check and a_check and a_lim_check and v_lim_check

    def check_with_timing(
        self,
        tf: float,
        jf: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        *,
        j_max: float | None = None,
    ) -> bool:
        """``checkWithTiming`` (both Swift overloads collapsed).

        Omit ``j_max`` for the plain delegating overload; pass it for the
        ``jMax``-guarded overload.
        """
        del tf
        if j_max is not None and not (abs(jf) < abs(j_max) + _J_EPS):
            return False
        return self.check(jf, v_max, v_min, a_max, a_min, control_signs, limits)

    @overload
    def set_boundary(self, profile: Profile, /) -> None: ...

    @overload
    def set_boundary(
        self,
        p0_new: float,
        v0_new: float,
        a0_new: float,
        pf_new: float,
        vf_new: float,
        af_new: float,
        /,
    ) -> None: ...

    def set_boundary(
        self,
        p0_new: Profile | float,
        v0_new: float | None = None,
        a0_new: float | None = None,
        pf_new: float | None = None,
        vf_new: float | None = None,
        af_new: float | None = None,
    ) -> None:
        """``setBoundary`` (both Swift overloads: copy-from-profile or set-directly)."""
        if isinstance(p0_new, Profile):
            other = p0_new
            self.a[0] = other.a[0]
            self.v[0] = other.v[0]
            self.p[0] = other.p[0]
            self.af = other.af
            self.vf = other.vf
            self.pf = other.pf
            self.brake = other.brake
            self.accel = other.accel
            return

        assert v0_new is not None
        assert a0_new is not None
        assert pf_new is not None
        assert vf_new is not None
        assert af_new is not None

        self.a[0] = a0_new
        self.v[0] = v0_new
        self.p[0] = p0_new
        self.af = af_new
        self.vf = vf_new
        self.pf = pf_new

    # MARK: - Second-order position interface

    def check_for_second_order(
        self,
        a_up: float,
        a_down: float,
        v_max: float,
        v_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
    ) -> bool:
        if self.t[0] < 0:
            return False

        self.t_sum[0] = self.t[0]
        for i in range(6):
            if self.t[i + 1] < 0:
                return False
            self.t_sum[i + 1] = self.t_sum[i] + self.t[i + 1]

        if self.t_sum[-1] > _T_MAX:
            return False

        self.j = [0.0] * 7
        if control_signs == ControlSigns.UDDU:
            self.a = [
                a_up if self.t[0] > 0 else 0.0,
                0.0,
                a_down if self.t[2] > 0 else 0.0,
                0.0,
                a_down if self.t[4] > 0 else 0.0,
                0.0,
                a_up if self.t[6] > 0 else 0.0,
                self.af,
            ]
        else:
            self.a = [
                a_up if self.t[0] > 0 else 0.0,
                0.0,
                a_down if self.t[2] > 0 else 0.0,
                0.0,
                a_up if self.t[4] > 0 else 0.0,
                0.0,
                a_down if self.t[6] > 0 else 0.0,
                self.af,
            ]

        self.direction = Direction.UP if v_max > 0 else Direction.DOWN
        v_upp_lim = (v_max if self.direction == Direction.UP else v_min) + _V_EPS
        v_low_lim = (v_min if self.direction == Direction.UP else v_max) - _V_EPS

        for i in range(7):
            self.p[i + 1], self.v[i + 1], _ = integrate_jerk(
                self.t[i], self.p[i], self.v[i], self.a[i], 0.0
            )

        self.control_signs = control_signs
        self.limits = limits

        return (
            abs(self.p[-1] - self.pf) < _P_PRECISION
            and abs(self.v[-1] - self.vf) < _V_PRECISION
            and self.v[2] <= v_upp_lim
            and self.v[3] <= v_upp_lim
            and self.v[4] <= v_upp_lim
            and self.v[5] <= v_upp_lim
            and self.v[6] <= v_upp_lim
            and self.v[2] >= v_low_lim
            and self.v[3] >= v_low_lim
            and self.v[4] >= v_low_lim
            and self.v[5] >= v_low_lim
            and self.v[6] >= v_low_lim
        )

    def check_for_second_order_with_timing(
        self,
        tf: float,
        a_up: float,
        a_down: float,
        v_max: float,
        v_min: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        *,
        a_max: float | None = None,
        a_min: float | None = None,
    ) -> bool:
        """``checkForSecondOrderWithTiming`` (both overloads collapsed).

        Pass ``a_max``/``a_min`` together for the bound-checked overload;
        omit both for the plain delegating overload.
        """
        del tf
        if a_max is not None and a_min is not None:
            if not (a_min - _A_EPS < a_up < a_max + _A_EPS):
                return False
            if not (a_min - _A_EPS < a_down < a_max + _A_EPS):
                return False
        return self.check_for_second_order(
            a_up, a_down, v_max, v_min, control_signs, limits
        )

    # MARK: - First-order position interface

    def check_for_first_order(
        self,
        v_up: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
    ) -> bool:
        if self.t[3] < 0.0:
            return False

        self.t_sum = [0.0, 0.0, 0.0, self.t[3], self.t[3], self.t[3], self.t[3]]
        if self.t_sum[-1] > _T_MAX:
            return False

        self.j = [0.0] * 7
        self.a = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, self.af]
        self.v = [0.0, 0.0, 0.0, v_up if self.t[3] > 0 else 0.0, 0.0, 0.0, 0.0, self.vf]

        for i in range(7):
            self.p[i + 1], _, _ = integrate_jerk(
                self.t[i], self.p[i], self.v[i], self.a[i], 0.0
            )

        self.control_signs = control_signs
        self.limits = limits

        self.direction = Direction.UP if v_up > 0 else Direction.DOWN

        return abs(self.p[-1] - self.pf) < _P_PRECISION

    def check_for_first_order_with_timing(
        self,
        tf: float,
        v_up: float,
        control_signs: ControlSigns,
        limits: ReachedLimits,
        *,
        v_max: float | None = None,
        v_min: float | None = None,
    ) -> bool:
        """``checkForFirstOrderWithTiming`` (both overloads collapsed).

        Pass ``v_max``/``v_min`` together for the bound-checked overload;
        omit both for the plain delegating overload.
        """
        del tf
        if v_max is not None and v_min is not None:
            if not (v_min - _V_EPS < v_up < v_max + _V_EPS):
                return False
        return self.check_for_first_order(v_up, control_signs, limits)

    # MARK: - Secondary features

    @staticmethod
    def check_position_extremum(
        t_ext: float,
        t_sum: float,
        t: float,
        p: float,
        v: float,
        a: float,
        j: float,
        ext: _PositionExtremumSink,
    ) -> None:
        if 0 < t_ext < t:
            p_ext, _, a_ext = integrate_jerk(t_ext, p, v, a, j)
            if a_ext > 0 and p_ext < ext.min:
                ext.min = p_ext
                ext.t_min = t_sum + t_ext
            elif a_ext < 0 and p_ext > ext.max:
                ext.max = p_ext
                ext.t_max = t_sum + t_ext

    @staticmethod
    def check_step_for_position_extremum(
        t_sum: float,
        t: float,
        p: float,
        v: float,
        a: float,
        j: float,
        ext: _PositionExtremumSink,
    ) -> None:
        if p < ext.min:
            ext.min = p
            ext.t_min = t_sum
        if p > ext.max:
            ext.max = p
            ext.t_max = t_sum

        if j != 0:
            d = a * a - 2 * j * v
            if abs(d) < _ULP:
                Profile.check_position_extremum(-a / j, t_sum, t, p, v, a, j, ext)
            elif d > 0.0:
                d_sqrt = math.sqrt(d)
                Profile.check_position_extremum(
                    (-a - d_sqrt) / j, t_sum, t, p, v, a, j, ext
                )
                Profile.check_position_extremum(
                    (-a + d_sqrt) / j, t_sum, t, p, v, a, j, ext
                )
