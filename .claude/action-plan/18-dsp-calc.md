---
chunk: 18-dsp-calc
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (CalcMixin), §Numerical conventions, §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 18 — `CalcMixin` (integrate / derivative)

**Deliverable:** `math_tools/waveforms/dsp/_calc.py` + tests. Swift
reference: `SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Calc.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_calc.py`,
`tests/waveforms/dsp/__init__.py`, `tests/waveforms/dsp/test_calc.py`.
Do NOT touch `waveform1d.py` (mixins compose in chunk 30). Tests exercise
the mixin via a local test subclass `class _W(CalcMixin, Waveform1D): pass`
— this pattern applies to every DSP chunk.

## Design constraints

- `class CalcMixin(WaveformProtocol)`; methods per spec table:
  `integrate(initial_value=0.0) -> Waveform1D` (cumulative trapezoid scaled
  by `dt` seconds, first sample = initial_value),
  `derivative() -> Waveform1D` (`np.gradient` over the time axis).
- Results built via `self._with_values(...)`; imports: scipy/numpy +
  `._protocol`/`._common` only (no sibling mixin imports — repo layering
  test extended here if not already covering `dsp/`).

## TDD steps

1. Failing tests (spec compliance 1): derivative of a linear ramp is
   constant (atol 1e-9); `integrate` of a constant is a ramp;
   `integrate().derivative()` recovers a smooth signal interior
   (rtol 1e-6).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] The three analytic tests pass
- [ ] `grep "from math_tools.waveforms.dsp._" src/math_tools/waveforms/dsp/_calc.py` shows only `_protocol`/`_common`
- [ ] `make uv-fullCheck` passes

## Out of scope

Any other mixin; composing into `Waveform1D`.
