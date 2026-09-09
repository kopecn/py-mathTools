---
version: 1.0
type: specification
name: sphericalGeometry
purpose: Behavioral contract for math_tools.spherical — arc/small-circle construction, generation, and coordinate transforms on the unit sphere
spec: SphericalGeometry
scope: project
status: draft
applies_to: src/math_tools/spherical/, tests/spherical/
last_updated: 2026-08-26
semver: 0.1.1
author: Nicholas Bergantz
---

# Spherical Geometry

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md), which owns layering, dependency policy, error semantics, and the shared API idioms this spec inherits. Reproduced defect evidence and implementation material are held in [the 2026-08-26 findings](../findings/2026-08-26-spherical-spatial-packaging.md).

## Role

`math_tools.spherical` is the Tier-3 implementation of the unit-sphere primitives whose Tier-1 carriers are `foundationTypes.mathTypes.MathTypes.UnitSphericalArcType` / `UnitSphericalSmallCircleType` and whose Tier-2 contracts are `foundation_abc.math.sphericalABCs.UnitSphericalArcABC` / `UnitSphericalSmallCircleABC`. It owns no storage type: every public entry point takes or returns an ABC-typed arc/circle, a scalar coordinate pair, or a numpy array of them.

## Coordinate convention

ISO physics convention. The `spherical_generators` module docstring is the canonical statement; other modules reference it rather than restating it.

- **θ (polar)** — colatitude from `+z`, range `[0, π]`. `0` = north pole, `π/2` = equator, `π` = south pole.
- **φ (azimuth)** — angle in the xy-plane from `+x`, counterclockwise viewed from `+z`.
- `x = sin θ cos φ`, `y = sin θ sin φ`, `z = cos θ`.

Azimuth output ranges differ by function and are part of each function's contract: `compute_spherical_arc_endpoint` returns `[0, 2π)`; `cartesian_to_spherical`, `generate_spherical_arc_points`, and `generate_spherical_small_circle_points` return `arctan2` range `(-π, π]`. Consumers comparing azimuths across these functions SHALL compare modulo `2π` (§Compliance 0).

## The `orient` convention

`orient` SHALL be an initial great-circle bearing measured from local north, positive toward local east (the direction of increasing azimuth):

- `orient = 0` → travel toward the north pole (decreasing θ).
- `orient = +π/2` → travel due east (increasing φ).
- `orient = ±π` → travel toward the south pole (increasing θ).

With `p̂` the outward radial at the start point, `ê = ẑ × p̂ / ‖ẑ × p̂‖` (local east) and `n̂ = p̂ × ê` (local north), the initial tangent direction SHALL be

```
d̂ = cos(orient) · n̂ + sin(orient) · ê
```

This convention governs every function in this subpackage, and public docstrings state it at the call site (§Compliance 10).

It diverges in sign from the wording of the inherited Tier-2 `UnitSphericalArcABC.orient` docstring. Tier-2 states no formula, so no implemented upstream contract is contradicted; reconciling the wording is owned by py-foundationTools.

## Degeneracy handling

Bearing is undefined at a pole. Every function resolving a bearing SHALL treat the start point as degenerate under one shared predicate:

```
POLE_EPS = 1e-10
degenerate  ⇔  abs(sin(polar)) < POLE_EPS
```

- Every bearing-resolving code path SHALL classify a point as degenerate under exactly this predicate, at exactly this threshold. `spherical_generators` and `spherical_transforms` SHALL agree on the classification of every input: no point is degenerate to one and non-degenerate to the other.
- At a degenerate start point the azimuth reference SHALL be the fixed `x̂`/`ŷ` basis, yielding `azimuth_end == orient` at both poles. This is definitional, not approximate.
- `generate_spherical_small_circle_points` resolves no bearing: a small circle is rotationally symmetric about its center, so its output does not depend on a choice of in-plane reference direction. It is not governed by `POLE_EPS`, and §Compliance 7 holds for every center position.

### Accuracy bands near the pole

Agreement between `generate_spherical_arc_points` and `compute_spherical_arc_endpoint` is bounded by the start point's proximity to a pole. The following bounds are normative:

| Start point | Guaranteed chordal agreement |
| --- | --- |
| `abs(sin(polar_start)) ≥ 1e-6` | `< 1e-9` |
| `POLE_EPS ≤ abs(sin(polar_start)) < 1e-6` | `< 1e-6` |
| `abs(sin(polar_start)) < POLE_EPS` | exact (shared pole convention) |

## Public surface

Seven functions, re-exported from `math_tools/spherical/__init__.py` with `__all__` per the umbrella's Public surface rule.

### `spherical_transforms`

- `plate_carree_transform(azimuth, polar) -> (x, y)` — `x = azimuth`, `y = π/2 − polar`. Accepts float or ndarray via `FloatOrNDArray`.
- `spherical_to_cartesian(azimuth, polar) -> (x, y, z)` — unit-sphere point per §Coordinate convention.
- `cartesian_to_spherical(point) -> (azimuth, polar)` — normalizes `point`, then `azimuth = arctan2(y, x)`, `polar = arccos(clip(z, −1, 1))`.
- `compute_spherical_arc_endpoint(arc) -> (azimuth_end, polar_end)` — the reference implementation of the arc contract (§Cross-function consistency). Spherical law of cosines for `polar_end`; `arctan2` for `Δazimuth`; degenerate start → `azimuth_end = orient`; degenerate end → `azimuth_end = arc.azimuth`; result in `[0, 2π)`.

### `spherical_generators`

- `generate_spherical_small_circle_points(circle, num_points=120) -> (azimuths, polars)` — `num_points` samples over `t ∈ [−π, π]`, each at exactly `circle.radius_angle` from the center.
- `generate_spherical_arc_points(arc, num_points=120) -> (azimuths, polars)` — `num_points` samples over `t ∈ [0, arc.arc_length]`, inclusive at both ends, along the great circle leaving `(arc.azimuth, arc.polar)` on bearing `arc.orient` per §The `orient` convention. Negative `arc_length` traverses the opposite bearing.

### `constructors`

- `arc_from_two_points(azimuth1, polar1, azimuth2, polar2, isPositive=True) -> UnitSphericalArcABC` — an arc rooted at point 1 whose bearing and length carry it to point 2:

  ```
  arc_length = arccos(clip(cos θ₁ cos θ₂ + sin θ₁ sin θ₂ cos Δφ, −1, 1))
  orient     = atan2( sin Δφ · sin θ₂ ,
                      sin θ₁ · cos θ₂ − cos θ₁ · sin θ₂ · cos Δφ )
  ```

  Both expressions are part of the contract, including the order of terms in the `orient` denominator.

  `isPositive=False` negates `arc_length` and leaves `orient` unchanged, producing the reverse traversal from point 1. That arc does not reach point 2, and its docstring SHALL say so.

## Cross-function consistency

`compute_spherical_arc_endpoint` is the single source of truth for where an arc ends. The other two arc functions are defined by agreement with it:

1. **Generator ≡ endpoint.** `generate_spherical_arc_points(arc, n)`'s final sample SHALL equal `compute_spherical_arc_endpoint(arc)`, compared per §Compliance 0 and bounded by §Accuracy bands near the pole.
2. **Constructor round-trip.** `compute_spherical_arc_endpoint(arc_from_two_points(φ₁, θ₁, φ₂, θ₂))` SHALL equal `(φ₂ mod 2π, θ₂)` on the same terms.

A change that breaks either invariant is a regression regardless of how the individual formula reads.

## Error semantics

Inherited from [mathToolsArchitecture.md](mathToolsArchitecture.md) §Error semantics. This subpackage raises no domain errors: inputs are floats or ABC-typed carriers, every `arccos` argument is clipped to `[−1, 1]`, and every normalization divisor is guarded by §Degeneracy handling. No `MathToolsError` subtype applies.

## Compliance requirements

Stable observable outcomes of a conforming implementation.

0. **Comparison metric.** Agreement between two `(azimuth, polar)` results is measured as chordal error, with the azimuth difference taken modulo `2π` as `abs(((a − b + π) % (2π)) − π)` and weighted by `sin(polar)`. Every tolerance below is expressed in this metric.
1. **Constructor round-trip.** For any `(φ₁, θ₁, φ₂, θ₂)` with `abs(sin θ) ≥ 1e-6`, `compute_spherical_arc_endpoint(arc_from_two_points(φ₁, θ₁, φ₂, θ₂))` recovers `(φ₂, θ₂)` to `< 1e-9`.
2. **Generator ≡ endpoint.** `generate_spherical_arc_points`' final sample matches `compute_spherical_arc_endpoint` for the same arc, within the bounds of §Accuracy bands near the pole, for `arc_length ∈ [−π, π]`.
3. **North-tangent orientation.** For an equatorial start, `orient = 0`, and `0 < L ≤ π/2`, `polar(s) = π/2 − s` for `s ∈ [0, L]`.
4. **Pole agreement.** For start `polar ∈ {0, π}`, the generator's final sample matches `compute_spherical_arc_endpoint` exactly, and `azimuth_end ≡ orient (mod 2π)`, for both positive and negative `orient`.
5. **Uniform degeneracy predicate.** For any point, `spherical_generators` and `spherical_transforms` return the same degeneracy classification, and that classification is the §Degeneracy handling predicate at its stated threshold. No bearing-resolving path applies a different threshold.
6. **Midpoint agreement.** The generator's sample at parameter `L/2` matches `compute_spherical_arc_endpoint` of the same arc with `arc_length = L/2`, to `< 1e-9`.
7. **Small-circle radius.** Every sample of `generate_spherical_small_circle_points` sits at `radius_angle` from the center to atol `1e-12`, for centers anywhere on the sphere including at a pole.
8. **Transform inverses.** `cartesian_to_spherical ∘ spherical_to_cartesian` is the identity away from the poles to atol `1e-12`. `plate_carree_transform` maps `polar = 0 → y = π/2` and `polar = π → y = −π/2`.
9. **Public surface.** `math_tools.spherical.__all__` pins exactly the seven names, each resolving by identity to its defining module.
10. **Docstrings carry the convention.** The `spherical_generators` module docstring defines `orient` per §The `orient` convention. Each arc function's docstring states that convention and notes its divergence from the inherited `UnitSphericalArcABC.orient` wording. No docstring or comment in the subpackage describes `orient` as a rotation about the radial vector.
11. mypy strict clean.

## Non-goals

1. **No new spherical types.** Tier-1 carriers stay upstream; this subpackage defines no arc/circle class.
2. **No azimuth-range harmonization.** The per-function ranges in §Coordinate convention are contract, not drift.
2. **No upstream ABC docstring change.** Owned by py-foundationTools.
3. **No small-circle degeneracy rework.** See §Degeneracy handling.
4. **No reformulation of `compute_spherical_arc_endpoint`.** The bands in §Accuracy bands near the pole are the contract; tightening them is a separate governed change.
5. **No `isPositive` redesign.** Reverse-traversal semantics are contract.
