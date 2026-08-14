---
chunk: 42-otg-oracle-suites
track: E
status: complete
depends_on: [41]
spec: ../specs/otg.md §Oracle and test strategy, §Compliance 1–2
last_updated: 2026-07-23
semver: 0.0.3
author: Nicholas Bergantz
---

# 42 — OTG oracle suites

**Deliverable:** the classification corpus, the 31-case numeric truth
table, and the ported continuity/comprehensive/regression suites — the
proof the port is faithful.

## Files

- Create: `tests/otg/data/successful_trajectories.json`,
  `tests/otg/data/failed_trajectories.json` (copied UNMODIFIED from
  `SWIFT_TESTS/OTGTests/truthTables/`),
  `tests/otg/data/otg_numeric_truth.json` (transcribed from the hardcoded
  31-case array in `SWIFT_TESTS/OTGTests/OTGTruthTableTests.swift` — each
  case: inputs + `expectedDuration` + `expectedTimeIntervals`; note the
  transcription source file/lines in a `_meta` key)
- Create: `tests/otg/test_otg_truth_table.py`,
  `tests/otg/test_otg_continuity.py`, `tests/otg/test_otg_comprehensive.py`,
  `tests/otg/test_otg_failure_fixes.py`, `tests/otg/test_otg_invariants.py`

## Design constraints

1. Classification suite: successful cases → `calculate` returns
   `Result >= 0`; failed cases → `Result < 0` (free-text error strings are
   NOT mapped to specific codes). Load through `InputParameter.from_dict`.
2. Numeric suite: per case, duration rtol 1e-6; the selected profile's
   `t` segment times vs `expectedTimeIntervals` atol 1e-6.
3. Continuity: port `OTGContinuityTests.swift` — across consecutive
   `update` cycles, position/velocity/acceleration are continuous
   (|Δ| bounded by the cycle's kinematic limits) including at section
   changes.
4. Comprehensive/failure-fix: port `OTGComprehensiveTests.swift` and
   `OTGFailureFixTests.swift` case-for-case (skip Swift cases that only
   test Swift-specific machinery; list every skip with a reason in the
   test file docstring).
5. Invariants (spec §Oracle 4): seeded random valid inputs — limits never
   exceeded beyond 1e-9, target reached at `duration` within 1e-8,
   FINISHED within `duration/control_cycle + 2` updates.
6. If any oracle case fails: do NOT tune tolerances — the port is wrong;
   report the failing case IDs and stop.

## TDD steps

Oracle-first by construction: land the data + all suites (failing where the
port is wrong), then fix ports via follow-up notes — this chunk itself only
adds tests/data and may not modify `src/`.

## Acceptance criteria

- [x] 100% classification corpus pass (~1,782/1,782 cases)
- [x] 31/31 numeric cases pass -- only 31 cases exist in the Swift source
      (not 32 as originally described in the spec/chunk brief; see
      Resolution notes). otg.md §Oracle and test strategy 2 / §Compliance 1
      were corrected (semver 0.0.4 → 0.0.5) to atol 1e-6 on segment times,
      since the Swift literals are themselves recorded to only 6 decimal
      places and no correct port can satisfy a tighter tolerance. All 31
      cases pass duration rtol 1e-6 and segment-time atol 1e-6.
- [x] Continuity + comprehensive + failure-fix + invariant suites pass
- [x] `git diff --stat` for this chunk touches only `tests/otg/`
- [x] `make uv-fullCheck` passes (full repo) -- 1353 passed, ruff and mypy
      strict clean.

## Out of scope

Any `src/` modification (failures are reported, fixed under the owning
chunk's spec); performance benchmarks.

## Resolution notes

**Data sources.**
- `tests/otg/data/successful_trajectories.json` /
  `failed_trajectories.json` copied byte-for-byte (MD5-verified) from
  `SWIFT_TESTS/OTGTests/truthTables/`.
- `tests/otg/data/otg_numeric_truth.json` transcribed from the `truthTable`
  array literal in `SWIFT_TESTS/OTGTests/OTGTruthTableTests.swift` (lines
  27-490). Transcription was cross-checked mechanically: a standalone
  regex parse of the Swift literal was diffed field-for-field against the
  JSON and found to match exactly (0 mismatches across all 11 numeric
  fields × 31 cases).

**Deviation 1 -- 31 cases, not 32.** otg.md §Oracle and test strategy 2 and
this chunk's own brief both describe "the 32-case hardcoded truth table."
The Swift source array actually contains 31 entries (`Test Case 1` through
`Test Case 31`, no gaps, no duplicated indices; confirmed by both manual
count and the mechanical regex parse above). All 31 real cases are
transcribed and asserted; none were invented or duplicated to reach 32.
Recommend the spec's "32-case" wording be corrected to "31-case" in a
follow-up spec-only change (out of this chunk's scope, since it doesn't
touch `src/` or change test behavior).

**Deviation 2 -- numeric truth table tolerance vs. transcription
precision (design constraint 6 applies: not tuned).** `test_otg_truth_table.py`
implements otg.md's exact mandated tolerances (duration rtol 1e-6, segment
times atol 1e-8). Against those tolerances, 1/31 cases pass in full (case
1, whose expected values happen to be exact round numbers) and all 31 pass
on duration; 30/31 fail the atol-1e-8 segment-time check. Root-cause
analysis (see the case-by-case diffs surfaced by the gate run): every
failing diff is ≤ 4.9e-7 (e.g. case 31 `t[0]`: actual
`1.1093968047096334` vs. expected `1.109397`, diff ≈1.95e-7), which is
exactly the maximum possible rounding error for a value the Swift source
only recorded to 6 decimal places (max rounding error = 5e-7). Every
computed value is consistent with being the correctly-rounded 6-decimal
truncation of the port's own output, and every diff is ~2,000x smaller
than the Swift test's own tolerance (`accuracy: 0.001`) for the identical
assertion. This pattern (uniformly small, uniformly rounding-consistent
diffs, zero outliers, 100% pass on the independent duration assertion)
indicates a data-precision ceiling in the source literal, not a port
defect -- but per design constraint 6 this is reported, not adjudicated:
the test file was written to and left at the spec's literal atol 1e-8 and
is not tuned to pass. Options for a human/spec owner to resolve, not
applied here: (a) relax otg.md's atol to something the 6-decimal source
data can support (e.g. 1e-6), (b) regenerate `otg_numeric_truth.json` from
a higher-precision Swift-side re-run of the same 31 inputs, or (c) accept
the current atol 1e-8 as aspirational/inapplicable to this data source and
scope the compliance check to the duration-only assertion.

**Comprehensive suite skips (design constraint 4).** Documented in
`test_otg_comprehensive.py`'s module docstring: the Swift file's own
`testTruthTable` (3 cases, itself a duplicate subset of
`OTGTruthTableTests.swift`) and its `testSuccessfulTrajectoriesFromJSON`/
`testFailedTrajectoriesFromJSON` (which load the exact same JSON files
copied into `tests/otg/data/` by this chunk) are skipped as exact-data
duplicates of `test_otg_truth_table.py`'s own suites, not ported a second
time under a different tolerance. **Correction (chunk 56, post-audit
finding E-11):** this line originally claimed "All 4 of the Swift file's
`testBugFix_*` cases are ported case-for-case" -- the Swift source in fact
defines 5 `testBugFix_*` cases; `testBugFix_NegativeTimeInterval_Case3` was
missed by this chunk and was ported by chunk 56.

**Invariant suite (design constraint 5) design decisions.** Interpreted
"output never exceeds max velocity/acceleration/jerk beyond 1e-9" as the
`OutputParameter` fields sampled once per `Otg.update()` control cycle
(not a dense continuous re-sample of `at_time`), matching "FINISHED
reached within `duration/control_cycle + 2` update calls," which is
inherently about the discrete `update()` call sequence. Random valid
inputs are rejection-sampled through `InputParameter.validate()` with both
`check_current_state_within_limits` and `check_target_state_within_limits`
set, so a transiently-out-of-limits current state (a deliberate
brake-profile scenario already covered by the classification corpus) is
excluded from this suite's definition of "valid." Seed `20260711`, 50
cases, 0 generation-rejection failures observed; all 3 invariants held for
all 50 cases with 0 failures.

**Gate result (initial).** `make uv-fullCheck`: `uv-lint` clean,
`uv-typecheck` clean (mypy strict, 116 source files), `uv-test` 30 subtest
failures (all in `TestNumericTruthTable`, per Deviation 2 above) out of
1,353 collected top-level test items. No `src/` files were modified;
`git diff --stat` for this chunk touches only new files under
`tests/otg/`.

**Resolution (post-report, human-approved).** Per Deviation 2's option
(a): the user chose to relax otg.md's segment-time atol from 1e-8 to 1e-6
(matching duration rtol; still 500x tighter than the Swift test's own
`accuracy: 0.001`), since the source literals' 6-decimal precision makes
1e-8 unsatisfiable by any correct port. otg.md §Oracle and test strategy 2
and §Compliance 1 updated accordingly (semver 0.0.4 → 0.0.5,
last_updated 2026-07-22); `test_otg_truth_table.py`'s `_TIME_INTERVAL_ATOL`
and `otg_numeric_truth.json`'s `_meta.tolerances` updated to match; all
"32-case" wording corrected to "31-case" throughout (spec, test docstring,
data `_meta`). Re-ran `make uv-fullCheck`: 1353 passed, ruff/mypy clean.
Chunk now genuinely complete against the corrected spec.
