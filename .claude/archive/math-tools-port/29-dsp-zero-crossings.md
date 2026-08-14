---
chunk: 29-dsp-zero-crossings
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (ZeroCrossingMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
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

- [x] Rate and sub-sample interpolation tests pass
- [x] `make uv-fullCheck` passes

## Out of scope

Trigger detection (27).

## Resolution notes

- Implemented per the chunk's own Design constraints, using
  `dsp/_triggers.py`'s `_sign_change_events` sign-change-mask technique
  (`previous <= 0 & current > 0` for rising, mirrored for falling) at
  `level=0`, plus a per-crossing linear-interpolation refinement step for
  `time_seconds`. "Exact zeros count once" falls out of that same
  non-strict/strict split used by the trigger mixin: a sample sitting
  exactly on zero can only ever be the *departed* side of one crossing,
  never both.
- Mixin follows the chunk-18 self-typing idiom exactly (`class
  ZeroCrossingMixin:` with `self: WaveformProtocol` per method); no nominal
  `Protocol` inheritance. Only the two already-merged factories were
  needed: `segments_between_zero_crossings` uses `_with_t0` (same `dt`, new
  `t0` per segment); no fourth factory was required.
- `zero_crossing_count`/`zero_crossing_rate` both took on an optional
  `direction: WaveformZeroCrossingDirection = BOTH` parameter beyond the
  chunk's literal `zero_crossing_rate() -> float` text, matching the Swift
  reference's `zeroCrossingRate(direction:)` overload and this mixin's own
  `zero_crossings(direction=...)`. This is a backward-compatible superset
  (the chunk's own `zero_crossing_rate()` call still works via the
  default) rather than a contract narrowing, so no spec edit/semver bump
  was needed for it.
- `segments_between_zero_crossings` mirrors the Swift reference's
  *inclusive*-range segmentation (`values[startIdx...endIdx]`), not
  `dsp/_time_alignment.py`'s exclusive/non-overlapping split — each
  interior crossing sample is shared by the two segments it borders, which
  is what makes "lengths sum to ≈ n" (not exactly `n`) true, matching the
  chunk's own TDD wording. Return type is `list[WaveformProtocol]`
  (self-typed), not the spec table's descriptive `list[Waveform1D]` — same
  established discrepancy already present for `TimeAlignmentMixin.
  synchronize`/`time_windows`/`time_segments` in the same spec table; no
  spec change needed.
- No surprises during implementation; all 14 new tests passed on the first
  run against the initial implementation, and `make uv-fullCheck` (ruff +
  mypy strict + full 1116-test pytest suite, including the sibling-import
  layering test) passed clean.
