---
chunk: 34-otg-block-brake-bound
track: E
status: pending
depends_on: [33]
spec: ../specs/otg.md §Internal fidelity 3–5
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 34 — `Block`, `BrakeProfile`, `Bound`, `Interval`

**Deliverable:** the block-interval synchronization support types and the
brake pre-trajectory. Faithful ports of `SWIFT_MATH/OTG/Block.swift`,
`Brake.swift`, `Bound.swift`.

## Files

- Create: `src/math_tools/otg/block.py` (Block + Interval),
  `src/math_tools/otg/brake.py`, `src/math_tools/otg/bound.py`
- Edit: `src/math_tools/otg/profile.py` ONLY if chunk 33 left the
  BrakeProfile fields as deferred placeholders (wire the real type in)
- Create: `tests/otg/test_block.py`, `tests/otg/test_brake.py`

## Design constraints

1. `bound.py`: `Bound` (min/max/t_min/t_max) — plain mutable dataclass.
2. `brake.py`: `BrakeProfile` — port `finalize`, `finalize_second_order`,
   `acceleration_brake`, `velocity_brake`,
   `get_position_brake_trajectory`, `get_velocity_brake_trajectory`,
   `v_at_t`, `v_at_a_zero`, `==` branch-for-branch.
3. `block.py`: `Block` (`p_min`, `t_min`, optional intervals `a`/`b`,
   `calculate_block`, `is_blocked`, `get_profile`) and `Interval`
   (`left`/`right`/`profile`). Preserve the blocked-interval selection
   logic exactly — it drives synchronization in chunk 40.
4. Stdlib `math` + `functional.roots` only.

## TDD steps

1. Failing tests: brake — a state exceeding max acceleration produces a
   non-zero brake duration and `v_at_t(0)` equals the initial velocity;
   a within-limits state produces an empty brake (t[0] == 0). Block —
   `is_blocked` boundary behavior at interval edges; `get_profile` returns
   the interval's profile for an in-interval t.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Brake zero/non-zero cases pass; interval edge cases pinned
- [ ] `make uv-fullCheck` passes

## Out of scope

Step solvers; TargetCalculator.
