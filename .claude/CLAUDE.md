# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`py-MathTools` is the **Tier 3 math implementation layer** of the foundation
math tiers defined in py-foundationTools' `mathTypeTiers.md`: it subclasses
the Tier-2 `foundation_abc.math.*` ABCs, chooses numpy-backed storage, and
implements arithmetic, composition, interpolation, DSP, and trajectory
generation on top of the Tier-1 `foundationTypes.mathTypes` data carriers.
Unlike `pyFoundationTools` (zero-dependency by policy), this repo depends on
a curated set of mature numeric packages rather than reimplementing them.

## Packages and layering

Two top-level snake_case packages under `src/`, one-way dependency:

```
math_plot_helpers  →  math_tools  →  pyFoundationTools  →  stdlib
       (matplotlib)      (numpy, scipy, numpy-quaternion)
```

`math_tools` never imports `math_plot_helpers` or `matplotlib`; only
`math_plot_helpers` imports `matplotlib`. This is enforced by
`tests/test_package_layering.py` (static AST scan of `src/`).

## Commands

All workflows go through the Makefile (`make help` lists them); **the
Makefile is the source of truth for tooling**, not this file or the README.
The `uv-` prefixed targets are the primary path. Key ones:

- `make uv-fullCheck` — CI gate: `uv-lint` + `uv-typecheck` + `uv-test`. Run
  this before considering work done.
- `make uv-lint` — ruff check
- `make uv-format` — `ruff format` + `ruff check --fix --unsafe-fixes`
- `make uv-typecheck` — strict `mypy` over `src/` + `tests/`
- `make uv-test` — sync deps then run pytest
- `make uv-refresh` — clean cache + reinstall from `requirements.txt` +
  upgrade editable dev install (required after a `pyFoundationTools` pin
  changes; a stale `.venv` makes the gate meaningless)

## Specs

`.claude/specs/` is the authoritative contract for this repo's architecture
and every module's behavior. Consult the relevant spec before extending a
module; if implementation forces a contract change, the spec is updated in
the same change and its `semver` bumped.

- [mathToolsArchitecture.md](specs/mathToolsArchitecture.md) — umbrella:
  layering, package layout, dependency policy, shared conventions, error
  semantics
- [templateConformance.md](specs/templateConformance.md) — template
  migration: packaging, Makefile/CI parity, rename, governance docs
- [precisionTimeMath.md](specs/precisionTimeMath.md) — `PrecisionTimeInterval`,
  `PrecisionTimestamp`
- [spatialMath.md](specs/spatialMath.md) — `Position`, `Quaternion`,
  `SpatialPose`
- [waveformCore.md](specs/waveformCore.md) — `Waveform1D` + aggregate
  waveform containers
- [waveformDsp.md](specs/waveformDsp.md) — DSP families, scipy mapping,
  support types
- [polynomials.md](specs/polynomials.md) — polynomial type + analytic root
  solvers
- [otg.md](specs/otg.md) — online trajectory generation (Ruckig port)

## Tests

Tests live in `tests/`, `unittest.TestCase` style run under pytest
(`test*.py` files, `test_*` methods), mirroring the package layout under
`src/` (e.g. `tests/spatial/test_position.py`).
