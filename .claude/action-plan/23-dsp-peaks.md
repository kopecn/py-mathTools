---
chunk: 23-dsp-peaks
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (PeakMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 23 — `PeakMixin`

**Deliverable:** `dsp/_peaks.py` + tests. Swift references:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Peak.swift`;
`SWIFT_TESTS/Waveform1DPeakTests.swift` (27 tests — port representative
cases).

## Files

Create `src/math_tools/waveforms/dsp/_peaks.py`,
`tests/waveforms/dsp/test_peaks.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `detect_peaks(min_height=None, min_distance=None,
  min_prominence=None) -> list[WaveformPeak]`, `detect_valleys(...)`
  (negate + detect_peaks), `find_most_prominent_peaks(count,
  min_distance=None) -> list[WaveformPeakWithProminence]`. Backing
  `scipy.signal.find_peaks` / `peak_prominences`.
- `WaveformPeak.time_seconds` = `index * dt` seconds; empty list on no-hit
  (never raise for no peaks).

## TDD steps

1. Failing tests (spec compliance 1): `sine(n, f, fs)` yields exactly
   `⌊n·f/fs⌋` peaks (choose n, f, fs so the count is unambiguous);
   valleys mirror peaks under negation; prominence ordering on a two-tone
   signal (big + small bumps) returns the big ones first; flat signal → [].
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Sine peak-count and prominence-order tests pass
- [ ] `make uv-fullCheck` passes

## Out of scope

Trigger detection (27); zero crossings (29).
