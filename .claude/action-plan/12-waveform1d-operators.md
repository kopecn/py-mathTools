---
chunk: 12-waveform1d-operators
track: C
status: pending
depends_on: [11]
spec: ../specs/waveformCore.md §Waveform1D Operators, §Compliance 2
last_updated: 2026-07-11
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

- [ ] Compliance item 2 named test passes
- [ ] `(w + 1.0).t0 == w.t0` and `is not w`
- [ ] `make uv-fullCheck` passes

## Out of scope

Generators, DSP, aggregate operators (aggregates have none).
