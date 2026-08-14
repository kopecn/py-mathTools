"""Comprehensive trajectory validation suite.

Port of ``SWIFT_TESTS/OTGTests/OTGComprehensiveTests.swift``. See
``.claude/specs/otg.md`` §Oracle and test strategy 3 and
``.claude/action-plan/42-otg-oracle-suites.md``'s design constraint 4
("port ... case-for-case; skip Swift cases that only test Swift-specific
machinery; list every skip with a reason").

**Ported (5 cases):** the "Bug Fix Tests" section (``testBugFix_*``), which
asserts unconditional success plus the file's own ``validateTrajectory``
helper (no negative time intervals, acceleration/velocity limits held
throughout a 100-sample sweep, AND the final state matches the target
within 0.01) -- strictly stronger than ``test_otg_failure_fixes.py``'s port
of the same inputs from ``OTGFailureFixTests.swift`` (which only checks
limits, not target-reached, and does so under the "may legitimately fail"
contract). Both ports are kept: they assert different things about the
same inputs, matching the two Swift source files' own duplication.

**Chunk 56 correction (post-audit finding E-11).** The Swift source's "Bug
Fix Tests" section defines 5 ``testBugFix_*`` cases, not 4:
``testBugFix_NegativeTimeInterval_Case3`` was missing from this port (this
docstring previously claimed "all 4" were ported, as did
``.claude/action-plan/42-otg-oracle-suites.md``'s Resolution notes -- both
corrected by this chunk). It matters beyond a count: the only prior port of
that exact input (``test_otg_failure_fixes.py``'s ``test_case_3_...``) wraps
every assertion in ``if result >= 0:``, so a regression to an error
``Result`` would silently assert nothing there, whereas
``TestBugFixNegativeTimeInterval.test_case_3`` below asserts unconditional
success, closing that gap.

**Skipped (5 cases), with reasons -- not "Swift-specific machinery" in the
literal sense, but exact-data duplicates of suites this same chunk already
lands, per Decision Framework "Define once, reference everywhere" /
stay-in-scope's minimum-diff default:**

- ``testTruthTable`` (3 cases: Swift's local ``TruthTableData.testCases``,
  itself a copy-pasted subset -- cases 1, 2, and 24 -- of the full 31-case
  array in ``OTGTruthTableTests.swift``): the full 31-case table is already
  transcribed verbatim into ``tests/otg/data/otg_numeric_truth.json`` and
  asserted by ``test_otg_truth_table.py::TestNumericTruthTable`` with a
  *tighter* tolerance (duration rtol 1e-6, segment atol 1e-6, vs. this
  Swift file's 0.001 accuracy on both) -- re-asserting the same 3 inputs
  here with a looser bound would add no coverage.
- ``testSuccessfulTrajectoriesFromJSON`` /
  ``testFailedTrajectoriesFromJSON``: load the exact same
  ``successful_trajectories.json`` / ``failed_trajectories.json`` files
  copied byte-for-byte into ``tests/otg/data/`` by this same chunk, and
  assert exactly the classify-only contract (non-error vs. error
  ``Result``) that ``test_otg_truth_table.py``'s
  ``TestClassificationCorpus*`` classes already assert over the identical
  data.
"""

from __future__ import annotations

import unittest

from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter
from math_tools.otg.trajectory import Trajectory

_CONTROL_CYCLE = 0.01
_LIMIT_TOLERANCE = 0.001
_TARGET_TOLERANCE = 0.01
_SAMPLE_COUNT = 100


def _calculate(inp: InputParameter) -> tuple[int, OutputParameter]:
    otg = Otg(_CONTROL_CYCLE, dofs=inp.degrees_of_freedom)
    output = OutputParameter(dofs=inp.degrees_of_freedom)
    result = otg.calculate(inp, output)
    return int(result), output


def _validate_trajectory(
    test: unittest.TestCase, trajectory: Trajectory, inp: InputParameter
) -> None:
    """``validateTrajectory`` -- no negative time intervals, acceleration
    and velocity limits held throughout, and the final sampled state
    matches the target."""
    profile = trajectory.profiles[0][0]
    for i in range(7):
        test.assertGreaterEqual(
            profile.t[i], 0.0, f"time interval t[{i}] must be non-negative, got {profile.t[i]}"
        )

    duration = trajectory.duration
    dt = duration / _SAMPLE_COUNT
    for i in range(_SAMPLE_COUNT + 1):
        t = i * dt
        _p, v, a = trajectory.at_time(t)
        test.assertLessEqual(
            abs(a[0]),
            inp.max_acceleration[0] + _LIMIT_TOLERANCE,
            f"acceleration {abs(a[0])} exceeds limit {inp.max_acceleration[0]} at t={t}",
        )
        test.assertLessEqual(
            abs(v[0]),
            inp.max_velocity[0] + _LIMIT_TOLERANCE,
            f"velocity {abs(v[0])} exceeds limit {inp.max_velocity[0]} at t={t}",
        )

    final_p, final_v, final_a = trajectory.at_time(duration)
    test.assertAlmostEqual(final_p[0], inp.target_position[0], delta=_TARGET_TOLERANCE)
    test.assertAlmostEqual(final_v[0], inp.target_velocity[0], delta=_TARGET_TOLERANCE)
    test.assertAlmostEqual(final_a[0], inp.target_acceleration[0], delta=_TARGET_TOLERANCE)


class TestBugFixAccelerationLimit(unittest.TestCase):
    """``testBugFix_AccelerationLimit_Case{1,2}`` -- must succeed (no
    "may legitimately fail" escape hatch, unlike the failure-fix port),
    and the full ``validateTrajectory`` contract must hold."""

    def test_case_1(self) -> None:
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
        _validate_trajectory(self, output.trajectory, inp)

    def test_case_2(self) -> None:
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
        _validate_trajectory(self, output.trajectory, inp)


class TestBugFixNegativeTimeInterval(unittest.TestCase):
    """``testBugFix_NegativeTimeInterval_Case{1,2}`` -- same inputs as
    ``test_otg_failure_fixes.py``'s ``TestNegativeTimeIntervalWithHighLimits``
    cases 2 and 1 respectively, but here the Swift source asserts
    unconditional success (no legitimate-failure escape hatch) plus the
    full ``validateTrajectory`` contract."""

    def test_case_1(self) -> None:
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

        self.assertGreaterEqual(result, 0, f"expected trajectory to succeed, got {result!r}")
        _validate_trajectory(self, output.trajectory, inp)

    def test_case_2(self) -> None:
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

        self.assertGreaterEqual(result, 0, f"expected trajectory to succeed, got {result!r}")
        _validate_trajectory(self, output.trajectory, inp)

    def test_case_3(self) -> None:
        """``testBugFix_NegativeTimeInterval_Case3`` -- same input as
        ``test_case_2`` but with a different (lower) ``max_velocity``. Same
        input as ``test_otg_failure_fixes.py``'s
        ``test_case_3_previously_produced_negative_t5_different_max_vel``,
        but here unconditional success plus the full ``validateTrajectory``
        contract are required (post-audit finding E-11)."""
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

        self.assertGreaterEqual(result, 0, f"expected trajectory to succeed, got {result!r}")
        _validate_trajectory(self, output.trajectory, inp)


if __name__ == "__main__":
    unittest.main()
