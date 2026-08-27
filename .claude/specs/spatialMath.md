---
version: 1.0
type: specification
name: spatialMath
purpose: Behavioral contract for the Position, Quaternion, and SpatialPose math types
spec: SpatialMath
scope: project
status: draft
applies_to: src/math_tools/spatial/, tests/spatial/
last_updated: 2026-08-26
semver: 0.1.1
author: Nicholas Bergantz
---

# Spatial Math Types

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). Ports the
> Swift `Position` / `Quaternion` / `SpatialPose` behavior (base types from
> spmFoundationTools plus the operator/constructor extensions in
> spmMathTools `FoundationMathTypes/Spatial/`) as Tier-3 SE(3) classes.

## Modules and base contracts

| Class | Module | Subclasses | Storage |
|---|---|---|---|
| `Position` | `spatial/position.py` | `PositionABC` | `np.ndarray` shape `(3,)` float64 |
| `Quaternion` | `spatial/quaternion.py` | `QuaternionABC` | `numpy-quaternion` |
| `SpatialPose` | `spatial/spatial_pose.py` | `SpatialTransformABC` | composed `Position` + `Quaternion` |

`Quaternion` is the **existing, tested implementation** (~90 tests). Its
math behavior is authoritative and unchanged, but one structural edit is
REQUIRED: the pinned foundation branch deleted
`foundationTypes.mathTypes.quaternionABC` — the base class re-parents to
`foundation_abc.math.spatialABCs.QuaternionABC`. The old ABC also carried
`DataModelHelper`; the new one is `ABC`-only, so serialization tests that
assert `DataModelHelper` inheritance update their base-class assertions
(`to_dict`/`from_dict` behavior itself is preserved by the new ABC).
Beyond that, this spec only adds the members under "Quaternion additions".

## Coordinate conventions (single source of truth)

- **spherical** (`azimuth`, `elevation`): elevation measured from the xy-plane
  (geographic).
- **spherical ISO** (`azimuth`, `polar`): polar measured from +z (ISO 80000-2
  colatitude) — the convention already documented in
  `math_tools/spherical/spherical_generators.py`; both conventions preserved,
  as in Swift.
- Angles in radians everywhere.

## Cross-cutting API conventions (all three classes)

- `normalized()` is a **method** returning a copy (matches the incumbent
  `Quaternion.normalized()`); `normalize()` mutates in place.
- Approximate comparison is `isclose(other, rtol=1e-9, atol=0.0) -> bool`
  (incumbent signature style; numpy `rtol`/`atol` vocabulary repo-wide).
- These classes are **mutable → unhashable**: each sets `__hash__ = None`
  explicitly (pinned by test). Hashable time types are the immutable
  exception ([precisionTimeMath.md](precisionTimeMath.md)).
- `__array__(dtype=None)` on `Position` (→ `(3,)` vector) and `Quaternion`
  (→ `[w, x, y, z]`), so `np.asarray(x)` / `plt.plot(...)` work directly.

### Deserializer error semantics (normative)

`from_dict` is public API reachable from untrusted wire data, so its input
validation is behavior rather than a developer-time check. Its outcomes SHALL
be identical whether or not assertions are enabled.

Per [mathToolsArchitecture.md](mathToolsArchitecture.md) §Error semantics
(programmer errors raise stdlib `TypeError`/`ValueError`), every `from_dict` on
`Position`, `Quaternion`, and `SpatialPose` SHALL:

- raise `TypeError` when the payload is not a `dict`, or when a field's value
  is not a real number (`bool` is rejected: it is an `int` subclass and is not
  a coordinate);
- raise `ValueError` when a required key is absent;
- carry a message naming the class, the key, and the offending type.

All three classes SHALL apply the same numeric-field rule and raise the same
exception type, with a message of the same form, for the same malformed
payload. Validation behavior SHALL NOT vary by class, and the rule SHALL NOT
appear on any public surface.

All three SHALL expose `from_dict` as `(cls: type[T], obj: Any) -> T`, so a
subclass deserializes to its own type.

### Non-unit quaternion inputs (normative)

Quaternion magnitude is not part of the rotation a quaternion represents.
Two APIs return a rotation *angle* derived from quaternion components, and
both MUST be invariant to a positive rescaling of their inputs:

- `SpatialPose.angular_distance(to)` — `f(αq₁, βq₂) == f(q₁, q₂)` for all
  `α, β > 0`.
- `Quaternion.angle` — `(αq).angle == q.angle` for all `α > 0`.

This section governs those two members only. `Quaternion.axis` is
scale-invariant by construction and `interpolate` is outside this contract;
neither is governed here.

### Degenerate (zero) magnitude (normative)

A zero vector has no direction and a zero quaternion has no rotation. Neither
is representable, so producing `nan` components is prohibited: the operation
MUST raise `ValueError` at the point of the invalid input, before a corrupt
value can propagate into a pose, a waveform, or serialized output. This applies
uniformly to `Position` and `Quaternion`: the zero-vector rule stated for
`Position.normalize()` under §`Position` and the zero-quaternion rule under
§`Quaternion` are one contract, not two.

## `Position`

Mutable components (`p.x = 1.0` allowed), matching the existing `Quaternion`
dataclass idiom.

**Constructors**
- `Position(x=0.0, y=0.0, z=0.0)`
- `from_vector(v: npt.ArrayLike) -> Position` (copies; `ValueError` unless it
  coerces to shape `(3,)`) — covers lists/tuples/arrays; there is no
  separate sequence constructor
- `from_components(x=0.0, y=0.0, z=0.0)` — scalar args, defaulted, matching
  the incumbent `Quaternion.from_components(w, x, y, z)` shape
- `from_cylindrical(radius, angle, height)`
- `from_spherical(radius, azimuth, elevation)`
- `from_spherical_iso(radius, azimuth, polar)`
- classmethod constants: `origin()`, `unit_x()`, `unit_y()`, `unit_z()`
- `from_dict({"x","y","z"})` (ABC)

**Properties**
- `x, y, z: float` (settable); `vector: npt.NDArray` (copy out);
  `components: list[float]`
- Inverse coordinate accessors returning `NamedTuple`s:
  `cylindrical -> (radius, angle, height)`,
  `spherical -> (radius, azimuth, elevation)`,
  `spherical_iso -> (radius, azimuth, polar)`
- `magnitude`, `magnitude_squared`, `is_unit` (recomputed, tolerance 1e-12);
  `norm` as an alias of `magnitude` (parity with the incumbent
  `Quaternion.norm`) and `__abs__` returning it

**Operators / methods**
- `+`/`-` position±position and position±scalar (scalar broadcast, both orders);
  `*`/`/` by scalar (both orders for `*`); in-place variants; unary `-`, `+`
- `dot(other) -> float`, `cross(other) -> Position`
- `distance(to)`, `distance_squared(to)`
- `normalize()` (in place; `ValueError` on zero vector),
  `normalized() -> Position`
- `==` (exact), `isclose(other, rtol, atol)`, `repr`, `to_dict`/`from_dict`

Swift's custom `•`/`×` operators map to the named methods `dot`/`cross` plus
`@` is NOT used (reserved; matrix semantics would mislead).

## `Quaternion` additions

The members below are part of the `Quaternion` contract. Items 1–4 are
established and unchanged by this revision; items 5–6 are the requirements this
revision adds.

1. `dot(other) -> float` — 4-component dot product.
2. `rotation_matrix_elements -> RotationMatrixElements` — frozen dataclass
   with fields `xx, xy, xz, yx, yy, yz, zx, zy, zz` derived from
   `to_rotation_matrix()` (single source: delegates to the existing method).
3. `rotate_position(p: Position) -> Position` — thin wrapper over the existing
   `rotate_vector`, typed for `Position` (`q * p` NOT overloaded; explicit
   method only, to avoid ambiguity with the existing quaternion `*`).
4. `__array__(dtype=None)` per the cross-cutting conventions.
5. **Degenerate-input guards** (§Degenerate (zero) magnitude). Each of
   `normalized()`, `normalize()`, `inverse`, and
   `from_axis_angle(axis, angle)` SHALL raise `ValueError` on a zero-magnitude
   operand — a zero quaternion for the first three, a zero axis for the last.
   None SHALL return a non-finite component.

   The condition is exact equality with zero, not a tolerance: a very small
   but nonzero quaternion has a well-defined direction and SHALL be accepted.

   Each of the four docstrings SHALL carry a `Raises:` section.
6. snake_case aliases for the two camelCase slips on the public surface:
   `from_numpy_quaternion` (= `fromNumpyQuaternion`) and
   `to_unit_spherical_small_circle` (= `to_unitSphericalSmallCircle`). The
   camelCase spellings remain available and are documented as deprecated.

## `SpatialPose`

**Constructors**
- `SpatialPose(position: Position, orientation: Quaternion)` (defaults:
  origin, identity)
- `from_components(x, y, z, qw, qx, qy, qz)` — quaternion order w-first,
  matching the existing `Quaternion.from_components`.
- `from_homogeneous(matrix: npt.NDArray) -> SpatialPose` — `(4,4)`; rotation
  extracted via the existing `Quaternion.from_rotation_matrix`; `ValueError`
  on shape or non-rigid bottom row.
- `from_denavit_hartenberg(a: float, alpha: float, d: float, theta: float)` —
  standard DH; the Swift precomputed-cos/sin overload collapses into this one.
- `identity()` classmethod.
- `from_dict({"position", "orientation"})` (ABC).

**Properties**
- `position: Position`, `orientation: Quaternion` (ABC names; `orientation`
  is the ABC's name for Swift's `quaternion` — ABC wins)
- passthroughs `x, y, z, qw, qx, qy, qz: float`
- `homogeneous -> npt.NDArray` `(4,4)` float64 (orientation normalized first,
  Swift parity)
- `is_unit` — delegates to `orientation`

**Operators / methods** (SE(3) semantics; `*` = "apply", the universal
robotics reading)
- `pose * pose -> SpatialPose` — composition: result rotation
  `q1 * q2`, result position `p1 + q1.rotate(p2)`.
- `pose * position -> Position` — full SE(3) application, identical to
  `transform(p)` (`q.rotate(p) + position`).
- `transform(p: Position) -> Position` — the named form of the above.
- `translated(by: Position) -> SpatialPose` — translation-only shift of the
  pose. Swift's `pose + position` / `pose - position` operators are NOT
  ported: a `+` that ignores orientation reads like "apply" and silently
  drops rotation — the explicit method removes the footgun.
- `inverse -> SpatialPose` — `q⁻¹`, `-(q⁻¹.rotate(p))`.
- `relative_pose(to: SpatialPose) -> SpatialPose` — `self.inverse * to`.
- `interpolate(to, t: float) -> SpatialPose` — position lerp + quaternion
  slerp (delegates to existing `Quaternion.slerp`); `t` unclamped, Swift
  parity pinned by test.
- `position_distance(to)`, `position_distance_squared(to)`,
  `angular_distance(to) -> float` (radians, double-cover safe: uses
  `min(θ, 2π−θ)` via `|dot|`). Scale-invariant per §Non-unit quaternion inputs.
  Raises `ValueError` if either orientation has zero norm (§Degenerate (zero)
  magnitude).
- `normalize()` / `normalized()` — normalize orientation only.
- `==` exact, `isclose(other, rtol, atol)` (double-cover aware via
  `Quaternion.isclose`), `repr`, `to_dict`/`from_dict`.

## Compliance requirements (test-checkable)

1. All three classes satisfy `isinstance` of their ABC and round-trip
   `to_dict`/`from_dict` against the matching `foundationTypes` generated
   Type's wire output. The target names are `PositionType`,
   `QuaternionType`, and `SpatialTransformType`; verification is meaningful
   only against an environment matching the current foundation pin
   ([templateConformance.md](templateConformance.md) §Environment currency).
2. Coordinate inits/accessors are mutual inverses (property-style tests over
   a grid of radii/angles, both spherical conventions, atol 1e-12).
3. `cross` follows the right-hand rule (`unit_x × unit_y == unit_z` pinned).
4. DH: pinned against at least two published DH parameter sets (e.g. a 2-link
   planar arm at known joint angles → known end-effector pose).
5. Composition algebra: `pose * pose.inverse` ≈ identity;
   `(a * b).transform(p) == a.transform(b.transform(p))` (atol 1e-9).
6. `interpolate(t=0)` == self, `(t=1)` ≈ other (double-cover tolerant);
   midpoint rotation angle is half the total angle for a pure rotation.
7. `angular_distance` between `q` and `-q` is 0.
8. `homogeneous` ∘ `from_homogeneous` round-trips (atol 1e-9), including a
   non-normalized input quaternion (normalized on export).
9. Existing `Quaternion` test suite passes with import-path and base-class
   assertion edits only — no assertion on math behavior changes.
10. `__hash__ is None` pinned for all three classes; `np.asarray(x)` returns
    the documented array for `Position` and `Quaternion`.
11. mypy strict clean.
12. **Scale invariance.** For any positive scale factor applied to either
    operand, `SpatialPose.angular_distance` and `Quaternion.angle` are
    unchanged to atol 1e-12, as is `Quaternion.axis`. Compliance 7 (`q` vs
    `-q` → 0) is unaffected.
13. **No NaN escape.** `Quaternion.normalized()`, `normalize()`, `inverse`,
    and `from_axis_angle` raise `ValueError` on a zero-magnitude operand, and
    each carries a `Raises:` docstring section. For finite non-degenerate
    input, none of the four returns a non-finite component.
14. **Deserializer errors.** For each of `Position`, `Quaternion`,
    `SpatialPose`: a non-`dict` payload raises `TypeError`; a payload missing a
    required key raises `ValueError`; a field carrying a string or a `bool`
    raises `TypeError`. The three classes raise the same type for the same
    malformed payload, and every outcome is unchanged when assertions are
    disabled. All three `from_dict` docstrings carry a `Raises:` section.
15. **Wire round-trip preserved.** `to_dict` → `from_dict` remains exact for
    all three classes: the validation required by 13–14 rejects malformed
    input without narrowing well-formed input.
