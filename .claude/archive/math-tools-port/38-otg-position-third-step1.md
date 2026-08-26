---
chunk: 38-otg-position-third-step1
track: E
status: complete
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5; §Module layout (chunking hints)
last_updated: 2026-07-21
semver: 0.0.2
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

- [x] The three analytic cases pass with segment-time pinning
- [x] Every Swift method name has a snake_case counterpart (reviewer diff spot-check)
- [x] `make uv-fullCheck` passes

## Out of scope

Step2 (39); synchronization; blocks.

## Resolution notes

- **All 11 Swift methods ported 1:1, snake_cased**: `addProfile` →
  `_add_profile`, `resetProfiles` → `_reset_profiles`, `hasProfiles` →
  `_has_profiles`, `timeAllVel` → `_time_all_vel`, `timeAcc0Acc1` →
  `_time_acc0_acc1`, `timeAllNoneAcc0Acc1` → `_time_all_none_acc0_acc1`,
  `timeAcc1VelTwoStep` → `_time_acc1_vel_two_step`, `timeAcc0TwoStep` →
  `_time_acc0_two_step`, `timeVelTwoStep` → `_time_vel_two_step`,
  `timeNoneTwoStep` → `_time_none_two_step`, `timeAllSingleStep` →
  `_time_all_single_step`, `getProfile` → `get_profile`. Confirmed via a
  `grep`-diff of Swift `func` names against Python `def` names (see
  module docstring/report). The chunk description's example names
  (`time_acc0_acc1_vel`, `time_vel`, `time_acc0`) don't literally appear
  in the Swift source (the actual grouping methods are `timeAllVel` /
  `timeAcc0Acc1` / `timeAllNoneAcc0Acc1`); the acceptance criterion (every
  Swift method name has a snake_case counterpart) is satisfied by the
  literal Swift names, which is what was ported.
- **Confirmed dead code, ported anyway**: a source-tree `grep` for
  `timeAcc1VelTwoStep`/`timeAcc0TwoStep`/`timeVelTwoStep`/`timeNoneTwoStep`
  shows zero call sites anywhere in `SWIFT_MATH` outside their own
  declarations -- these four "only for numerical issues" methods are
  genuinely unreachable from `getProfile` in the Swift source too. Ported
  field-for-field per design constraint 2 and documented in the module
  docstring; no dedicated tests target them directly since they cannot be
  exercised through the public `get_profile` entry point (matching how
  `get_profile`'s own reachable paths are the only ones the TDD cases can
  drive).
- **New alias-mutation pattern beyond chunks 36/37**:
  `_time_all_none_acc0_acc1` introduces a pattern not seen in the velocity
  or first/second-order position steps -- the Swift source explicitly
  re-fetches `profile = validProfiles[profileCount]` mid-loop (with its
  own "BUG FIX: Get fresh profile reference..." comment) after a
  non-returning success. Ported as: `copy.deepcopy` on every *save*
  (`self.valid_profiles[self._profile_count] = copy.deepcopy(profile)`,
  severing the alias so later mutations can't corrupt what was just
  saved), but a *plain* reference reassignment for the mid-loop refresh
  itself (pointing `profile` at the fresh, not-yet-saved next slot needs
  no copy). Reasoning recorded in full in the module docstring.
- **Swift/Python IEEE 754 division divergence (new, spec-worthy)**: the
  three hand-derived TDD cases (rest-to-rest short move and the
  moving-start case) both hit a legitimate `t == 0` quartic root in
  `_time_all_none_acc0_acc1`'s NONE loop (whenever the polynomial's
  constant term `-h2_p2/j^2` is zero, `insertIfPositive` accepts `0.0` as
  a valid non-negative root). The subsequent `h0 = h2_none / (2*j*t)` is a
  genuine `0.0/0.0`, which Swift/IEEE754 silently resolves to `nan` (later
  rejected by `Profile.check`'s precision comparisons) but Python's `/`
  raises `ZeroDivisionError` on. Fixed with a small `_ieee754_div` helper
  used only at this one call site (not a blanket division-wrapping sweep).
  otg.md §Internal fidelity requirement 4 was updated (semver 0.0.2 →
  0.0.3) to document this as a recognized, narrowly-scoped port pattern
  for future step-solver chunks (39, `calculator_target`) to watch for
  and reuse rather than rediscover.
- **Three TDD cases, all closed-form, all verified by independent
  re-integration**: (a) long move, ACC0_ACC1_VEL, `t = pd/v_max +
  v_max/a_max + a_max/j_max = 8.0`, segments `[1,1,1,2,1,1,1]`; (b) short
  move, NONE, `t2 = (4*pd/j)**(1/3)` with `t0=t6=t2/2`; (c) moving-start
  (`a0=af=0.5`), NONE, `h2_none` collapses to 0 by choosing `a0=af`,
  reducing the quartic to a cubic with a hand-picked root `t2=2` pinning
  `pd=1.5`. All three additionally assert `profile.limits` matches the
  expected `ReachedLimits` member and reintegrate the returned segment
  times via `integrate_jerk` independently of `Profile`'s own internal
  loop, confirming the final `(p, v, a)` lands on the target state.
- No deviation from the chunk's file list or scope; `Out of scope` items
  (Step2, synchronization, blocks) untouched.
