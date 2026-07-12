---
chunk: 15-waveform-position
track: C
status: pending
depends_on: [11, 06]
spec: ../specs/waveformCore.md §ABC accessor, §Aggregate containers, §Compliance 1, 2, 8, 10
last_updated: 2026-07-11
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

- [ ] Compliance 1, 2, 8 named tests pass
- [ ] `w[i]` returns a `Position` equal to the stored row
- [ ] `make uv-fullCheck` passes

## Out of scope

Quaternion/pose containers (16, 17); DSP on components.
