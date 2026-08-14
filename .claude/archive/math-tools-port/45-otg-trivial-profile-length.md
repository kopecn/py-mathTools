---
chunk: 45-otg-trivial-profile-length
track: F
status: complete
depends_on: []
spec: ../specs/otg.md §Internal fidelity 1 (line 120)
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 45 — Trivial "already at target" profile must use fixed-length arrays

## Origin

Post-audit finding E-2 (class **c**). Confirmed at runtime:

```
trivial (1->1): (Result.WORKING, 7, 7, 7)   # len(p.p), len(p.v), len(p.a)
normal  (0->1): (Result.WORKING, 8, 8, 8)
```

`.claude/specs/otg.md:120` mandates `j[7]`, `a[8]`, `v[8]`, `p[8]` — "fixed
length, never resized". The trivial branch at
`src/math_tools/otg/calculator_target.py:366-372` builds 7-element `p.a`,
`p.v`, `p.p`, so `p.p[7]` raises `IndexError` on a trajectory that any other
path would make safely indexable. The repo's own continuity helper
(`tests/otg/test_otg_continuity.py:48`, `range(1, 8)`) would raise on such a
profile.

The same branch never assigns `p.pf`, so `Trajectory.position_extrema()`
reports `min=0.0` for a trajectory parked at `p=1.0`.

Note: the 7-element form is faithful to `CalculatorTarget.swift:256-261`. The
spec's fixed-length invariant is the higher authority here (00-overview
convention 1 ranks spec above line-level fidelity), and the Swift form is a
latent bug rather than a contract. Fix the port; do not propagate the defect.

## Files

- Edit: `src/math_tools/otg/calculator_target.py`
- Edit: `tests/otg/test_calculator_target.py`

## Design constraints

1. In the trivial branch, `p.a`, `p.v`, `p.p` become length **8**; `p.t`,
   `p.t_sum`, `p.j` stay length **7**. Match the lengths every non-trivial
   path already produces.
2. Set `p.pf` to the current position in the same branch, so
   `position_extrema()` reports the parked position rather than `0.0`.
3. Touch only the trivial branch. The `for dof` loop that follows it (`:378`)
   is the normal path and is correct.
4. Add a short comment noting the deliberate divergence from
   `CalculatorTarget.swift:256-261` and pointing at otg.md §Internal fidelity 1,
   so the next fidelity audit does not "fix" it back.

## TDD steps

1. Write failing tests: (a) a trivial-target `calculate` yields
   `len(p.p) == len(p.v) == len(p.a) == 8` and `len(p.t) == 7`; (b)
   `position_extrema()` on a trajectory parked at a non-zero position returns
   that position as both min and max, not `0.0`.
2. Apply the fix.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Trivial-target profile arrays are 8/8/8 and 7/7/7 as spec'd
- [x] `p.pf` set; `position_extrema()` correct for a parked trajectory
- [x] Both new tests fail before, pass after
- [x] Divergence comment present, citing otg.md §Internal fidelity 1
- [x] `make uv-fullCheck` passes

## Out of scope

Any other `CalculatorTarget` path. The phase-sync and discrete-duration
coverage gaps are chunk 56.

## Resolution notes

- `src/math_tools/otg/calculator_target.py`'s trivial branch (~line
  366-379) now builds `p.a`/`p.v`/`p.p` as 8-element lists (was 7) and sets
  `p.pf = input_parameter.current_position[dof]`; `p.t`/`p.t_sum`/`p.j`
  remain 7-element, matching every other path (`Profile.__init__` in
  `src/math_tools/otg/profile.py:113-119` is the authoritative fixed-length
  shape). Added an inline comment citing `CalculatorTarget.swift:256-261`
  and otg.md §Internal fidelity requirement 1 so a future fidelity audit
  doesn't "fix" this back to the 7-element Swift form.
- Confirmed via research that `Trajectory.position_extrema()` /
  `_profile_position_extrema` (`src/math_tools/otg/trajectory.py:244-291`)
  only reads `profile.p[i]` for `i in range(7)` (indices 0-6) directly, so
  the 7-vs-8 length alone wasn't what crashed `position_extrema`; the
  `IndexError` risk is in code that walks all 8 boundary indices (e.g.
  `tests/otg/test_otg_continuity.py`'s `range(1, 8)` helper, and any future
  caller relying on the spec's fixed-length invariant). `position_extrema`'s
  final min/max check does compare against `profile.pf` (lines 284-289),
  which is what made the parked-position test fail before the fix (`pf`
  stayed at its zero-init default in the trivial branch, since that branch
  never calls `Profile.set_boundary`).
- Added two tests to `tests/otg/test_calculator_target.py`:
  `TestTrivialProfileUsesFixedLengthArrays` (array-length assertions) and
  `TestTrivialProfilePositionExtrema` (parked non-zero position reported
  correctly by `position_extrema()`). Both were confirmed failing before
  the fix (`7 != 8` and `0.0 != 5.0`) and passing after.
- No spec change was needed -- the implementation was brought into
  conformance with the existing otg.md §Internal fidelity requirement 1,
  not the other way around.
- `make uv-fullCheck` is green: ruff clean, mypy strict clean (117 source
  files), 1359 tests passed (was 1357; +2 new).
