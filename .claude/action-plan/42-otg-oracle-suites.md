---
chunk: 42-otg-oracle-suites
track: E
status: pending
depends_on: [41]
spec: ../specs/otg.md §Oracle and test strategy, §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 42 — OTG oracle suites

**Deliverable:** the classification corpus, the 32-case numeric truth
table, and the ported continuity/comprehensive/regression suites — the
proof the port is faithful.

## Files

- Create: `tests/otg/data/successful_trajectories.json`,
  `tests/otg/data/failed_trajectories.json` (copied UNMODIFIED from
  `SWIFT_TESTS/OTGTests/truthTables/`),
  `tests/otg/data/otg_numeric_truth.json` (transcribed from the hardcoded
  32-case array in `SWIFT_TESTS/OTGTests/OTGTruthTableTests.swift` — each
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
   `t` segment times vs `expectedTimeIntervals` atol 1e-8.
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

- [ ] 100% classification corpus pass; 32/32 numeric cases pass
- [ ] Continuity + comprehensive + failure-fix + invariant suites pass
- [ ] `git diff --stat` for this chunk touches only `tests/otg/`
- [ ] `make uv-fullCheck` passes (full repo)

## Out of scope

Any `src/` modification (failures are reported, fixed under the owning
chunk's spec); performance benchmarks.
