---
chunk: 20-dsp-envelope
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (EnvelopeMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
author: Nicholas Bergantz
---

# 20 — `EnvelopeMixin`

**Deliverable:** `dsp/_envelope.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Envelope.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_envelope.py`,
`tests/waveforms/dsp/test_envelope.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `amplitude_envelope()` (Hilbert magnitude),
  `upper_lower_envelopes() -> tuple[Waveform1D, Waveform1D]` (peak/valley
  interpolation), `instantaneous_amplitude(method:
  WaveformInstantaneousMethod)` dispatching HILBERT / RMS (windowed) /
  PEAK (interp). Backing `scipy.signal.hilbert`, `find_peaks`, `np.interp`.
- Minimum-length `ValueError` with requirement in message (spec
  §Numerical conventions).

## TDD steps

1. Failing tests: envelope of `A·sin` is ≈ A on the interior (rtol 5e-2,
   edges excluded); envelope of a damped sinusoid tracks `A·exp(−λt)`
   (interior, rtol 0.1); upper ≥ lower everywhere; each
   `WaveformInstantaneousMethod` returns the right length.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Analytic sine/damped tests pass; import-fence grep per chunk 18
- [x] `make uv-fullCheck` passes

## Out of scope

Phase analysis (24); spectral features (21).

## Resolution notes

- **Mixin typing follows the chunk-18 fix, not this chunk's own literal
  code block** (this chunk file predates chunk 18): `EnvelopeMixin` is a
  plain class (no runtime base beyond `object`) that types `self` as
  `WaveformProtocol` on each method — the pattern in `dsp/_calc.py` /
  `dsp/_correlation.py`. Tests use the mandated `class _W(EnvelopeMixin,
  Waveform1D): pass` subclass with a `_wrap` rewrap helper, matching
  `test_calc.py`/`test_correlation.py`.
- **Backing implementation intentionally diverges from the Swift
  reference** (`Waveform1D+Envelope.swift`), per waveformDsp.md's
  preamble ("parity is judged per capability, not per Swift overload"):
  the Swift source approximates the Hilbert transform with a hand-rolled
  fixed-window "quadrature filter" and finds extrema via a windowed
  `allSatisfy` scan. This module uses the real `scipy.signal.hilbert`
  analytic signal for `amplitude_envelope`/`instantaneous_amplitude`
  (`HILBERT`), and `scipy.signal.find_peaks` + `np.interp` for
  `upper_lower_envelopes` and `instantaneous_amplitude(PEAK)` — the chunk
  file's own "Design constraints" section already specified this backing
  explicitly, so no spec-authored capability was skipped, only the Swift
  extension's specific (weaker) algorithm.
- **`upper_lower_envelopes` boundary handling:** local maxima/minima come
  from `find_peaks(values)` / `find_peaks(-values)`; the first and last
  sample indices are always added as extra interpolation anchors (sorted,
  deduplicated via `np.unique`) so a signal with no interior extrema (a
  monotonic ramp, pinned by `test_boundary_samples_are_anchored`) still
  produces an envelope spanning the full waveform via a straight line
  between the two boundary samples, instead of `find_peaks` returning
  nothing and the envelope being degenerate. This differs from the Swift
  reference's `windowSize`-gated constant-envelope fallback (which returns
  a flat `min`/`max`-valued envelope for short inputs) — the boundary-anchor
  approach works uniformly for every input length without a separate
  short-input branch, and is simpler.
- **`instantaneous_amplitude(RMS)` is a `window_size`-parameterized
  centered moving-window RMS** (edge-padded `np.convolve`, not a scipy
  call — the spec's family-contract row lists `find_peaks`/`hilbert`/
  `np.interp` as the family's backing implementations collectively, and
  RMS is the one path with no natural scipy primitive; `FilteringMixin`'s
  `moving_average_filter` in the same family-contract table is also
  `np.convolve`-backed, so this keeps the same idiom rather than adding a
  new dependency). Defaults to `window_size=5`; raises `ValueError` naming
  the requirement for `window_size < 1`.
- **Minimum-length `ValueError`** on all three methods for an empty input
  waveform (0 samples), each naming the requirement in the message — none
  of these are in the `detect_*`/`zero_crossings` empty-result-exempt
  family (waveformDsp.md §Numerical conventions).
- **Damped-sinusoid test tuning:** the TDD step's rtol-0.1 interior check
  needed a `time_constant` large enough relative to the signal's 1-second
  span that the tail doesn't decay into the amplitude range where the
  Hilbert envelope's relative error blows up (small absolute differences
  read as large relative ones once the true amplitude is near zero) —
  `time_constant=1.5` (decay to ~51% by t=1s) passes cleanly at rtol=0.1
  over the interior `[100:-100]` slice; `time_constant=0.5` (decay to
  ~13.5%) did not. This is a test-tuning choice, not an implementation
  change — the same `amplitude_envelope()` call is exercised either way.
- Full suite: 893 tests green (21 new in
  `tests/waveforms/dsp/test_envelope.py`), ruff clean, mypy strict clean
  (`make uv-fullCheck`).
