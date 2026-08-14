---
chunk: 33-otg-profile
track: E
status: complete
depends_on: [31]
spec: ../specs/otg.md §Internal fidelity 1, 4, 5
last_updated: 2026-07-21
semver: 0.0.1
author: Nicholas Bergantz
---

# 33 — `Profile`

**Deliverable:** the per-DOF kinematic profile record — the hot data
structure every step solver fills. Faithful port of
`SWIFT_MATH/OTG/Profile.swift` (~715 lines; translate mechanically,
preserve method and branch structure).

## Files

- Create: `src/math_tools/otg/profile.py`
- Create: `tests/otg/test_profile.py`

## Design constraints

1. Fixed-length `list[float]` arrays `t[7]`, `t_sum[7]`, `j[7]`, `a[8]`,
   `v[8]`, `p[8]` — never resized. Targets `pf/vf/af`; `limits:
   ReachedLimits`, `direction: Direction`, `control_signs: ControlSigns`;
   `brake`/`accel` BrakeProfile fields are typed as the placeholder until
   chunk 34 lands — declare them `brake: "BrakeProfile"` with a deferred
   import if 34 is not yet merged, or coordinate to land 34's dataclass
   stub here (note which).
2. Kinematic stepping uses `math_tools.functional.roots.integrate_jerk` —
   never a fresh implementation.
3. Port the full `check*` family (`check`, `check_for_velocity`,
   `check_for_second_order`, `check_for_first_order`, `set_boundary`,
   `*_with_timing` variants, `check_position_extremum`,
   `check_step_for_position_extremum`) with the Swift epsilon constants
   (`EPS16` etc. from `functional.roots`).
4. Stdlib `math` only.

## TDD steps

1. Failing tests: a hand-constructed 7-phase profile (constant jerk ±j)
   integrates to the expected `p/v/a` boundary arrays (compute the expected
   values with `integrate_jerk` in the test, independent of Profile's own
   loop ordering); `check` accepts a known-valid profile and rejects a
   perturbed one (`t[3] += 1e-3`); `t_sum` is the prefix sum of `t`.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Boundary-array integration test passes; perturbation rejected
- [x] `grep -n "integrate_jerk" src/math_tools/otg/profile.py` ≥ 1;
      no local jerk-integration reimplementation
- [x] `make uv-fullCheck` passes

## Out of scope

Brake trajectory computation (34); step solvers; trajectory sampling.

## Resolution notes

- **BrakeProfile forward reference (for chunk 34 to reconcile):** chunk 34
  had not landed, so `brake`/`accel` are typed as a module-private
  `_DeferredBrakeProfile` dataclass (top of `profile.py`) rather than a
  `TYPE_CHECKING`-guarded string forward reference to
  `math_tools.otg.brake.BrakeProfile` -- that module doesn't exist yet, and
  a `TYPE_CHECKING` import of a nonexistent module fails `mypy --strict`
  even though it's runtime-inert (mypy evaluates `TYPE_CHECKING` blocks).
  `_DeferredBrakeProfile` mirrors `Brake.swift`'s public shape exactly
  (`duration`, `t`, `j`, `a`, `v`, `p`, with the same `[0.0, 0.0]` defaults)
  so `Profile.__init__`'s `BrakeProfile()` defaults and
  `Profile.set_boundary`'s `brake`/`accel` copy are both faithful without
  needing a real instance of the future type. **Chunk 34 should**: delete
  `_DeferredBrakeProfile` from `profile.py`, import the real `BrakeProfile`
  from `math_tools.otg.brake`, and retype `Profile.brake`/`Profile.accel`
  (and the `set_boundary` copy) to it -- no other call site needs to
  change, since every chunk-33 method treats `brake`/`accel` as opaque
  (copied, never read field-by-field).
- **`Bound` forward reference:** `check_position_extremum` and
  `check_step_for_position_extremum`'s `ext` parameter is typed against a
  module-private structural `Protocol` (`_PositionExtremumSink`: `min`,
  `max`, `t_min`, `t_max` floats) instead of importing the not-yet-landed
  `Bound`. Since `34-otg-block-brake-bound.md` specifies `Bound` with
  exactly those field names, the real `Bound` will satisfy this Protocol
  automatically -- **chunk 34 does not need to touch `profile.py` for
  this one**; the Protocol can stay indefinitely, or be swapped for a
  direct `Bound` import later purely for readability.
- **Epsilon constants:** `otg.md`'s "exact epsilon constants (`EPS16`
  etc. from `functional.roots`)" guidance doesn't literally apply to
  `Profile.swift`'s own comparisons -- that file defines its own private
  module constants (`vEps`, `aEps`, `jEps`, `pPrecision`, `vPrecision`,
  `aPrecision`, `tPrecision`, `tMax`), none of which exist in
  `functional/roots.py` (`EPS16` = `16*ulp` ≈ 3.55e-15 is a different,
  unrelated constant used only by the polynomial-root kernel). Ported
  `Profile.swift`'s constants as verbatim module-level literals in
  `profile.py`. The one genuine overlap is `Double.ulpOfOne`, reproduced
  as `_ULP = sys.float_info.epsilon` (the same value `functional/roots.py`
  keeps in its own private, non-exported `_ULP` -- not importable across
  modules, so redefined rather than reimplemented).
- **Swift method-overload collapsing:** Python has no positional-overload
  dispatch. `set_boundary`'s two overloads (copy-from-`Profile` vs. six
  scalars) differ by type, so they're ported as `@typing.overload` +
  `isinstance` dispatch (positional-only parameters, `/`, on both overload
  stubs -- required to satisfy `mypy --strict`'s "overloaded implementation
  must accept all parameters of each signature" check, since the stubs'
  first parameter names differ). Every other Swift overload pair
  (`checkWithTiming`, `checkForVelocityWithTiming`,
  `checkForSecondOrderVelocityWithTiming`, `checkForSecondOrderWithTiming`,
  `checkForFirstOrderWithTiming`) differs only by one or two extra bound
  arguments inserted before the trailing `controlSigns`/`limits`
  parameters -- collapsed into one Python method each with the extra
  bound(s) as trailing keyword-only optional parameters (default `None`),
  rather than mirroring Swift's positional insertion point. This changes
  argument order relative to the Swift signature but preserves every
  branch exactly (guard runs only when the optional is provided, then
  delegates to the same shorter method). The unused `tf` timing parameter
  in every `*_with_timing` overload is kept (fidelity to the Swift
  signature) but genuinely unused in every branch, exactly as upstream.
- **Deferred out of scope (not in the chunk's `check*` list):**
  `getPositionExtrema()` and `getFirstStateAtPosition()` were not ported --
  design constraint 3 enumerates the required `check*` family explicitly
  and both are absent from it. Both also have real dependencies this chunk
  doesn't carry: `getPositionExtrema` reads `brake.duration`/`brake.t`
  (meaningless against the placeholder) and aggregates across the whole
  profile plus brake sub-profiles (a `Trajectory`-level concern, chunk 35);
  `getFirstStateAtPosition` needs
  `functional.polynomial.UnivariatePolynomial`'s cubic root solver, not
  wired into this module. Flagging so a later chunk (35, trajectory
  sampling) knows these two Swift methods still need a home.
- All 9 `integrate_jerk` call sites replace every Swift `for i in 0..<7`
  kinematic loop, including the "second-order"/"first-order" interfaces
  where Swift inlines the `j == 0` special case by hand (verified
  algebraically: `integrate_jerk(t, p0, v0, a0, 0.0)` reduces to exactly
  Swift's `v0 + t*a0` / `p0 + t*(v0 + t*a0/2)`).
