---
chunk: 20-dsp-envelope
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (EnvelopeMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] Analytic sine/damped tests pass; import-fence grep per chunk 18
- [ ] `make uv-fullCheck` passes

## Out of scope

Phase analysis (24); spectral features (21).
