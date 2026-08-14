---
chunk: 36-otg-velocity-steps
track: E
status: complete
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5
last_updated: 2026-07-21
semver: 0.0.2
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

- [x] Both analytic regimes pinned for third order; second order pinned
- [x] Class/method names diff-mappable to the Swift files (reviewer spot-check)
- [x] `make uv-fullCheck` passes

## Out of scope

Position-interface steps (37–39); synchronization.

## Resolution notes

- **Struct-value-copy semantics (the load-bearing decision this chunk had to
  make).** `Profile` is a Python class (reference type); Swift's `Profile`
  is a struct (value type). Several Swift lines are `var x = someProfile`
  followed by conditional keep-or-discard based on a `check*` call's
  success. A naive Python port (`x = some_profile`, a plain alias) would
  silently break correctness in two spots:
  - `VelocityThirdOrderStep1._time_acc0`/`_time_none`: Swift captures `var
    profile = validProfiles[profileCount]` **once** and reuses it across
    Solution 1 and Solution 2 within the same call. If Solution 1 succeeds
    (`validProfiles[profileCount] = profile`, a struct copy in Swift) and
    Solution 2 then mutates the same local further, Swift's copy already
    diverged from the array slot — the saved Solution 1 candidate is safe.
    A Python alias would let Solution 2's mutations retroactively corrupt
    the already-recorded Solution 1 profile. Fixed by `copy.deepcopy` at
    the read (`profile = copy.deepcopy(self.valid_profiles[...])`) **and**
    at each save (`self.valid_profiles[...] = copy.deepcopy(profile)`).
  - `VelocitySecondOrderStep1.get_profile` / `VelocityThirdOrderStep1`'s
    zero-limits branch: `var p = block.pMin` then `p.setBoundary(input)`
    — on failure Swift's `block.pMin` is untouched (the local copy is
    discarded); a Python alias would leave `block.p_min` mutated with
    partial/garbage state even though the function returned `False`. Fixed
    by `copy.deepcopy(block.p_min)` before mutating.
  All four `Profile` field types (float, list[float], `BrakeProfile`, `str`
  enum members) are plain and deepcopy-safe; no changes to `profile.py`
  were needed or made (out of scope, and unnecessary).
- **`VelocityThirdOrderStep2` needed no copy.** Its private helpers mutate
  a single `profile` argument passed straight through (Swift `inout` on
  one object) and always return on first success — Python's natural
  pass-by-reference mutable-object semantics already match Swift's
  `inout` here, so these are plain mechanical translations.
- **Dropped the `debugThis`/`print(...)` scaffolding** in
  `VelocitySecondOrderStep2.swift` (a `let debugThis = true` flag guarding
  `print` calls, with the intended real condition commented out:
  `// (abs(vd) < 0.01)`). This is debug noise, not part of the semantic
  contract (fidelity requirement 2 covers branch structure and method
  names, not console output), and printing from a library call is
  undesirable regardless. No other file in this chunk's scope had similar
  scaffolding.
- **Test boundary values pre-set via `Profile.set_boundary_for_velocity`.**
  A fresh `Profile()` has `vf = af = 0.0`; since `Step1.get_profile`
  copies its working profile's `vf`/`af`/`v[0]`/`a[0]` from the caller-
  supplied `input` profile (`set_boundary`'s "from-profile" overload), the
  test fixtures call `set_boundary_for_velocity(p0_new=0.0, v0_new=0.0,
  a0_new=..., vf_new=..., af_new=...)` on the input profile before
  invoking `get_profile` — mirroring how the (not-yet-built)
  `TargetCalculator` would populate it.
- **Test regime derivation** (both third-order analytic regimes, matching
  the chunk's TDD step): a = 2.0, j = 1.0 (a²/j = 4.0). Δv = 6.0 (≥ 4.0)
  exercises the trapezoidal-acceleration (`ACC0`) regime via `_time_acc0`,
  t = Δv/a + a/j = 5.0. Δv = 3.0 (< 4.0) exercises the triangular regime
  via `_time_none`'s Solution 2, t = 2·sqrt(Δv/j) ≈ 3.464. Second order:
  Δv = 4.0, aMax = 2.0, t = Δv/a = 2.0. Both Step2 tests use tf = 1.5 ×
  the corresponding Step1-optimal duration and assert the profile hits the
  target velocity/acceleration and spans exactly `tf`. All boundary arrays
  are cross-checked against `integrate_jerk` computed independently in the
  test, per `tests/otg/test_profile.py`'s established convention.
- No deviations from the plan's file list or design constraints; `otg.md`
  required no contract changes (only a semver bump for this landing).
