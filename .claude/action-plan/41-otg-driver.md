---
chunk: 41-otg-driver
track: E
status: pending
depends_on: [40]
spec: ../specs/otg.md §Public API (Otg), §Error semantics, §Compliance 5
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 41 — `Otg` driver

**Deliverable:** the per-cycle driver class and the finished public surface.
Faithful port of `SWIFT_MATH/OTG/spmOTG.swift`.

## Files

- Create: `src/math_tools/otg/otg.py`
- Edit: `src/math_tools/otg/__init__.py` (final `__all__` per spec §Module
  layout)
- Create: `tests/otg/test_otg_driver.py`

## Design constraints

1. `Otg(control_cycle, dofs, max_number_of_waypoints=0)`; `OtgError` for
   structural misuse only (non-positive control_cycle, DOF mismatch between
   constructor and parameters); `update(input, output) -> Result` (validate
   → recalc-on-change → step `output.time` → sample → WORKING/FINISHED),
   `calculate(input, output) -> Result`, `reset()`. Port the input-change
   detection and `interrupt_calculation_duration` handling as the Swift
   does.
2. `calculation_duration` measured with `time.perf_counter_ns()` → µs
   (Swift used DispatchTime).

## TDD steps

1. Failing tests: a 1-DOF rest-to-rest move driven via repeated `update`
   reaches `FINISHED` in ≤ `duration/control_cycle + 2` calls (spec
   invariant); `output.new_position` at each cycle matches
   `trajectory.at_time(output.time)`; invalid input → `ERROR_INVALID_INPUT`
   (no exception); DOF mismatch raises `OtgError`; `pass_to_input` +
   `update` chaining is stable (`new_calculation` False when input
   unchanged).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] FINISHED-within-bound and no-exception error paths pass
- [ ] `math_tools/otg/__init__.py` `__all__` == the spec's export list
      (pinned by test — spec compliance 5)
- [ ] `make uv-fullCheck` passes

## Out of scope

Oracle suites (42); performance tuning.
