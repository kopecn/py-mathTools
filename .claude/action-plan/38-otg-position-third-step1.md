---
chunk: 38-otg-position-third-step1
track: E
status: pending
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5; §Module layout (chunking hints)
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 38 — `PositionThirdOrderStep1` (time-optimal)

**Deliverable:** `steps/position_third_order_step1.py` — faithful port of
`SWIFT_MATH/OTG/PositionThirdOrderStep1.swift` (~850 lines). This is the
time-optimal profile finder for the full jerk-limited position interface.

## Files

- Create: `src/math_tools/otg/steps/position_third_order_step1.py`
- Create: `tests/otg/steps/test_position_third_step1.py`

## Design constraints

1. Mechanical translation: one Python method per Swift method
   (`time_acc0_acc1_vel`, `time_vel`, `time_acc0`, … — keep every profile-
   family case), same guard order, same use of `solve_cubic`/
   `solve_quartic_monic`/`shrink_interval` from `functional.roots`.
2. Do NOT simplify algebra or merge branches; if a Swift branch looks dead,
   port it anyway and note it.
3. The class's public entry mirrors the Swift `getProfile`-style API filling
   candidate `Profile`s and selecting valid ones via `Profile.check`.

## TDD steps

1. Failing tests: three hand-derivable cases — (a) rest-to-rest long move
   (all limits reached: ACC0_ACC1_VEL profile; total time
   `t = Δp/v + v/a + a/j` +symmetric phases — derive in the test comment),
   (b) rest-to-rest short move (jerk-dominated, no limit reached), (c) a
   moving-start case with a0 ≠ 0. Assert total duration (atol 1e-9) AND the
   7 segment times of the selected profile (this is what chunk 42's numeric
   oracle will lean on).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] The three analytic cases pass with segment-time pinning
- [ ] Every Swift method name has a snake_case counterpart (reviewer diff spot-check)
- [ ] `make uv-fullCheck` passes

## Out of scope

Step2 (39); synchronization; blocks.
