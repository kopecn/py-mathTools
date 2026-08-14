---
chunk: 26-dsp-time-alignment
track: D
status: complete
depends_on: [14, 19]
spec: ../specs/waveformDsp.md §Family contracts (TimeAlignmentMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
author: Nicholas Bergantz
---

# 26 — `TimeAlignmentMixin`

**Deliverable:** `dsp/_time_alignment.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+TimeAlignment.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_time_alignment.py`,
`tests/waveforms/dsp/test_time_alignment.py`. Test-subclass note: this
mixin's CORRELATION method calls the correlation surface, so the test
subclass composes both: `class _W(TimeAlignmentMixin, CorrelationMixin,
Waveform1D)`.

## Design constraints

- Methods per spec table: `aligned(to, method: WaveformAlignmentMethod =
  CORRELATION)` (shift by detected lag; START_TIME aligns `t0`s),
  `time_lag(to, max_lag=None) -> WaveformTimeLag | None` (None when no
  correlation peak qualifies), classmethod
  `synchronize(waveforms) -> list[Waveform1D]` (common overlapping span),
  `time_windows(window_duration, overlap=0.0) -> list[Waveform1D]`,
  `time_segments(boundaries) -> list[Waveform1D]`.
- Exception to the no-sibling-imports rule (documented in the spec's mixin
  rules as "via CorrelationMixin"): this mixin may TYPE against the
  protocol + call `self.cross_correlation`/`find_max_correlation` — declare
  those on a small local `Protocol` extension rather than importing
  `_correlation`, keeping module-level imports clean.

## TDD steps

1. Failing tests: `aligned` recovers a k-sample shift (result lag 0
   afterward); `synchronize` of two offset waveforms returns equal-length
   overlaps with matching `t0`; `time_windows(1.0, overlap=0.5)` count
   formula pinned; segment boundaries respected.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Shift-recovery and synchronize tests pass
- [x] No `import ... _correlation` at module level (grep)
- [x] `make uv-fullCheck` passes

## Out of scope

Resampling to a common rate (25's `resampled_to_match`).

## Resolution notes

- **Forced contract change: `WaveformProtocol` gained a third factory,
  `_with_t0(values, t0) -> WaveformProtocol`.** Every method in this chunk
  (`aligned`, `synchronize`, `time_windows`, `time_segments`) produces a
  result with the same `dt` as its source but a genuinely different `t0` —
  a shape neither existing factory covers (`_with_values`: same `dt`, same
  `t0`; `_with_axis`: new `dt`, same `t0`, added by chunk 25). Added
  `_with_t0` to `dsp/_protocol.py`'s `WaveformProtocol` and implemented it
  on `Waveform1D` (`waveforms/waveform1d.py`), giving the three factories a
  complete same-dt/same-t0 triangle. Per the 00-overview.md convention,
  `waveformDsp.md` §Organization documents the addition and its semver was
  bumped 0.0.4 → 0.0.5. `_protocol.py` and `waveform1d.py` are the only
  files touched outside this chunk's own `Files` list.
- **`time_lag` is deliberately `t0`-aware, unlike `CorrelationMixin.
  find_max_correlation`.** `find_max_correlation` is a pure value-domain
  measure — it correlates `values` arrays and never looks at either
  waveform's `t0`. That's correct for "how similar are these sample
  arrays," but wrong for a method named `time_lag` living in a mixin about
  time-axis reasoning: two waveforms whose `t0`s already differ can have
  identical values (raw lag 0) yet clearly occur at different real times.
  `TimeAlignmentMixin.time_lag` (via the module-level `_correlating_time_lag`
  helper) adds the existing `t0` offset between the two waveforms (rounded
  to the nearest sample) to the raw value-domain lag `find_max_correlation`
  returns, producing a genuine real-world sample/second offset. This is
  also what makes `aligned`'s `CORRELATION` method a true round trip:
  shifting `t0` by `-lag_samples * dt` always drives a second `time_lag`
  call back to lag 0 (the pinned "result lag 0 afterward" acceptance
  criterion) — a purely value-domain lag could not guarantee that once the
  two waveforms' `t0`s already differ, since shifting `t0` alone never
  touches the values `find_max_correlation` looks at. Verified directly:
  `TestAlignedCorrelationRecoversKnownShift` pins the round trip for k in
  {0, 3, 17} sample shifts, and `TestTimeLagAccountsForExistingT0Offset`
  pins the `t0`-offset-only case (identical values, different `t0`) against
  a raw `find_max_correlation` call that would report lag 0 for the same
  inputs.
- **Correlation-mixin cross-reference without importing `_correlation`.**
  Per the design constraint, `aligned`'s `CORRELATION` method and `time_lag`
  need `CorrelationMixin.find_max_correlation` but must not import
  `dsp/_correlation.py` (waveformDsp.md §Organization / §Compliance 2, "no
  sibling mixin imports"). Declared a small local `Protocol` extension,
  `_CorrelatingWaveform(WaveformProtocol, Protocol)`, naming only the
  `find_max_correlation` signature needed; any host composing both mixins
  (this chunk's own `_W(TimeAlignmentMixin, CorrelationMixin, Waveform1D)`
  test subclass, and `Waveform1D` from the compose chunk onward) satisfies
  it structurally. `tests/test_package_layering.py::
  test_dsp_mixins_do_not_import_sibling_mixins` (a static AST scan) and a
  manual grep both confirm no `_correlation` import exists in the module.
  `find_max_correlation`/`time_lag` are called through a module-level
  helper (`_correlating_time_lag`), not a same-class `self.time_lag(...)`
  call from `aligned` — matching every other DSP mixin's internal-sharing
  convention of module-level helpers over same-class method calls (e.g.
  `dsp/_resampling.py`'s `_resample_to_frequency`).
- **Chunk 19's import-cycle risk (point 4 of this chunk's brief): still
  latent, not triggered.** This mixin imports `WaveformAlignmentMethod`/
  `WaveformTimeLag` from `waveforms/support.py`, which imports
  `waveforms/waveform1d.py` — the same shape chunk 19 flagged for
  `_correlation.py`. `waveform1d.py` still does not import back into
  `dsp/` (mixins compose in a later chunk, 30), so no cycle exists today;
  documented again in the module docstring per the brief's instruction to
  report rather than silently work around it.
- **`time_segments(boundaries)` and `time_windows(window_duration,
  overlap)` take float-seconds arguments** (relative to `t0`), not sample
  indices or `PrecisionTimestamp`s — the spec table's `time_windows(...)`/
  `time_segments(...)` entries were intentionally abbreviated (matching
  other family-contract rows with optional-heavy signatures); the concrete
  signatures are pinned by this chunk's own tests.
  `time_windows`/`time_segments` are not detectors (waveformDsp.md
  §Numerical conventions), so both raise `ValueError` (naming the
  requirement) rather than returning `[]` when the input is too short —
  `time_windows` when even one window doesn't fit, `time_segments` when the
  waveform is empty or a boundary falls outside the open span
  `(0, duration_seconds)`.
- **`synchronize` does not resample mismatched-rate inputs**, unlike the
  Swift reference's `resampleToCommonRate` option — matching this chunk's
  own Out of scope note ("Resampling to a common rate" is chunk 25's
  `resampled_to_match`, not this one's). Every input to `synchronize` must
  already share the same `dt`; a mismatch raises `WaveformCompatibilityError`.
- Bug caught by the TDD run itself (not by inspection): `time_segments`'s
  first implementation zipped `split_points` against `split_points[1:]`
  with `strict=True`, added defensively for ruff's B905 ("zip without an
  explicit strict= parameter"). Since that pairwise idiom's two sequences
  are intentionally offset by one element, `strict=True` made every
  non-trivial call raise `ValueError: zip() argument 2 is shorter than
  argument 1`. Fixed to `strict=False`, which still satisfies B905 (an
  explicit value was given) while preserving the intended pairwise
  semantics.
- 26 new tests in `tests/waveforms/dsp/test_time_alignment.py`; full gate
  (`make uv-fullCheck`) green: ruff clean, mypy strict clean (70 source
  files), 1055 passed.
