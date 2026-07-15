---
chunk: 16-waveform-quaternion
track: C
status: complete
depends_on: [11, 07]
spec: ../specs/waveformCore.md §ABC accessor, §Aggregate containers, §Compliance 1, 2, 8
last_updated: 2026-07-14
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

- [x] Compliance 1, 2, 8 named tests pass; tuple field names are `(w, x, y, z)`
- [x] `w[i]` returns a `Quaternion` equal to the stored row
- [x] `make uv-fullCheck` passes

## Out of scope

Pose container (17); slerp/orientation interpolation on series (not in spec).

## Resolution notes

- `WaveformQuaternion(QuaternionWaveformABC)` mirrors `WaveformPosition`'s
  (chunk 15) structure exactly, with `Element = Quaternion` and `(n, 4)`
  storage in **`(w, x, y, z)` order** — pinned repo-wide, NOT Swift's
  x-first order. `component_waveforms`'s `NamedTuple` fields are literally
  named `w`, `x`, `y`, `z` in that order; `from_components(w, x, y, z)` is
  w-first. Time-axis properties copied (not shared via a base class),
  matching chunk 15's own precedent.
- `_quaternions_to_array` / element materialization use `Quaternion`'s
  real `as_float_array()`/`from_float_array()` methods (chunk 07's
  `__array__`-adjacent additions), not invented ones.
- `are_all_unit` and `normalize()`'s zero-magnitude `ValueError` mirror
  `WaveformPosition`'s exact tolerance (`atol=1e-12`) and message style
  (`"cannot normalize a zero-magnitude quaternion at index {i}"`) — a
  judgment call since `Quaternion` itself has no `normalize()` method
  (only `normalized()`, no explicit zero-magnitude raise), so
  `WaveformPosition`/`Position.normalize`'s convention was the correct
  precedent to follow, not `Quaternion`'s.
  `are_all_unit`'s flip-after-append-non-unit behavior (an explicit TDD
  step in this chunk) is covered by
  `test_are_all_unit_flips_after_appending_non_unit`.
- `extend`/`concatenate` compat-check only `dt` (not length), matching
  chunk 15's precedent for concatenation ops.
- Verified live: `w[i]` returns a `Quaternion` equal to the stored row;
  `component_waveforms.w/x/y/z` (by name, not tuple position) matches the
  stored `(w,x,y,z)` order exactly; `to_dict()`/`from_dict()` round-trips
  to an equal instance; `foundationTypes.mathTypes.MathTypes.
  QuaternionWaveformType.from_dict()` accepts the same dict; the wire
  dict's per-element shape is confirmed to be exactly `{"w","x","y","z"}`
  (compliance 1).
- No spec change was needed; implementation matches waveformCore.md's
  §Aggregate containers section (Element = Quaternion) as written.
- Verified: 68 new tests in `tests/waveforms/test_waveform_quaternion.py`
  (including two 100,000-element compliance-10 smoke tests), full suite
  752 tests green, ruff clean, mypy strict clean (`make uv-fullCheck`).
