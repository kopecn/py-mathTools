---
chunk: 53-window-convention-reconciliation
track: F
status: complete
depends_on: []
spec: ../specs/waveformDsp.md §Family contracts
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 53 — Reconcile the symmetric/periodic window split between DSP families

## Origin

Post-audit finding D-windowing-(c). Confirmed by grep:

- `_windowing.py:86` — `get_window(..., fftbins=False)` (**symmetric**)
- `_spectral.py:100` — `get_window(...)` with scipy's default (**periodic**)

So `window_processing_gain(HANN)` and `window_coherent_gain(HANN)` describe a
different window than `power_spectral_density(window=HANN)` and
`spectrogram(window=HANN)` actually apply. A caller who uses the gain helpers
to correct a spectral estimate — the whole reason those helpers exist — gets a
subtly wrong scale factor.

`_windowing.py:7-12` documents the symmetric choice as deliberate, and it is
individually defensible; the defect is that the two families disagree and
nothing spec's or tests the seam.

Also folded in (same seam, same two files): `_DEFAULT_KAISER_BETA = 14.0` is
hardcoded independently at `_windowing.py:54` and `_spectral.py:80`, with no
shared constant and no test pinning them equal. The Swift reference makes beta
caller-supplied (`WaveformWindowType.swift:16`, `case kaiser(beta:)`), so the
Python surface silently narrows the capability *and* can drift between copies.

## Files

- Edit: `src/math_tools/waveforms/dsp/_windowing.py`
- Edit: `src/math_tools/waveforms/dsp/_spectral.py`
- Edit: `src/math_tools/waveforms/support.py` (if beta moves onto the enum)
- Edit: `tests/waveforms/dsp/test_windowing.py`
- Edit: `tests/waveforms/dsp/test_spectral.py`
- Edit: `.claude/specs/waveformDsp.md`

## Design constraints

1. **Decide and document, do not silently unify.** Both conventions are
   legitimate: symmetric for filter design and gain analysis, periodic for
   STFT/PSD. The requirement is that the spec states which family uses which
   and *why*, and that the gain helpers can describe the periodic window when
   asked. Recommended: keep the per-family defaults, but give the gain helpers
   and `generate_window` an explicit `periodic: bool = False` parameter so a
   caller correcting a PSD can request the matching convention.
2. Update waveformDsp.md §Family contracts with the chosen rule; bump `semver`.
3. Kaiser beta: single shared constant, imported by both modules — not two
   literals. If exposing caller-supplied beta (closing the Swift gap) is
   cheap given the enum shape, do it and spec it; if it forces an enum
   redesign, keep the shared constant and record the narrowing as a known
   deviation in the spec. State which path you took and why.
4. Do not change any existing default behavior of `power_spectral_density` or
   `spectrogram` — additive parameters only. Existing callers must be unaffected.

## TDD steps

1. Failing tests first:
   - `generate_window(HANN, n, periodic=True)` equals
     `scipy.signal.get_window("hann", n)` and `periodic=False` equals
     `get_window("hann", n, fftbins=False)` — pin both against scipy directly
   - the gain helpers, asked for the periodic convention, return the gain of the
     window `power_spectral_density` actually applies
   - a test asserting the Kaiser beta used by `_windowing` and `_spectral` is
     the same value, sourced from one constant
2. Implement.
3. Update the spec, bump `semver`.
4. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Spec states the per-family window convention and the rationale
- [x] Gain helpers can describe either convention; defaults unchanged
- [x] One shared Kaiser beta constant; equality pinned by test
- [x] Kaiser-beta decision (expose vs. document narrowing) recorded in the spec
- [x] `waveformDsp.md` `semver` bumped
- [x] `make uv-fullCheck` passes

## Out of scope

The broader DSP coverage gaps — chunk 55. The unconsumed support types
(`WaveformPaddingStrategy`, `WaveformFilterCoefficients`, `WaveformFrequencyRange`,
`WaveformSpectrogramScaling`) — chunk 57 records the decision.

## Resolution notes

- **Path taken:** kept the per-family defaults (`WindowingMixin` symmetric,
  `SpectralMixin` periodic) and added an explicit `periodic: bool = False`
  parameter to `generate_window`, `window_coherent_gain`, and
  `window_processing_gain` — the recommended path in the design constraints.
  `windowed` was deliberately left without a `periodic` parameter: it's
  `WindowingMixin`'s own use case (filter/analysis framing on a whole
  waveform), not a spectral-estimate-correction helper, so the extra
  parameter would be unused surface.
- **Kaiser beta:** moved to a single shared constant,
  `dsp/_common.DEFAULT_KAISER_BETA = 14.0`, imported by both
  `_windowing.py` and `_spectral.py` (both re-export it in `__all__` so
  mypy strict's explicit-reexport check allows the cross-module equality
  test). `support.py` was **not** touched — `WaveformWindowType` is a flat
  `str` enum with no `beta` field, and adding a caller-supplied beta would
  force an enum redesign (out of scope per the chunk's own constraint 3
  "if it forces an enum redesign, keep the shared constant and record the
  narrowing"). Recorded as a known Swift-parity deviation in
  waveformDsp.md's new §Window convention section.
- **Spec change:** added a new `## Window convention` section to
  `waveformDsp.md` (between §Family contracts and §Support descriptor
  types) documenting the symmetric-vs-periodic rule, why each family keeps
  its own default, the `periodic` parameter fix, and the Kaiser-beta
  decision. Updated the `WindowingMixin` row of the family-contracts table
  to show the new parameter. Bumped `semver` 0.0.7 → 0.0.8, `last_updated`
  → 2026-07-23.
- **Tests:** added to both `tests/waveforms/dsp/test_windowing.py` (pins
  `periodic=True`/`False` against `scipy.signal.get_window` directly, pins
  the gain helpers at `periodic=True` against `_spectral._window_array`'s
  actual output, pins the two Kaiser constants/arrays equal) and
  `tests/waveforms/dsp/test_spectral.py` (mirrors the shared-constant pin
  from that module's side, plus a regression pin that
  `power_spectral_density`'s default output/window is untouched by the
  reconciliation).
- **Surprise:** mypy strict's explicit-reexport rule (no
  `--no-implicit-reexport` override in this repo) rejected the tests'
  `module.DEFAULT_KAISER_BETA` attribute access until the constant was
  added to each module's `__all__` — a one-line fix in both
  `_windowing.py` and `_spectral.py`, no behavior change.
- **Gate:** `make uv-fullCheck` green — ruff clean, mypy strict clean
  (119 source files), pytest 1429 passed (0 failures, 0 skipped).
