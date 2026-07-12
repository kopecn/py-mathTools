---
chunk: 19-dsp-correlation
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (CorrelationMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 19 — `CorrelationMixin`

**Deliverable:** `dsp/_correlation.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Correlation.swift`; test ideas:
`SWIFT_TESTS/Waveform1DCorrelationTests.swift` (39 tests — port the
representative cases).

## Files

Create `src/math_tools/waveforms/dsp/_correlation.py`,
`tests/waveforms/dsp/test_correlation.py`. Test-subclass pattern per
chunk 18.

## Design constraints

- Methods per spec table: `auto_correlation(max_lag=None, normalized=True)`,
  `cross_correlation(other, max_lag=None, normalized=True)` (dt mismatch →
  `WaveformCompatibilityError`), `find_max_correlation(other, max_lag=None)
  -> WaveformTimeLag`. Backing `scipy.signal.correlate`/`correlation_lags`.
- Normalized autocorrelation is 1.0 at lag 0; `WaveformTimeLag` carries
  `lag_samples`, `lag_seconds` (= lag · dt seconds), `correlation`.

## TDD steps

1. Failing tests: autocorrelation of white noise ≈ δ (lag-0 dominates);
   `find_max_correlation` of a signal vs itself shifted by k samples
   returns lag k (exact) with correlation ≈ 1; dt mismatch raises.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Known-shift lag recovery exact for k ∈ {0, 3, 17}
- [ ] Import-fence grep per chunk 18
- [ ] `make uv-fullCheck` passes

## Out of scope

Time alignment (chunk 26 consumes this); phase coherence (24).
