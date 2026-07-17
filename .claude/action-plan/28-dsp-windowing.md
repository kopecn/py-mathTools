---
chunk: 28-dsp-windowing
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (WindowingMixin), §Compliance 1–2
last_updated: 2026-07-17
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

- [x] All enum members covered; HANN gain test passes
- [x] `make uv-fullCheck` passes

## Out of scope

Spectral methods' internal window use (21 handles its own).

## Resolution notes

- Implemented `WindowingMixin` in `src/math_tools/waveforms/dsp/_windowing.py`
  per chunk 18's mixin-typing fix (§Organization): plain class, `self` typed
  `WaveformProtocol` on each instance method, `generate_window` a
  `@staticmethod` — not `class WindowingMixin(WaveformProtocol)`. The chunk
  file's own reference (Swift extension) predates that fix; followed the
  merged convention instead, per this chunk's own instructions.
- `scipy.signal.get_window` is called with `fftbins=False` (symmetric, not
  periodic) — this is what makes the TDD step's HANN acceptance criterion
  literally true (endpoints exactly 0.0, an odd-length midpoint sample
  exactly 1.0); the default periodic (`fftbins=True`) form does not have
  that property and is what `dsp/_spectral.py` uses for its own STFT-frame
  purpose. Verified numerically before committing to this choice.
- `WaveformWindowType.KAISER` carries no `beta` field (flat `str` enum,
  unlike the Swift `.kaiser(beta:)` associated value), and the chunk's own
  `generate_window(window, length) -> npt.NDArray` signature exposes none
  either — fixed one default beta (`14.0`), independently declared (not
  imported) but numerically matching `dsp/_spectral.py`'s own independent
  default for the same reason (comparable sidelobe suppression to
  Blackman). No spec change needed; `waveformDsp.md` already documents
  `WaveformWindowType` as a flat enum and doesn't promise a `beta`
  parameter on `generate_window`.
- The enum->scipy-name map deliberately duplicates a few lines already
  present in `dsp/_spectral.py` rather than sharing them, per chunk 21's own
  documented design constraint (§Organization / §Compliance 2: no sibling
  mixin imports) and this chunk's item 4 instruction not to unify the two.
- `window_coherent_gain`/`window_processing_gain` are instance methods
  (mean / RMS of `generate_window` at `self`'s own sample count), matching
  the Swift reference's `windowCoherentGain(for:)`/`windowProcessingGain(for:)`
  and the family-contract table (only `generate_window` is called out as a
  staticmethod).
- No new result-factory needed: `windowed` reuses `_with_values` (same
  `dt`/`t0`, new samples) — no contract change to `waveformDsp.md` was
  required.
- `windowed`/`window_coherent_gain`/`window_processing_gain` raise
  `ValueError` on an empty (0-sample) waveform, and `generate_window` raises
  `ValueError` for `length <= 0` — per §Numerical conventions (these are not
  detector methods).
- Gate: `make uv-fullCheck` green (ruff clean, mypy strict clean over
  `src`+`tests`, pytest 1102 passed, including the 15 new tests in
  `tests/waveforms/dsp/test_windowing.py` and the existing
  `test_dsp_mixins_do_not_import_sibling_mixins` layering test, which
  confirms `_windowing.py` imports only scipy/numpy plus
  `_protocol`/`support`).
- No deviation from the chunk beyond following the already-merged chunk 18
  mixin-typing fix as instructed.
