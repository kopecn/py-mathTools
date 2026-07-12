---
chunk: 22-dsp-filtering
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (FilteringMixin), §Numerical conventions, §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 22 — `FilteringMixin`

**Deliverable:** `dsp/_filtering.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Filtering.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_filtering.py`,
`tests/waveforms/dsp/test_filtering.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `low_pass_filter(cutoff_hz, order=4)`,
  `high_pass_filter(cutoff_hz, order=4)`, `band_pass_filter(low_hz,
  high_hz, order=4)`, generic `filtered(filter_type: WaveformFilterType,
  ...)` dispatching to the above (+ BAND_STOP), `moving_average_filter(
  window_size)`, `exponential_filter(alpha)`,
  `savitzky_golay_filter(window_length, polyorder, deriv=0)`,
  `whittaker_henderson_filter(lam, order=2)` (sparse difference-matrix
  solve via `scipy.sparse` + `spsolve`), `frequency_response(...) ->
  WaveformSpectrum`.
- Butterworth designs zero-phase via `filtfilt` (spec: zero-phase unless a
  `causal=` flag). Cutoffs validated against Nyquist (`ValueError`).

## Whittaker–Henderson recipe (the one clever bit)

```python
n = len(v); D = sparse.eye(n, format="csc")
for _ in range(order): D = D[1:] - D[:-1]          # order-th difference matrix
z = spsolve((sparse.eye(n) + lam * D.T @ D).tocsc(), v)
```

## TDD steps

1. Failing tests (spec compliance 1): 5 Hz + 200 Hz mix (fs = 2 kHz) →
   `low_pass_filter(50)` attenuates the 200 Hz component ≥ 40 dB while the
   5 Hz amplitude survives (rtol 5e-2), measured via chunk-local rfft;
   high-pass mirror; band-pass keeps only the in-band tone; moving average
   of a constant is identity; savgol on a noiseless cubic reproduces it
   (atol 1e-8); Whittaker–Henderson with `lam→0` ≈ identity and large `lam`
   ≈ linear trend.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] The ≥ 40 dB attenuation test and savgol-cubic test pass
- [ ] Nyquist-violation cutoff raises `ValueError`
- [ ] `make uv-fullCheck` passes

## Out of scope

Resampling (25); windowing utilities (28).
