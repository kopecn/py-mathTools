---
chunk: 32-otg-input-parameter
track: E
status: pending
depends_on: [31]
spec: ../specs/otg.md §Public API (InputParameter)
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 32 — `InputParameter`

**Deliverable:** the per-cycle input struct with validation and wire codec.

## Files

- Create: `src/math_tools/otg/input_parameter.py`
- Edit: `src/math_tools/otg/__init__.py` (export)
- Create: `tests/otg/test_input_parameter.py`

## Design constraints

1. Field-for-field port of `SWIFT_MATH/OTG/InputParameter.swift` (read it
   first; snake_case the names): state/target arrays, limits, optional
   min/positional limits, `enabled`, per-DOF interface/sync overrides,
   `intermediate_positions`, per-section arrays, `minimum_duration`,
   `interrupt_calculation_duration`. Constructor `InputParameter(dofs)`
   fills the Swift defaults (arrays sized to dofs).
2. `validate(check_current_state_within_limits=False,
   check_target_state_within_limits=True) -> bool` — port the Swift checks
   (NaN/inf, limit positivity, target within limits, enabled handling)
   branch-for-branch.
3. `==` field equality; `to_dict`/`from_dict` with the camelCase keys from
   `SWIFT_MATH/OTG/extensions/InputParameter+codable.swift` — these keys
   MUST match the truth-table JSON corpus (chunk 42 loads it through this
   codec).
4. `list[float]` fields, stdlib only.

## TDD steps

1. Failing tests: default construction shapes; a valid input validates; each
   invalidity class (zero max jerk, target velocity over limit, NaN) flips
   `validate()`; `from_dict` on one literal case copied verbatim out of
   `successful_trajectories.json` (embed the dict in the test) round-trips
   `to_dict`.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] The embedded truth-table case parses; `==` and codec round-trip pass
- [ ] `make uv-fullCheck` passes

## Out of scope

OutputParameter/Trajectory (35); any solver logic.
