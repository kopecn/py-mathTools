---
chunk: 22-dsp-filtering
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (FilteringMixin), §Numerical conventions, §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
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

- [x] The ≥ 40 dB attenuation test and savgol-cubic test pass
- [x] Nyquist-violation cutoff raises `ValueError`
- [x] `make uv-fullCheck` passes

## Out of scope

Resampling (25); windowing utilities (28).

## Resolution notes

- Followed the chunk-18 self-typed-mixin pattern throughout (`FilteringMixin`
  is a plain class, no `WaveformProtocol` base); this chunk's own code
  samples didn't show the broken nominal-inheritance pattern, so no
  correction was needed there.
- The chunk doc's design-constraints bullet gives `filtered(filter_type:
  WaveformFilterType, ...)` with an elided `...`; resolved the omitted
  signature as `filtered(filter_type, cutoff_hz=None, low_hz=None,
  high_hz=None, order=4, causal=False)` — the union of the args the four
  dispatched Butterworth families need, with per-branch `ValueError` when
  the wrong ones are missing. `low_pass_filter`/`high_pass_filter`/
  `band_pass_filter`/`filtered` all funnel through one private
  `_butter_coefficients` design helper so validation and design parameters
  can't drift between the dedicated methods and the dispatcher.
  `frequency_response` reuses the same helper against `scipy.signal.freqz`.
- `causal: bool = False` was added (not explicitly named in the chunk file,
  but required by the spec's own line: "Butterworth designs zero-phase via
  `filtfilt` unless a `causal=` flag" — §Numerical conventions). Zero-phase
  `filtfilt` is the default; `causal=True` switches to a single
  `scipy.signal.lfilter` pass.
- Deviated from the Swift reference's silent-no-op-on-invalid-input
  behavior (e.g. `guard windowSize > 0 ... else { return self }`): every
  invalid parameter (bad `window_size`, `alpha` outside `(0, 1]`, bad
  `savgol` window/polyorder/deriv combination, `order < 1`, Nyquist
  violations, missing dispatch args) raises `ValueError` naming the
  requirement instead, per waveformDsp.md §Numerical conventions (already
  the convention every prior DSP mixin chunk follows) and the spec's
  "parity is judged per capability, not per Swift overload" policy.
- `moving_average_filter` implements a centered average whose window
  shrinks (not zero-pads) at the edges — closest Python-idiomatic
  equivalent of the Swift reference's clamped-index behavior — via a
  vectorized cumulative-sum formulation (no explicit Python loop).
- `exponential_filter` is a genuinely sequential recursion
  (`y[i]` depends on `y[i-1]`); implemented as a plain Python loop since a
  vectorized closed form would need `alpha*(1-alpha)**arange(n)` weights
  convolved against `values`, which is a real de-vectorization win only at
  large `n` and adds nontrivial complexity — correctness/clarity outrank
  that here (tenets: Correctness/Clarity > Performance; no evidence this is
  ever a bottleneck for typical waveform sizes).
- `savitzky_golay_filter` passes `delta=dt_seconds` to
  `scipy.signal.savgol_filter` only when `deriv > 0` (scipy scales
  derivative estimates by `1/delta**deriv`; passing a real `delta` for
  `deriv=0` is harmless but pointless) so the returned derivative carries
  proper physical units — not explicit in the chunk file, inferred from
  waveformDsp.md's general "scale by dt seconds" convention used by
  `CalcMixin`.
- `whittaker_henderson_filter` implements the chunk's own sparse
  difference-matrix recipe verbatim (`D = D[1:] - D[:-1]` applied `order`
  times, then `spsolve(I + lam * D^T @ D, v)`).
- No spec changes were needed — implementation matched
  `waveformDsp.md`'s family-contract row and numerical conventions as
  written; only the elided `filtered(...)` signature and the `causal=`
  parameter required interpretation, and both are already licensed by the
  spec text itself (§Numerical conventions) rather than contradicting it.
- Test coverage exceeds the two acceptance-box-named cases (40 dB
  attenuation, savgol-cubic) to satisfy the repo-wide §Compliance 1 ("every
  mixin method tested against an analytically known signal"): all 9 public
  methods have dedicated tests, including the TDD step's high-pass mirror,
  band-pass in-band-survival, moving-average identity, and
  Whittaker-Henderson `lam→0`/`lam→∞` cases.
- `dsp/__init__.py` and `waveform1d.py` were not touched (mixin composition
  is chunk 30's job per waveformDsp.md's "Composition phasing").
