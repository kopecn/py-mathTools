---
chunk: 39-otg-position-third-step2
track: E
status: pending
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5; §Module layout (chunking hints)
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 39 — `PositionThirdOrderStep2` (prescribed-duration)

**Deliverable:** `steps/position_third_order_step2.py` — faithful port of
`SWIFT_MATH/OTG/PositionThirdOrderStep2.swift` (~1,900 lines, the single
largest file in the port). Solves a profile hitting the target at an
EXACT prescribed duration (the synchronization workhorse).

## Files

- Create: `src/math_tools/otg/steps/position_third_order_step2.py`
- Create: `tests/otg/steps/test_position_third_step2.py`

## Design constraints

1. Same mechanical-translation rules as chunk 38. If a single session
   cannot finish, split at Swift function boundaries and leave the
   remaining functions raising `NotImplementedError` with the chunk noted
   `in_progress` — never merge a silently wrong branch.
2. Every polynomial solve routes through `functional.roots`; epsilon
   comparisons use the shared constants.

## TDD steps

1. Failing tests: take chunk 38's three analytic cases, compute their
   optimal durations, then ask Step2 for 1.25×, 1.5×, and 3× that duration —
   assert the returned profile (a) passes `Profile.check`, (b) reaches
   `pf/vf/af` (atol 1e-8), (c) has `t_sum[-1]` equal to the prescribed
   duration (atol 1e-9). Add one negative test: a duration BELOW optimal
   yields no valid profile.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] All three scale factors × three cases pass; below-optimal rejected
- [ ] `make uv-fullCheck` passes

## Out of scope

Step1 changes; TargetCalculator.
