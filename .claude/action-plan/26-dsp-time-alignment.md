---
chunk: 26-dsp-time-alignment
track: D
status: pending
depends_on: [14, 19]
spec: ../specs/waveformDsp.md §Family contracts (TimeAlignmentMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] Shift-recovery and synchronize tests pass
- [ ] No `import ... _correlation` at module level (grep)
- [ ] `make uv-fullCheck` passes

## Out of scope

Resampling to a common rate (25's `resampled_to_match`).
