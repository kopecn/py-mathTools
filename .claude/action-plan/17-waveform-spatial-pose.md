---
chunk: 17-waveform-spatial-pose
track: C
status: pending
depends_on: [08, 15, 16]
spec: ../specs/waveformCore.md §Aggregate containers, §Compliance 1, 2, 8, 9
last_updated: 2026-07-11
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

- [ ] Compliance 1, 2, 8, 9 named tests pass
- [ ] `from_waveforms(w.position_waveform, w.quaternion_waveform) == w`
- [ ] `make uv-fullCheck` passes

## Out of scope

Trajectory math on pose series; interpolation between samples.
