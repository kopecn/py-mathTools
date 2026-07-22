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


if __name__ == "__main__":
    unittest.main()
