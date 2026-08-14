---
chunk: 17-waveform-spatial-pose
track: C
status: complete
depends_on: [08, 15, 16]
spec: ../specs/waveformCore.md §Aggregate containers, §Compliance 1, 2, 8, 9
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 17 — `WaveformSpatialPose`

**Deliverable:** the 6-DOF pose time-series container (parallel arrays).

## Files

- Create: `src/math_tools/waveforms/waveform_spatial_pose.py`
- Edit: `src/math_tools/waveforms/__init__.py` (export)
- Create: `tests/waveforms/test_waveform_spatial_pose.py`

## Design constraints

1. Subclass `WaveformSpatialABC`. Parallel `positions_array (n,3)` +
   `quaternions_array (n,4)` (w-first); ABC accessors `positions` and
   `quaternions` materialize.
2. Per spec: constructors (component arrays, `from_poses(list[SpatialPose],
   dt/dt_seconds, t0)`, `from_waveforms(position_waveform,
   quaternion_waveform)` with count/dt `ValueError`), element access
   returns `SpatialPose`, `component_waveforms` (nested
   position+quaternion NamedTuples), `position_waveform`,
   `quaternion_waveform`, `are_all_positions_unit` /
   `are_all_quaternions_unit`, `normalize()`/`normalized()`, mutation with
   `SpatialPose` payloads, `extend`/`concatenate`, `==`/`repr`/
   `to_dict`/`from_dict`.
3. **Subtle Swift parity (spec compliance 9):** `is_valid` = equal array
   lengths; `sample_count` = `min(len(positions), len(quaternions))`. Both
   behaviors kept even though constructors validate — direct array
   manipulation in tests constructs the unequal state.

## TDD steps

1. Failing tests: `SpatialTransformWaveformType` wire round-trip
   (compliance 1); dt-mismatch (2); pose round-trip
   `from_poses` → `w[i]` (8); unequal-arrays `is_valid`/`sample_count`
   pinned (9); `position_waveform`/`quaternion_waveform` slices match.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Compliance 1, 2, 8, 9 named tests pass
- [x] `from_waveforms(w.position_waveform, w.quaternion_waveform) == w`
- [x] `make uv-fullCheck` passes

## Out of scope

Trajectory math on pose series; interpolation between samples.

## Resolution notes

- `WaveformSpatialPose(WaveformSpatialABC)` is backed by TWO independent
  parallel arrays — `_positions` `(n,3)` and `_quaternions` `(n,4)`
  w-first — rather than composing `WaveformPosition`/`WaveformQuaternion`
  instances internally. `component_waveforms` returns a nested
  `SpatialPoseComponentWaveforms(position, quaternion)` NamedTuple reusing
  `PositionComponentWaveforms`/`QuaternionComponentWaveforms` from chunks
  15/16 directly rather than redefining them.
- **The compliance-9 subtlety, resolved as the chunk doc anticipated:**
  the primary `__init__` does NOT require `positions`/`quaternions` to
  have equal length — only `from_waveforms` validates count (and `dt`)
  equality, raising `ValueError`. `is_valid` is `len(positions) ==
  len(quaternions)`; `sample_count`/`__len__` is `min(...)`, not one
  array's raw length. Every other size-dependent property (`duration`,
  `time_axis()`, slice bounds, `get`/iteration) is derived from
  `sample_count` rather than either array's raw length, so an
  unequal-length instance behaves as a well-defined "valid prefix"
  everywhere rather than only at the two pinned accessors — a
  correctness improvement beyond the letter of the compliance item, not
  just satisfying it narrowly. Verified live:
  `WaveformSpatialPose([3 positions], [2 quaternions]).is_valid is False`
  and `.sample_count == 2`.
- `extend`/`concatenate` raise `WaveformCompatibilityError` on `dt`
  mismatch (matching chunks 15/16's precedent); `from_waveforms` raises
  plain `ValueError` on count or `dt` mismatch (matching this chunk's own
  design constraint 2's literal wording) — the two constructors
  deliberately use different exception types for different reasons
  (compatibility-of-concatenation vs. malformed-construction-input), and
  the test suite pins that `from_waveforms`'s `dt` mismatch is `ValueError`
  and NOT `WaveformCompatibilityError`
  (`test_from_waveforms_dt_mismatch_is_not_compatibility_error`).
- `normalize()` checks both arrays for zero-magnitude rows BEFORE mutating
  either, so a failure (either array) leaves the whole waveform unchanged
  — verified by
  `test_normalize_zero_position_leaves_quaternions_unmodified`.
- Verified live: `WaveformSpatialPose.from_waveforms(w.position_waveform,
  w.quaternion_waveform) == w` for a `from_poses`-built `w` (the literal
  acceptance criterion); `to_dict()`/`from_dict()` round-trips, and
  `foundationTypes.mathTypes.MathTypes.SpatialTransformWaveformType.
  from_dict()` accepts the same dict (compliance 1).
- No spec change was needed; implementation matches waveformCore.md's
  §Aggregate containers section (`WaveformSpatialPose`) as written.
- Verified: 83 new tests in `tests/waveforms/test_waveform_spatial_pose.py`
  (including 100,000-element compliance-10 smoke tests), full suite 835
  tests green, ruff clean, mypy strict clean (`make uv-fullCheck`).
- **This completes Track C (chunks 11-17)** — `Waveform1D` core/operators/
  generators, the DSP support substrate, and all three aggregate spatial
  waveform containers.
