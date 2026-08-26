"""Unit tests for ``math_tools.otg.enums`` and ``math_tools.otg.errors``.

Pins the wire-stable ``Result`` integer values (Ruckig parity, including the
intentional gap at -103) and the string enums' values against
``.claude/specs/otg.md`` §Public API, transcribed from
``SWIFT_MATH/OTG/enums/*.swift``. See otg.md §Compliance 3.
"""

import unittest

from math_tools.errors import MathToolsError
from math_tools.otg.enums import (
    ControlInterface,
    ControlSigns,
    Direction,
    DurationDiscretization,
    ReachedLimits,
    Result,
    Synchronization,
)
from math_tools.otg.errors import OtgError


class TestResultEnum(unittest.TestCase):
    def test_working_is_zero(self) -> None:
        self.assertEqual(Result.WORKING, 0)

    def test_finished_is_one(self) -> None:
        self.assertEqual(Result.FINISHED, 1)

    def test_error_is_negative_one(self) -> None:
        self.assertEqual(Result.ERROR, -1)

    def test_error_invalid_input_is_negative_100(self) -> None:
        self.assertEqual(Result.ERROR_INVALID_INPUT, -100)

    def test_error_trajectory_duration_is_negative_101(self) -> None:
        self.assertEqual(Result.ERROR_TRAJECTORY_DURATION, -101)

    def test_error_positional_limits_is_negative_102(self) -> None:
        self.assertEqual(Result.ERROR_POSITIONAL_LIMITS, -102)

    def test_error_zero_limits_is_negative_104(self) -> None:
        self.assertEqual(Result.ERROR_ZERO_LIMITS, -104)

    def test_error_execution_time_calculation_is_negative_110(self) -> None:
        self.assertEqual(Result.ERROR_EXECUTION_TIME_CALCULATION, -110)

    def test_error_synchronization_calculation_is_negative_111(self) -> None:
        self.assertEqual(Result.ERROR_SYNCHRONIZATION_CALCULATION, -111)

    def test_result_has_exactly_nine_members(self) -> None:
        self.assertEqual(len(Result), 9)

    def test_negative_103_gap_is_not_a_result(self) -> None:
        with self.assertRaises(ValueError):
            Result(-103)


class TestControlInterfaceEnum(unittest.TestCase):
    def test_position_value(self) -> None:
        self.assertEqual(ControlInterface.POSITION, "Position")

    def test_velocity_value(self) -> None:
        self.assertEqual(ControlInterface.VELOCITY, "Velocity")


class TestSynchronizationEnum(unittest.TestCase):
    def test_time_value(self) -> None:
        self.assertEqual(Synchronization.TIME, "Time")

    def test_time_if_necessary_value(self) -> None:
        self.assertEqual(Synchronization.TIME_IF_NECESSARY, "TimeIfNecessary")

    def test_phase_value(self) -> None:
        self.assertEqual(Synchronization.PHASE, "Phase")

    def test_none_value(self) -> None:
        self.assertEqual(Synchronization.NONE, "None")


class TestDurationDiscretizationEnum(unittest.TestCase):
    def test_continuous_value(self) -> None:
        self.assertEqual(DurationDiscretization.CONTINUOUS, "Continuous")

    def test_discrete_value(self) -> None:
        self.assertEqual(DurationDiscretization.DISCRETE, "Discrete")


class TestControlSignsEnum(unittest.TestCase):
    def test_uddu_value(self) -> None:
        self.assertEqual(ControlSigns.UDDU, "UDDU")

    def test_udud_value(self) -> None:
        self.assertEqual(ControlSigns.UDUD, "UDUD")


class TestDirectionEnum(unittest.TestCase):
    def test_up_value(self) -> None:
        self.assertEqual(Direction.UP, "UP")

    def test_down_value(self) -> None:
        self.assertEqual(Direction.DOWN, "DOWN")


class TestReachedLimitsEnum(unittest.TestCase):
    def test_has_exactly_eight_members(self) -> None:
        self.assertEqual(len(ReachedLimits), 8)

    def test_member_values(self) -> None:
        self.assertEqual(ReachedLimits.ACC0_ACC1_VEL, "ACC0_ACC1_VEL")
        self.assertEqual(ReachedLimits.VEL, "VEL")
        self.assertEqual(ReachedLimits.ACC0, "ACC0")
        self.assertEqual(ReachedLimits.ACC1, "ACC1")
        self.assertEqual(ReachedLimits.ACC0_ACC1, "ACC0_ACC1")
        self.assertEqual(ReachedLimits.ACC0_VEL, "ACC0_VEL")
        self.assertEqual(ReachedLimits.ACC1_VEL, "ACC1_VEL")
        self.assertEqual(ReachedLimits.NONE, "NONE")


class TestOtgError(unittest.TestCase):
    def test_otg_error_subclasses_math_tools_error(self) -> None:
        self.assertTrue(issubclass(OtgError, MathToolsError))

    def test_otg_error_is_catchable_as_math_tools_error(self) -> None:
        with self.assertRaises(MathToolsError):
            raise OtgError("dof mismatch")


if __name__ == "__main__":
    unittest.main()
