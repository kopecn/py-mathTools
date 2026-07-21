"""Pre-trajectory braking profile: brings an out-of-limits kinematic state
within bounds before the main synchronized trajectory begins.

Faithful port of ``SWIFT_MATH/OTG/Brake.swift`` (method and branch structure
preserved mechanically). See ``.claude/specs/otg.md`` §Internal fidelity
requirements 1, 4, 5 and ``.claude/action-plan/34-otg-block-brake-bound.md``
design constraint 2.

All kinematic stepping goes through
:func:`math_tools.functional.roots.integrate_jerk` (Swift's free function
``integrate``) -- never a fresh constant-jerk integration, matching
``profile.py``'s identical convention (otg.md §Internal fidelity
requirement 1).

Swift's ``inout`` position/velocity/acceleration parameters on ``finalize``
and ``finalizeSecondOrder`` become returned ``(p, v, a)`` tuples here --
Python has no by-reference scalar parameters.
"""

from __future__ import annotations

import math

from math_tools.functional.roots import integrate_jerk

__all__ = ["BrakeProfile"]

#: Brake.swift's own private module constant (transcribed verbatim) -- NOT
#: functional.roots.EPS16/POLYNOMIAL_* (a distinct, unrelated tolerance),
#: matching profile.py's identical convention for its own private epsilons.
_EPS = 2.2e-14


class BrakeProfile:
    """Models a pre-trajectory braking motion to bring a system within
    acceptable kinematic limits (position, velocity, acceleration) before
    the main synchronized trajectory begins.

    Computed via either a second-order (acceleration-limited) or
    third-order (jerk-limited) profile, depending on which limits are
    violated.
    """

    def __init__(self) -> None:
        self.duration: float = 0.0
        self.t: list[float] = [0.0, 0.0]
        self.j: list[float] = [0.0, 0.0]
        self.a: list[float] = [0.0, 0.0]
        self.v: list[float] = [0.0, 0.0]
        self.p: list[float] = [0.0, 0.0]

    # MARK: - Equality

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BrakeProfile):
            return NotImplemented
        return (
            self.duration == other.duration
            and self.t == other.t
            and self.j == other.j
            and self.a == other.a
            and self.v == other.v
            and self.p == other.p
        )

    # MARK: - Finalization

    def finalize(self, p_s: float, v_s: float, a_s: float) -> tuple[float, float, float]:
        """``finalize`` (third-order braking). Returns the updated
        ``(position, velocity, acceleration)`` state."""
        if self.t[0] <= 0.0 and self.t[1] <= 0.0:
            self.duration = 0.0
            return p_s, v_s, a_s

        self.duration = self.t[0]
        self.p[0] = p_s
        self.v[0] = v_s
        self.a[0] = a_s
        p_s, v_s, a_s = integrate_jerk(self.t[0], p_s, v_s, a_s, self.j[0])

        if self.t[1] > 0.0:
            self.duration += self.t[1]
            self.p[1] = p_s
            self.v[1] = v_s
            self.a[1] = a_s
            p_s, v_s, a_s = integrate_jerk(self.t[1], p_s, v_s, a_s, self.j[1])

        return p_s, v_s, a_s

    def finalize_second_order(
        self, p_s: float, v_s: float, a_s: float
    ) -> tuple[float, float, float]:
        """``finalizeSecondOrder``. Returns the updated ``(position,
        velocity, acceleration)`` state."""
        if self.t[0] <= 0.0:
            self.duration = 0.0
            return p_s, v_s, a_s

        self.duration = self.t[0]
        self.p[0] = p_s
        self.v[0] = v_s
        p_s, v_s, a_s = integrate_jerk(self.t[0], p_s, v_s, self.a[0], 0.0)
        return p_s, v_s, a_s

    # MARK: - Velocity helpers

    def v_at_t(self, v0: float, a0: float, j: float, t: float) -> float:
        """``vAtT`` -- velocity at time ``t`` under constant jerk ``j``."""
        return v0 + t * (a0 + j * t / 2)

    def v_at_a_zero(self, v0: float, a0: float, j: float) -> float:
        """``vAtAZero`` -- velocity at the moment acceleration reaches zero."""
        return v0 + (a0 * a0) / (2 * j)

    # MARK: - Brake construction

    def acceleration_brake(
        self,
        v0: float,
        a0: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        """``accelerationBrake`` -- brings acceleration into bounds first,
        falling back to :meth:`velocity_brake` when velocity would still be
        out of bounds once acceleration is corrected."""
        self.j[0] = -j_max

        t_to_a_max = (a0 - a_max) / j_max
        t_to_a_zero = a0 / j_max

        v_at_a_max = self.v_at_t(v0, a0, -j_max, t_to_a_max)
        v_at_a_zero = self.v_at_t(v0, a0, -j_max, t_to_a_zero)

        if (v_at_a_zero > v_max and j_max > 0) or (v_at_a_zero < v_max and j_max < 0):
            self.velocity_brake(v0, a0, v_max, v_min, a_max, a_min, j_max)
        elif (v_at_a_max < v_min and j_max > 0) or (v_at_a_max > v_min and j_max < 0):
            t_to_v_min = -(v_at_a_max - v_min) / a_max
            t_to_v_max = -a_max / (2 * j_max) - (v_at_a_max - v_max) / a_max

            self.t[0] = t_to_a_max + _EPS
            self.t[1] = max(min(t_to_v_min, t_to_v_max - _EPS), 0.0)
        else:
            self.t[0] = t_to_a_max + _EPS

    def velocity_brake(
        self,
        v0: float,
        a0: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        """``velocityBrake`` -- brings velocity into bounds directly.

        ``a_max`` is accepted (matching the Swift signature) but unused in
        every branch, exactly as upstream.
        """
        self.j[0] = -j_max

        t_to_a_min = (a0 - a_min) / j_max
        t_to_v_max = a0 / j_max + math.sqrt(a0 * a0 + 2 * j_max * (v0 - v_max)) / abs(j_max)
        t_to_v_min = a0 / j_max + math.sqrt(a0 * a0 / 2 + j_max * (v0 - v_min)) / abs(j_max)
        t_min_to_v = min(t_to_v_max, t_to_v_min)

        if t_to_a_min < t_min_to_v:
            v_at_a_min = self.v_at_t(v0, a0, -j_max, t_to_a_min)
            t_to_v_max_with_constant = -(v_at_a_min - v_max) / a_min
            t_to_v_min_with_constant = a_min / (2 * j_max) - (v_at_a_min - v_min) / a_min

            self.t[0] = max(t_to_a_min - _EPS, 0.0)
            self.t[1] = max(min(t_to_v_max_with_constant, t_to_v_min_with_constant), 0.0)
        else:
            self.t[0] = max(t_min_to_v - _EPS, 0.0)

    # MARK: - Trajectory selection

    def get_position_brake_trajectory(
        self,
        v0: float,
        a0: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        """``getPositionBrakeTrajectory`` -- selects acceleration- or
        velocity-based braking (or none) from the third-order position
        interface's initial state and limits."""
        self.t = [0.0, 0.0]
        self.j = [0.0, 0.0]

        if j_max == 0.0 or a_max == 0.0 or a_min == 0.0:
            return

        if a0 > a_max:
            self.acceleration_brake(v0, a0, v_max, v_min, a_max, a_min, j_max)
        elif a0 < a_min:
            self.acceleration_brake(v0, a0, v_min, v_max, a_min, a_max, -j_max)
        elif (v0 > v_max and self.v_at_a_zero(v0, a0, -j_max) > v_min) or (
            a0 > 0 and self.v_at_a_zero(v0, a0, j_max) > v_max
        ):
            self.velocity_brake(v0, a0, v_max, v_min, a_max, a_min, j_max)
        elif (v0 < v_min and self.v_at_a_zero(v0, a0, j_max) < v_max) or (
            a0 < 0 and self.v_at_a_zero(v0, a0, -j_max) < v_min
        ):
            self.velocity_brake(v0, a0, v_min, v_max, a_min, a_max, -j_max)

    def get_second_order_position_brake_trajectory(
        self,
        v0: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> None:
        """``getSecondOrderPositionBrakeTrajectory`` -- acceleration-only
        braking from the second-order position interface."""
        self.t = [0.0, 0.0]
        self.j = [0.0, 0.0]
        self.a = [0.0, 0.0]

        if a_max == 0.0 or a_min == 0.0:
            return

        if v0 > v_max:
            self.a[0] = a_min
            self.t[0] = (v_max - v0) / a_min + _EPS
        elif v0 < v_min:
            self.a[0] = a_max
            self.t[0] = (v_min - v0) / a_max + _EPS

    def get_velocity_brake_trajectory(
        self,
        a0: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        """``getVelocityBrakeTrajectory`` -- jerk-limited braking that
        brings acceleration into bounds, for the second-order velocity
        interface."""
        self.t = [0.0, 0.0]
        self.j = [0.0, 0.0]

        if j_max == 0.0:
            return

        if a0 > a_max:
            self.j[0] = -j_max
            self.t[0] = (a0 - a_max) / j_max + _EPS
        elif a0 < a_min:
            self.j[0] = j_max
            self.t[0] = -(a0 - a_min) / j_max + _EPS

    def get_second_order_velocity_brake_trajectory(self) -> None:
        """``getSecondOrderVelocityBrakeTrajectory`` -- no-op reset, ported
        verbatim (the Swift source documents this as a placeholder)."""
        self.t = [0.0, 0.0]
        self.j = [0.0, 0.0]
