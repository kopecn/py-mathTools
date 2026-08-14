---
chunk: 19-dsp-correlation
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (CorrelationMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
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

- [x] Known-shift lag recovery exact for k ∈ {0, 3, 17}
- [x] Import-fence grep per chunk 18
- [x] `make uv-fullCheck` passes

## Out of scope

Time alignment (chunk 26 consumes this); phase coherence (24).

## Resolution notes

- **Lag sign convention diverges from the Swift reference (documented in
  `_correlation.py`'s module docstring, not silently).** Swift's hand-rolled
  `findMaxCorrelation` computes `actualLag = maxIndex - (other.count - 1)`
  ("other's index minus self's"); empirically verifying
  `scipy.signal.correlate`/`correlation_lags` against Swift's own
  `findMaxCorrelationShifted` test fixture (`original`/`shifted` arrays)
  showed scipy's native lag is the exact negation of Swift's for the same
  input. Per waveformDsp.md's preamble ("parity is judged per capability,
  not per Swift overload... scipy semantics win and the divergence is
  documented"), this module keeps scipy's native sign rather than negating
  it post-hoc: `other` trailing `self` by `k` samples
  (`other[i] == self[i - k]`) yields `lag_samples == -k`. Verified exact
  (not approximate) lag recovery at `n=2000` for `k ∈ {0, 3, 17}` via
  `np.roll`-shifted white noise, correlation ≥ 0.99 in all three cases.
- **Python surface intentionally narrower than Swift's:** the spec's
  `cross_correlation(other, max_lag=None, normalized=True)` signature has no
  `mode` parameter, so only scipy's `mode="full"` is implemented — Swift's
  `WaveformCorrelationMode` (`valid`/`same`) overloads are not ported
  (YAGNI; add with a caller that needs them). `max_lag` trims the full-mode
  result to `abs(lag) <= max_lag` for both `cross_correlation` and
  `find_max_correlation`, which is this repo's addition (Swift's
  `crossCorrelation` has no lag cap; its `findMaxCorrelation` has a
  `searchRange` instead — `max_lag` is the simpler, symmetric analogue the
  Python spec actually asks for).
- **Empty-input / dt-mismatch handling:** `auto_correlation` and
  `cross_correlation` raise `ValueError` naming the requirement on an empty
  waveform (waveformDsp.md §Numerical conventions — correlation is not a
  `detect_*`/`zero_crossings` detector, so it doesn't get the empty-result
  exemption Swift's `nil`-returning Optionals use instead).
  `cross_correlation`/`find_max_correlation` raise
  `WaveformCompatibilityError` on `other.dt != self.dt`, per the chunk's
  design constraint.
- **Zero-variance signal parity:** ported Swift's `autoCorrelation`
  zero-variance special case exactly — a nonzero constant signal normalizes
  to `1.0` at every lag, an all-zero signal to `0.0` at every lag (both
  pinned by tests).
- **`WaveformTimeLag` import from `waveforms/support.py`, not `dsp/_*`:**
  the family contract requires `find_max_correlation -> WaveformTimeLag`,
  a descriptor type support.py already defines (chunk 14). Importing it
  does not trip `test_dsp_mixins_do_not_import_sibling_mixins` (verified —
  that test only flags `math_tools.waveforms.dsp.*`/relative-within-`dsp/`
  imports, not `waveforms/support.py`, which lives outside the `dsp/`
  package) and introduces no import cycle at this chunk (`support.py`
  already imports `waveform1d.py`, which imports nothing from `dsp/`).
  Flagging for whichever chunk composes `Waveform1D`'s final mixin list
  (30): `support.py` importing `waveform1d.py` while `waveform1d.py` will
  need to import every mixin (including this one, which imports
  `support.py`) is a latent cycle that chunk 30 will need to resolve (e.g.
  a lazy/`TYPE_CHECKING` import in `support.py`, or moving `Waveform1D`
  aggregate-referencing descriptors elsewhere) — not a chunk 19 problem
  since no mixin is composed into `Waveform1D` yet, but worth knowing going
  in; `TriggerMixin` (chunk 27, `WaveformWithEvents`) will hit the same
  shape of dependency.
- Full suite: 872 tests green (24 new in
  `tests/waveforms/dsp/test_correlation.py`), ruff clean, mypy strict clean
  (`make uv-fullCheck`).
