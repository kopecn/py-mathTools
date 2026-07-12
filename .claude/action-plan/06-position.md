---
chunk: 06-position
track: B
status: pending
depends_on: [02]
spec: ../specs/spatialMath.md §Cross-cutting conventions, §Position, §Compliance 1–3, 10
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 06 — `Position`

**Deliverable:** the numpy-backed 3D position type.

## Files

- Create: `src/math_tools/spatial/position.py`
- Edit: `src/math_tools/spatial/__init__.py` (export `Position` alongside
  the existing `Quaternion`)
- Create: `tests/spatial/__init__.py`, `tests/spatial/test_position.py`

## Design constraints

1. Subclass `foundation_abc.math.spatialABCs.PositionABC`. Storage: private
   `(3,)` float64 ndarray; `x/y/z` are settable properties into it.
2. Full surface per spec §Position: constructors (`__init__(x, y, z)`,
   `from_vector(ArrayLike)`, `from_components(x, y, z)` scalars,
   `from_cylindrical`, `from_spherical`, `from_spherical_iso`,
   `origin/unit_x/unit_y/unit_z`, `from_dict`), NamedTuple inverse
   accessors (`cylindrical`, `spherical`, `spherical_iso`), operators
   (`+ - * /` with scalar broadcast both orders, in-place, unary),
   `dot`/`cross`/`distance`/`distance_squared`,
   `magnitude`/`magnitude_squared`/`norm`/`__abs__`/`is_unit`,
   `normalize()`/`normalized()` (`ValueError` on zero vector),
   `==`/`isclose(rtol, atol)`/`repr`/`to_dict`, `__array__`,
   `__hash__ = None`.
3. Coordinate conventions per spec §Coordinate conventions — the two
   spherical variants are distinct; reuse the ISO docstring language from
   `math_tools/spherical/spherical_generators.py` by reference, not copy.
4. Style-match the incumbent `spatial/quaternion.py` (dataclass-flavored,
   docstrings, classmethod constructors).

## TDD steps

1. Failing tests: coordinate init/accessor inverse grids (compliance 2),
   `unit_x × unit_y == unit_z` (compliance 3), operator algebra, zero-vector
   normalize `ValueError`, `__hash__ is None`, `np.asarray(p)` shape.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Round-trip with `foundationTypes` `PositionType` wire dicts (compliance 1)
- [ ] Both spherical conventions inverse-tested over a radius/angle grid, atol 1e-12
- [ ] `hash` raises `TypeError`; `np.asarray(p)` returns the `(3,)` vector
- [ ] `make uv-fullCheck` passes

## Out of scope

`SpatialPose` (08); Quaternion changes (07); any use in waveforms.
