---
chunk: 08-spatial-pose
track: B
status: pending
depends_on: [07]
spec: ../specs/spatialMath.md §SpatialPose, §Compliance 4–8
last_updated: 2026-07-11
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

- [ ] Spec compliance items 4–8 each have named tests and pass
- [ ] Round-trip with `foundationTypes` `SpatialTransformType` wire dicts
- [ ] `pose * position` equals `transform(position)` exactly
- [ ] `make uv-fullCheck` passes

## Out of scope

Waveform containers; velocity/twist (se(3)) math; ROS/URDF interop.
