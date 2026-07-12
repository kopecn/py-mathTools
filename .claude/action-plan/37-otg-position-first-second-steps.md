---
chunk: 37-otg-position-first-second-steps
track: E
status: pending
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] Trapezoidal + triangular regimes pinned in both directions
- [ ] `make uv-fullCheck` passes

## Out of scope

Third-order steps (38, 39).
