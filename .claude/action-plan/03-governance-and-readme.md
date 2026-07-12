---
chunk: 03-governance-and-readme
track: A
status: complete
depends_on: [02]
spec: ../specs/templateConformance.md §Gap 2, §Gap 3, §Gap 4
last_updated: 2026-07-11
semver: 0.0.2
author: Nicholas Bergantz
---

# 03 — Governance docs, README, dependency names

**Deliverable:** `.claude/CLAUDE.md`, real README, pyproject dependency
names, fixed examples.

## Files

- Create: `.claude/CLAUDE.md`
- Edit: `README.md`, `pyproject.toml` (deps + description only),
  `examples/sphericalPlotting/plotArcs.py`,
  `examples/sphericalPlotting/plotQuatUnitCircles.py`

## Design constraints

1. `.claude/CLAUDE.md` follows the shape of py-foundationTools
   `.claude/CLAUDE.md` but stays short: repo role (Tier 3 of foundation's
   `mathTypeTiers.md`), the two-package layering diagram, gate command,
   Makefile-is-source-of-truth note, and a linked index of every spec in
   `.claude/specs/`. Reference specs; never duplicate their content.
2. `pyproject.toml` `dependencies` = names only:
   `pyFoundationTools`, `numpy`, `scipy`, `numpy-quaternion`, `matplotlib`.
   Replace the boilerplate `description`.
3. README per templateConformance Gap 4: describe only what exists at
   execution time (quaternion, spherical utilities, template workflows);
   sections: title → Features → Installation → Quick Start → Development
   Workflows → Requirements. Quick Start snippets must actually run.
4. `plotArcs.py`: fix the dead
   `foundationTypes.mathTypes.UnitSphericalArc.UnitSphericalArc` import to
   the real generated type in `foundationTypes.mathTypes.MathTypes`
   (verify the class name by reading that module).

## TDD steps

1. Add a test `tests/test_governance.py`: `.claude/CLAUDE.md` exists and its
   text links every `*.md` in `.claude/specs/`; `README.md` contains no
   "Boilerplate". Watch it fail.
2. Write the docs; run both example scripts manually
   (`uv run python examples/sphericalPlotting/plotArcs.py` with a
   non-interactive matplotlib backend) to prove imports resolve.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] `tests/test_governance.py` passes
- [x] `pyproject.toml` deps are exactly the five names, unpinned
- [x] Both example scripts import-run without error
- [x] `make uv-fullCheck` passes

## Out of scope

Makefile/CI edits; requirements pin changes; any `src/` code beyond the
example imports.

## Resolution notes

- `tests/test_governance.py` added: asserts `.claude/CLAUDE.md` exists and
  its text contains the filename of every `.claude/specs/*.md` file, and
  that `README.md` contains no `"Boilerplate"` text. Confirmed it failed
  before the docs existed, passed after.
- `.claude/CLAUDE.md` written to the shape of py-foundationTools'
  `.claude/CLAUDE.md` (Project Overview → layering → Commands → Specs index
  → Tests) but scoped to what exists in this repo today: Tier 3 role, the
  two-package layering diagram, the gate command, a Makefile-is-source-of-
  truth note, and a linked index of all 7 specs in `.claude/specs/`.
- `README.md` rewritten per Gap 4's section shape (title → Features →
  Installation → Quick Start → Development Workflows → Requirements),
  describing only what exists at execution time: `Quaternion`, the
  spherical arc/small-circle utilities, `errors.py`, and the
  `math_plot_helpers` plotting package. Both Quick Start snippets
  (quaternion arithmetic/conversion, spherical arc construction +
  endpoint) were executed directly to confirm they run as written.
- `pyproject.toml`: `dependencies` set to the five names
  (`pyFoundationTools`, `numpy`, `scipy`, `numpy-quaternion`, `matplotlib`)
  — the prior list was missing `numpy`/`scipy` and had an unrelated stray
  order; `description` replaced with a one-line Tier-3 summary.
- `examples/sphericalPlotting/plotArcs.py`: fixed the dead
  `foundationTypes.mathTypes.UnitSphericalArc.UnitSphericalArc` import to
  `foundationTypes.mathTypes.MathTypes.UnitSphericalArcType` (verified the
  real class name by reading the installed `MathTypes.py`) and updated the
  two local usages/type hints accordingly.
- `examples/sphericalPlotting/plotQuatUnitCircles.py`: same dead-import
  pattern existed for `UnitSphericalSmallCircle` (not called out by name in
  the chunk's design constraint 4, but the file was listed for edit and the
  acceptance criterion requires *both* scripts to import-run without
  error) — fixed to `foundationTypes.mathTypes.MathTypes.UnitSphericalSmallCircleType`.
- Both example scripts verified to run end-to-end with
  `MPLBACKEND=Agg PYTHONPATH=src .venv/bin/python examples/sphericalPlotting/<script>.py`
  — exit 0, only a benign "FigureCanvasAgg is non-interactive" UserWarning
  from `show_plot=True` under a non-interactive backend. Examples are not
  wired into `make uv-fullCheck` (`PY_EXAMPLES` is unset in `.env`), so
  this was a manual verification step, not a gate addition (out of scope
  per this chunk: "Makefile/CI edits").
- Gate: `make uv-fullCheck` passes — ruff clean, `mypy src tests` strict
  clean (16 source files), pytest 106 passed (includes the new
  `tests/test_governance.py`).
