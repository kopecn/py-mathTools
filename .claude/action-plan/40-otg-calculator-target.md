---
chunk: 40-otg-calculator-target
track: E
status: pending
depends_on: [32, 35, 36, 37, 38, 39]
spec: ../specs/otg.md §Internal fidelity 3
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 40 — `TargetCalculator`

**Deliverable:** `calculator_target.py` — faithful port of
`SWIFT_MATH/OTG/CalculatorTarget.swift` (~780 lines): per-DOF Step1/Step2
dispatch plus cross-DOF synchronization (Block/Interval logic, the
discrete-duration path, phase sync).

## Files

- Create: `src/math_tools/otg/calculator_target.py`
- Create: `tests/otg/test_calculator_target.py`

## Design constraints

1. Port `calculate(...)` and `synchronize(...)` branch-for-branch: per-DOF
   control-interface dispatch to the step solver classes (36–39), Block
   construction, blocked-interval resolution, `Synchronization` mode
   handling (TIME / TIME_IF_NECESSARY / PHASE / NONE), minimum-duration and
   discrete-duration paths.
2. Error paths return the spec'd `Result` codes
   (`ERROR_EXECUTION_TIME_CALCULATION`, `ERROR_SYNCHRONIZATION_CALCULATION`)
   — no exceptions.
3. Fills a `Trajectory` (chunk 35); consumes `InputParameter` (32).

## TDD steps

1. Failing tests: (a) 1-DOF position case reproduces chunk 38's analytic
   duration through the full calculate path; (b) 3-DOF TIME sync — all DOFs
   report identical trajectory duration equal to the slowest DOF's optimal
   (compose from chunk 38's cases with different distances); (c) NONE sync —
   per-DOF durations equal their independent optima; (d) an `enabled=False`
   DOF stays at its current state; (e) an unsolvable synchronization input
   returns `ERROR_SYNCHRONIZATION_CALCULATION` rather than raising.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] TIME/NONE sync duration semantics pinned; disabled-DOF pinned
- [ ] No `raise` in the calculate path (grep for `raise` → only in
      structural-misuse guards, if any)
- [ ] `make uv-fullCheck` passes

## Out of scope

The `Otg` driver loop (41); waypoints beyond what the Swift implements.
