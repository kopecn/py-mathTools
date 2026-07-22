"""``TargetCalculator``: per-DOF Step1/Step2 dispatch plus cross-DOF
synchronization (Block/Interval logic, the discrete-duration path, phase
sync).

Faithful port of ``SWIFT_MATH/OTG/CalculatorTarget.swift`` (~780 lines). See
``.claude/specs/otg.md`` §Internal fidelity requirement 3 and
``.claude/action-plan/40-otg-calculator-target.md``.

**Alias-mutation hazard (otg.md's cross-chunk pattern, see chunks 36-39's
module docstrings).** ``Profile`` is a Python class (reference type); Swift's
``Profile`` is a struct (value type), so every Swift ``profiles[i] =
someBlock.pMin`` (or ``.a!.profile!`` / ``.b!.profile!``) is an *independent
copy* in Swift but a *shared alias* in Python unless explicitly severed.
``self._blocks`` is instance state that persists across ``calculate()``
calls (mirroring Swift's per-DOF ``blocks`` array living on the
``TargetCalculator`` instance), and ``Block.p_min``/``Interval.profile`` are
read again on later calls (e.g. Step1's own ``copy.deepcopy(block.p_min)``
pattern) and within the same call (the "Time Synchronization" loop can, when
``discrete_duration`` is true, still reach and mutate a profile that
``synchronize()`` or the "None Synchronization" loop already wrote from a
block). Every site that assigns a ``Block``/``Interval``-held ``Profile``
into ``trajectory.profiles[0][...]`` therefore goes through
``copy.deepcopy()`` here: :meth:`TargetCalculator._synchronize`'s own
``profiles[div_rem] = ...`` save point, the "None Synchronization" loop, the
``trajectory.duration == 0.0`` copy-all-profiles branch, the 1-DOF
shortcut, and the "Time Synchronization" loop's three early-exit branches
(exact duration already matches an extremal profile). Everywhere else,
``trajectory.profiles[0][dof]`` is read, mutated in place, and (redundantly
but harmlessly, matching the Swift read-mutate-writeback structure)
reassigned to itself -- these are the trajectory's own persistent per-cycle
objects, never a fresh alias, so no copy is needed.

**Known, accepted Python/Swift divergence (not fixed, not tested):** Swift's
per-DOF loop reads ``var p = trajectory.profiles[0][dof]`` as a *local
struct copy*; an early ``return`` (e.g. ``.ErrorZeroLimits``,
``.ErrorExecutionTimeCalculation``) leaves ``trajectory.profiles[0][dof]``
untouched for any DOF whose mutations hadn't been explicitly written back
yet. In Python, since ``Profile`` is a reference type, mutating ``p``
*is* mutating ``trajectory.profiles[0][dof]`` immediately -- an early error
return leaves partially-mutated profile state in place rather than Swift's
clean rollback. otg.md's fidelity ranking is (1) oracle results, (2) public
semantics, (3) code structure; nothing in the oracle/classification/numeric
test strategy inspects trajectory state after an error ``Result``, so this
divergence is unobservable through the documented contract and is not
patched with defensive copying (that would violate the "not blanket
everywhere" scoping of the alias-mutation fix above).

**Debug ``print`` statements dropped.** The Swift source has four
``print("[DEBUG] ...")`` calls (in ``synchronize()``'s failure path and
``calculate()``'s two error branches) that are unconditional developer
tracing, not part of the algorithm -- same category as chunk 39's
``debugTimeVel``-gated print block, which was dropped as "not part of the
algorithm; every branch/root-search/Newton-step it wrapped is preserved
exactly." Dropped here for the same reason; every branch/decision they
straddled is preserved.

Division in :meth:`TargetCalculator._is_input_collinear` (``pd[dof] /
scale``, etc.) uses the bare ``/`` operator, not ``_ieee754_div``: ``scale``
is ``scale_vector[scale_dof]``, and ``scale_dof`` is only ever selected when
``abs(scale_vector[scale_dof]) > _EPS`` was already checked immediately
before -- the denominator is provably nonzero at every call site, unlike the
degenerate-root cases in chunks 38/39 that motivated ``_ieee754_div``
(otg.md §Internal fidelity requirement 4: only wrap where a *failing test*
shows a zero-denominator is reachable). ``controlLimiting * currentScale /
scaleLimiting``'s denominator (``scale_vector[limiting_dof]``) has no such
proof and could in principle be zero for some phase-sync input; no failing
test in this chunk's suite reaches that case, so it is left as a bare ``/``
per the same narrowly-scoped precedent, flagged here for any future chunk
that does hit it.
"""

from __future__ import annotations

import copy
import math
import sys

from math_tools.otg.block import Block
from math_tools.otg.enums import (
    ControlInterface,
    ControlSigns,
    Direction,
    DurationDiscretization,
    ReachedLimits,
    Result,
    Synchronization,
)
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.profile import Profile
from math_tools.otg.steps.position_first_order import (
    PositionFirstOrderStep1,
    PositionFirstOrderStep2,
)
from math_tools.otg.steps.position_second_order import (
    PositionSecondOrderStep1,
    PositionSecondOrderStep2,
)
from math_tools.otg.steps.position_third_order_step1 import PositionThirdOrderStep1
from math_tools.otg.steps.position_third_order_step2 import PositionThirdOrderStep2
from math_tools.otg.steps.velocity_second_order import (
    VelocitySecondOrderStep1,
    VelocitySecondOrderStep2,
)
from math_tools.otg.steps.velocity_third_order import (
    VelocityThirdOrderStep1,
    VelocityThirdOrderStep2,
)
from math_tools.otg.trajectory import Trajectory

__all__: list[str] = []

#: Swift ``Double.ulpOfOne`` -- ``CalculatorTarget.swift``'s own ``private
#: static let eps`` (transcribed under its Swift-local name rather than
#: profile.py's/block.py's ``_ULP``, matching this port's per-Swift-file
#: private-constant convention).
_EPS = sys.float_info.epsilon

#: ``CalculatorTarget.swift``'s ``private static let returnErrorAtMaximalDuration = true``.
_RETURN_ERROR_AT_MAXIMAL_DURATION = True

#: ``CalculatorTarget.swift``'s numerical trajectory-duration ceiling.
_MAX_DURATION = 7.6e3


class TargetCalculator:
    """Calculation class for a state-to-state trajectory.

    Owns large, pre-allocated per-DOF buffers (``_blocks``,
    ``_possible_t_syncs``, ``_idx``, ...) mutated in place on every call to
    :meth:`calculate`, mirroring the Swift ``class`` (reference type) for
    the same reason: this is the hot path of a real-time control loop.
    """

    def __init__(self, dofs: int) -> None:
        self.degrees_of_freedom = dofs

        self._blocks: list[Block] = [Block() for _ in range(dofs)]
        self._inp_min_velocity: list[float] = [0.0] * dofs
        self._inp_min_acceleration: list[float] = [0.0] * dofs
        self._inp_per_dof_control_interface: list[ControlInterface] = [
            ControlInterface.POSITION
        ] * dofs
        self._inp_per_dof_synchronization: list[Synchronization] = [
            Synchronization.NONE
        ] * dofs

        self._new_phase_control: list[float] = [0.0] * dofs
        self._pd: list[float] = [0.0] * dofs  # For phase synchronization.
        self._possible_t_syncs: list[float] = [math.inf] * (3 * dofs + 1)
        self._idx: list[int] = [0] * (3 * dofs + 1)

    # MARK: - Phase-synchronization collinearity check

    def _is_input_collinear(
        self, inp: InputParameter, limiting_direction: Direction, limiting_dof: int
    ) -> bool:
        """``isInputCollinear`` -- is the trajectory (in principle) phase
        synchronizable? Checks that ``pd``/``v0``/``a0``/``vf``/``af`` are
        collinear across every DOF tagged ``Synchronization.PHASE``."""
        dofs = self.degrees_of_freedom
        for dof in range(dofs):
            self._pd[dof] = inp.target_position[dof] - inp.current_position[dof]

        scale_vector: list[float] | None = None
        scale_dof: int | None = None  # Need a scale DOF: limiting DOF might not be phase synced.

        for dof in range(dofs):
            if self._inp_per_dof_synchronization[dof] != Synchronization.PHASE:
                continue

            if (
                self._inp_per_dof_control_interface[dof] == ControlInterface.POSITION
                and abs(self._pd[dof]) > _EPS
            ):
                scale_vector = self._pd
                scale_dof = dof
                break
            elif abs(inp.current_velocity[dof]) > _EPS:
                scale_vector = inp.current_velocity
                scale_dof = dof
                break
            elif abs(inp.current_acceleration[dof]) > _EPS:
                scale_vector = inp.current_acceleration
                scale_dof = dof
                break
            elif abs(inp.target_velocity[dof]) > _EPS:
                scale_vector = inp.target_velocity
                scale_dof = dof
                break
            elif abs(inp.target_acceleration[dof]) > _EPS:
                scale_vector = inp.target_acceleration
                scale_dof = dof
                break

        if scale_dof is None or scale_vector is None:
            # Zero everywhere is in theory collinear, but that trivial case
            # is better handled elsewhere.
            return False

        scale = scale_vector[scale_dof]
        pd_scale = self._pd[scale_dof] / scale
        v0_scale = inp.current_velocity[scale_dof] / scale
        vf_scale = inp.target_velocity[scale_dof] / scale
        a0_scale = inp.current_acceleration[scale_dof] / scale
        af_scale = inp.target_acceleration[scale_dof] / scale

        scale_limiting = scale_vector[limiting_dof]
        if math.isinf(inp.max_jerk[limiting_dof]):
            control_limiting = (
                inp.max_acceleration[limiting_dof]
                if limiting_direction == Direction.UP
                else self._inp_min_acceleration[limiting_dof]
            )
        else:
            control_limiting = (
                inp.max_jerk[limiting_dof]
                if limiting_direction == Direction.UP
                else -inp.max_jerk[limiting_dof]
            )

        for dof in range(dofs):
            if self._inp_per_dof_synchronization[dof] != Synchronization.PHASE:
                continue

            current_scale = scale_vector[dof]
            if (
                (
                    self._inp_per_dof_control_interface[dof] == ControlInterface.POSITION
                    and abs(self._pd[dof] - pd_scale * current_scale) > _EPS
                )
                or abs(inp.current_velocity[dof] - v0_scale * current_scale) > _EPS
                or abs(inp.current_acceleration[dof] - a0_scale * current_scale) > _EPS
                or abs(inp.target_velocity[dof] - vf_scale * current_scale) > _EPS
                or abs(inp.target_acceleration[dof] - af_scale * current_scale) > _EPS
            ):
                return False

            self._new_phase_control[dof] = control_limiting * current_scale / scale_limiting

        return True

    # MARK: - Cross-DOF time synchronization

    def _synchronize(
        self,
        t_min: float | None,
        profiles: list[Profile],
        discrete_duration: bool,
        delta_time: float,
    ) -> tuple[bool, float, int | None]:
        """``synchronize`` -- returns ``(found, t_sync, limiting_dof)``.
        Mutates ``profiles`` (``trajectory.profiles[0]``) in place at its
        selected index, matching Swift's ``inout [Profile]`` parameter."""
        dofs = self.degrees_of_freedom

        # Possible tSyncs are the start times of the intervals and optional t_min.
        any_interval = False
        for dof in range(dofs):
            # Ignore DoFs without synchronization here.
            if self._inp_per_dof_synchronization[dof] == Synchronization.NONE:
                self._possible_t_syncs[dof] = 0.0
                self._possible_t_syncs[dofs + dof] = math.inf
                self._possible_t_syncs[2 * dofs + dof] = math.inf
                continue

            block = self._blocks[dof]
            self._possible_t_syncs[dof] = block.t_min
            self._possible_t_syncs[dofs + dof] = block.a.right if block.a is not None else math.inf
            self._possible_t_syncs[2 * dofs + dof] = (
                block.b.right if block.b is not None else math.inf
            )
            any_interval = any_interval or block.a is not None or block.b is not None

        self._possible_t_syncs[3 * dofs] = t_min if t_min is not None else math.inf
        any_interval = any_interval or t_min is not None

        if discrete_duration:
            for i in range(len(self._possible_t_syncs)):
                if math.isinf(self._possible_t_syncs[i]):
                    continue
                remainder = math.fmod(self._possible_t_syncs[i], delta_time)  # in [0, delta_time)
                if remainder > _EPS:
                    self._possible_t_syncs[i] += delta_time - remainder

        # Test them in sorted order.
        idx_end = len(self._idx) if any_interval else dofs
        for i in range(idx_end):
            self._idx[i] = i
        self._idx[0:idx_end] = sorted(
            self._idx[0:idx_end], key=lambda i: self._possible_t_syncs[i]
        )

        # Start at last tmin (or worse).
        for i in range(dofs - 1, idx_end):
            possible_t_sync = self._possible_t_syncs[self._idx[i]]
            is_blocked = False
            for dof in range(dofs):
                if self._inp_per_dof_synchronization[dof] == Synchronization.NONE:
                    continue  # inner dof loop
                if self._blocks[dof].is_blocked(possible_t_sync):
                    is_blocked = True
                    break  # inner dof loop

            floor = t_min if t_min is not None else 0.0
            if is_blocked or possible_t_sync < floor or math.isinf(possible_t_sync):
                continue

            t_sync = possible_t_sync
            if self._idx[i] == 3 * dofs:  # Optional t_min.
                return True, t_sync, None

            div_quot, div_rem = divmod(self._idx[i], dofs)
            limiting_dof = div_rem
            block = self._blocks[div_rem]
            if div_quot == 0:
                profiles[div_rem] = copy.deepcopy(block.p_min)
            elif div_quot == 1 and block.a is not None and block.a.profile is not None:
                profiles[div_rem] = copy.deepcopy(block.a.profile)
            elif div_quot == 2 and block.b is not None and block.b.profile is not None:
                profiles[div_rem] = copy.deepcopy(block.b.profile)
            return True, t_sync, limiting_dof

        return False, 0.0, None

    # MARK: - Calculation

    def calculate(
        self,
        input_parameter: InputParameter,
        trajectory: Trajectory,
        delta_time: float,
    ) -> Result:
        """Calculate the time-optimal waypoint-based trajectory. Never
        raises for per-cycle failures (otg.md §Error semantics) -- returns
        an error :class:`~math_tools.otg.enums.Result` instead."""
        dofs = self.degrees_of_freedom

        # Check for the trivial case: all positions equal, all
        # velocities/accelerations zero.
        all_positions_equal = True
        all_velocities_zero = True
        all_accelerations_zero = True

        for dof in range(dofs):
            position_delta = (
                input_parameter.target_position[dof] - input_parameter.current_position[dof]
            )
            if abs(position_delta) > _EPS:
                all_positions_equal = False
            if (
                abs(input_parameter.current_velocity[dof]) > _EPS
                or abs(input_parameter.target_velocity[dof]) > _EPS
            ):
                all_velocities_zero = False
            if (
                abs(input_parameter.current_acceleration[dof]) > _EPS
                or abs(input_parameter.target_acceleration[dof]) > _EPS
            ):
                all_accelerations_zero = False

        if all_positions_equal and all_velocities_zero and all_accelerations_zero:
            # Trivial case: already at target with zero motion.
            trajectory.duration = 0.0
            trajectory.cumulative_times[0] = 0.0

            for dof in range(dofs):
                p = trajectory.profiles[0][dof]
                p.t = [0.0] * 7
                p.t_sum = [0.0] * 7
                p.j = [0.0] * 7
                p.a = [input_parameter.current_acceleration[dof]] * 7
                p.v = [input_parameter.current_velocity[dof]] * 7
                p.p = [input_parameter.current_position[dof]] * 7
                trajectory.independent_min_durations[dof] = 0.0

            return Result.WORKING

        for dof in range(dofs):
            p = trajectory.profiles[0][dof]

            self._inp_min_velocity[dof] = (
                input_parameter.min_velocity[dof]
                if input_parameter.min_velocity is not None
                else -input_parameter.max_velocity[dof]
            )
            self._inp_min_acceleration[dof] = (
                input_parameter.min_acceleration[dof]
                if input_parameter.min_acceleration is not None
                else -input_parameter.max_acceleration[dof]
            )
            self._inp_per_dof_control_interface[dof] = (
                input_parameter.per_dof_control_interface[dof]
                if input_parameter.per_dof_control_interface is not None
                else input_parameter.control_interface
            )
            self._inp_per_dof_synchronization[dof] = (
                input_parameter.per_dof_synchronization[dof]
                if input_parameter.per_dof_synchronization is not None
                else input_parameter.synchronization
            )

            if not input_parameter.enabled[dof]:
                p.p[-1] = input_parameter.current_position[dof]
                p.v[-1] = input_parameter.current_velocity[dof]
                p.a[-1] = input_parameter.current_acceleration[dof]
                p.t_sum[-1] = 0.0
                self._blocks[dof].t_min = 0.0
                self._blocks[dof].a = None
                self._blocks[dof].b = None
                trajectory.profiles[0][dof] = p
                continue

            control_interface = self._inp_per_dof_control_interface[dof]

            # Calculate brake (if input exceeds or will exceed limits).
            if control_interface == ControlInterface.POSITION:
                if not math.isinf(input_parameter.max_jerk[dof]):
                    p.brake.get_position_brake_trajectory(
                        input_parameter.current_velocity[dof],
                        input_parameter.current_acceleration[dof],
                        input_parameter.max_velocity[dof],
                        self._inp_min_velocity[dof],
                        input_parameter.max_acceleration[dof],
                        self._inp_min_acceleration[dof],
                        input_parameter.max_jerk[dof],
                    )
                elif not math.isinf(input_parameter.max_acceleration[dof]):
                    p.brake.get_second_order_position_brake_trajectory(
                        input_parameter.current_velocity[dof],
                        input_parameter.max_velocity[dof],
                        self._inp_min_velocity[dof],
                        input_parameter.max_acceleration[dof],
                        self._inp_min_acceleration[dof],
                    )
                p.set_boundary(
                    input_parameter.current_position[dof],
                    input_parameter.current_velocity[dof],
                    input_parameter.current_acceleration[dof],
                    input_parameter.target_position[dof],
                    input_parameter.target_velocity[dof],
                    input_parameter.target_acceleration[dof],
                )
            else:  # ControlInterface.VELOCITY
                if not math.isinf(input_parameter.max_jerk[dof]):
                    p.brake.get_velocity_brake_trajectory(
                        input_parameter.current_acceleration[dof],
                        input_parameter.max_acceleration[dof],
                        self._inp_min_acceleration[dof],
                        input_parameter.max_jerk[dof],
                    )
                else:
                    p.brake.get_second_order_velocity_brake_trajectory()
                p.set_boundary_for_velocity(
                    input_parameter.current_position[dof],
                    input_parameter.current_velocity[dof],
                    input_parameter.current_acceleration[dof],
                    input_parameter.target_velocity[dof],
                    input_parameter.target_acceleration[dof],
                )

            # Finalize pre & post-trajectories.
            if not math.isinf(input_parameter.max_jerk[dof]):
                p.p[0], p.v[0], p.a[0] = p.brake.finalize(p.p[0], p.v[0], p.a[0])
            elif not math.isinf(input_parameter.max_acceleration[dof]):
                p.p[0], p.v[0], p.a[0] = p.brake.finalize_second_order(p.p[0], p.v[0], p.a[0])

            found_profile = False
            if control_interface == ControlInterface.POSITION:
                if not math.isinf(input_parameter.max_jerk[dof]):
                    # MARK: - P-ThirdOrderStep1
                    step1_p3 = PositionThirdOrderStep1(
                        p0=p.p[0],
                        v0=p.v[0],
                        a0=p.a[0],
                        pf=p.pf,
                        vf=p.vf,
                        af=p.af,
                        v_max=input_parameter.max_velocity[dof],
                        v_min=self._inp_min_velocity[dof],
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                        j_max=input_parameter.max_jerk[dof],
                    )
                    found_profile = step1_p3.get_profile(p, self._blocks[dof])
                elif not math.isinf(input_parameter.max_acceleration[dof]):
                    # MARK: - P-SecondOrderStep1
                    step1_p2 = PositionSecondOrderStep1(
                        p0=p.p[0],
                        v0=p.v[0],
                        pf=p.pf,
                        vf=p.vf,
                        v_max=input_parameter.max_velocity[dof],
                        v_min=self._inp_min_velocity[dof],
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                    )
                    found_profile = step1_p2.get_profile(p, self._blocks[dof])
                else:
                    # MARK: - P-FirstOrderStep1
                    step1_p1 = PositionFirstOrderStep1(
                        p0=p.p[0],
                        pf=p.pf,
                        v_max=input_parameter.max_velocity[dof],
                        v_min=self._inp_min_velocity[dof],
                    )
                    found_profile = step1_p1.get_profile(p, self._blocks[dof])
            else:  # ControlInterface.VELOCITY
                if not math.isinf(input_parameter.max_jerk[dof]):
                    # MARK: - V-ThirdOrderStep1
                    step1_v3 = VelocityThirdOrderStep1(
                        v0=p.v[0],
                        a0=p.a[0],
                        vf=p.vf,
                        af=p.af,
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                        j_max=input_parameter.max_jerk[dof],
                    )
                    found_profile = step1_v3.get_profile(p, self._blocks[dof])
                else:
                    # MARK: - V-SecondOrderStep1
                    step1_v2 = VelocitySecondOrderStep1(
                        v0=p.v[0],
                        vf=p.vf,
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                    )
                    found_profile = step1_v2.get_profile(p, self._blocks[dof])

            if not found_profile:
                has_zero_limits = (
                    input_parameter.max_acceleration[dof] == 0.0
                    or self._inp_min_acceleration[dof] == 0.0
                    or input_parameter.max_jerk[dof] == 0.0
                )
                if has_zero_limits:
                    return Result.ERROR_ZERO_LIMITS
                return Result.ERROR_EXECUTION_TIME_CALCULATION

            trajectory.independent_min_durations[dof] = self._blocks[dof].t_min
            trajectory.profiles[0][dof] = p

        discrete_duration = (
            input_parameter.duration_discretization == DurationDiscretization.DISCRETE
        )
        if dofs == 1 and input_parameter.minimum_duration is None and not discrete_duration:
            trajectory.duration = self._blocks[0].t_min
            trajectory.profiles[0][0] = copy.deepcopy(self._blocks[0].p_min)
            trajectory.cumulative_times[0] = trajectory.duration
            return Result.WORKING

        limiting_dof: int | None = None  # The DoF that doesn't need step 2.
        found_synchronization, t_sync, limiting_dof = self._synchronize(
            input_parameter.minimum_duration,
            trajectory.profiles[0],
            discrete_duration,
            delta_time,
        )
        if found_synchronization:
            trajectory.duration = t_sync

        if not found_synchronization:
            has_zero_limits = False
            for dof in range(dofs):
                if (
                    input_parameter.max_acceleration[dof] == 0.0
                    or self._inp_min_acceleration[dof] == 0.0
                    or input_parameter.max_jerk[dof] == 0.0
                ):
                    has_zero_limits = True
                    break

            if has_zero_limits:
                return Result.ERROR_ZERO_LIMITS
            return Result.ERROR_SYNCHRONIZATION_CALCULATION

        # None Synchronization.
        for dof in range(dofs):
            if (
                input_parameter.enabled[dof]
                and self._inp_per_dof_synchronization[dof] == Synchronization.NONE
            ):
                trajectory.profiles[0][dof] = copy.deepcopy(self._blocks[dof].p_min)
                if self._blocks[dof].t_min > trajectory.duration:
                    trajectory.duration = self._blocks[dof].t_min
                    limiting_dof = dof
        trajectory.cumulative_times[0] = trajectory.duration

        if _RETURN_ERROR_AT_MAXIMAL_DURATION and trajectory.duration > _MAX_DURATION:
            return Result.ERROR_TRAJECTORY_DURATION

        if trajectory.duration == 0.0:
            # Copy all profiles for end state.
            for dof in range(dofs):
                trajectory.profiles[0][dof] = copy.deepcopy(self._blocks[dof].p_min)
            return Result.WORKING

        if not discrete_duration and all(
            sync == Synchronization.NONE for sync in self._inp_per_dof_synchronization
        ):
            return Result.WORKING

        # Phase Synchronization.
        if limiting_dof is not None and Synchronization.PHASE in self._inp_per_dof_synchronization:
            p_limiting = trajectory.profiles[0][limiting_dof]
            if self._is_input_collinear(input_parameter, p_limiting.direction, limiting_dof):
                found_time_synchronization = True
                for dof in range(dofs):
                    if (
                        not input_parameter.enabled[dof]
                        or dof == limiting_dof
                        or self._inp_per_dof_synchronization[dof] != Synchronization.PHASE
                    ):
                        continue

                    p = trajectory.profiles[0][dof]
                    t_profile = trajectory.duration - p.brake.duration - p.accel.duration

                    p.t = list(p_limiting.t)  # Copy timing information from limiting DoF.
                    p.control_signs = p_limiting.control_signs

                    # ReachedLimits.NONE is a small hack, as there is no
                    # specialization for that in the check function.
                    if found_time_synchronization:
                        dof_control_interface = self._inp_per_dof_control_interface[dof]
                        j_max_dof = input_parameter.max_jerk[dof]
                        a_max_dof = input_parameter.max_acceleration[dof]
                        a_min_dof = self._inp_min_acceleration[dof]
                        v_max_dof = input_parameter.max_velocity[dof]
                        v_min_dof = self._inp_min_velocity[dof]
                        phase_control = self._new_phase_control[dof]

                        if dof_control_interface == ControlInterface.POSITION:
                            if p.control_signs == ControlSigns.UDDU:
                                if not math.isinf(j_max_dof):
                                    ok = p.check_with_timing(
                                        t_profile,
                                        phase_control,
                                        v_max_dof,
                                        v_min_dof,
                                        a_max_dof,
                                        a_min_dof,
                                        ControlSigns.UDDU,
                                        ReachedLimits.NONE,
                                        j_max=j_max_dof,
                                    )
                                elif not math.isinf(a_max_dof):
                                    ok = p.check_for_second_order_with_timing(
                                        t_profile,
                                        phase_control,
                                        -phase_control,
                                        v_max_dof,
                                        v_min_dof,
                                        ControlSigns.UDDU,
                                        ReachedLimits.NONE,
                                        a_max=a_max_dof,
                                        a_min=a_min_dof,
                                    )
                                else:
                                    ok = p.check_for_first_order_with_timing(
                                        t_profile,
                                        phase_control,
                                        ControlSigns.UDDU,
                                        ReachedLimits.NONE,
                                        v_max=v_max_dof,
                                        v_min=v_min_dof,
                                    )
                            else:  # UDUD
                                if not math.isinf(j_max_dof):
                                    ok = p.check_with_timing(
                                        t_profile,
                                        phase_control,
                                        v_max_dof,
                                        v_min_dof,
                                        a_max_dof,
                                        a_min_dof,
                                        ControlSigns.UDUD,
                                        ReachedLimits.NONE,
                                        j_max=j_max_dof,
                                    )
                                else:
                                    ok = p.check_for_second_order_with_timing(
                                        t_profile,
                                        phase_control,
                                        -phase_control,
                                        v_max_dof,
                                        v_min_dof,
                                        ControlSigns.UDUD,
                                        ReachedLimits.NONE,
                                        a_max=a_max_dof,
                                        a_min=a_min_dof,
                                    )
                        else:  # ControlInterface.VELOCITY
                            if p.control_signs == ControlSigns.UDDU:
                                if not math.isinf(j_max_dof):
                                    ok = p.check_for_velocity_with_timing(
                                        t_profile,
                                        phase_control,
                                        a_max_dof,
                                        a_min_dof,
                                        ControlSigns.UDDU,
                                        ReachedLimits.NONE,
                                        j_max=j_max_dof,
                                    )
                                else:
                                    ok = p.check_for_second_order_velocity_with_timing(
                                        t_profile,
                                        phase_control,
                                        ControlSigns.UDDU,
                                        ReachedLimits.NONE,
                                        a_max=a_max_dof,
                                        a_min=a_min_dof,
                                    )
                            else:  # UDUD
                                if not math.isinf(j_max_dof):
                                    ok = p.check_for_velocity_with_timing(
                                        t_profile,
                                        phase_control,
                                        a_max_dof,
                                        a_min_dof,
                                        ControlSigns.UDUD,
                                        ReachedLimits.NONE,
                                        j_max=j_max_dof,
                                    )
                                else:
                                    ok = p.check_for_second_order_velocity_with_timing(
                                        t_profile,
                                        phase_control,
                                        ControlSigns.UDUD,
                                        ReachedLimits.NONE,
                                        a_max=a_max_dof,
                                        a_min=a_min_dof,
                                    )

                        found_time_synchronization = found_time_synchronization and ok

                    p.limits = p_limiting.limits  # After check method call, to set correct limits.
                    trajectory.profiles[0][dof] = p

                if found_time_synchronization and all(
                    sync in (Synchronization.PHASE, Synchronization.NONE)
                    for sync in self._inp_per_dof_synchronization
                ):
                    return Result.WORKING

        # Time Synchronization.
        for dof in range(dofs):
            dof_sync = self._inp_per_dof_synchronization[dof]
            skip_synchronization = (
                dof == limiting_dof or dof_sync == Synchronization.NONE
            ) and not discrete_duration
            if not input_parameter.enabled[dof] or skip_synchronization:
                continue

            p = trajectory.profiles[0][dof]
            t_profile = trajectory.duration - p.brake.duration - p.accel.duration

            if (
                self._inp_per_dof_synchronization[dof] == Synchronization.TIME_IF_NECESSARY
                and abs(input_parameter.target_velocity[dof]) < _EPS
                and abs(input_parameter.target_acceleration[dof]) < _EPS
            ):
                trajectory.profiles[0][dof] = copy.deepcopy(self._blocks[dof].p_min)
                continue

            # Check if the final time corresponds to an extremal profile
            # calculated in step 1. Use 2*eps because of numerical
            # robustness in duration discretization.
            block = self._blocks[dof]
            if abs(t_profile - block.t_min) < 2 * _EPS:
                trajectory.profiles[0][dof] = copy.deepcopy(block.p_min)
                continue
            block_a, block_b = block.a, block.b
            if block_a is not None and block_a.profile is not None:
                if abs(t_profile - block_a.right) < 2 * _EPS:
                    trajectory.profiles[0][dof] = copy.deepcopy(block_a.profile)
                    continue
            if block_b is not None and block_b.profile is not None:
                if abs(t_profile - block_b.right) < 2 * _EPS:
                    trajectory.profiles[0][dof] = copy.deepcopy(block_b.profile)
                    continue

            found_time_synchronization = False
            control_interface = self._inp_per_dof_control_interface[dof]
            if control_interface == ControlInterface.POSITION:
                if not math.isinf(input_parameter.max_jerk[dof]):
                    # MARK: - P-ThirdOrderStep2
                    step2_p3 = PositionThirdOrderStep2(
                        t_profile,
                        p.p[0],
                        p.v[0],
                        p.a[0],
                        p.pf,
                        p.vf,
                        p.af,
                        input_parameter.max_velocity[dof],
                        self._inp_min_velocity[dof],
                        input_parameter.max_acceleration[dof],
                        self._inp_min_acceleration[dof],
                        input_parameter.max_jerk[dof],
                    )
                    found_time_synchronization = step2_p3.get_profile(p)
                elif not math.isinf(input_parameter.max_acceleration[dof]):
                    # MARK: - P-SecondOrderStep2
                    step2_p2 = PositionSecondOrderStep2(
                        t_profile,
                        p.p[0],
                        p.v[0],
                        p.pf,
                        p.vf,
                        input_parameter.max_velocity[dof],
                        self._inp_min_velocity[dof],
                        input_parameter.max_acceleration[dof],
                        self._inp_min_acceleration[dof],
                    )
                    found_time_synchronization = step2_p2.get_profile(p)
                else:
                    # MARK: - P-FirstOrderStep2
                    step2_p1 = PositionFirstOrderStep2(
                        tf=t_profile,
                        p0=p.p[0],
                        pf=p.pf,
                        v_max=input_parameter.max_velocity[dof],
                        v_min=self._inp_min_velocity[dof],
                    )
                    found_time_synchronization = step2_p1.get_profile(profile=p)
            else:  # ControlInterface.VELOCITY
                if not math.isinf(input_parameter.max_jerk[dof]):
                    # MARK: - V-ThirdOrderStep2
                    step2_v3 = VelocityThirdOrderStep2(
                        tf=t_profile,
                        v0=p.v[0],
                        a0=p.a[0],
                        vf=p.vf,
                        af=p.af,
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                        j_max=input_parameter.max_jerk[dof],
                    )
                    found_time_synchronization = step2_v3.get_profile(p)
                else:
                    # MARK: - V-SecondOrderStep2
                    step2_v2 = VelocitySecondOrderStep2(
                        tf=t_profile,
                        v0=p.v[0],
                        vf=p.vf,
                        a_max=input_parameter.max_acceleration[dof],
                        a_min=self._inp_min_acceleration[dof],
                    )
                    found_time_synchronization = step2_v2.get_profile(p)

            if not found_time_synchronization:
                return Result.ERROR_SYNCHRONIZATION_CALCULATION

            trajectory.profiles[0][dof] = p

        return Result.WORKING
