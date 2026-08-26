"""Regression tests for previously-failing trajectory inputs.

Port of ``SWIFT_TESTS/OTGTests/OTGFailureFixTests.swift`` (all 5 cases,
test-for-test -- none are Swift-specific machinery). See
``.claude/specs/otg.md`` §Oracle and test strategy 3 and
``.claude/action-plan/42-otg-oracle-suites.md``'s design constraint 4.

Two bug categories, each ported with the Swift source's own pass/fail
contract:

- **Bug #1 (acceleration-limit violations with non-zero target velocity):**
  the Swift test asserts the calculation succeeds (``XCTFail`` otherwise)
  and then checks no negative time intervals and that
  acceleration/velocity limits hold throughout the sampled trajectory.
- **Bug #2 (negative time intervals with high limits):** the Swift test
  does NOT require success -- a legitimate failure is acceptable, it only
  asserts that *if* the calculation succeeds, the returned profile has no
  negative time intervals and respects its limits (i.e. it must never
  silently return an invalid trajectory).
"""

from __future__ import annotations

import unittest

from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter
from math_tools.otg.trajectory import Trajectory

_CONTROL_CYCLE = 0.01
_LIMIT_TOLERANCE = 0.001
_SAMPLE_COUNT = 100


def _calculate(inp: InputParameter) -> tuple[int, OutputParameter]:
    otg = Otg(_CONTROL_CYCLE, dofs=inp.degrees_of_freedom)
    output = OutputParameter(dofs=inp.degrees_of_freedom)
    result = otg.calculate(inp, output)
    return int(result), output


def _assert_no_negative_time_intervals(test: unittest.TestCase, trajectory: Trajectory) -> None:
    profile = trajectory.profiles[0][0]
    for i in range(7):
        test.assertGreaterEqual(
            profile.t[i], 0.0, f"time interval t[{i}] must be non-negative, got {profile.t[i]}"
        )


def _assert_acceleration_limit_respected(
    test: unittest.TestCase, trajectory: Trajectory, max_acc: float
) -> None:
    duration = trajectory.duration
    dt = duration / _SAMPLE_COUNT
    for i in range(_SAMPLE_COUNT + 1):
        t = i * dt
        _p, _v, a = trajectory.at_time(t)
        test.assertLessEqual(
            abs(a[0]),
            max_acc + _LIMIT_TOLERANCE,
            f"acceleration {abs(a[0])} exceeds limit {max_acc} at t={t}",
        )


def _assert_velocity_limit_respected(
    test: unittest.TestCase, trajectory: Trajectory, max_vel: float
) -> None:
    duration = trajectory.duration
    dt = duration / _SAMPLE_COUNT
    for i in range(_SAMPLE_COUNT + 1):
        t = i * dt
        _p, v, _a = trajectory.at_time(t)
        test.assertLessEqual(
            abs(v[0]),
            max_vel + _LIMIT_TOLERANCE,
            f"velocity {abs(v[0])} exceeds limit {max_vel} at t={t}",
        )


class TestAccelerationLimitWithNonZeroTargetVelocity(unittest.TestCase):
    """Bug #1: must succeed, and the resulting trajectory must respect its
    own limits throughout."""

    def test_case_1(self) -> None:
        # target_vel=-2.95, max_acc=1.94
        inp = InputParameter(1)
        inp.current_position = [-6.139891324284666]
        inp.current_velocity = [0.0]
        inp.current_acceleration = [0.0]
        inp.target_position = [10.0]
        inp.target_velocity = [-2.9531593910491565]
        inp.target_acceleration = [0.0]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [1.9425898752751283]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"expected trajectory to succeed, got {result!r}")
        _assert_no_negative_time_intervals(self, output.trajectory)
        _assert_acceleration_limit_respected(self, output.trajectory, 1.9425898752751283)
        _assert_velocity_limit_respected(self, output.trajectory, 4.0)

    def test_case_2(self) -> None:
        # target_vel=1.345, max_acc=5.0
        inp = InputParameter(1)
        inp.current_position = [-6.139891324284666]
        inp.current_velocity = [0.0]
        inp.current_acceleration = [0.0]
        inp.target_position = [10.0]
        inp.target_velocity = [1.345062591709465]
        inp.target_acceleration = [0.0]
        inp.max_velocity = [4.0]
        inp.max_acceleration = [5.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        self.assertGreaterEqual(result, 0, f"expected trajectory to succeed, got {result!r}")
        _assert_no_negative_time_intervals(self, output.trajectory)
        _assert_acceleration_limit_respected(self, output.trajectory, 5.0)
        _assert_velocity_limit_respected(self, output.trajectory, 4.0)


class TestNegativeTimeIntervalWithHighLimits(unittest.TestCase):
    """Bug #2: success is not required -- a legitimate failure is
    acceptable. Only asserts that a returned trajectory (if any) never has
    a negative time interval or violates its own limits."""

    def test_case_1_previously_produced_negative_t5(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [-2.2569699192956714]
        inp.current_velocity = [0.6924924339691851]
        inp.current_acceleration = [0.6756694790902418]
        inp.target_position = [6.790054108584006]
        inp.target_velocity = [-1.159379585473221]
        inp.target_acceleration = [-1.2629539618488628]
        inp.max_velocity = [10.0]
        inp.max_acceleration = [10.0]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        if result >= 0:
            _assert_no_negative_time_intervals(self, output.trajectory)
            _assert_acceleration_limit_respected(self, output.trajectory, 10.0)
            _assert_velocity_limit_respected(self, output.trajectory, 10.0)

    def test_case_2_previously_produced_negative_t5(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [2.6603799559471364]
        inp.current_velocity = [1.9695301027900147]
        inp.current_acceleration = [1.972541529001468]
        inp.target_position = [-6.297064289647577]
        inp.target_velocity = [-1.5414200165198237]
        inp.target_acceleration = [-1.5255311582232012]
        inp.max_velocity = [9.088312224669604]
        inp.max_acceleration = [9.973774779735683]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        if result >= 0:
            _assert_no_negative_time_intervals(self, output.trajectory)
            _assert_acceleration_limit_respected(self, output.trajectory, 9.973774779735683)
            _assert_velocity_limit_respected(self, output.trajectory, 9.088312224669604)

    def test_case_3_previously_produced_negative_t5_different_max_vel(self) -> None:
        inp = InputParameter(1)
        inp.current_position = [2.6603799559471364]
        inp.current_velocity = [1.9695301027900147]
        inp.current_acceleration = [1.972541529001468]
        inp.target_position = [-6.297064289647577]
        inp.target_velocity = [-1.5414200165198237]
        inp.target_acceleration = [-1.5255311582232012]
        inp.max_velocity = [6.282291093061675]
        inp.max_acceleration = [9.973774779735683]
        inp.max_jerk = [10.0]

        result, output = _calculate(inp)

        if result >= 0:
            _assert_no_negative_time_intervals(self, output.trajectory)
            _assert_acceleration_limit_respected(self, output.trajectory, 9.973774779735683)
            _assert_velocity_limit_respected(self, output.trajectory, 6.282291093061675)


if __name__ == "__main__":
    unittest.main()
