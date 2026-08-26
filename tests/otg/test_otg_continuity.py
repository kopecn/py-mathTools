"""Continuity tests: no kinematic discontinuities at profile boundaries.

Port of ``SWIFT_TESTS/OTGTests/OTGContinuityTests.swift`` (all 5 cases,
test-for-test -- none are Swift-specific machinery). See
``.claude/specs/otg.md`` §Oracle and test strategy 3, §Compliance 2, and
``.claude/action-plan/42-otg-oracle-suites.md``'s design constraint 3.

``_check_trajectory_continuity`` ports the Swift ``checkTrajectoryContinuity``
helper: integrate forward across each of the profile's 7 segment boundaries
using its own ``(t, j)`` and compare against the profile's own stored
``p``/``v``/``a`` at that boundary. Both use the same closed-form
constant-jerk integration (``integrate_jerk``), so this is a self-consistency
check on the profile's internal bookkeeping, not a comparison against an
external oracle -- exactly the Swift test's intent.

**Chunk 56 addition (post-audit finding E-7).** The 5 classes above only
call ``Otg.calculate`` once each and never cross a section boundary --
a self-consistency check on one profile's own bookkeeping, not a check of
continuity *across* real ``update()`` control cycles including the section
transition ``OutputParameter.did_section_change`` flags. ``TestUpdateCycleContinuity``
below drives a real ``update()`` control loop to completion and asserts
continuity at every cycle boundary, including the one genuine section
transition a single-section (no-waypoint) trajectory has: the cycle where
``output.time`` first crosses ``trajectory.duration`` and
``Trajectory._state_to_integrate_from`` switches from section 0 to the
"past the last section" branch (``new_section = len(self.profiles) == 1``),
which is exactly the cycle ``did_section_change`` flips ``True`` and
``update()`` returns ``FINISHED``.
"""

from __future__ import annotations

import unittest

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.enums import Result
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter
from math_tools.otg.trajectory import Trajectory

_CONTROL_CYCLE = 0.01
_CONTINUITY_TOLERANCE = 1e-6
_BOUNDARY_TOLERANCE = 1e-6

_UPDATE_V_MAX = 2.0
_UPDATE_A_MAX = 1.0
_UPDATE_J_MAX = 1.0
_UPDATE_CONTROL_CYCLE = 0.1
_UPDATE_TARGET = 2.0


def _check_trajectory_continuity(
    trajectory: Trajectory, dof: int = 0, tolerance: float = _CONTINUITY_TOLERANCE
) -> bool:
    """``checkTrajectoryContinuity`` -- integrating from each profile
    boundary's own stored state must reproduce the next boundary's stored
    state, for all 7 segments."""
    if not trajectory.profiles or len(trajectory.profiles[0]) <= dof:
        return False

    profile = trajectory.profiles[0][dof]

    previous_p = profile.p[0]
    previous_v = profile.v[0]
    previous_a = profile.a[0]

    for i in range(1, 8):
        current_p = profile.p[i]
        current_v = profile.v[i]
        current_a = profile.a[i]

        t = profile.t[i - 1]
        j = profile.j[i - 1]
        integrated_p, integrated_v, integrated_a = integrate_jerk(
            t, previous_p, previous_v, previous_a, j
        )

        if abs(integrated_p - current_p) > tolerance:
            return False
        if abs(integrated_v - current_v) > tolerance:
            return False
        if abs(integrated_a - current_a) > tolerance:
            return False

        previous_p = current_p
        previous_v = current_v
        previous_a = current_a

    return True


def _calculate(inp: InputParameter) -> tuple[Result, OutputParameter]:
    otg = Otg(_CONTROL_CYCLE, dofs=inp.degrees_of_freedom)
    output = OutputParameter(dofs=inp.degrees_of_freedom)
    result = otg.calculate(inp, output)
    return result, output


class TestNonZeroVelocityBoundaryConditions(unittest.TestCase):
    def test_continuous_with_nonzero_start_and_end_velocity(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [2.929012715930903]
        inp.current_velocity = [1.3368222168905952]
        inp.current_acceleration = [0.0]
        inp.target_position = [10.0]
        inp.target_velocity = [-1.3503178982725528]
        inp.target_acceleration = [0.0]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"calculation should succeed, got {result!r}")
        self.assertTrue(
            _check_trajectory_continuity(output.trajectory), "trajectory must be continuous"
        )

        start_p, start_v, start_a = output.trajectory.at_time(0.0)
        self.assertAlmostEqual(start_p[0], inp.current_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_v[0], inp.current_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_a[0], inp.current_acceleration[0], delta=_BOUNDARY_TOLERANCE)

        end_p, end_v, end_a = output.trajectory.at_time(output.trajectory.duration)
        self.assertAlmostEqual(end_p[0], inp.target_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_v[0], inp.target_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_a[0], inp.target_acceleration[0], delta=_BOUNDARY_TOLERANCE)


class TestNonZeroAccelerationBoundaryConditions(unittest.TestCase):
    def test_continuous_with_nonzero_start_and_end_acceleration(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [0.0]
        inp.current_velocity = [0.0]
        inp.current_acceleration = [-1.5686480326295587]
        inp.target_position = [10.0]
        inp.target_velocity = [0.0]
        inp.target_acceleration = [2.3736654270633393]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"calculation should succeed, got {result!r}")
        self.assertTrue(
            _check_trajectory_continuity(output.trajectory), "trajectory must be continuous"
        )

        start_p, start_v, start_a = output.trajectory.at_time(0.0)
        self.assertAlmostEqual(start_p[0], inp.current_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_v[0], inp.current_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_a[0], inp.current_acceleration[0], delta=_BOUNDARY_TOLERANCE)

        end_p, end_v, end_a = output.trajectory.at_time(output.trajectory.duration)
        self.assertAlmostEqual(end_p[0], inp.target_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_v[0], inp.target_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_a[0], inp.target_acceleration[0], delta=_BOUNDARY_TOLERANCE)


class TestInvertedBoundaryConditions(unittest.TestCase):
    def test_continuous_with_inverted_start_and_target(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [7.1647072936660265]
        inp.current_velocity = [-1.5912907869481767]
        inp.current_acceleration = [1.2187350047984646]
        inp.target_position = [-0.1964371401151649]
        inp.target_velocity = [1.8250659788867563]
        inp.target_acceleration = [-1.9871641074856043]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"calculation should succeed, got {result!r}")
        self.assertTrue(
            _check_trajectory_continuity(output.trajectory), "trajectory must be continuous"
        )

        start_p, start_v, start_a = output.trajectory.at_time(0.0)
        self.assertAlmostEqual(start_p[0], inp.current_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_v[0], inp.current_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(start_a[0], inp.current_acceleration[0], delta=_BOUNDARY_TOLERANCE)

        end_p, end_v, end_a = output.trajectory.at_time(output.trajectory.duration)
        self.assertAlmostEqual(end_p[0], inp.target_position[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_v[0], inp.target_velocity[0], delta=_BOUNDARY_TOLERANCE)
        self.assertAlmostEqual(end_a[0], inp.target_acceleration[0], delta=_BOUNDARY_TOLERANCE)


class TestZeroTargetBoundaryConditions(unittest.TestCase):
    def test_continuous_with_zero_target_conditions(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [2.5]
        inp.current_velocity = [1.2]
        inp.current_acceleration = [-0.8]
        inp.target_position = [10.0]
        inp.target_velocity = [0.0]
        inp.target_acceleration = [0.0]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"calculation should succeed, got {result!r}")
        self.assertTrue(
            _check_trajectory_continuity(output.trajectory), "trajectory must be continuous"
        )


class TestZeroInitialBoundaryConditions(unittest.TestCase):
    def test_continuous_with_zero_initial_conditions(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [0.0]
        inp.current_velocity = [0.0]
        inp.current_acceleration = [0.0]
        inp.target_position = [10.0]
        inp.target_velocity = [1.5]
        inp.target_acceleration = [-2.0]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"calculation should succeed, got {result!r}")
        self.assertTrue(
            _check_trajectory_continuity(output.trajectory), "trajectory must be continuous"
        )


class TestUpdateCycleContinuity(unittest.TestCase):
    """Post-audit E-7: continuity across real ``Otg.update()`` control
    cycles, including the ``did_section_change`` transition."""

    def test_continuous_across_update_cycles_including_section_change(self) -> None:
        otg = Otg(_UPDATE_CONTROL_CYCLE, dofs=1)
        inp = InputParameter(1)
        inp.target_position = [_UPDATE_TARGET]
        inp.max_velocity = [_UPDATE_V_MAX]
        inp.min_velocity = [-_UPDATE_V_MAX]
        inp.max_acceleration = [_UPDATE_A_MAX]
        inp.min_acceleration = [-_UPDATE_A_MAX]
        inp.max_jerk = [_UPDATE_J_MAX]
        output = OutputParameter(dofs=1)

        max_calls = 1000
        calls = 0
        result = Result.WORKING
        section_change_cycles: list[int] = []
        previous_state: tuple[float, float, float] | None = None

        while result != Result.FINISHED:
            calls += 1
            self.assertLessEqual(calls, max_calls, "did not reach FINISHED within bound")

            result = otg.update(inp, output)
            self.assertGreaterEqual(result, 0, f"update() returned an error on call {calls}")

            if output.did_section_change:
                section_change_cycles.append(calls)

            # A fresh, independent at_time() query at this cycle's time
            # must reproduce update()'s own sampled state -- on every
            # cycle, including the section-change cycle (this is the
            # continuity check: at_time uses a different branch of
            # Trajectory._state_to_integrate_from once time >= duration).
            expected_p, expected_v, expected_a = output.trajectory.at_time(output.time)
            self.assertAlmostEqual(
                output.new_position[0], expected_p[0], delta=1e-9, msg=f"call {calls} position"
            )
            self.assertAlmostEqual(
                output.new_velocity[0], expected_v[0], delta=1e-9, msg=f"call {calls} velocity"
            )
            self.assertAlmostEqual(
                output.new_acceleration[0],
                expected_a[0],
                delta=1e-9,
                msg=f"call {calls} acceleration",
            )

            # Cross-cycle continuity: the state must not jump beyond what
            # one control cycle of bounded jerk/acceleration/velocity can
            # produce -- generous bounds (a few control cycles' worth),
            # not tight kinematic integration, since this is a
            # discontinuity smoke check, not a duplicate of the numeric
            # oracle.
            current_state = (
                output.new_position[0],
                output.new_velocity[0],
                output.new_acceleration[0],
            )
            if previous_state is not None:
                prev_p, prev_v, prev_a = previous_state
                self.assertLessEqual(
                    abs(current_state[0] - prev_p),
                    (_UPDATE_V_MAX + 1.0) * _UPDATE_CONTROL_CYCLE,
                    f"call {calls}: position jump too large across cycle boundary",
                )
                self.assertLessEqual(
                    abs(current_state[1] - prev_v),
                    (_UPDATE_A_MAX + 1.0) * _UPDATE_CONTROL_CYCLE,
                    f"call {calls}: velocity jump too large across cycle boundary",
                )
                self.assertLessEqual(
                    abs(current_state[2] - prev_a),
                    (_UPDATE_J_MAX + 1.0) * _UPDATE_CONTROL_CYCLE,
                    f"call {calls}: acceleration jump too large across cycle boundary",
                )
            previous_state = current_state

            output.pass_to_input(inp)

        self.assertEqual(result, Result.FINISHED)
        # A single-section (no-waypoint) trajectory has exactly one real
        # section transition: section 0 -> "past the last section", which
        # coincides with the FINISHED cycle.
        self.assertEqual(
            section_change_cycles,
            [calls],
            "expected exactly one did_section_change transition, on the FINISHED cycle",
        )

        # The transition itself must land exactly on the target state.
        self.assertAlmostEqual(output.new_position[0], _UPDATE_TARGET, delta=1e-6)
        self.assertAlmostEqual(output.new_velocity[0], 0.0, delta=1e-6)
        self.assertAlmostEqual(output.new_acceleration[0], 0.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
