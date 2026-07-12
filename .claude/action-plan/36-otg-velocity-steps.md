---
chunk: 36-otg-velocity-steps
track: E
status: pending
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 36 — Velocity-interface step solvers

**Deliverable:** `steps/velocity_second_order.py` +
`steps/velocity_third_order.py`. Faithful ports of
`SWIFT_MATH/OTG/VelocitySecondOrderStep1.swift`, `...Step2.swift`,
`VelocityThirdOrderStep1.swift`, `...Step2.swift`.

## Files

- Create: `src/math_tools/otg/steps/__init__.py`,
  `src/math_tools/otg/steps/velocity_second_order.py`,
  `src/math_tools/otg/steps/velocity_third_order.py`
- Create: `tests/otg/steps/__init__.py`,
  `tests/otg/steps/test_velocity_steps.py`

## Design constraints

1. One class per Swift class, same names (`VelocityThirdOrderStep1` etc.),
   same method names snake_cased, same branch structure — translate
   mechanically; the case analysis encodes the Ruckig profile taxonomy and
   must stay diffable against the Swift.
2. Roots/epsilons exclusively from `math_tools.functional.roots`.
3. Step1 computes the time-optimal profile (fills a `Profile`); Step2
   computes a profile for a prescribed duration. Keep the
   `check`-based validation flow (Profile methods from chunk 33).

## TDD steps

1. Failing tests (analytic, hand-derived in test comments): third-order
   velocity change Δv under jerk limit j and accel limit a — when
   `Δv ≥ a²/j` the optimal profile is trapezoidal-acceleration with
   `t = Δv/a + a/j` total; when `Δv < a²/j` it is triangular with
   `t = 2·sqrt(Δv/j)`. Pin both regimes and the profile's boundary arrays;
   second-order (no jerk limit) `t = Δv/a`. Step2: prescribed duration
   1.5× optimal yields a valid profile hitting the target velocity.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Both analytic regimes pinned for third order; second order pinned
- [ ] Class/method names diff-mappable to the Swift files (reviewer spot-check)
- [ ] `make uv-fullCheck` passes

## Out of scope

Position-interface steps (37–39); synchronization.
