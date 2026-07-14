---
chunk: 08-spatial-pose
track: B
status: complete
depends_on: [07]
spec: ../specs/spatialMath.md §SpatialPose, §Compliance 4–8
last_updated: 2026-07-13
semver: 0.0.1
author: Nicholas Bergantz
---

# 08 — `SpatialPose`

**Deliverable:** the SE(3) pose type composing `Position` + `Quaternion`.

## Files

- Create: `src/math_tools/spatial/spatial_pose.py`
- Edit: `src/math_tools/spatial/__init__.py` (export)
- Create: `tests/spatial/test_spatial_pose.py`

## Design constraints

1. Subclass `foundation_abc.math.spatialABCs.SpatialTransformABC` — the
   ABC's rotation accessor name is `orientation` (not `quaternion`).
2. Full surface per spec §SpatialPose: constructors (`__init__(position,
   orientation)` with identity defaults, `from_components(x,y,z,qw,qx,qy,qz)`
   w-first, `from_homogeneous((4,4))` with rigid-bottom-row `ValueError`,
   `from_denavit_hartenberg(a, alpha, d, theta)`, `identity()`, `from_dict`),
   passthrough properties, `homogeneous` (orientation normalized on export),
   operators (`pose * pose` composition, `pose * position` = full SE(3)
   apply = `transform(p)`), `translated(by)`, `inverse`,
   `relative_pose(to)`, `interpolate(to, t)` (lerp + existing `slerp`,
   unclamped t), `position_distance(_squared)`, `angular_distance`
   (double-cover safe via `|dot|`), `normalize()`/`normalized()`,
   `==`/`isclose`/`repr`/`to_dict`, `__hash__ = None`.
3. Composition recipe (pin exact form):
   `(a * b).position == a.position + a.orientation.rotate_position(b.position)`,
   `(a * b).orientation == a.orientation * b.orientation`.
4. DH reference: `SWIFT_MATH/Spatial/Constructors/SpatialPose+DenavitHartenberg.swift`
   (standard DH matrix; the precomputed-cos/sin overload collapses into the
   one Python signature).

## TDD steps

1. Failing tests: spec compliance 4 (two published DH sets — use a 2-link
   planar arm: `a1=a2=1, alpha=d=0`, θ=(90°, 0°) → end effector (0, 2, 0)
   via chained poses, plus one non-planar set with alpha≠0 computed by hand
   in the test comment), 5 (composition algebra), 6 (interpolate endpoints +
   half-angle midpoint), 7 (`angular_distance(q, -q) == 0`), 8 (homogeneous
   round-trip incl. non-normalized input).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Spec compliance items 4–8 each have named tests and pass
- [x] Round-trip with `foundationTypes` `SpatialTransformType` wire dicts
- [x] `pose * position` equals `transform(position)` exactly
- [x] `make uv-fullCheck` passes

## Out of scope

Waveform containers; velocity/twist (se(3)) math; ROS/URDF interop.

## Resolution notes

- `SpatialPose` composes a copied `Position` (mutable, so copied on
  construction to prevent aliasing) and an aliased `Quaternion` (immutable,
  safe to alias) per the ABC's `position`/`orientation` accessor names.
- `*` is deliberately the only operator ported from Swift's pose algebra:
  `pose * pose` composes, `pose * position` applies the full transform
  (identical to `transform()`). Swift's `pose ± position` were intentionally
  not ported (silent rotation-dropping footgun); `translated()` is the named
  replacement.
- Composition recipe pinned exactly per the spec:
  `(a * b).position == a.position + a.orientation.rotate_position(b.position)`,
  `(a * b).orientation == a.orientation * b.orientation`.
- `homogeneous` always normalizes the orientation on export (Swift parity),
  even when the stored orientation isn't currently unit; verified live with
  a non-normalized `Quaternion.from_components(2,0,0,0)` round-tripping
  through `from_homogeneous` to a unit orientation.
- `angular_distance` uses `|dot|` for double-cover safety; verified live
  that `angular_distance(pose_with_q, pose_with_-q)` is ~0 (float noise,
  not exactly 0, consistent with floating-point rotation composition).
- DH: verified the two-link planar arm (`a1=a2=1, alpha=d=0`,
  `theta=(90°, 0°)`) chains to end-effector `(0, 2, 0)` within float
  tolerance; `to_dict`/`from_dict` round-trip verified against
  `foundationTypes.mathTypes.MathTypes.SpatialTransformType`.
- One lint fix during review: `from_homogeneous`'s `ValueError` message
  exceeded the 100-char line limit; wrapped across two string literals with
  no change in message content.
- No spec changes were needed — the implementation matches
  `spatialMath.md` §SpatialPose as written.
- Note: this chunk's implementation/tests were originally drafted in an
  earlier session pass that was interrupted before the gate was run to
  green; this pass fixed the one outstanding lint error, independently
  re-verified every acceptance criterion against the running code, and
  confirmed no other chunk's files were touched.
