---
chunk: 01-template-rename-and-refresh
track: A
status: complete
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

- [x] `grep -rn "pyMathTools" src/ tests/ examples/ Makefile .env pyproject.toml` → no hits
- [x] `grep -rn "foundationTypes.mathTypes.quaternionABC" src/ tests/` → no hits
- [x] `git log --follow --oneline src/math_tools/spatial/quaternion.py` shows history (moves were `git mv`) — verified via `git status`/`git diff --staged` showing `renamed: src/pyMathTools/spatial/Quaternion.py -> src/math_tools/spatial/quaternion.py`; `--follow` itself needs a commit to walk, which this chunk intentionally leaves to the supervising process
- [x] All ~90 quaternion tests pass (89 collected/passed); diff to `tests/test_quaternion.py` contains only import lines, base-class assertion lines, and their two adjacent docstring lines (see Resolution notes)
- [x] `make uv-fullCheck` passes

## Out of scope

`errors.py`, layering test, README, `.claude/CLAUDE.md`, pyproject dependency
list, any new math code, any `__init__.py` re-export curation beyond fixing
broken imports.

## Resolution notes

- `make uv-refresh` pulled the pinned foundation branch fresh; pre-move
  `make uv-test` baseline reproduced the expected pre-existing break
  (`ModuleNotFoundError: foundationTypes.mathTypes.quaternionABC`), confirming
  the venv was stale before this chunk and the gate is meaningful after.
- Moves done via `git mv` as specified. `git status`/`git diff --staged`
  correctly report `quaternion.py` as a rename from `Quaternion.py`; git's
  similarity heuristic cross-matched some of the (byte-identical, empty)
  `__init__.py` files to different-but-equivalent old empty `__init__.py`
  paths — cosmetic only, every file's on-disk destination was verified
  directly with `find`, and it does not affect `--follow` on the files that
  matter (confirmed for `quaternion.py`).
- The old-layout ABC repoint (design constraint 2) turned out to reach beyond
  `quaternion.py`: `foundationTypes.mathTypes.unitSphericalArcABC` and
  `unitSphericalSmallCircleABC` (imported by `spherical_generators.py`,
  `spherical_transforms.py`, `constructors.py`, `plot_unit_spherical.py`)
  were also deleted from the pinned foundation branch and now live at
  `foundation_abc.math.sphericalABCs`. Re-pointed all of them per the chunk's
  explicit "grep `foundationTypes.mathTypes.` across `src/`" instruction —
  required for `make uv-fullCheck` (mypy strict) to pass, since mypy scans
  all of `src/`, not just the quaternion module. `foundationTypes.mathTypes.MathTypes.*`
  imports (the codegen `*Type` classes) were left untouched — that module
  still exists unchanged in the new layout.
  This is a scope note, not a spec deviation: constraint 2's own text
  authorized exactly this action; the "Files" list section above just didn't
  enumerate every file it touched.
- `examples/sphericalPlotting/plotArcs.py` and `plotQuatUnitCircles.py` got
  only the mechanical package-name substitution, per constraint 3 and Gap 4's
  explicit ownership of their pre-existing broken `foundationTypes.mathTypes.UnitSphericalArc`
  / `UnitSphericalSmallCircle` imports (not part of this chunk's scope, and
  not scanned by `make uv-typecheck` since `PY_EXAMPLES` is unset in `.env`).
- `tests/test_quaternion.py`: `test_inheritance_from_data_model_helper`
  asserted `isinstance(q, DataModelHelper)`, which is no longer true (the new
  `QuaternionABC` is ABC-only). Repointed the import and assertion to
  `QuaternionABC` per constraint 2's directive, and updated that test's and
  the class's docstrings by one line each so the docstrings don't contradict
  the assertion right below them — the only lines in this diff beyond raw
  import-path substitution. No `to_dict`/`from_dict` value assertions were
  touched.
- Added `py.typed` at `src/math_tools/` and `src/math_plot_helpers/` package
  roots (subpackage ones already existed).
- No `Makefile`/`.env` edits were needed — neither names packages explicitly
  (both scope quality targets via path variables, not package names).
- `pyproject.toml` `description` left untouched — no trivially co-located
  edit was applicable in this chunk; still boilerplate text, tracked as Gap 4
  (chunk 03).
