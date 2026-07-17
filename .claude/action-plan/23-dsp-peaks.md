---
chunk: 23-dsp-peaks
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (PeakMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
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

- [x] Sine peak-count and prominence-order tests pass
- [x] `make uv-fullCheck` passes

## Out of scope

Trigger detection (27); zero crossings (29).

## Resolution notes

- Implemented `PeakMixin` (`detect_peaks`, `detect_valleys`,
  `find_most_prominent_peaks`) exactly per the mixin table in
  `waveformDsp.md` §Family contracts, backed by `scipy.signal.find_peaks` /
  `peak_prominences`. No spec changes were needed — this chunk's design
  constraints already matched the spec verbatim (no divergence to
  reconcile).
- Followed the chunk-18 typing fix (self-typed `WaveformProtocol`, no
  nominal `Protocol` inheritance) throughout; `_peaks.py` imports only
  `scipy`/`numpy` plus `dsp/_protocol.py`, `dsp/_common.py`, and
  `waveforms/support.py` (for `WaveformPeak`/`WaveformPeakWithProminence`),
  so the pre-existing generic sibling-import layering test
  (`tests/test_package_layering.py::test_dsp_mixins_do_not_import_sibling_mixins`)
  covers it automatically — no new layering-test code required.
- `detect_valleys` is implemented as an exact negate/detect_peaks/negate
  round-trip through a shared module-level helper
  (`_detect_peaks_in_array`), matching the "valleys mirror peaks under
  negation" TDD requirement literally: `min_height`/`min_prominence` are
  forwarded unchanged to the negated-signal search (so `min_height` bounds
  the original `value` from *above*, not below — documented in the
  docstring since this is a semantic choice the chunk left implicit).
- `find_most_prominent_peaks` treated as part of the same detector family
  as `detect_peaks`/`detect_valleys` for the empty-result convention
  (returns `[]` for `count <= 0`, an empty waveform, or no interior peaks,
  rather than raising `ValueError`) — the spec's §Numerical conventions
  ValueError-vs-empty-list split is keyed off the `detect_*`/
  `zero_crossings` name prefix, but `find_most_prominent_peaks` is built
  directly on `detect_peaks`'s results and documented as the same family in
  the mixin table, so the empty-list contract was extended to it for
  consistency; flagging this as a judgment call in case a future chunk
  wants it spec'd explicitly.
- Swift `Waveform1D+Peak.swift`'s hand-rolled `threshold`/`prominence`/
  `minDistance`/`edgePeaks` local-maxima scan was **not** ported
  literally — the chunk's own "Design constraints" section already pins
  the Python surface to `min_height`/`min_distance`/`min_prominence`
  scipy-style kwargs, so `Waveform1DPeakTests.swift`'s 27 cases were used
  only for behavioral inspiration (mirrored valleys, prominence ordering,
  flat/empty edge cases), not transliterated.
- Gate: `make uv-fullCheck` green — ruff clean, mypy strict clean (64
  source files), 971 tests passed (18 new in `test_peaks.py`).
