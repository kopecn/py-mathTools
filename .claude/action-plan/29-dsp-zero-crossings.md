---
chunk: 29-dsp-zero-crossings
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (ZeroCrossingMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 29 — `ZeroCrossingMixin`

**Deliverable:** `dsp/_zero_crossings.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+ZeroX.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_zero_crossings.py`,
`tests/waveforms/dsp/test_zero_crossings.py`. Test-subclass pattern per
chunk 18.

## Design constraints

- Methods per spec table: `zero_crossings(direction:
  WaveformZeroCrossingDirection = BOTH) -> list[WaveformZeroCrossing]`
  (sign-change indexing + sub-sample linear interpolation for
  `time_seconds`), `zero_crossing_count(direction=BOTH)`,
  `zero_crossing_rate() -> float` (crossings per second),
  `segments_between_zero_crossings() -> list[Waveform1D]` (each segment
  carries a correctly shifted `t0`).
- Exact zeros count once; empty list on no-hit.

## TDD steps

1. Failing tests (spec compliance 1): f-Hz sine over an integer number of
   periods → `zero_crossing_rate() == 2f` ± one crossing; POSITIVE +
   NEGATIVE counts sum to BOTH; sub-sample interp: crossing of a line
   `y = t − 0.5` lands at 0.5 s (atol dt/100); segments' t0s are
   monotonically increasing and lengths sum to ≈ n.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Rate and sub-sample interpolation tests pass
- [ ] `make uv-fullCheck` passes

## Out of scope

Trigger detection (27).
