---
chunk: 15-waveform-position
track: C
status: complete
depends_on: [11, 06]
spec: ../specs/waveformCore.md §ABC accessor, §Aggregate containers, §Compliance 1, 2, 8, 10
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 15 — `WaveformPosition`

**Deliverable:** the position time-series container.

## Files

- Create: `src/math_tools/waveforms/waveform_position.py`
- Edit: `src/math_tools/waveforms/__init__.py` (export)
- Create: `tests/waveforms/test_waveform_position.py`

## Design constraints

1. Subclass `PositionWaveformABC`. Storage `(n, 3)` float64
   `positions_array`; ABC accessor `positions -> Sequence[PositionABC]`
   materializes `Position` objects on access. Time axis identical to
   `Waveform1D` (same shared behavior — extract a private helper/mixin from
   `waveform1d.py` ONLY if it avoids real duplication; copying the ~6 small
   time properties is acceptable).
2. Per spec §Aggregate containers with `Element = Position`: constructors
   (element list, `from_components(x, y, z)` from `Waveform1D`s with
   count/dt `ValueError`), element access (`w[i]`, `w[a:b]`, `get(i)`,
   `__iter__`), `component_waveforms -> NamedTuple(x, y, z)`,
   `are_all_unit`, `normalize()`/`normalized()` (`ValueError` on
   zero-magnitude element), mutation verbs with `Position` payloads,
   `extend`/`concatenate` (`WaveformCompatibilityError` on dt mismatch),
   `==`/`repr`/`to_dict`/`from_dict`.
3. Bulk paths (normalize, component split) are vectorized over
   `positions_array` — never loop over materialized `Position`s
   (spec compliance 10).

## TDD steps

1. Failing tests: `PositionWaveformType` wire round-trip (compliance 1);
   dt-mismatch raises (2); `component_waveforms` → `from_components`
   round-trip (8); slice materialization; normalize on a zero row raises.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Compliance 1, 2, 8 named tests pass
- [x] `w[i]` returns a `Position` equal to the stored row
- [x] `make uv-fullCheck` passes

## Out of scope

Quaternion/pose containers (16, 17); DSP on components.

## Resolution notes

- `WaveformPosition(PositionWaveformABC)`: `(n, 3)` float64 storage in
  `_positions`; `positions_array` bulk accessor (copied on read); the
  ABC-required `positions` accessor materializes a fresh `Position` list
  on each access, while `normalize`/`normalized`/`component_waveforms`
  stay fully vectorized over `_positions` and never construct per-element
  objects internally (compliance 10).
- Time-axis properties (`dt`, `t0`, `duration(_seconds)`,
  `sampling_frequency_hz`, `nyquist_frequency_hz`, `sample_count`/
  `__len__`, `time_axis()`) are copied from `Waveform1D`'s implementation
  rather than shared via a base class, per this chunk's own explicit
  "copying the ~6 small time properties is acceptable" constraint — a
  premature shared base was correctly avoided.
- `from_components(x, y, z)` validates length and `dt` equality (raising
  `ValueError` on either mismatch, replacing Swift's optional-returning
  `init?`); `t0` is taken from `x` alone (not cross-checked), which is
  sufficient for an exact round-trip since `component_waveforms` always
  produces `x`/`y`/`z` sharing the source waveform's own `t0`.
  `extend`/`concatenate` compat-check only `dt` (not length) since these
  are concatenation ops, matching the spec's literal "dt mismatch" wording
  (contrast with `Waveform1D`'s elementwise operators, which check both).
- `are_all_unit` and the zero-magnitude `ValueError` in `normalize()` use
  the same `atol=1e-12` tolerance and error-message style as
  `Position.is_unit`/`Position.normalize()`, for parity with the
  non-waveform type.
- Verified live: `w[i]` returns a `Position` equal to the stored row;
  `to_dict()`/`from_dict()` round-trips to an equal instance, and
  `foundationTypes.mathTypes.MathTypes.PositionWaveformType.from_dict()`
  accepts the same dict without error (compliance 1).
- No spec change was needed; implementation matches waveformCore.md's
  §Aggregate containers section (Element = Position) as written.
- Verified: 66 new tests in `tests/waveforms/test_waveform_position.py`
  (including two 100,000-sample compliance-10 smoke tests for `normalize`
  and `component_waveforms`, each asserted under 5s), full suite 684 tests
  green, ruff clean, mypy strict clean (`make uv-fullCheck`).
