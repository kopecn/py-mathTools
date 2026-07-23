"""Unit tests for ``math_tools.otg.calculator_target.TargetCalculator``.

See ``.claude/specs/otg.md`` §Internal fidelity requirement 3 and
``.claude/action-plan/40-otg-calculator-target.md``'s TDD steps (a)-(e).
Cases (a)-(c) reuse chunk 38's rest-to-rest ``PositionThirdOrderStep1``
boundary conditions (``v_max=2, a_max=1, j_max=1``, ``pd/v_max +
v_max/a_max + a_max/j_max`` as the closed-form optimal duration) scaled to
different target distances, composed through the full ``calculate()`` path
rather than the bare step solver.
"""

import math
import unittest
from unittest.mock import patch

from math_tools.otg.block import Interval
from math_tools.otg.calculator_target import TargetCalculator
from math_tools.otg.enums import Result, Synchronization
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.trajectory import Trajectory

_V_MAX = 2.0
_A_MAX = 1.0
_J_MAX = 1.0


def _rest_to_rest_optimal_duration(pd: float) -> float:
    """Closed-form time-optimal duration for a rest-to-rest move of
    distance ``pd`` under ``_V_MAX``/``_A_MAX``/``_J_MAX`` (matches chunk
    38's ``expected_total = pf / v_max + v_max / a_max + a_max / j_max``,
    valid whenever the move is long enough to saturate both limits)."""
    return pd / _V_MAX + _V_MAX / _A_MAX + _A_MAX / _J_MAX


def _make_position_input(dofs: int, targets: list[float]) -> InputParameter:
    inp = InputParameter(dofs)
    inp.target_position = list(targets)
    inp.max_velocity = [_V_MAX] * dofs
    inp.min_velocity = [-_V_MAX] * dofs
    inp.max_acceleration = [_A_MAX] * dofs
    inp.min_acceleration = [-_A_MAX] * dofs
    inp.max_jerk = [_J_MAX] * dofs
    return inp


class TestSingleDofMatchesStep1AnalyticDuration(unittest.TestCase):
    """(a) 1-DOF position case reproduces chunk 38's analytic duration
    through the full ``calculate()`` path (the 1-DOF shortcut branch)."""

    def test_matches_chunk_38_long_move_duration_and_segments(self) -> None:
        dofs = 1
        calc = TargetCalculator(dofs)
        inp = _make_position_input(dofs, [10.0])

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)
        expected_duration = _rest_to_rest_optimal_duration(10.0)
        self.assertAlmostEqual(trajectory.duration, expected_duration, delta=1e-9)
        self.assertAlmostEqual(trajectory.cumulative_times[0], expected_duration, delta=1e-9)

        expected_t = [1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0]
        profile = trajectory.profiles[0][0]
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")
        self.assertAlmostEqual(profile.p[-1], 10.0, delta=1e-8)


class TestThreeDofTimeSynchronization(unittest.TestCase):
    """(b) 3-DOF TIME sync -- every DOF reports the same trajectory
    duration, equal to the slowest DOF's own optimal duration."""

    def test_all_dofs_reach_the_slowest_dofs_optimal_duration(self) -> None:
        dofs = 3
        calc = TargetCalculator(dofs)
        targets = [10.0, 5.0, 2.0]
        inp = _make_position_input(dofs, targets)
        inp.synchronization = Synchronization.TIME

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)
        expected_duration = _rest_to_rest_optimal_duration(max(targets))
        self.assertAlmostEqual(trajectory.duration, expected_duration, delta=1e-9)

        for dof in range(dofs):
            profile = trajectory.profiles[0][dof]
            total = profile.t_sum[-1] + profile.brake.duration + profile.accel.duration
            self.assertAlmostEqual(total, expected_duration, delta=1e-8, msg=f"dof {dof}")
            self.assertAlmostEqual(profile.p[-1], targets[dof], delta=1e-6, msg=f"dof {dof}")


class TestThreeDofNoneSynchronization(unittest.TestCase):
    """(c) NONE sync -- per-DOF durations equal their independent optima
    (not stretched to the slowest DOF)."""

    def test_each_dof_keeps_its_own_optimal_duration(self) -> None:
        dofs = 3
        calc = TargetCalculator(dofs)
        targets = [10.0, 5.0, 2.0]
        inp = _make_position_input(dofs, targets)
        inp.synchronization = Synchronization.NONE

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)

        for dof in range(dofs):
            profile = trajectory.profiles[0][dof]
            total = profile.t_sum[-1] + profile.brake.duration + profile.accel.duration
            own_optimum = trajectory.independent_min_durations[dof]
            self.assertAlmostEqual(total, own_optimum, delta=1e-8, msg=f"dof {dof}")
            self.assertAlmostEqual(profile.p[-1], targets[dof], delta=1e-6, msg=f"dof {dof}")

        # Distinct targets (10/5/2) under identical limits must give
        # genuinely distinct independent optima -- otherwise this test
        # can't distinguish NONE sync from TIME sync.
        durations = trajectory.independent_min_durations
        self.assertGreater(durations[0], durations[1])
        self.assertGreater(durations[1], durations[2])

        # The trajectory's own bookkeeping duration is still the max
        # (slowest DOF), used for e.g. FINISHED detection by a driver.
        self.assertAlmostEqual(trajectory.duration, max(durations), delta=1e-9)


class TestDisabledDofStaysAtCurrentState(unittest.TestCase):
    """(d) an ``enabled=False`` DOF stays at its current state."""

    def test_disabled_dof_profile_holds_current_state(self) -> None:
        dofs = 2
        calc = TargetCalculator(dofs)
        inp = _make_position_input(dofs, [10.0, 99.0])  # dof1's target is irrelevant (disabled).
        inp.current_position = [0.0, 3.0]
        inp.current_velocity = [0.0, 0.5]
        inp.current_acceleration = [0.0, 0.1]
        inp.enabled = [True, False]

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)

        disabled_profile = trajectory.profiles[0][1]
        self.assertAlmostEqual(disabled_profile.p[-1], 3.0, delta=1e-12)
        self.assertAlmostEqual(disabled_profile.v[-1], 0.5, delta=1e-12)
        self.assertAlmostEqual(disabled_profile.a[-1], 0.1, delta=1e-12)
        self.assertAlmostEqual(disabled_profile.t_sum[-1], 0.0, delta=1e-12)

        # The enabled DOF must still solve normally.
        enabled_profile = trajectory.profiles[0][0]
        self.assertAlmostEqual(enabled_profile.p[-1], 10.0, delta=1e-6)


class TestTrivialProfileUsesFixedLengthArrays(unittest.TestCase):
    """(f) chunk 45 / post-audit finding E-2: the trivial "already at
    target" branch must produce the same fixed-length ``Profile`` arrays
    (``a``/``v``/``p`` length 8, ``t``/``t_sum``/``j`` length 7) as every
    other path, per ``.claude/specs/otg.md`` §Internal fidelity requirement
    1 -- not the 7-element form that made ``p.p[7]`` raise ``IndexError``.
    """

    def test_trivial_target_profile_arrays_are_fixed_length(self) -> None:
        dofs = 1
        calc = TargetCalculator(dofs)
        inp = _make_position_input(dofs, [0.0])  # current_position defaults to 0.0 -> trivial.

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)
        profile = trajectory.profiles[0][0]
        self.assertEqual(len(profile.p), 8)
        self.assertEqual(len(profile.v), 8)
        self.assertEqual(len(profile.a), 8)
        self.assertEqual(len(profile.t), 7)
        self.assertEqual(len(profile.t_sum), 7)
        self.assertEqual(len(profile.j), 7)


class TestTrivialProfilePositionExtrema(unittest.TestCase):
    """(g) a trajectory parked at a non-zero position (trivial branch)
    must report that position as both min and max extrema, not ``0.0`` --
    requires ``p.pf`` to be set in the trivial branch."""

    def test_parked_trajectory_extrema_report_parked_position(self) -> None:
        dofs = 1
        calc = TargetCalculator(dofs)
        inp = _make_position_input(dofs, [5.0])
        inp.current_position = [5.0]  # already at target -> trivial branch.

        trajectory = Trajectory(dofs)
        result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.WORKING)
        extrema = trajectory.position_extrema()
        self.assertAlmostEqual(extrema[0].min, 5.0, delta=1e-12)
        self.assertAlmostEqual(extrema[0].max, 5.0, delta=1e-12)


class TestUnsolvableSynchronizationReturnsErrorNotRaise(unittest.TestCase):
    """(e) an unsolvable synchronization input returns
    ``ERROR_SYNCHRONIZATION_CALCULATION`` rather than raising.

    ``TargetCalculator._synchronize``'s search is provably complete for any
    ``Block`` state actually produced by a successful Step1 call: a DOF's
    own ``t_min`` is never self-blocked at its own boundary, and neither is
    an ``Interval``'s own ``right`` edge (``Interval.is_blocked`` excludes
    both endpoints). Reaching "no candidate found" through a *naturally*
    Step1-derived ``InputParameter`` would require an adversarial multi-DOF
    interval coincidence that is impractical to hand-derive, so this is
    exercised two ways instead: directly, with a hand-built ``Block`` state
    proven (by construction, see the docstring below) to block every finite
    candidate; and through ``calculate()`` itself, with ``_synchronize``
    forced to fail via ``unittest.mock.patch.object`` to confirm the error
    propagates to the ``Result`` code without an exception.
    """

    def test_synchronize_returns_false_without_raising_when_all_candidates_blocked(self) -> None:
        calc = TargetCalculator(2)
        calc._inp_per_dof_synchronization = [Synchronization.TIME, Synchronization.TIME]

        # dof0: reachable only at t == 1.0 exactly (blocked for every t > 1.0
        # via an interval with an infinite right edge).
        calc._blocks[0].t_min = 1.0
        calc._blocks[0].a = Interval(1.0, math.inf)

        # dof1: its own t_min floor (2.0) blocks dof0's only escape point
        # (t == 1.0 < 2.0 == dof1.t_min -> Block.is_blocked(1.0) is True for
        # dof1), and dof1 contributes no interval of its own beyond that.
        calc._blocks[1].t_min = 2.0

        trajectory = Trajectory(2)
        found, _t_sync, _limiting_dof = calc._synchronize(
            None, trajectory.profiles[0], discrete_duration=False, delta_time=0.001
        )

        self.assertFalse(found)

    def test_calculate_propagates_synchronization_failure_without_raising(self) -> None:
        dofs = 2
        calc = TargetCalculator(dofs)
        inp = _make_position_input(dofs, [10.0, 5.0])

        trajectory = Trajectory(dofs)
        with patch.object(TargetCalculator, "_synchronize", return_value=(False, 0.0, None)):
            result = calc.calculate(inp, trajectory, delta_time=0.001)

        self.assertEqual(result, Result.ERROR_SYNCHRONIZATION_CALCULATION)


if __name__ == "__main__":
    unittest.main()
