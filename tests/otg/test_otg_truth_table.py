"""Oracle tests: the classification corpus and the numeric truth table.

See ``.claude/specs/otg.md`` §Oracle and test strategy (1)-(2), §Compliance
1, and ``.claude/action-plan/42-otg-oracle-suites.md``'s design constraints
1-2.

Two independent oracle tiers, both driven off data in ``tests/otg/data/``:

1. **Classification corpus** (``successful_trajectories.json`` /
   ``failed_trajectories.json``, ~1,680 / ~100 cases, copied byte-for-byte
   from ``SWIFT_TESTS/OTGTests/truthTables/``): records inputs only, no
   expected numbers. Each successful case must produce a non-error
   ``Result`` (``>= 0``); each failed case must produce an error ``Result``
   (``< 0``). The JSON's free-text ``"error"`` field on failed cases is
   never mapped to a specific error code (design constraint 1) -- it is
   ignored by ``InputParameter.from_dict``.
2. **Numeric truth table** (``otg_numeric_truth.json``, transcribed
   verbatim from the hardcoded Swift array in
   ``SWIFT_TESTS/OTGTests/OTGTruthTableTests.swift``): pins the exact
   trajectory duration and the 7 per-DOF profile segment times
   (``Profile.t``) for 31 specific 1-DOF cases, which is a much stronger
   assertion than "did it succeed" -- it pins which profile branch the
   step solvers select, not just a coincidentally-summable duration.

   The Swift source array (lines 27-490 of ``OTGTruthTableTests.swift``)
   contains 31 entries (Test Case 1..31, no gaps, no duplicated indices)
   -- verified by a mechanical regex parse of the Swift literal compared
   field-for-field against ``otg_numeric_truth.json`` during authoring.
   All 31 are transcribed and asserted.

   Segment-time assertions use atol 1e-6, not a tighter value: the Swift
   literals themselves are recorded to only 6 decimal places, so no
   correct port can satisfy a tighter tolerance than the source data's
   own precision ceiling (max possible rounding error 5e-7). See this
   chunk's Resolution notes for the analysis.
"""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path
from typing import Any

from math_tools.otg.enums import Result
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter

_DATA_DIR = Path(__file__).parent / "data"
_CONTROL_CYCLE = 0.01

_DURATION_RTOL = 1e-6
_TIME_INTERVAL_ATOL = 1e-6


def _load_json(name: str) -> Any:
    with (_DATA_DIR / name).open() as f:
        return json.load(f)


class TestClassificationCorpusSuccessfulCases(unittest.TestCase):
    """otg.md §Oracle and test strategy 1: every case in
    ``successful_trajectories.json`` must ``calculate`` to a non-error
    ``Result`` (``Result >= 0``, i.e. ``WORKING`` or ``FINISHED``)."""

    def test_all_successful_cases_calculate_without_error(self) -> None:
        cases = _load_json("successful_trajectories.json")
        self.assertGreater(len(cases), 0, "successful_trajectories.json is empty")

        failures: list[tuple[int, Result]] = []
        for index, case in enumerate(cases):
            inp = InputParameter.from_dict(case)
            otg = Otg(_CONTROL_CYCLE, dofs=inp.degrees_of_freedom)
            output = OutputParameter(dofs=inp.degrees_of_freedom)

            result = otg.calculate(inp, output)
            if result < 0:
                failures.append((index, result))

        self.assertEqual(
            failures,
            [],
            f"{len(failures)}/{len(cases)} classification-corpus 'successful' cases "
            f"returned an error Result (first few: {failures[:10]})",
        )


class TestClassificationCorpusFailedCases(unittest.TestCase):
    """otg.md §Oracle and test strategy 1: every case in
    ``failed_trajectories.json`` must ``calculate`` to an error ``Result``
    (``Result < 0``). The free-text ``"error"`` field is not asserted
    against a specific error code."""

    def test_all_failed_cases_calculate_to_an_error(self) -> None:
        cases = _load_json("failed_trajectories.json")
        self.assertGreater(len(cases), 0, "failed_trajectories.json is empty")

        unexpected_successes: list[int] = []
        for index, case in enumerate(cases):
            inp = InputParameter.from_dict(case)
            otg = Otg(_CONTROL_CYCLE, dofs=inp.degrees_of_freedom)
            output = OutputParameter(dofs=inp.degrees_of_freedom)

            result = otg.calculate(inp, output)
            if result >= 0:
                unexpected_successes.append(index)

        self.assertEqual(
            unexpected_successes,
            [],
            f"{len(unexpected_successes)}/{len(cases)} classification-corpus 'failed' "
            f"cases unexpectedly succeeded (indices: {unexpected_successes[:10]})",
        )


class TestNumericTruthTable(unittest.TestCase):
    """otg.md §Oracle and test strategy 2, §Compliance 1: the 31-case
    (see module docstring) hardcoded numeric oracle -- duration rtol
    1e-6, segment times atol 1e-8."""

    def test_all_cases_match_expected_duration_and_segment_times(self) -> None:
        data = _load_json("otg_numeric_truth.json")
        cases = data["cases"]
        self.assertGreater(len(cases), 0, "otg_numeric_truth.json has no cases")

        for case in cases:
            with self.subTest(case_id=case["id"], description=case["description"]):
                inp = InputParameter(1)
                inp.current_position = [case["currentPosition"]]
                inp.current_velocity = [case["currentVelocity"]]
                inp.current_acceleration = [case["currentAcceleration"]]
                inp.target_position = [case["targetPosition"]]
                inp.target_velocity = [case["targetVelocity"]]
                inp.target_acceleration = [case["targetAcceleration"]]
                inp.max_velocity = [case["maxVelocity"]]
                inp.max_acceleration = [case["maxAcceleration"]]
                inp.max_jerk = [case["maxJerk"]]

                otg = Otg(_CONTROL_CYCLE, dofs=1)
                output = OutputParameter(dofs=1)
                result = otg.calculate(inp, output)

                self.assertGreaterEqual(
                    result,
                    0,
                    f"case {case['id']}: calculate() failed with {result!r}",
                )

                trajectory = output.trajectory
                self.assertTrue(
                    math.isclose(
                        trajectory.duration, case["expectedDuration"], rel_tol=_DURATION_RTOL
                    ),
                    f"case {case['id']}: duration {trajectory.duration} != "
                    f"expected {case['expectedDuration']} (rtol {_DURATION_RTOL})",
                )

                profile = trajectory.profiles[0][0]
                self.assertEqual(len(profile.t), 7)
                for segment_index, expected_t in enumerate(case["expectedTimeIntervals"]):
                    actual_t = profile.t[segment_index]
                    self.assertTrue(
                        math.isclose(actual_t, expected_t, abs_tol=_TIME_INTERVAL_ATOL),
                        f"case {case['id']}: t[{segment_index}] = {actual_t} != "
                        f"expected {expected_t} (atol {_TIME_INTERVAL_ATOL})",
                    )


if __name__ == "__main__":
    unittest.main()
