---
chunk: 21-dsp-spectral
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (SpectralMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.1
author: Nicholas Bergantz
---

# 21 — `SpectralMixin` (FFT / PSD / spectrogram / mel / features)

**Deliverable:** `dsp/_spectral.py` + tests. Swift references:
`Waveform1D+FFT.swift`, `+Spectrogram.swift` under
`SWIFT_MATH/Waveform1D/Extensions/`.

## Files

Create `src/math_tools/waveforms/dsp/_spectral.py`,
`tests/waveforms/dsp/test_spectral.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `fft() -> WaveformSpectrum` (rfft; frequencies in
  Hz from `sampling_frequency_hz`), `power_spectral_density(window=...,
  scaling: WaveformPSDScaling = DENSITY, nperseg=None) -> WaveformSpectrum`
  (`scipy.signal.welch`), `spectrogram(window=..., nperseg=..., overlap=...)
  -> WaveformSpectrogram` (`scipy.signal.ShortTimeFFT` or
  `scipy.signal.spectrogram`), `mel_spectrogram(n_mels=..., ...) ->
  WaveformMelSpectrogram` (hand-built triangular filterbank over the
  spectrogram — numpy), `spectral_features() -> WaveformSpectralFeatures`
  (centroid, spread, rolloff, flatness — match the Swift field set from
  `extractSpectralFeatures`; read the Swift struct first and mirror its
  fields exactly).
- Minimum-length `ValueError` per §Numerical conventions.

## TDD steps

1. Failing tests (spec compliance 1): `fft` of a pure 10 Hz sine
   (fs = 1 kHz, n = 1000) peaks at the 10 Hz bin; Parseval sanity
   (`sum(|X|²)` vs `sum(x²)`, rtol 1e-6); PSD of white noise is flat within
   a loose band; spectrogram of a chirp has monotonically increasing
   argmax-frequency per column; mel filterbank rows sum ≈ 1 where fully
   inside the band; spectral centroid of the 10 Hz sine ≈ 10 Hz (rtol 5e-2).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Peak-bin, chirp-monotone, and centroid tests pass
- [x] All four descriptor types round out of the methods without eq/hash errors
- [x] `make uv-fullCheck` passes

## Out of scope

Filtering (22), phase (24), windows themselves (28 — take `window`
parameters as `WaveformWindowType` and map via `scipy.signal.get_window`
directly here; chunk 28's helpers are for user-facing window utilities).

## Resolution notes

- **`spectral_features` field-set decision.** This chunk's own bullet said
  to "mirror the Swift `extractSpectralFeatures` struct's fields exactly,"
  but that Swift struct (`Waveform1D/Support/WaveformSpectralFeatures.swift`)
  is a *per-time-frame* result derived from a spectrogram
  (`spectralCentroids`/`spectralRolloffs`/`spectralFluxes`/`timeFrames`,
  all arrays) — not the four scalars (`centroid`, `spread`, `rolloff`,
  `flatness`) the same bullet names. The Python `WaveformSpectralFeatures`
  dataclass already shipped in `waveforms/support.py` from chunk 14 (merged
  before this chunk) uses that scalar shape, and waveformDsp.md §Support
  descriptor types already documents it that way — both predate this chunk
  and already agree with each other, so no spec or `support.py` change was
  needed. Implemented `spectral_features()` against the existing scalar
  shape (whole-spectrum summary over the FFT magnitude spectrum) rather than
  reopening `support.py` for a per-frame shape; documented the reasoning in
  `_spectral.py`'s module docstring. Only the chunk doc's own bullet was
  stale/self-contradictory — no other spec drift found.
- `WaveformSpectrogramScaling` (LINEAR/DB/MEL, defined in `support.py` from
  chunk 14) is not consumed by this chunk: the design-constraints bullet for
  `spectrogram()` lists only `window`/`nperseg`/`overlap`, no `scaling`
  parameter, and `MEL` isn't a coherent magnitude-scaling option anyway
  (it's a frequency-axis warp). Left unconsumed per YAGNI; a later chunk can
  wire it up if a caller needs it.
- `KAISER` window support needed a shape parameter (`beta`) that the family
  contract doesn't expose; fixed a default (`beta=14.0`) documented inline
  in `_spectral.py` rather than adding a beta parameter no other window
  needs.
- Window arguments are mapped to concrete arrays via `scipy.signal.get_window`
  directly in `_spectral.py` (not through a shared `dsp/_common.py` helper),
  per this chunk's own design-constraint text ("map ... directly here").
- Mel filterbank rows are normalized to sum to ~1 by construction (each row
  divided by its own weight sum) rather than the usual peak-height-1
  triangle — satisfies the TDD step's "rows sum ≈ 1" requirement directly;
  documented as a deliberate choice, not a Slaney-style bandwidth
  normalization.
- No deviation from the chunk 18 mixin-typing pattern was needed: this
  chunk's own code was written fresh following `_calc.py`/`_correlation.py`/
  `_envelope.py` (self-typed `self: WaveformProtocol`, no nominal Protocol
  inheritance).
