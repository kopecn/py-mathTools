"""Invariant tests over seeded random valid inputs.

See ``.claude/specs/otg.md`` §Oracle and test strategy 4 and
``.claude/action-plan/42-otg-oracle-suites.md``'s design constraint 5: for
randomized (seeded) valid inputs --

1. output never exceeds max velocity/acceleration/jerk beyond 1e-9;
2. ``at_time(duration)`` hits the target state within 1e-8;
3. ``FINISHED`` is reached within ``duration/control_cycle + 2`` update
   calls.

Driven through ``Otg.update()`` in a real control loop (the "output" the
spec refers to is ``OutputParameter.new_velocity``/``new_acceleration`` at
each control cycle, matching ``test_otg_driver.py``'s convention), not a
dense continuous re-sampling of ``at_time`` -- this is what a real
consumer of this driver observes each cycle, and is the natural reading of
"output never exceeds ... " (an ``OutputParameter`` field) plus the
"within duration/control_cycle + 2 update calls" framing, which is
inherently about the discrete ``update()`` call sequence.

**Random-input generation.** ``InputParameter.validate()`` rejects a
current/target velocity or acceleration that would push the profile beyond
its own limits once acceleration decays to zero
(``_velocity_at_acceleration_zero``), so candidates are generated with a
comfortable margin (50% of the velocity limit, 30% of the acceleration
limit) and then rejection-sampled through ``validate()`` (with both
``check_current_state_within_limits`` and ``check_target_state_within_limits``
set, since a transiently-out-of-limits *current* state is a deliberate
brake-profile scenario the classification corpus already covers elsewhere,
not part of this suite's "valid input" contract) to guarantee validity
without asserting anything about the algorithm under test.
"""

from __future__ import annotations

import random
import unittest

from math_tools.otg.enums import Result
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter

_SEED = 20260711
_NUM_CASES = 50
_MAX_GENERATION_ATTEMPTS = 200
_CONTROL_CYCLE = 0.05

_LIMIT_TOLERANCE = 1e-9
_TARGET_TOLERANCE = 1e-8

_ERROR_RESULTS = (
    Result.ERROR,
    Result.ERROR_INVALID_INPUT,
    Result.ERROR_TRAJECTORY_DURATION,
    Result.ERROR_POSITIONAL_LIMITS,
    Result.ERROR_ZERO_LIMITS,
    Result.ERROR_EXECUTION_TIME_CALCULATION,
    Result.ERROR_SYNCHRONIZATION_CALCULATION,
)


def _random_valid_input(rng: random.Random) -> InputParameter:
    """Rejection-sample a random 1-DOF ``InputParameter`` that passes
    ``validate()`` with both current and target state checked."""
    for _attempt in range(_MAX_GENERATION_ATTEMPTS):
        max_vel = rng.uniform(1.0, 10.0)
        max_acc = rng.uniform(1.0, 10.0)
        max_jerk = rng.uniform(1.0, 20.0)

        inp = InputParameter(1)
        inp.current_position = [rng.uniform(-10.0, 10.0)]
        inp.target_position = [rng.uniform(-10.0, 10.0)]
        inp.current_velocity = [rng.uniform(-0.5 * max_vel, 0.5 * max_vel)]
        inp.target_velocity = [rng.uniform(-0.5 * max_vel, 0.5 * max_vel)]
        inp.current_acceleration = [rng.uniform(-0.3 * max_acc, 0.3 * max_acc)]
        inp.target_acceleration = [rng.uniform(-0.3 * max_acc, 0.3 * max_acc)]
        inp.max_velocity = [max_vel]
        inp.max_acceleration = [max_acc]
        inp.max_jerk = [max_jerk]

        if inp.validate(
            check_current_state_within_limits=True, check_target_state_within_limits=True
        ):
            return inp

    raise RuntimeError(
        f"could not generate a valid random input in {_MAX_GENERATION_ATTEMPTS} attempts"
    )


def _generate_cases(seed: int, count: int) -> list[InputParameter]:
    rng = random.Random(seed)
    return [_random_valid_input(rng) for _ in range(count)]


class TestRandomizedValidInputInvariants(unittest.TestCase):
    """Drives each seeded-random valid input through a full ``update()``
    control loop and checks all three invariants per case."""

    def test_invariants_hold_for_seeded_random_valid_inputs(self) -> None:
        cases = _generate_cases(_SEED, _NUM_CASES)
        self.assertEqual(len(cases), _NUM_CASES)

        for case_index, inp in enumerate(cases):
            with self.subTest(case_index=case_index):
                otg = Otg(_CONTROL_CYCLE, dofs=1)
                output = OutputParameter(dofs=1)

                # Bound calls generously (the exact optimal duration is not
                # known up front for a random case); refine to the exact
                # `duration / control_cycle + 2` bound once FINISHED is
                # reached and the trajectory's true duration is known.
                max_calls_generous = 100_000

                calls = 0
                result = Result.WORKING
                exact_bound: int | None = None
                while result != Result.FINISHED:
                    calls += 1
                    self.assertLessEqual(
                        calls,
                        max_calls_generous,
                        f"case {case_index}: did not reach FINISHED within a generous bound",
                    )

                    result = otg.update(inp, output)
                    self.assertNotIn(
                        result,
                        _ERROR_RESULTS,
                        f"case {case_index}: update() returned an error Result on call "
                        f"{calls}: {result!r}",
                    )

                    if exact_bound is None:
                        exact_bound = int(
                            output.trajectory.duration / _CONTROL_CYCLE + 2
                        )

                    # (1) output never exceeds max velocity/acceleration/jerk
                    # beyond 1e-9.
                    self.assertLessEqual(
                        abs(output.new_velocity[0]),
                        inp.max_velocity[0] + _LIMIT_TOLERANCE,
                        f"case {case_index} call {calls}: velocity "
                        f"{output.new_velocity[0]} exceeds max_velocity "
                        f"{inp.max_velocity[0]}",
                    )
                    self.assertLessEqual(
                        abs(output.new_acceleration[0]),
                        inp.max_acceleration[0] + _LIMIT_TOLERANCE,
                        f"case {case_index} call {calls}: acceleration "
                        f"{output.new_acceleration[0]} exceeds max_acceleration "
                        f"{inp.max_acceleration[0]}",
                    )
                    self.assertLessEqual(
                        abs(output.new_jerk[0]),
                        inp.max_jerk[0] + _LIMIT_TOLERANCE,
                        f"case {case_index} call {calls}: jerk {output.new_jerk[0]} "
                        f"exceeds max_jerk {inp.max_jerk[0]}",
                    )

                    output.pass_to_input(inp)

                assert exact_bound is not None
                self.assertLessEqual(
                    calls,
                    exact_bound,
                    f"case {case_index}: FINISHED not reached within "
                    f"duration/control_cycle + 2 = {exact_bound} update calls "
                    f"(took {calls})",
                )

                # (2) at_time(duration) hits the target state within 1e-8.
                # `inp.target_*` is never mutated by `pass_to_input` (only
                # `current_*` is), so it still holds this case's original
                # target throughout the loop.
                trajectory = output.trajectory
                final_p, final_v, final_a = trajectory.at_time(trajectory.duration)
                self.assertAlmostEqual(
                    final_p[0], inp.target_position[0], delta=_TARGET_TOLERANCE
                )
                self.assertAlmostEqual(
                    final_v[0], inp.target_velocity[0], delta=_TARGET_TOLERANCE
                )
                self.assertAlmostEqual(
                    final_a[0], inp.target_acceleration[0], delta=_TARGET_TOLERANCE
                )


if __name__ == "__main__":
    unittest.main()
