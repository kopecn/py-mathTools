---
chunk: 07-quaternion-additions
track: B
status: pending
depends_on: [06]
spec: ../specs/spatialMath.md §Quaternion additions, §Cross-cutting conventions
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 07 — `Quaternion` additions

**Deliverable:** the five spec'd additions to the existing class — nothing
else changes.

## Files

- Edit: `src/math_tools/spatial/quaternion.py`
- Create: `tests/spatial/test_quaternion_additions.py` (existing
  `tests/test_quaternion.py` is untouched)

## Design constraints

Per spec §Quaternion additions, add exactly:

1. `dot(other: Quaternion) -> float` — 4-component dot.
2. `rotation_matrix_elements` property → new frozen dataclass
   `RotationMatrixElements` (fields `xx…zz`, float) defined in the same
   module, derived by delegating to the existing `to_rotation_matrix()`
   (single source — do not re-derive from components).
3. `rotate_position(p: Position) -> Position` — wraps the existing
   `rotate_vector`; import `Position` from `.position`.
4. `__array__(dtype=None)` → `[w, x, y, z]` float64.
5. Aliases `from_numpy_quaternion` / `to_unit_spherical_small_circle`
   delegating to the camelCase originals; originals get a "deprecated
   spelling" docstring line, no removal, no warning machinery.

Existing behavior is authoritative — if a change to an existing method seems
needed, STOP and report instead.

## TDD steps

1. Failing tests: `dot` (orthogonal → 0, self → norm²),
   `rotation_matrix_elements` equals `to_rotation_matrix()` entries,
   `rotate_position` matches `rotate_vector` on the same input,
   `np.asarray(q)` order `[w,x,y,z]`, aliases are the same functions.
2. Implement. 3. `make uv-fullCheck` green (all ~90 legacy tests still pass).

## Acceptance criteria

- [ ] Diff to `quaternion.py` is additive only (no modified existing lines except imports)
- [ ] Legacy `tests/test_quaternion.py` passes unmodified in this chunk
- [ ] `make uv-fullCheck` passes

## Out of scope

Renaming/refactoring existing members; `SpatialPose`; double-cover changes.
