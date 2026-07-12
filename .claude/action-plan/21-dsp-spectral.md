---
chunk: 21-dsp-spectral
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (SpectralMixin), §Compliance 1–2
last_updated: 2026-07-11
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

- [ ] Peak-bin, chirp-monotone, and centroid tests pass
- [ ] All four descriptor types round out of the methods without eq/hash errors
- [ ] `make uv-fullCheck` passes

## Out of scope

Filtering (22), phase (24), windows themselves (28 — take `window`
parameters as `WaveformWindowType` and map via `scipy.signal.get_window`
directly here; chunk 28's helpers are for user-facing window utilities).
