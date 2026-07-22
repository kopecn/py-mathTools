---
chunk: 37-otg-position-first-second-steps
track: E
status: complete
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5
last_updated: 2026-07-21
semver: 0.0.2
author: Nicholas Bergantz
---

# 37 — Position first/second-order step solvers

**Deliverable:** `steps/position_first_order.py` +
`steps/position_second_order.py`. Faithful ports of
`SWIFT_MATH/OTG/PositionFirstOrderStep1.swift`, `...Step2.swift`,
`PositionSecondOrderStep1.swift`, `...Step2.swift`.

## Files

- Create: `src/math_tools/otg/steps/position_first_order.py`,
  `src/math_tools/otg/steps/position_second_order.py`
- Create: `tests/otg/steps/test_position_first_second.py`

## Design constraints

Same porting rules as chunk 36 (mechanical translation, roots/epsilons from
`functional.roots`, Profile from chunk 33).

## TDD steps

1. Failing tests (analytic): first order (velocity-limited only) —
   `t = |Δp|/v_max`, profile position endpoints exact. Second order
   (velocity+acceleration) — trapezoidal velocity when
   `|Δp| ≥ v_max²/a_max` with
   `t = |Δp|/v_max + v_max/a_max`, else triangular with
   `t = 2·sqrt(|Δp|/a_max)`; pin both, both directions (Δp < 0 exercises
   `Direction.DOWN`). Step2: prescribed duration 2× optimal reaches the
   target position.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Trapezoidal + triangular regimes pinned in both directions
- [x] `make uv-fullCheck` passes

## Out of scope

Third-order steps (38, 39).

## Resolution notes

- **Alias-mutation hazard, per chunk 36's flagged pattern.** Both
  `PositionFirstOrderStep1.get_profile` and
  `PositionSecondOrderStep1.get_profile`'s zero-limits branch reproduce
  Swift's `var p = block.pMin` (a struct value copy) as
  `copy.deepcopy(block.p_min)`, matching
  `VelocitySecondOrderStep1.get_profile`'s identical pattern: without the
  deep copy, a Python alias would let a failed candidate's partial
  mutations corrupt `block.p_min` even though the function returns
  `False` (Swift's local copy is simply discarded on failure).
- **No copy needed in `PositionSecondOrderStep1._time_acc0`/`_time_none`,
  unlike `VelocityThirdOrderStep1`'s equivalent helpers.** The Swift
  source mutates `validProfiles[profileCount]` directly through the array
  subscript on every line -- it never captures a local `var profile =
  validProfiles[profileCount]` first the way
  `VelocityThirdOrderStep1._time_acc0`/`_time_none` do. Python list
  indexing has the same direct-mutation semantics, and `_add_profile`
  always advances to a fresh, distinct `Profile()` instance before the
  next attempt, so a plain mechanical port (no `copy.deepcopy`) already
  reproduces Swift's behavior exactly. Verified this by hand-deriving both
  analytic regimes (trapezoidal and triangular) independently and
  confirming the ported code reproduces them bit-for-bit on the first test
  run -- see the test file's docstrings for the derivations. `valid_profiles`
  is still built as three genuinely separate `Profile()` instances (`[Profile()
  for _ in range(3)]`, never `[Profile()] * 3`), matching the same hazard
  `VelocityThirdOrderStep1` calls out.
- **`PositionSecondOrderStep2` needs no copy at all** (mirrors
  `VelocityThirdOrderStep2`): its methods mutate a single `profile`
  argument passed straight through and always return on first success --
  Python's natural pass-by-reference mutable-object semantics already
  match Swift's `inout` here.
- **Two Swift function parameters are declared but unused in the function
  body** (`PositionSecondOrderStep1.timeAcc0`'s `returnAfterFound` --
  there is only ever one candidate write in that function, so nothing to
  short-circuit; `timeAllSingleStep`'s `aMax`/`aMin` -- only `vMax`/`vMin`
  are threaded into `checkForSecondOrder`). Ported faithfully with
  `del return_after_found` / `del a_max, a_min` (matching `profile.py`'s
  established `del tf` convention for the same situation) rather than
  dropping the parameters, to keep the signatures diff-mappable to the
  Swift source per fidelity requirement 2.
- **Test design.** Point-to-point cases (`v0 = vf = 0`) exercise each
  solver's "no final velocity" branch, matching `TargetCalculator`'s
  expected common usage. First-order: `p0=0, pf=±5, vMax=2` pins `t =
  |Δp|/vMax` in both directions. Second-order: `vMax = aMax = 2.0` =>
  `vMax²/aMax = 2.0`; `pd=6.0` (>= 2.0, `Direction.UP`) pins the
  trapezoidal regime, `pd=-1.0` (< 2.0, `Direction.DOWN`) pins the
  triangular regime -- covering both analytic regimes and both directions
  across the two tests, per the chunk's TDD step. Step2 tests use `tf = 2x`
  the corresponding Step1-optimal duration (per the chunk's TDD step
  wording) and assert the profile reaches the target position and spans
  exactly `tf`. All boundary-array expectations are recomputed
  independently via `integrate_jerk` in the test, per
  `tests/otg/steps/test_velocity_steps.py`'s established convention. All
  ten tests passed on the first run against the mechanically-ported
  implementation, confirming the hand-derived formulas and the port agree.
- No deviations from the plan's file list or design constraints; `otg.md`
  required no contract changes.
