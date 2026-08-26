---
chunk: 52-subpackage-public-surface
track: F
status: complete
depends_on: []
spec: ../specs/mathToolsArchitecture.md:114-116
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 52 — Empty subpackage `__init__.py` for `spherical` and `math_plot_helpers`

## Origin

Post-audit findings A-1 (class **a**) and A-2 (class **c**). Confirmed:
`src/math_tools/spherical/__init__.py` and
`src/math_plot_helpers/__init__.py` are both **0 bytes**.

mathToolsArchitecture.md:114-116 requires each package and subpackage
`__init__.py` to re-export its public API with `__all__`. 7 public functions in
`spherical/` (`constructors.py:14`, `spherical_generators.py:62,159`,
`spherical_transforms.py:33,77,105,131`) and 4 in `plot_unit_spherical.py`
(`:28,252,488,702`) are unexported.

This cascades into A-2: the same spec line forbids deep module paths
("consumers import from the subpackage … never deep module paths"), yet
`README.md:48,61-62` and `examples/sphericalPlotting/*.py` all use deep paths —
because there is no subpackage-level path to import.

No chunk ever owned this. Chunk 01 explicitly out-of-scoped `__init__.py`
curation (`01:73-75`); chunk 43 touched only the root. Both packages are
**pre-existing legacy, not scope violations** — verified via
`git log --diff-filter=A`, and `mathToolsArchitecture.md:94` names `spherical/`
in the module map as "behavior unchanged".

## Files

- Edit: `src/math_tools/spherical/__init__.py`
- Edit: `src/math_plot_helpers/__init__.py`
- Edit: `README.md`
- Edit: `examples/sphericalPlotting/plotArcs.py`
- Edit: `examples/sphericalPlotting/plotQuatUnitCircles.py`
- Create: `tests/spherical/__init__.py`, `tests/spherical/test_public_surface.py`

## Design constraints

1. Re-exports only, with an explicit `__all__`. No logic in either
   `__init__.py` — follow the pattern chunk 43 established at
   `src/math_tools/__init__.py`.
2. `math_plot_helpers/__init__.py` may import matplotlib transitively; that is
   allowed for this package and only this package. Re-run
   `tests/test_package_layering.py` to confirm the one-way rule still holds —
   `math_tools` must not gain a matplotlib path.
3. Update README and both example scripts to import from the subpackage, not
   deep module paths, so documented usage matches the spec's own rule.
4. Do **not** add these names to the root `math_tools.__all__` — chunk 43 pinned
   that list to the umbrella spec's 19 names, and widening it requires a spec
   bump that is not in scope here.

## TDD steps

1. Write a failing test pinning each subpackage's `__all__` and asserting every
   name imports from the subpackage level (mirroring
   `tests/test_public_surface.py`'s identity-check shape).
2. Wire the re-exports.
3. Update README and the two example scripts; run both scripts to confirm they
   still execute (they are outside the gate — see chunk 57).
4. `make uv-fullCheck` green, including the layering test.

## Acceptance criteria

- [x] Both `__init__.py` files export their public API via `__all__`
- [x] All 11 public functions importable from the subpackage level
- [x] README and both examples use subpackage imports
- [x] Both example scripts execute without error
- [x] `tests/test_package_layering.py` still passes
- [x] `make uv-fullCheck` passes

## Out of scope

Behavioral tests for `spherical/` and `math_plot_helpers/` (finding A-7, 11
untested public functions) — recorded; see chunk 57's "Recorded — no action" section. This
chunk pins the surface only.

## Resolution notes

- `src/math_tools/spherical/__init__.py` re-exports 7 functions:
  `arc_from_two_points` (constructors.py), `generate_spherical_arc_points`,
  `generate_spherical_small_circle_points` (spherical_generators.py),
  `cartesian_to_spherical`, `compute_spherical_arc_endpoint`,
  `plate_carree_transform`, `spherical_to_cartesian`
  (spherical_transforms.py).
- `src/math_plot_helpers/__init__.py` re-exports the 4 plotting entry points:
  `plot_unit_spherical_advanced`, `plot_unit_spherical_polar`,
  `plot_unit_spherical_3d`, `plot_unit_spherical_multiplot`. The `demo()`
  function in `plot_unit_spherical.py` is a `__main__`-only demo, not public
  API, and was intentionally left unexported.
- TDD was verified literally: the new test file was run against the
  (temporarily re-emptied) `__init__.py` files first to confirm 13 failures,
  then the implementation was restored and the test suite re-run green
  before proceeding.
- `tests/spherical/test_public_surface.py` pins **both** subpackages'
  `__all__` in one file (mirroring the two test files named in the chunk's
  "Files" list — no `tests/math_plot_helpers/` directory was created, since
  none was listed and none of this chunk's other files needed it).
- The module-level angle constants in `plot_unit_spherical.py` (`deg45`,
  `deg90`, `deg180`, `deg22_5`) are not part of the "4 public functions"
  the origin section confirmed, so they were deliberately left off
  `math_plot_helpers.__all__`; `examples/sphericalPlotting/plotArcs.py`
  still imports them via the deep module path (unavoidable — they are not
  curated public surface).
- **Adjacent issue found, not fixed (per stay-in-scope):** README.md's
  "Quaternions" Quick Start section and
  `examples/sphericalPlotting/plotQuatUnitCircles.py` both import
  `Quaternion` via the deep path `math_tools.spatial.quaternion` even
  though `math_tools.spatial` already re-exports `Quaternion` in its
  `__init__.py` (from chunk 06/07). This is the same deep-path anti-pattern
  the umbrella spec forbids, but it belongs to the `spatial` subpackage,
  not this chunk's scope (`spherical`/`math_plot_helpers`, per Origin
  A-1/A-2). Recording here for a future chunk / chunk 57's docs sweep to
  pick up.
- Both example scripts were executed with `MPLBACKEND=Agg` and completed
  without error (only the expected "FigureCanvasAgg is non-interactive"
  `plt.show()` warning).
