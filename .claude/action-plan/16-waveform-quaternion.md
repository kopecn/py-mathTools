---
chunk: 16-waveform-quaternion
track: C
status: pending
depends_on: [11, 07]
spec: ../specs/waveformCore.md §ABC accessor, §Aggregate containers, §Compliance 1, 2, 8
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 16 — `WaveformQuaternion`

**Deliverable:** the quaternion time-series container.

## Files

- Create: `src/math_tools/waveforms/waveform_quaternion.py`
- Edit: `src/math_tools/waveforms/__init__.py` (export)
- Create: `tests/waveforms/test_waveform_quaternion.py`

## Design constraints

1. Subclass `QuaternionWaveformABC`. Storage `(n, 4)` float64
   `quaternions_array` in **`(w, x, y, z)` order** (pinned repo-wide); ABC
   accessor `quaternions -> Sequence[QuaternionABC]` materializes
   `Quaternion` objects.
2. Mirror chunk 15's structure with `Element = Quaternion`:
   `from_components(w, x, y, z)` (w-first),
   `component_waveforms -> NamedTuple(w, x, y, z)` (w-first — NOT the Swift
   x-first order), `are_all_unit` (unit stem, not "normalized"),
   `normalize()`/`normalized()`, element access/iteration, mutation verbs,
   `extend`/`concatenate`, `==`/`repr`/`to_dict`/`from_dict`.
3. Vectorized normalization: row-wise norm over the array; `ValueError` on a
   zero row.

## TDD steps

1. Failing tests: `QuaternionWaveformType` wire round-trip (compliance 1;
   note wire dicts are per-element `{"w","x","y","z"}`); dt-mismatch (2);
   `component_waveforms` → `from_components` exact round-trip with the
   w-first order pinned by name access (compliance 8); `are_all_unit` flips
   after appending a non-unit element.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Compliance 1, 2, 8 named tests pass; tuple field names are `(w, x, y, z)`
- [ ] `w[i]` returns a `Quaternion` equal to the stored row
- [ ] `make uv-fullCheck` passes

## Out of scope

Pose container (17); slerp/orientation interpolation on series (not in spec).
