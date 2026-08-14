---
chunk: 12-waveform1d-operators
track: C
status: complete
depends_on: [11]
spec: ../specs/waveformCore.md §Waveform1D Operators, §Compliance 2
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 12 — `Waveform1D` operators & comparison

**Deliverable:** the elementwise operator surface.

## Files

- Edit: `src/math_tools/waveforms/waveform1d.py`
- Create: `tests/waveforms/test_waveform1d_operators.py`

## Design constraints

1. Per spec §Operators: `+ - * / // %` (waveform⊕waveform requires equal
   `dt` AND length else `WaveformCompatibilityError`; scalar both orders),
   in-place variants (mutate), bitwise `& | ^ << >> ~` integer-dtype-only
   (`TypeError` with a clear message otherwise), unary `- + abs`,
   `elements_equal` / `elements_less_than` / `elements_greater_than`
   (→ bool ndarray), `isclose_elementwise(other, rtol=1e-9, atol=0.0)`,
   whole-object `isclose(other, rtol, atol)`.
2. Results carry `dt`/`t0` from the left operand; binary op result dtype
   follows numpy promotion.
3. Foreign types → `NotImplemented` (so `np.float64 + w` behaves).

## TDD steps

1. Failing tests: dt-mismatch and length-mismatch raise
   `WaveformCompatibilityError` (spec compliance 2); scalar both orders;
   in-place mutates in place (identity check); bitwise on float raises
   `TypeError`; int `%` and `<<`; `isclose_elementwise` tolerance behavior;
   `isclose` False on differing `t0`.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Compliance item 2 named test passes
- [x] `(w + 1.0).t0 == w.t0` and `is not w`
- [x] `make uv-fullCheck` passes

## Out of scope

Generators, DSP, aggregate operators (aggregates have none).

## Resolution notes

- Added the full elementwise operator surface: `+ - * / // %` (forward,
  reflected, in-place — 18 methods), bitwise `& | ^ << >> ~` (integer-dtype
  only, numpy's own `TypeError` surfaced unwrapped since its message was
  already clear), unary `- + abs`, and the comparison producers
  (`elements_equal`, `elements_less_than`, `elements_greater_than`,
  `isclose_elementwise(rtol, atol)`, whole-waveform `isclose(rtol, atol)`).
  `Waveform1D op Waveform1D` requires equal `dt` AND length
  (`WaveformCompatibilityError` otherwise, via a shared
  `_check_compatible` helper); results carry `dt`/`t0` from the left
  operand; foreign right-hand types return `NotImplemented`.
  `WaveformCompatibilityError` extended to the comparison producers too
  (not just arithmetic), reading spec compliance 2's "any binary ... op"
  literally — a judgment call, not a deviation.
- **One real bug found and fixed during review, not by the implementing
  agent's own tests:** `Waveform1D` defines `__array__`, which makes numpy
  treat any bare `numpy.float64`/`numpy.ndarray` operand as array-like and
  handle the operation via its own ufunc machinery — bypassing Python's
  normal operator protocol entirely, so `w.__radd__` was never called.
  Concretely, `np.float64(2.0) + w` (and `np.array([...]) * w`) silently
  returned a bare `ndarray` (samples only, `dt`/`t0` discarded) instead of
  a `Waveform1D`, even though `2.0 + w` (a plain Python float) worked
  correctly. This directly contradicted this chunk's own design constraint
  3, which names `np.float64 + w` as the motivating example for the
  `NotImplemented` convention. Fixed with the standard idiom for this
  problem: `__array_ufunc__ = None` on the class, which forces numpy to
  return `NotImplemented` for any binop against a foreign array/scalar,
  handing control back to Python's operator protocol (and this class's
  reflected dunders). Verified live: `np.float64(2.0) + w` now returns a
  `Waveform1D` with `dt`/`t0` preserved; `np.asarray(w)` (chunk 11's
  `__array__` contract) is unaffected since it doesn't go through the
  ufunc path. Added a regression test
  (`test_numpy_scalar_reflected_add_returns_waveform_not_bare_ndarray`).
  Plain-`ndarray`-as-operand (e.g. `np.array([1,2,3]) * w`) now correctly
  raises `TypeError` rather than silently returning a bare array — this is
  in spec (operands are `Waveform1D | scalar` only, general ndarray
  broadcasting was never a declared operand kind).
- Verified live: `(w + 1.0).t0 == w.t0` and `is not w`; dt-mismatch raises
  `WaveformCompatibilityError` for `+`; foreign-type `w + object()` raises
  `TypeError`.
- Verified: 35 tests in `tests/waveforms/test_waveform1d_operators.py`
  (34 from the implementing agent + 1 regression test added during
  review), full suite 590 tests green, ruff clean, mypy strict clean
  (`make uv-fullCheck`).
