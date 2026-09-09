---
version: 1.0
type: findings
name: spherical-spatial-packaging-defects
purpose: Reproduced defect evidence, measurements, and implementation material displaced from the specs during the 2026-08-26 normalization
scope: project
status: open
applies_to: src/math_tools/spherical/, src/math_tools/spatial/, src/math_tools/waveforms/, requirements.txt, Makefile, README.md
last_updated: 2026-08-26
semver: 0.1.1
author: Nicholas Bergantz
---

# Findings — spherical geometry, spatial math, packaging

Companion to [sphericalGeometry.md](../specs/sphericalGeometry.md),
[spatialMath.md](../specs/spatialMath.md),
[waveformCore.md](../specs/waveformCore.md), and
[templateConformance.md](../specs/templateConformance.md).

This artifact holds what those specs must not: current-defect evidence,
reproductions, measured values, source locations, and implementation material.
The specs state the durable expected outcomes; this states what was observed on
2026-08-26 and what an implementer needs in hand.

Nothing here is normative. Recording an observation does not authorize a
requirement.

## Source

Eight findings produced by an audit pass on 2026-08-26 and then presented to
the human for decisions. All eight were independently reproduced before any
spec was drafted. Two additional defects were found during that reproduction
and are marked as such. None of these findings is human-authorized; they are
observations, and the decisions taken on them are recorded separately.

## F1 — `arc_from_two_points` bearing uses transposed colatitude terms

**Location:** `src/math_tools/spherical/constructors.py:84`

**Observed:** the `x` component is written
`cos θ₁ · sin θ₂ − sin θ₁ · cos θ₂ · cos Δφ`; substituting `lat = π/2 − θ` into
the standard initial-bearing formula gives `sin θ₁ · cos θ₂ − cos θ₁ · sin θ₂ · cos Δφ`.
The two terms are transposed.

| input `(φ₁,θ₁) → (φ₂,θ₂)` | requested endpoint | actual endpoint |
| --- | --- | --- |
| `(0.5, 0.8) → (1.2, 1.0)` | `(1.2000, 1.0000)` | `(1.3506, 0.6944)` |
| `(0.0, 0.01) → (π/2, 1.0)` | `(1.5708, 1.0000)` | `(2.3516, 0.9930)` |

**Why it survived review:** the transposed form is not wrong everywhere.
Measured over 200 random pairs per family, correct and transposed agree
*exactly* on the equator, on any `θ₁ = θ₂` pair, and on the `Δφ = π`
antimeridian pair. They disagree on all 200 of `Δφ = π/2`, and differ by
exactly `π` (opposite bearings) at `Δφ = 0`. Equal-colatitude pairs are the
easiest examples to write by hand, which is why hand-checked spot tests pass.

**Corrected form validated:** round-trip through
`compute_spherical_arc_endpoint` over 4,000 seeded random cases, worst chordal
error **4.1e-13**.

## F1a — near-pole bearing regression vector (compliance item withdrawn)

A "pole-start bearing" compliance item was drafted requiring the constructed
arc to reach the requested target azimuth for start points down to
`abs(sin θ₁) ≥ 1e-6`. It was withdrawn from the spec: it restated the
constructor round-trip item without adding an observable, its "at any distance
from a pole" wording contradicted its own lower bound, and target azimuth is
undefined when the *target* is at a pole — an endpoint the item left unbounded.

The vector it was built from is still worth exercising, with both endpoints
held away from the poles. The near-pole start row of the F1 table above is that
vector: `(0.0, 0.01) → (π/2, 1.0)`, requested `(1.5708, 1.0000)`, actual on the
defective code `(2.3516, 0.9930)`. The round-trip item covers it, since
`abs(sin 0.01) = 0.0099 ≥ 1e-6`.

## F2 — arc generator builds a reversed local-north tangent

**Location:** `src/math_tools/spherical/spherical_generators.py:217`

**Observed:** `north_tangent = cross(east, start_point)`, which equals `−n̂`.
The initial direction is therefore `−cos(orient)·n̂ + sin(orient)·ê`.

From the equator with `orient = 0` and `arc_length = π/4`, generated points
travel **south** to polar `2.3562` (`3π/4`), while
`compute_spherical_arc_endpoint` correctly predicts `0.7854` (`π/4`).

`generate_spherical_small_circle_points:112` already uses the correct
`cross(center, east)` form — the two functions in the same module disagree.

**Corrected form validated:** `cross(start_point, east)`, with the pole
threshold shared with `compute_spherical_arc_endpoint`, agrees with the
endpoint function to worst chordal **2.1e-14** over 4,000 seeded arcs at
`num_points=33`.

**Why it survived review:** `tests/spherical/` contains only
`test_public_surface.py`, which pins exports and identity. No geometry test
exists for the subpackage.

## F2a — pole-threshold mismatch (found during reproduction, not reported)

`compute_spherical_arc_endpoint:189` tests `abs(sin(theta_start)) < 1e-10`.
The generator's branch tests `abs(z_start) < 0.999`, i.e. colatitude within
~2.56° of a pole — a band roughly 8 orders of magnitude wider.

Measured consequence of leaving them mismatched: raising only the generator's
threshold to `1e-6` while the endpoint function stays at `1e-10` produces a
chordal error of **1.075 radians** across the whole intervening band. A
proposal to widen one side as a fix was evaluated and rejected on this
measurement.

## F2b — near-pole conditioning limit (found during reproduction)

After both fixes, agreement is not machine-precision arbitrarily close to a
pole. `compute_spherical_arc_endpoint` recovers `Δazimuth` through a quotient
whose denominator is `sin(θ_start)·sin(θ_end)`; that division loses
significance as `sin(θ_start) → 0`. The generator rotates a Cartesian vector
and does not. The residual is the endpoint function's conditioning.

Measured worst-case chordal disagreement, shared threshold at `1e-10`:

| `abs(sin(polar_start))` | worst chordal error |
| --- | --- |
| `1e-4` | 1.4e-13 |
| `1e-5` | 5.8e-12 |
| `1e-6` | 1.3e-10 |
| `1e-7` | 7.0e-10 |
| `1e-8` | 9.9e-09 |
| `1e-9` | 3.4e-08 |
| `1.1e-10` | 4.2e-07 |
| below threshold | exact (shared pole convention) |

The spec states the resulting bands as normative outcomes. Narrowing the
sliver would require reformulating the endpoint function's `Δazimuth`
computation — not requested, not authorized.

## F2c — azimuth range split defeats naive comparison

`compute_spherical_arc_endpoint` normalizes to `[0, 2π)`; the generators
return raw `arctan2` output in `(-π, π]`. For `orient = -2.0` a correct
implementation yields `4.283185…` and `-2.0` — exactly `2π` apart. Any
equality or `assertAlmostEqual` comparison fails on correct code. Verified
live.

## F2d — a monotonicity test has no power against F2

A monotone-traversal check was drafted as a compliance item on the reasoning
that a tangent sign error produces fold-back at the midpoint. Measured against
the live F2 defect: **0 of 200** random arcs produced any fold-back. A sign
flip reverses direction without folding the path. The item was replaced with a
midpoint-agreement check, which does discriminate.

## F3 — `angular_distance` saturates for non-unit quaternions

**Location:** `src/math_tools/spatial/spatial_pose.py:242`

Clips an unnormalized dot product. Two quaternions separated by 60° and scaled
by 3 report **0.0** rather than `1.047198`. Clipping does not sanitize an
unnormalized dot — it saturates it.

## F3a — `Quaternion.angle` has the same defect (found during review)

**Location:** `src/math_tools/spatial/quaternion.py:317`

`2.0 * arccos(clip(self.w, -1.0, 1.0))` reads a raw `w` with no norm division.
A 60° rotation scaled by 5 reports **0.0°**.

`Quaternion.axis` was checked and is already scale-invariant.

Authorized by the human on 2026-08-26 to become normative for `angle` only;
`axis` and `interpolate` explicitly left unchanged.

## F4 — zero-magnitude normalization yields NaN

| Location | Observed |
| --- | --- |
| `quaternion.py:684` (`from_axis_angle`) | `quaternion(0.8775825618903728, nan, nan, nan)` — finite `w`, three NaN |
| `quaternion.py:293` (`normalized`) | `quaternion(nan, nan, nan, nan)` |
| `quaternion.py` (`inverse`) | `1.0 / q` on the zero quaternion is NaN |

The `from_axis_angle` case is the worse of the two: a plausible-looking finite
`w` makes the result read as valid at a glance.

`Position.normalize()` already raises `ValueError` on the zero vector, so the
sibling contract exists and `Quaternion` diverges from it.

## F5 — the foundation dependency pin is dead

`requirements.txt:22` pins
`pyFoundationTools @ git+https://github.com/kopecn/py-foundationTools.git@feat/switch-to-new-template`.

That branch **does not exist on the remote**. Verified:

```
$ git ls-remote --heads https://github.com/kopecn/py-foundationTools.git
ada8247… refs/heads/dev
1082ccb… refs/heads/feat/new-features
1216008… refs/heads/main
fc22d72… refs/heads/prod

$ git ls-remote --tags …
b476033… refs/tags/v0.0.2
efb630e… refs/tags/v0.0.3
fc22d72… refs/tags/v0.0.4
```

A clean `uv pip install -r requirements.txt` therefore **fails outright
today**. The repo builds only because the existing `.venv` holds an install of
commit `323e4b09` (per its `direct_url.json`), reachable from a local clone but
from nothing on the remote. The reported green gate — 1,550 tests passing — is
evidence about a stale environment, not about a fresh checkout.

**Selected pin: `v0.0.4`.** It resolves to `fc22d72`, is tag-reachable, is
identical to `refs/heads/prod`, and carries the post-template
`foundation_abc/math/` layout including `sphericalABCs.py` and
`waveformABCs.py`. `git diff 323e4b09 v0.0.4` restricted to
`src/foundation_abc/` and `src/foundationTypes/mathTypes/` is **empty** —
adopting it is behaviour-preserving, not an upgrade.

A commit-SHA fallback is unavailable: the only SHA that would serve
(`323e4b09`) is the unreachable object that caused the problem.

## F6 — the two CI jobs install from different sources

`Makefile:306` (`uv-test-all`) runs `uv pip install -q -e ".[dev]"`, bypassing
`requirements.txt`. It is the only install path in the Makefile that does so;
`uv-bootstrap`, `uv-sync`, `uv-sync-headless`, `uv-sync-dev`, `uv-refresh`, and
the pip fallback all install `-r requirements.txt` first.

Consequence: the `compatibility` job resolves `pyFoundationTools` from the
configured index (where it is not published) while `quality` resolves it from
the git pointer. The two jobs can test different code, and post-F5 the
compatibility job cannot resolve the dependency at all.

## F7 — waveform insertion rejects indices `list.insert` clamps

**Locations:** `waveform1d.py:812`, `waveform_position.py:324`,
`waveform_quaternion.py:352`, `waveform_spatial_pose.py:620` — all bare
`np.insert`.

`np.insert` raises `IndexError` outside `[-n, n]`; `list.insert` clamps.
Measured on a 3-sample waveform, `insert(99, x)` raises on all four classes,
where `[0,1,2].insert(99, 9)` appends.

None of the four `insert` methods carries a docstring, unlike `pop()` beside
each, which documents its `IndexError`.

## F8 — spatial deserializers rely on assertions

| Location | `from_dict(<non-dict>)` raises |
| --- | --- |
| `position.py:149` | `AssertionError` |
| `spatial_pose.py:118` | `AssertionError` |
| `quaternion.py:829` | `AttributeError` (no `isinstance` check at all) |

Under `python -O` the asserts are stripped and `Position.from_dict` degrades to
`AttributeError` — verified live. Two duplicate assert-based numeric coercers
exist: `Position._from_float` (`position.py:53`) and `Quaternion.from_float`
(`quaternion.py:47`).

---

# Material for the implementation plan

Displaced from the specs during normalization. This is plan input, not
contract.

## Index-clamping recipe (F7)

Clamp before delegating to the array helper, in each of the four `insert`
methods:

```python
n = len(self._values)
if index < 0:
    index = max(0, n + index)
else:
    index = min(index, n)
```

`WaveformSpatialPose.insert` clamps **once** and applies the same index to
both parallel arrays, so `len(positions) == len(quaternions)` is preserved. A
per-array clamp would desynchronize them.

## Shared deserializer helper (F8)

New private module `src/math_tools/spatial/_serde.py`, replacing
`Position._from_float` and `Quaternion.from_float`. Private: leading
underscore, no `__all__` entry, no public-surface change.

While editing the three `from_dict` methods, unify their signatures:
`Position` and `SpatialPose` use `from_dict(cls: type[T], obj: Any) -> T`;
`Quaternion.from_dict(cls, obj: Any) -> Quaternion` hardcodes the return type
and breaks subclass covariance. `Quaternion` adopts the `TypeVar` form.

## Docstring edit targets (spherical)

`spherical_generators.py` describes `orient` as a right-hand-rule rotation
about the radial vector at lines 169–171, 181–182, 202, 209, and 226 — replace,
do not append. Line 227 already reads "orient=0 points north, positive orient
rotates towards east", so the file contradicts itself; the compass wording is
the one that stays. The module docstring (lines 7–36) documents θ and φ but
never defines `orient` at all.

`arc_from_two_points`' docstring claims the `isPositive=False` arc "reaches
toward (azimuth2, polar2)". It does not.

Suggested check after the edit:
`grep -niE "right.hand|thumb|fingers curl" src/math_tools/spherical/` returns
nothing.

## Shared-constant check (spherical)

`spherical_generators.py:132` carries an unrelated, legitimate
`axis_norm > 1e-10` (a Rodrigues axis-degeneracy guard in the small-circle
loop). A bare `grep 1e-10` cannot distinguish it from a pole literal, so the
conformance check must be line-scoped to lines involving `sin(`.

## Test material

- Regression case for F1: `(0.5, 0.8) → (1.2, 1.0)`.
- Non-discriminating control worth asserting as such: a `θ₁ = θ₂` pair, which
  both the correct and transposed formulas pass.
- Mandatory case for F2c: `orient = -2.0`, which exposes a naive `==`.
- Literal scale cases: 60°/scale-3 for `angular_distance`, 60°/scale-5 for
  `Quaternion.angle`.
- `tests/spherical/` currently holds only `test_public_surface.py`; geometry
  test files do not yet exist.
- Gate: `make uv-fullCheck`.

## Downstream consumers to re-check after the spherical fixes

`examples/sphericalPlotting/plotArcs.py` chains
`compute_spherical_arc_endpoint` into `arc_from_two_points`. Note it is **not**
a discriminating check: its inputs land on `Δφ = -π/2` with `θ₂ = 0`, where
both bearing formulas return 0.

`src/math_plot_helpers/plot_unit_spherical.py:878-892` holds demo arcs whose
expected directions are only consistent with the compass reading of `orient`.

## Recorded, not actioned

- `Makefile` `uv-sync-release` installs `requirements-release.txt`, which does
  not exist; the target fails if run. Human decision 2026-08-26: leave it,
  report only.
- `Quaternion` keeps `fromNumpyQuaternion` / `to_unitSphericalSmallCircle` as
  permanent aliases with no `DeprecationWarning` and no sunset path.
- The Tier-2 ABC docstring `UnitSphericalArcABC.orient` ("Rotated orientation
  about the origin->start vector") carries the right-hand-rule wording that
  conflicts with the compass convention. Fixing it is a py-foundationTools
  change; worth filing upstream.

## Test vectors and verification procedure

Displaced from spec compliance sections, which state outcomes rather than the
inputs that demonstrate them.

### Waveform insertion (F7)

Differential vector against stdlib. On a 3-sample waveform, for
`i ∈ {-99, -4, -3, -1, 0, 1, 2, 3, 4, 99}`, the resulting order matches the
identical `list.insert` call on `[0, 1, 2]` and nothing raises. Boundary
illustrations:

```
[1, 2, 3].insert(99, 9)   → [1, 2, 3, 9]
[1, 2, 3].insert(-99, 0)  → [0, 1, 2, 3]
```

`WaveformSpatialPose` is additionally checked for equal parallel-array lengths
after a clamped insertion.

### Spherical geometry

- Randomized items use an explicitly seeded generator (`np.random.default_rng`
  with a literal seed) so failures reproduce.
- Constructor round-trip coverage must include a pair with `Δφ ∉ {0, π}` and
  `θ₁ ≠ θ₂`. Coincident-value families do not discriminate the contracted
  formula from the transposed one (F1), so a suite built only from
  equal-colatitude or antimeridian pairs passes against the defect.
- Generator/endpoint agreement is exercised in both accuracy bands: the
  guaranteed band and the near-pole sliver.
- Pole agreement is exercised with at least one negative `orient`, which is
  where the azimuth-range split (F2c) makes a naive equality comparison fail
  on correct code.
- `POLE_EPS` conformance is checked line-scoped to bearing-resolving code, not
  by a bare literal grep — see the `spherical_generators.py:132` caveat above.

### Spatial math

- Scale invariance: literal cases 60°/scale-3 for `angular_distance` and
  60°/scale-5 for `Quaternion.angle`, plus scale factors below 1.
- Deserializer suite runs twice, once under `python -O`.

### Packaging

Pin and install-path conformance is verified against a **fresh** environment.
An existing working environment is not evidence: it can hold an install of a
ref that is no longer remotely reachable, which is precisely what masked F5.

## Implementation notes displaced from spec prose

- **Scale invariance (F3, F3a):** divide by the operand norms, or normalize,
  *before* the range-limiting step. Clipping an unnormalized dot product or a
  raw `w` component to `[-1, 1]` saturates rather than sanitizes.
- **Near-pole bands (F2b):** the bound originates in
  `compute_spherical_arc_endpoint`'s `Δazimuth` recovery, whose denominator
  carries a factor of `sin(θ_start)`. The generator rotates a Cartesian vector
  and does not share the conditioning.
- **`assert` on deserializer paths (F8):** prohibited, because assertions are
  stripped under `python -O`, turning a rejected payload into a silently
  constructed object. The spec states the equivalent outcome (behaviour
  identical with assertions disabled) rather than the mechanism ban.
