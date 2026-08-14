"""Unit tests for ``math_tools.otg.output_parameter.OutputParameter``.

See ``.claude/specs/otg.md`` §Public API (OutputParameter) and
``.claude/action-plan/35-otg-trajectory-and-output.md``'s TDD steps:
``pass_to_input`` must copy every kinematic field, asserted against a
sentinel-filled ``InputParameter``.
"""

import unittest

from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.output_parameter import OutputParameter


class TestDefaultConstruction(unittest.TestCase):
    def test_default_field_shapes(self) -> None:
        output = OutputParameter(dofs=2)
        self.assertEqual(output.degrees_of_freedom, 2)
        self.assertEqual(output.new_position, [0.0, 0.0])
        self.assertEqual(output.new_velocity, [0.0, 0.0])
        self.assertEqual(output.new_acceleration, [0.0, 0.0])
        self.assertEqual(output.new_jerk, [0.0, 0.0])
        self.assertEqual(output.time, 0.0)
        self.assertEqual(output.new_section, 0)
        self.assertFalse(output.did_section_change)
        self.assertFalse(output.new_calculation)
        self.assertEqual(output.calculation_duration, 0.0)
        self.assertEqual(output.trajectory.degrees_of_freedom, 2)

    def test_rejects_non_positive_dofs(self) -> None:
        with self.assertRaises(ValueError):
            OutputParameter(dofs=0)

    def test_max_number_of_waypoints_sizes_trajectory_sections(self) -> None:
        output = OutputParameter(dofs=1, max_number_of_waypoints=3)
        self.assertEqual(len(output.trajectory.profiles), 4)


class TestPassToInputFieldCoverage(unittest.TestCase):
    def _sentinel_input(self, dofs: int) -> InputParameter:
        input_parameter = InputParameter(dofs=dofs)
        input_parameter.current_position = [-999.0] * dofs
        input_parameter.current_velocity = [-999.0] * dofs
        input_parameter.current_acceleration = [-999.0] * dofs
        return input_parameter

    def test_copies_every_kinematic_field(self) -> None:
        dofs = 3
        output = OutputParameter(dofs=dofs)
        output.new_position = [1.0, 2.0, 3.0]
        output.new_velocity = [4.0, 5.0, 6.0]
        output.new_acceleration = [7.0, 8.0, 9.0]

        input_parameter = self._sentinel_input(dofs)
        output.pass_to_input(input_parameter)

        for dof in range(dofs):
            self.assertEqual(input_parameter.current_position[dof], output.new_position[dof])
            self.assertEqual(input_parameter.current_velocity[dof], output.new_velocity[dof])
            self.assertEqual(
                input_parameter.current_acceleration[dof], output.new_acceleration[dof]
            )

    def test_section_change_removes_first_intermediate_position(self) -> None:
        output = OutputParameter(dofs=1)
        output.did_section_change = True
        input_parameter = self._sentinel_input(1)
        input_parameter.intermediate_positions = [[1.0], [2.0]]

        output.pass_to_input(input_parameter)

        self.assertEqual(input_parameter.intermediate_positions, [[2.0]])

    def test_no_section_change_keeps_intermediate_positions(self) -> None:
        output = OutputParameter(dofs=1)
        output.did_section_change = False
        input_parameter = self._sentinel_input(1)
        input_parameter.intermediate_positions = [[1.0], [2.0]]

        output.pass_to_input(input_parameter)

        self.assertEqual(input_parameter.intermediate_positions, [[1.0], [2.0]])

    def test_section_change_with_no_intermediate_positions_is_a_no_op(self) -> None:
        output = OutputParameter(dofs=1)
        output.did_section_change = True
        input_parameter = self._sentinel_input(1)

        output.pass_to_input(input_parameter)  # must not raise

        self.assertEqual(input_parameter.intermediate_positions, [])

    def test_mismatched_array_size_raises(self) -> None:
        output = OutputParameter(dofs=2)
        output.new_position = [1.0]  # wrong length
        input_parameter = self._sentinel_input(2)

        with self.assertRaises(ValueError):
            output.pass_to_input(input_parameter)


class TestRepr(unittest.TestCase):
    def test_repr_contains_field_labels(self) -> None:
        output = OutputParameter(dofs=1)
        text = repr(output)
        self.assertIn("out.new_position", text)
        self.assertIn("out.new_velocity", text)
        self.assertIn("out.new_acceleration", text)
        self.assertIn("out.new_jerk", text)
        self.assertIn("out.time", text)
        self.assertIn("out.calculation_duration", text)
