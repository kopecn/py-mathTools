---
chunk: 06-position
track: B
status: complete
depends_on: [02]
spec: ../specs/spatialMath.md §Cross-cutting conventions, §Position, §Compliance 1–3, 10
last_updated: 2026-07-13
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

- [x] Round-trip with `foundationTypes` `PositionType` wire dicts (compliance 1)
- [x] Both spherical conventions inverse-tested over a radius/angle grid, atol 1e-12
- [x] `hash` raises `TypeError`; `np.asarray(p)` returns the `(3,)` vector
- [x] `make uv-fullCheck` passes

## Out of scope

`SpatialPose` (08); Quaternion changes (07); any use in waveforms.

## Resolution notes

- `spatial/__init__.py` was empty (0 bytes) before this chunk — `Quaternion`
  was never exported there (tests import it directly from
  `math_tools.spatial.quaternion`). "Export `Position` alongside the existing
  `Quaternion`" was read as: populate `__init__.py` with both, since that's
  the first time the package `__init__` gets real content.
- Inverse-coordinate `NamedTuple`s are named `CylindricalCoordinates`,
  `SphericalCoordinates`, `SphericalIsoCoordinates` (module-level in
  `position.py`) — the spec only names the properties, not the tuple types.
- `distance`/`distance_squared` use parameter name `to` (matching the Swift
  `distance(to:)` label and the spec's literal `distance(to)` signature)
  rather than `other`.
- `__array__` implements the newer NEP 51 two-arg signature
  (`dtype`, `copy`) for numpy 2.x compatibility (installed: numpy 2.5.1) and
  always returns a defensive copy regardless of the `copy` argument, to keep
  the private `_vector` unaliased — same rationale as the `vector` property.
- Division is scalar-only, forward direction only (`position / scalar`); per
  spec, only `*` gets both left/right scalar orders, `/` does not get an
  `__rtruediv__`. Confirmed by literal spec wording and the Swift source
  (`Position+Arithmetic.swift` has no `Double / Position` overload).
- `normalize()`/`normalized()` raise `ValueError` on the zero vector — this is
  a deliberate, spec-pinned deviation from the Swift source, which silently
  zeroes the vector instead of raising. No spec change needed; the chunk's
  design constraints already called this out explicitly.
- No `errors.py` changes: `ValueError`/`TypeError` (stdlib) fully cover this
  chunk's failure modes per `mathToolsArchitecture.md` §Error semantics; no
  new `MathToolsError` subtype was warranted.
