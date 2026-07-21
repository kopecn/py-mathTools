"""Unit tests for ``math_tools.otg.input_parameter.InputParameter``.

Field-for-field port of ``SWIFT_MATH/OTG/InputParameter.swift`` (validation
logic) and ``SWIFT_MATH/OTG/extensions/InputParameter+codable.swift`` (wire
codec). See ``.claude/specs/otg.md`` §Public API (InputParameter) and
``.claude/action-plan/32-otg-input-parameter.md``.

Deviation from the chunk's literal wording: the chunk lists "zero max jerk"
as an invalidity class, but the Swift ``validateJerkLimits`` only rejects
``jMax.isNaN || jMax < 0.0`` -- zero is a legal (if degenerate) jerk limit.
The "limit positivity" check is exercised here with a *negative* max jerk,
the actual boundary the Swift source enforces (see Resolution notes in the
chunk file).
"""

import math
import unittest

from math_tools.otg.enums import (
    ControlInterface,
    DurationDiscretization,
    Synchronization,
)
from math_tools.otg.input_parameter import InputParameter

# Copied verbatim from spmMathTools' truthTables/successful_trajectories.json
# (first entry), per otg.md §Oracle and test strategy.
_TRUTH_TABLE_CASE = {
    "degreesOfFreedom": 1,
    "controlInterface": "Position",
    "synchronization": "Time",
    "durationDiscretization": "Continuous",
    "currentPosition": [6.649087426675152],
    "currentVelocity": [-1.7196585619659843],
    "currentAcceleration": [-3.6835022695742996],
    "targetPosition": [-4.632519332535045],
    "targetVelocity": [1.9218188748830034],
    "targetAcceleration": [5.820923498653984],
    "maxVelocity": [2.36187254995664],
    "maxAcceleration": [8.000641420127906],
    "maxJerk": [13.235404890387207],
    "intermediatePositions": [],
    "enabled": [True],
}


def _valid_single_dof() -> InputParameter:
    inp = InputParameter(1)
    inp.current_position = [0.0]
    inp.current_velocity = [0.0]
    inp.current_acceleration = [0.0]
    inp.target_position = [1.0]
    inp.target_velocity = [0.0]
    inp.target_acceleration = [0.0]
    inp.max_velocity = [1.0]
    inp.max_acceleration = [1.0]
    inp.max_jerk = [1.0]
    return inp


class TestConstruction(unittest.TestCase):
    def test_degrees_of_freedom_stored(self) -> None:
        self.assertEqual(InputParameter(3).degrees_of_freedom, 3)

    def test_zero_dofs_raises(self) -> None:
        with self.assertRaises(ValueError):
            InputParameter(0)

    def test_negative_dofs_raises(self) -> None:
        with self.assertRaises(ValueError):
            InputParameter(-1)

    def test_kinematic_state_arrays_sized_and_zeroed(self) -> None:
        inp = InputParameter(3)
        self.assertEqual(inp.current_position, [0.0, 0.0, 0.0])
        self.assertEqual(inp.current_velocity, [0.0, 0.0, 0.0])
        self.assertEqual(inp.current_acceleration, [0.0, 0.0, 0.0])
        self.assertEqual(inp.target_position, [0.0, 0.0, 0.0])
        self.assertEqual(inp.target_velocity, [0.0, 0.0, 0.0])
        self.assertEqual(inp.target_acceleration, [0.0, 0.0, 0.0])

    def test_max_velocity_defaults_zero(self) -> None:
        self.assertEqual(InputParameter(2).max_velocity, [0.0, 0.0])

    def test_max_acceleration_defaults_infinite(self) -> None:
        self.assertEqual(InputParameter(2).max_acceleration, [math.inf, math.inf])

    def test_max_jerk_defaults_infinite(self) -> None:
        self.assertEqual(InputParameter(2).max_jerk, [math.inf, math.inf])

    def test_enabled_defaults_true(self) -> None:
        self.assertEqual(InputParameter(2).enabled, [True, True])

    def test_control_configuration_defaults(self) -> None:
        inp = InputParameter(1)
        self.assertEqual(inp.control_interface, ControlInterface.POSITION)
        self.assertEqual(inp.synchronization, Synchronization.TIME)
        self.assertEqual(inp.duration_discretization, DurationDiscretization.CONTINUOUS)

    def test_optional_fields_default_none(self) -> None:
        inp = InputParameter(1)
        self.assertIsNone(inp.min_velocity)
        self.assertIsNone(inp.min_acceleration)
        self.assertIsNone(inp.max_position)
        self.assertIsNone(inp.min_position)
        self.assertIsNone(inp.per_section_max_velocity)
        self.assertIsNone(inp.per_section_max_acceleration)
        self.assertIsNone(inp.per_section_max_jerk)
        self.assertIsNone(inp.per_section_min_velocity)
        self.assertIsNone(inp.per_section_min_acceleration)
        self.assertIsNone(inp.per_section_max_position)
        self.assertIsNone(inp.per_section_min_position)
        self.assertIsNone(inp.per_dof_control_interface)
        self.assertIsNone(inp.per_dof_synchronization)
        self.assertIsNone(inp.minimum_duration)
        self.assertIsNone(inp.per_section_minimum_duration)
        self.assertIsNone(inp.interrupt_calculation_duration)

    def test_intermediate_positions_defaults_empty(self) -> None:
        self.assertEqual(InputParameter(1).intermediate_positions, [])


class TestValidate(unittest.TestCase):
    def test_valid_input_validates(self) -> None:
        self.assertTrue(_valid_single_dof().validate())

    def test_negative_max_jerk_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.max_jerk = [-1.0]
        self.assertFalse(inp.validate())

    def test_zero_max_jerk_is_legal(self) -> None:
        # Swift's validateJerkLimits only rejects NaN or < 0.0; zero is legal.
        inp = _valid_single_dof()
        inp.max_jerk = [0.0]
        self.assertTrue(inp.validate())

    def test_nan_max_jerk_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.max_jerk = [math.nan]
        self.assertFalse(inp.validate())

    def test_negative_max_acceleration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.max_acceleration = [-1.0]
        self.assertFalse(inp.validate())

    def test_positive_min_acceleration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.min_acceleration = [1.0]
        self.assertFalse(inp.validate())

    def test_nan_current_acceleration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.current_acceleration = [math.nan]
        self.assertFalse(inp.validate())

    def test_nan_target_acceleration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.target_acceleration = [math.nan]
        self.assertFalse(inp.validate())

    def test_negative_max_velocity_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.max_velocity = [-1.0]
        self.assertFalse(inp.validate())

    def test_positive_min_velocity_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.min_velocity = [1.0]
        self.assertFalse(inp.validate())

    def test_target_velocity_over_limit_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.target_velocity = [2.0]  # max_velocity is 1.0
        self.assertFalse(inp.validate(check_target_state_within_limits=True))
        self.assertFalse(inp.validate())

    def test_nan_target_velocity_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.target_velocity = [math.nan]
        self.assertFalse(inp.validate())

    def test_current_state_out_of_limits_ignored_by_default(self) -> None:
        inp = _valid_single_dof()
        inp.current_velocity = [5.0]  # exceeds max_velocity of 1.0
        self.assertTrue(inp.validate())

    def test_current_state_out_of_limits_checked_when_requested(self) -> None:
        inp = _valid_single_dof()
        inp.current_velocity = [5.0]
        self.assertFalse(inp.validate(check_current_state_within_limits=True))

    def test_velocity_check_skipped_for_velocity_control_interface(self) -> None:
        inp = _valid_single_dof()
        inp.control_interface = ControlInterface.VELOCITY
        inp.target_velocity = [1000.0]  # would exceed max_velocity under Position
        self.assertTrue(inp.validate())

    def test_nan_current_position_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.current_position = [math.nan]
        self.assertFalse(inp.validate())

    def test_nan_target_position_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.target_position = [math.nan]
        self.assertFalse(inp.validate())

    def test_intermediate_positions_with_minimum_duration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        inp.minimum_duration = 1.0
        self.assertFalse(inp.validate())

    def test_intermediate_positions_with_discrete_duration_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        inp.duration_discretization = DurationDiscretization.DISCRETE
        self.assertFalse(inp.validate())

    def test_intermediate_positions_with_per_dof_control_interface_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        inp.per_dof_control_interface = [ControlInterface.POSITION]
        self.assertFalse(inp.validate())

    def test_intermediate_positions_with_per_dof_synchronization_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        inp.per_dof_synchronization = [Synchronization.TIME]
        self.assertFalse(inp.validate())

    def test_intermediate_positions_with_infinite_jerk_invalidates(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        inp.max_jerk = [math.inf]
        self.assertFalse(inp.validate())

    def test_intermediate_positions_otherwise_valid(self) -> None:
        inp = _valid_single_dof()
        inp.intermediate_positions = [[0.5]]
        self.assertTrue(inp.validate())


class TestEquality(unittest.TestCase):
    def test_equal_when_all_fields_match(self) -> None:
        self.assertEqual(_valid_single_dof(), _valid_single_dof())

    def test_not_equal_when_a_field_differs(self) -> None:
        a = _valid_single_dof()
        b = _valid_single_dof()
        b.target_position = [2.0]
        self.assertNotEqual(a, b)

    def test_not_equal_to_other_type(self) -> None:
        self.assertNotEqual(_valid_single_dof(), object())


class TestCodec(unittest.TestCase):
    def test_from_dict_parses_truth_table_case(self) -> None:
        inp = InputParameter.from_dict(_TRUTH_TABLE_CASE)
        self.assertEqual(inp.degrees_of_freedom, 1)
        self.assertEqual(inp.control_interface, ControlInterface.POSITION)
        self.assertEqual(inp.current_position, [6.649087426675152])
        self.assertEqual(inp.max_jerk, [13.235404890387207])
        self.assertEqual(inp.enabled, [True])

    def test_round_trip_truth_table_case(self) -> None:
        inp = InputParameter.from_dict(_TRUTH_TABLE_CASE)
        self.assertEqual(inp.to_dict(), _TRUTH_TABLE_CASE)

    def test_round_trip_with_optional_fields(self) -> None:
        inp = _valid_single_dof()
        inp.min_velocity = [-2.0]
        inp.min_acceleration = [-3.0]
        inp.max_position = [10.0]
        inp.min_position = [-10.0]
        inp.per_section_max_velocity = [[1.0], [2.0]]
        inp.per_dof_control_interface = [ControlInterface.POSITION]
        inp.per_dof_synchronization = [Synchronization.PHASE]
        inp.minimum_duration = 5.0
        inp.per_section_minimum_duration = [1.0, 2.0]
        inp.interrupt_calculation_duration = 0.5

        round_tripped = InputParameter.from_dict(inp.to_dict())
        self.assertEqual(inp, round_tripped)
        self.assertEqual(
            round_tripped.interrupt_calculation_duration,
            0.5,
        )

    def test_to_dict_omits_none_optional_fields(self) -> None:
        data = _valid_single_dof().to_dict()
        self.assertNotIn("minVelocity", data)
        self.assertNotIn("minAcceleration", data)
        self.assertNotIn("maxPosition", data)
        self.assertNotIn("minPosition", data)
        self.assertNotIn("perSectionMaxVelocity", data)
        self.assertNotIn("perDofControlInterface", data)
        self.assertNotIn("perDofSynchronization", data)
        self.assertNotIn("minimumDuration", data)
        self.assertNotIn("perSectionMinimumDuration", data)
        self.assertNotIn("interruptCalculationDuration", data)

    def test_from_dict_ignores_unknown_keys(self) -> None:
        data = dict(_TRUTH_TABLE_CASE)
        data["error"] = "\n[ruckig] target velocity exceeds its maximum velocity limit."
        inp = InputParameter.from_dict(data)
        self.assertEqual(inp.degrees_of_freedom, 1)


if __name__ == "__main__":
    unittest.main()
