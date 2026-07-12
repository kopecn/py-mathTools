---
chunk: 28-dsp-windowing
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (WindowingMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 28 — `WindowingMixin`

**Deliverable:** `dsp/_windowing.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Windowing.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_windowing.py`,
`tests/waveforms/dsp/test_windowing.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `windowed(window: WaveformWindowType)`
  (elementwise multiply), staticmethods `generate_window(window, length)
  -> npt.NDArray` (`scipy.signal.get_window`; KAISER takes a beta default
  matching the Swift parameterization — read the Swift enum first),
  `window_coherent_gain(window) -> float` (mean of the window),
  `window_processing_gain(window) -> float`.

## TDD steps

1. Failing tests: RECTANGULAR `windowed` is identity; HANN endpoints ≈ 0 and
   midpoint ≈ 1; coherent gain of HANN ≈ 0.5 (rtol 1e-2 for finite length);
   every `WaveformWindowType` member generates without error.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] All enum members covered; HANN gain test passes
- [ ] `make uv-fullCheck` passes

## Out of scope

Spectral methods' internal window use (21 handles its own).
