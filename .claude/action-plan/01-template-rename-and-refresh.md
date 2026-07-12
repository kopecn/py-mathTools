---
chunk: 01-template-rename-and-refresh
track: A
status: pending
depends_on: []
spec: ../specs/templateConformance.md §Gap 1, §Gap 2.4; ../specs/spatialMath.md §Modules (ABC re-parent)
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 01 — Package rename + environment refresh

**Deliverable:** the repo builds and gates green under the new snake_case
package names against the pinned foundation branch. Mechanical migration —
no behavior changes beyond the required ABC re-parent.

## Files

- `git mv src/pyMathTools src/math_tools`; inside it:
  `git mv src/math_tools/spatial/Quaternion.py src/math_tools/spatial/quaternion.py`,
  `git mv src/math_tools/spherical/sphericalGenerators.py src/math_tools/spherical/spherical_generators.py`,
  `git mv src/math_tools/spherical/sphericalTransforms.py src/math_tools/spherical/spherical_transforms.py`
  (`constructors.py`, `hints.py` keep their names).
- `git mv src/pyMathToolsPlotHelpers src/math_plot_helpers`;
  `git mv src/math_plot_helpers/plotUnitSpherical.py src/math_plot_helpers/plot_unit_spherical.py`.
- Edit: `src/math_tools/spatial/quaternion.py` (imports/base only, see below),
  every `__init__.py` touched by moves, `tests/test_quaternion.py`,
  `examples/sphericalPlotting/plotArcs.py`,
  `examples/sphericalPlotting/plotQuatUnitCircles.py`, `Makefile` (mypy
  package list if it names packages), `.env` if it names packages.
- Add: `py.typed` in `src/math_tools/` and `src/math_plot_helpers/` roots
  (keep the existing ones in subpackages).

## Design constraints

1. **First action:** `make uv-refresh` so `.venv` matches the
   `requirements.txt` branch pin (the stale install has the pre-template ABC
   layout; nothing imports correctly until this runs).
2. **ABC re-parent (the one semantic edit):** in `quaternion.py`, replace
   `from foundationTypes.mathTypes.quaternionABC import QuaternionABC` with
   `from foundation_abc.math.spatialABCs import QuaternionABC`. The old ABC
   carried `DataModelHelper`; the new one is ABC-only with a concrete
   `to_dict`. In `tests/test_quaternion.py`, update the serialization tests'
   base-class assertions (`DataModelHelper` inheritance assertion → the new
   ABC) — assertions on `to_dict`/`from_dict` *values* stay untouched. If any
   other import from the old layout exists (grep `foundationTypes.mathTypes.`
   across `src/`), re-point to `foundation_abc.math.*` /
   `foundationTypes.mathTypes.MathTypes` equivalents.
3. All other edits are import-path text substitutions
   (`pyMathTools` → `math_tools`, `pyMathToolsPlotHelpers` →
   `math_plot_helpers`, moved module filenames).
4. `pyproject.toml`: update `description` only if trivially co-located; the
   deps list changes in chunk 03, not here.

## TDD steps

1. `make uv-refresh`; run `make uv-test` to record the pre-existing pass/fail
   baseline (the ABC import may already be broken — note it).
2. Perform moves + edits.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] `grep -rn "pyMathTools" src/ tests/ examples/ Makefile .env pyproject.toml` → no hits
- [ ] `grep -rn "foundationTypes.mathTypes.quaternionABC" src/ tests/` → no hits
- [ ] `git log --follow --oneline src/math_tools/spatial/quaternion.py` shows history (moves were `git mv`)
- [ ] All ~90 quaternion tests pass; diff to `tests/test_quaternion.py` contains only import lines and base-class assertion lines
- [ ] `make uv-fullCheck` passes

## Out of scope

`errors.py`, layering test, README, `.claude/CLAUDE.md`, pyproject dependency
list, any new math code, any `__init__.py` re-export curation beyond fixing
broken imports.
