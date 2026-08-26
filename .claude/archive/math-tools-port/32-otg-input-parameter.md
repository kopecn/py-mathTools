---
chunk: 32-otg-input-parameter
track: E
status: complete
depends_on: [31]
spec: ../specs/otg.md §Public API (InputParameter)
last_updated: 2026-07-21
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

- [x] The embedded truth-table case parses; `==` and codec round-trip pass
- [x] `make uv-fullCheck` passes

## Out of scope

OutputParameter/Trajectory (35); any solver logic.

## Resolution notes

- `validate()` returns `bool` rather than throwing, per `otg.md` §Error
  semantics (per-cycle failures are `Result` codes, never exceptions in this
  port -- `InputParameter.swift`'s `RuckigError` throws are the exception
  this repo's contract explicitly carves against). Each private
  `_validate_*` helper returns `False` at the first violation instead of
  raising with a message, matching the checked branches 1:1 but not the
  error text.
- Deviation from the chunk's literal TDD wording: it lists "zero max jerk"
  as an invalidity class, but Swift's `validateJerkLimits` only rejects
  `jMax.isNaN || jMax < 0.0` -- zero is a legal (if degenerate) limit in the
  Swift source. Ported that check verbatim (reject NaN/negative only) and
  added `test_zero_max_jerk_is_legal` to pin the boundary; the "limit
  positivity" example is instead exercised with a negative max jerk
  (`test_negative_max_jerk_invalidates`).
- The design constraints' parenthetical "enabled handling" does not
  correspond to any branch in `InputParameter.swift`'s `validate()` --
  `enabled` is read only by `CalculatorTarget.swift` (chunk 40, out of
  scope). Ported `enabled` as a stored/equatable/codec field only, with no
  validate() branch, matching the Swift source exactly.
- `__eq__` is implemented as full field equality (including
  `degrees_of_freedom` and `interrupt_calculation_duration`), which is a
  superset of Swift's hand-written `==` (which omits both of those fields).
  No oracle or spec text pins `InputParameter` equality semantics beyond
  "field equality," so the simpler/more defensible full-field comparison
  was chosen; flagging in case downstream chunks assumed the narrower
  Swift-literal behavior.
- `from_dict` ignores unrecognized keys (e.g. the classification corpus'
  `"error"` string on failed cases) rather than rejecting them, so chunk 42
  can feed corpus records straight through the codec without pre-filtering.
- `to_dict` omits `None`-valued optional fields (mirrors Swift's
  `encodeIfPresent`), which is what makes the truth-table round-trip
  produce a dict `==`-equal to the embedded literal.
