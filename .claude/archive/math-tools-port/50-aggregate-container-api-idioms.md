---
chunk: 50-aggregate-container-api-idioms
track: F
status: complete
depends_on: [49]
spec: ../specs/mathToolsArchitecture.md §API idioms (lines 126-128), ../specs/waveformCore.md:137
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 50 — Aggregate waveform containers: missing shared API idioms

## Origin

Post-audit findings C-1, C-2, C-3 (class **a**). Confirmed at runtime:

```
WaveformPosition     array: False  isclose: False  from_components: True
WaveformQuaternion   array: False  isclose: False  from_components: True
WaveformSpatialPose  array: False  isclose: False  from_components: False
```

Three repo-wide idioms that `Position`, `Quaternion`, and `Waveform1D` all
honor are absent from all three aggregate containers:

- **`__array__`** — mathToolsArchitecture.md:128 ("array-like classes implement
  `__array__` so `np.asarray(x)` works"), inherited by every chunk via
  00-overview convention 7.
- **`isclose(rtol, atol)`** — mathToolsArchitecture.md:126-128. The containers
  currently offer only exact `==`, which is close to useless for float
  trajectories.
- **`from_components`** on `WaveformSpatialPose` — waveformCore.md:137 says all
  *three* aggregates share it; pose got only `from_poses`/`from_waveforms`,
  which the spec calls *additional*. Chunk 17 dropped it silently.

Depends on 49 so the pose indexing fix lands first — `__array__` and `isclose`
must both read through the corrected `sample_count` prefix.

## Files

- Edit: `src/math_tools/waveforms/waveform_position.py`
- Edit: `src/math_tools/waveforms/waveform_quaternion.py`
- Edit: `src/math_tools/waveforms/waveform_spatial_pose.py`
- Edit: `tests/waveforms/test_waveform_position.py`
- Edit: `tests/waveforms/test_waveform_quaternion.py`
- Edit: `tests/waveforms/test_waveform_spatial_pose.py`

## Design constraints

1. `__array__` returns the `sample_count`-truncated array, not the raw backing
   store. For `WaveformSpatialPose` — which has two backing arrays — decide the
   shape deliberately: prefer a `(sample_count, 7)` stack of
   `[x, y, z, w, i, j, k]`, document it in the docstring, and state it in
   waveformCore.md. This is a contract addition, so bump that spec's `semver`.
2. `__array__` must honor NumPy 2's `copy` argument: raise `ValueError` when
   `copy=False` is requested and a copy is unavoidable. (`Waveform1D.__array__`
   at `waveform1d.py:1118-1121` gets this wrong too — finding C-7 — fix it there
   in the same pass, since it is the same three lines and the same contract.)
3. `isclose(other, rtol=..., atol=...)` mirrors the signature already used by
   `Position.isclose` — do not invent a different parameter order. Return
   `False` on differing `sample_count`. For `WaveformQuaternion` and the
   quaternion half of `WaveformSpatialPose`, be **double-cover aware**: `q` and
   `-q` are the same rotation, matching `Quaternion.isclose`.
4. `WaveformSpatialPose.from_components` takes per-component `Waveform1D`s
   consistent with the other two aggregates' signature. Read
   `WaveformPosition.from_components` and follow its shape exactly.

## TDD steps

1. Failing tests first, for each of the three containers:
   - `np.asarray(w)` returns the documented shape and the truncated sample count
   - `np.array(w, copy=False)` raises `ValueError`
   - `isclose` true for a perturbation within tolerance, false outside it,
     false on differing `sample_count`
   - quaternion containers: `isclose(w, -w)` is `True` (double cover)
   - `WaveformSpatialPose.from_components(...)` round-trips against
     `from_poses`
2. Implement.
3. Update `waveformCore.md` with the `__array__` shape contract; bump `semver`.
4. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All three containers expose `__array__`, `isclose`, `from_components`
- [x] `__array__` reads the `sample_count` prefix and honors `copy=False`
- [x] `Waveform1D.__array__` `copy` contract fixed too
- [x] Double-cover awareness tested for both quaternion-bearing containers
- [x] `waveformCore.md` documents the array shape; `semver` bumped
- [x] `make uv-fullCheck` passes

## Out of scope

Generator off-by-one fixes (chunk 51). DSP mixin coverage (chunk 55).

## Resolution notes

- **`Waveform1D.__array__` fix (design constraint 2)** was not listed under
  this chunk's `## Files`, but the chunk body explicitly directs fixing it
  "in the same pass" (finding C-7) — treated that instruction as
  authoritative over the (stale) file list. Added a regression test to
  `tests/waveforms/test_waveform1d_core.py` (also not in the original file
  list) for the same reason; no other file outside the listed set was
  touched.
- **`isclose` scope beyond the literal test list**: in addition to the
  required `sample_count` check, all three `isclose` implementations also
  return `False` on differing `dt`/`t0` (mirroring `Waveform1D.isclose`'s
  "same `dt`, same `t0`, all samples close" contract). This wasn't spelled
  out in the TDD steps but follows directly from what "whole-waveform
  isclose" means for a time series with its own time axis; tests for it were
  added alongside the required cases.
- **`isclose` tolerance defaults**: each container's `atol` default mirrors
  its wrapped element type — `0.0` for `WaveformPosition` (matches
  `Position.isclose`), `1e-11` for `WaveformQuaternion` (matches
  `Quaternion.isclose`), and `0.0` for `WaveformSpatialPose` (position
  default; one `rtol`/`atol` pair is applied uniformly to both the position
  and quaternion halves — no separate per-half tolerance parameter was
  introduced, keeping the signature identical in shape to
  `Position.isclose`).
- **Double-cover awareness is per-sample, not per-waveform**: for
  `WaveformQuaternion`/`WaveformSpatialPose`, each row independently may
  match `other`'s row or its negation (vectorized via
  `np.isclose(a, b) | np.isclose(a, -b)` reduced per row), not a single
  "flip everything or nothing" decision — this is the correct vectorization
  of `Quaternion.isclose`'s per-element double-cover check.
- **`WaveformSpatialPose.from_components` signature**: chose seven flat
  `Waveform1D` parameters (`position_x/y/z`, `quaternion_w/x/y/z`) rather
  than a nested-tuple signature accepting `PositionComponentWaveforms` /
  `QuaternionComponentWaveforms`, per design constraint 4's "follow
  `WaveformPosition.from_components`'s shape exactly" — each component stays
  its own explicit, individually-typed argument, consistent with the sibling
  constructors.
- Verified: `make uv-fullCheck` green (ruff clean, mypy strict clean over
  `src/` + `tests/`, 1410 tests passed).
