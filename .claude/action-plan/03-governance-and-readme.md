---
chunk: 03-governance-and-readme
track: A
status: pending
depends_on: [02]
spec: ../specs/templateConformance.md §Gap 2, §Gap 3, §Gap 4
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] `tests/test_governance.py` passes
- [ ] `pyproject.toml` deps are exactly the five names, unpinned
- [ ] Both example scripts import-run without error
- [ ] `make uv-fullCheck` passes

## Out of scope

Makefile/CI edits; requirements pin changes; any `src/` code beyond the
example imports.
