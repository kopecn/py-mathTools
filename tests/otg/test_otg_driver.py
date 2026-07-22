"""Unit tests for ``math_tools.otg.otg.Otg``.

See ``.claude/specs/otg.md`` §Public API (Otg), §Error semantics,
§Compliance 5 and ``.claude/action-plan/41-otg-driver.md``'s TDD steps: a
1-DOF rest-to-rest move driven via repeated ``update`` reaches ``FINISHED``
within ``duration/control_cycle + 2`` calls; ``output.new_position`` at each
cycle matches ``trajectory.at_time(output.time)``; invalid input returns
``ERROR_INVALID_INPUT`` without raising; a DOF mismatch raises ``OtgError``;
``pass_to_input`` + ``update`` chaining is stable (``new_calculation`` is
``False`` once the input stops changing).

Limits (``v_max=2, a_max=1, j_max=1``) and the closed-form rest-to-rest
optimal duration formula reuse chunk 40's ``test_calculator_target.py``
convention, scaled to a short move (target distance 2.0) so the
control-loop test converges in ~40 cycles instead of thousands.
"""

import math
import unittest

from math_tools.otg import ControlInterface, InputParameter, Otg, OtgError, OutputParameter, Result

_V_MAX = 2.0
_A_MAX = 1.0
_J_MAX = 1.0
_CONTROL_CYCLE = 0.1
_TARGET = 2.0


def _rest_to_rest_optimal_duration(pd: float) -> float:
    """Closed-form time-optimal duration for a rest-to-rest move of
    distance ``pd`` under ``_V_MAX``/``_A_MAX``/``_J_MAX`` (chunk 38/40's
    ``pd / v_max + v_max / a_max + a_max / j_max``)."""
    return pd / _V_MAX + _V_MAX / _A_MAX + _A_MAX / _J_MAX


def _rest_to_rest_input(dofs: int = 1, target: float = _TARGET) -> InputParameter:
    inp = InputParameter(dofs)
    inp.target_position = [target] * dofs
    inp.max_velocity = [_V_MAX] * dofs
    inp.min_velocity = [-_V_MAX] * dofs
    inp.max_acceleration = [_A_MAX] * dofs
    inp.min_acceleration = [-_A_MAX] * dofs
    inp.max_jerk = [_J_MAX] * dofs
    return inp


class TestUpdateLoopReachesFinishedWithinBound(unittest.TestCase):
    """(1)+(2)+(5) drive a 1-DOF rest-to-rest move to completion, checking
    the FINISHED-within-bound invariant, per-cycle sampling consistency
    against ``trajectory.at_time``, and stable ``new_calculation`` chaining
    -- all in one control loop, since they describe the same drive."""

    def test_reaches_finished_within_bound_with_consistent_sampling(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=1)
        inp = _rest_to_rest_input()
        output = OutputParameter(dofs=1)

        expected_duration = _rest_to_rest_optimal_duration(_TARGET)
        max_calls = math.ceil(expected_duration / _CONTROL_CYCLE) + 2

        results = []
        calls = 0
        result = Result.WORKING
        while result != Result.FINISHED:
            calls += 1
            self.assertLessEqual(calls, max_calls, "did not reach FINISHED within bound")

            result = otg.update(inp, output)
            self.assertNotIn(
                result,
                (
                    Result.ERROR,
                    Result.ERROR_INVALID_INPUT,
                    Result.ERROR_TRAJECTORY_DURATION,
                    Result.ERROR_ZERO_LIMITS,
                    Result.ERROR_EXECUTION_TIME_CALCULATION,
                    Result.ERROR_SYNCHRONIZATION_CALCULATION,
                ),
                f"update() returned an error Result on call {calls}: {result!r}",
            )
            results.append((calls, result, output.new_calculation))

            # (2) the just-sampled state must match a fresh independent
            # query of the same trajectory at the same time.
            expected_p, expected_v, expected_a = output.trajectory.at_time(output.time)
            for dof in range(1):
                self.assertAlmostEqual(
                    output.new_position[dof], expected_p[dof], delta=1e-9, msg=f"call {calls}"
                )
                self.assertAlmostEqual(
                    output.new_velocity[dof], expected_v[dof], delta=1e-9, msg=f"call {calls}"
                )
                self.assertAlmostEqual(
                    output.new_acceleration[dof], expected_a[dof], delta=1e-9, msg=f"call {calls}"
                )

            output.pass_to_input(inp)

        self.assertEqual(result, Result.FINISHED)
        self.assertLessEqual(calls, max_calls)

        # (5) new_calculation is True only on the first (recalculating)
        # cycle -- every later cycle reuses the cached trajectory because
        # pass_to_input keeps `inp` and the driver's cached input in sync.
        first_call, _first_result, first_new_calc = results[0]
        self.assertEqual(first_call, 1)
        self.assertTrue(first_new_calc)
        for call_index, _cycle_result, new_calc in results[1:]:
            self.assertFalse(new_calc, f"call {call_index} unexpectedly recalculated")

        # Final position reaches the target.
        self.assertAlmostEqual(output.new_position[0], _TARGET, delta=1e-6)
        self.assertAlmostEqual(output.new_velocity[0], 0.0, delta=1e-6)
        self.assertAlmostEqual(output.new_acceleration[0], 0.0, delta=1e-6)


class TestInvalidInputReturnsErrorWithoutRaising(unittest.TestCase):
    """(3) an invalid input (negative max_jerk) returns
    ``ERROR_INVALID_INPUT`` from both ``calculate`` and ``update``, never
    raising."""

    def _invalid_input(self) -> InputParameter:
        inp = _rest_to_rest_input()
        inp.max_jerk = [-1.0]
        return inp

    def test_calculate_returns_error_invalid_input(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=1)
        output = OutputParameter(dofs=1)

        result = otg.calculate(self._invalid_input(), output)

        self.assertEqual(result, Result.ERROR_INVALID_INPUT)

    def test_update_returns_error_invalid_input(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=1)
        output = OutputParameter(dofs=1)

        result = otg.update(self._invalid_input(), output)

        self.assertEqual(result, Result.ERROR_INVALID_INPUT)

    def test_too_many_intermediate_positions_returns_error_invalid_input(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=1, max_number_of_waypoints=1)
        output = OutputParameter(dofs=1, max_number_of_waypoints=1)
        inp = _rest_to_rest_input()
        inp.control_interface = ControlInterface.POSITION
        inp.intermediate_positions = [[0.5], [1.0], [1.5]]  # exceeds max_number_of_waypoints=1

        result = otg.calculate(inp, output)

        self.assertEqual(result, Result.ERROR_INVALID_INPUT)


class TestDegreesOfFreedomMismatchRaises(unittest.TestCase):
    """(4) a DOF mismatch between the driver and a per-cycle parameter is
    structural misuse -- raises ``OtgError``, not a ``Result`` code."""

    def test_input_dof_mismatch_raises_on_calculate(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=2)
        inp = _rest_to_rest_input(dofs=3)
        output = OutputParameter(dofs=2)

        with self.assertRaises(OtgError):
            otg.calculate(inp, output)

    def test_input_dof_mismatch_raises_on_update(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=2)
        inp = _rest_to_rest_input(dofs=3)
        output = OutputParameter(dofs=2)

        with self.assertRaises(OtgError):
            otg.update(inp, output)

    def test_output_dof_mismatch_raises(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=2)
        inp = _rest_to_rest_input(dofs=2)
        output = OutputParameter(dofs=3)

        with self.assertRaises(OtgError):
            otg.calculate(inp, output)


class TestConstructorStructuralMisuse(unittest.TestCase):
    def test_non_positive_control_cycle_raises(self) -> None:
        with self.assertRaises(OtgError):
            Otg(0.0, dofs=1)
        with self.assertRaises(OtgError):
            Otg(-0.001, dofs=1)

    def test_non_positive_dofs_raises(self) -> None:
        with self.assertRaises(OtgError):
            Otg(_CONTROL_CYCLE, dofs=0)


class TestReset(unittest.TestCase):
    def test_reset_forces_recalculation_on_next_update(self) -> None:
        otg = Otg(_CONTROL_CYCLE, dofs=1)
        inp = _rest_to_rest_input()
        output = OutputParameter(dofs=1)

        otg.update(inp, output)
        self.assertTrue(output.new_calculation)
        output.pass_to_input(inp)

        otg.update(inp, output)
        self.assertFalse(output.new_calculation)
        output.pass_to_input(inp)

        otg.reset()
        otg.update(inp, output)
        self.assertTrue(output.new_calculation)


class TestPublicSurface(unittest.TestCase):
    """otg.md §Compliance 5: the public surface is exactly the
    ``__init__.py`` re-export list, nothing else."""

    def test_all_matches_spec_export_list(self) -> None:
        import math_tools.otg as otg_package

        expected = {
            "ControlInterface",
            "DurationDiscretization",
            "InputParameter",
            "Otg",
            "OtgError",
            "OutputParameter",
            "Profile",
            "Result",
            "Synchronization",
            "Trajectory",
        }
        self.assertEqual(set(otg_package.__all__), expected)
        for name in expected:
            self.assertTrue(hasattr(otg_package, name), f"missing export: {name}")


if __name__ == "__main__":
    unittest.main()
