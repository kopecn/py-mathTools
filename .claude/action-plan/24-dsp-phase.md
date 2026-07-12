---
chunk: 24-dsp-phase
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (PhaseMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 24 — `PhaseMixin`

**Deliverable:** `dsp/_phase.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+PhaseAnalysis.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_phase.py`,
`tests/waveforms/dsp/test_phase.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `instantaneous_phase(unwrapped=True)` (Hilbert
  angle), `unwrap_phase(threshold=π)` (`np.unwrap` on already-phase data),
  `instantaneous_frequency() -> WaveformInstantaneousFrequency` (phase
  gradient / 2π), `phase_difference(other)`, `phase_coherence(other,
  window=...)`, `phase_synchronization_index(other) -> float` (PLV, in
  [0, 1]), `group_delay(...)`. dt mismatch on binary methods →
  `WaveformCompatibilityError`.

## TDD steps

1. Failing tests (spec compliance 1): unwrapped phase of a chirp is
   monotone increasing; instantaneous frequency of a pure f-Hz sine ≈ f on
   the interior (rtol 1e-2); PLV of a signal with itself == 1.0 and with an
   independent seeded-noise signal < 0.3; `phase_difference` of `sin` vs
   `cos` ≈ π/2 interior.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Chirp-monotone and PLV tests pass
- [ ] `make uv-fullCheck` passes

## Out of scope

Envelope (20); spectral (21).
