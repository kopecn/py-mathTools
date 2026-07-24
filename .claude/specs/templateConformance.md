---
version: 1.0
type: specification
name: templateConformance
purpose: Bring py-MathTools into full conformance with the py-foundationTools template conventions
spec: TemplateConformance
scope: project
status: accepted
applies_to: pyproject.toml, requirements.txt, Makefile, .env, .github/, .claude/, src/, README.md
last_updated: 2026-07-23
semver: 0.0.3
author: Nicholas Bergantz
---

# Template Conformance

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). The
> authoritative template reference is py-foundationTools at branch
> `feat/switch-to-new-template`
> (`/Users/nbergantz/__Workspaces__/pythonWorkspaces/py-foundationTools`);
> this spec states what "conformant" means for this repo, not a copy of that
> repo's content.

## Already conformant (verify, don't re-do)

The current branch already carries: the uv Makefile (with `uv-fullCheck`
gate), `.env` (`PY_SRC=src`), `.bumpversion.cfg`, the `ci-cd.yml` workflow
(quality checks + Python compatibility matrix on PRs to `dev`/`prod`),
names-only `pyproject.toml` policy, and pinned `requirements.txt`.
Conformance work MUST NOT rewrite these wholesale; only close the specific
gaps below.

## Gap 1 — package rename (breaking, approved)

| Current | Target |
|---|---|
| `src/pyMathTools/` | `src/math_tools/` |
| `src/pyMathToolsPlotHelpers/` | `src/math_plot_helpers/` |

Requirements:

1. `git mv` the trees; module layout inside follows the umbrella's module map
   (existing `spatial/`, `spherical/`, `hints.py` migrate; `Quaternion.py` →
   `spatial/quaternion.py`; `plotUnitSpherical.py` →
   `math_plot_helpers/plot_unit_spherical.py`). Module **filenames** become
   snake_case; class names are unchanged.
2. Behavior of migrated code is unchanged in the rename chunk — imports and
   paths only ([stay-in-scope]). Extensions to migrated classes come later
   under their own sibling specs.
3. All imports updated: `tests/`, `examples/`, intra-package.
4. Every package dir (`math_tools`, each subpackage with public API,
   `math_plot_helpers`) contains `py.typed`.
5. `pyproject.toml` needs no `packages` edit (`package-dir = {"" = "src"}`
   auto-discovers), but the Makefile's mypy package list (`MYPY_PKGS` pattern
   from the template) and any name references MUST resolve to the new names.
6. Distribution name stays `py_math_tools`; only import packages rename.

## Gap 2 — dependencies

1. `pyproject.toml` `dependencies`: names only —
   `pyFoundationTools`, `numpy`, `scipy`, `numpy-quaternion`, `matplotlib`.
2. `requirements.txt`: keep the `pyFoundationTools @ git+...@feat/switch-to-new-template`
   pin until foundation tags a release, then move to a tag pin (tracked as a
   known follow-up, not part of this effort).
3. No `uv.lock` committed (repo BKM).
4. **Hard prerequisite for every other chunk:** the installed `.venv` may
   hold a pre-template `pyfoundationtools` (old per-type ABC layout,
   `foundationTypes.mathTypes.quaternionABC` etc.). The first chunk MUST
   `make uv-refresh` (or equivalent) so the environment matches the branch
   pin's layout (`foundation_abc.math.*`, `PositionType`,
   `SpatialTransformType`, `ScalarWaveformType`); the gate is meaningless
   against the stale install.

## Gap 3 — `.claude/` governance

1. `.claude/CLAUDE.md` authored for this repo: role (Tier 3 of foundation's
   math tiers), package map, gate command, pointer to `.claude/specs/`.
   It references specs — never duplicates their content.
2. `.claude/specs/` — this spec set.
3. `.claude/action-plan/` — the chunk set produced from these specs.

## Gap 4 — README and metadata

1. `README.md` replaces the "Python Boilerplate" stub, following the
   template's section shape: title → Features → Installation → Quick Start →
   Development Workflows → Requirements. Content MUST describe what actually
   exists at the time the chunk runs (no aspirational feature lists).
2. `pyproject.toml` `description` updated from boilerplate text.
3. `examples/sphericalPlotting/*` imports fixed to real module paths (note:
   `plotArcs.py` currently imports a nonexistent
   `foundationTypes.mathTypes.UnitSphericalArc` path).

## Gap 5 — layering test

Port the template's layering-enforcement pattern
(py-foundationTools `tests/test_package_layering.py`) as
`tests/test_package_layering.py` asserting, via import/AST scan of `src/`:

- `math_tools` never imports `math_plot_helpers` or `matplotlib`.
- `math_plot_helpers` may import `math_tools`.
- Only `math_plot_helpers` imports `matplotlib`.

## Compliance checklist (mechanically verifiable)

- [x] `grep -r "pyMathTools" src/ tests/ examples/ Makefile pyproject.toml` → no hits
- [x] `find src -name py.typed` covers every public package
- [x] `make uv-fullCheck` passes after rename
- [x] `.claude/CLAUDE.md` exists and links every spec in `.claude/specs/`
- [x] `README.md` contains no "Boilerplate" text
- [x] `tests/test_package_layering.py` passes and fails if `import matplotlib` is added to any `math_tools` module
