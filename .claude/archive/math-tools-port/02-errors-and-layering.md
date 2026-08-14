---
chunk: 02-errors-and-layering
track: A
status: complete
depends_on: [01]
spec: ../specs/mathToolsArchitecture.md §Error semantics; ../specs/templateConformance.md §Gap 5
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 02 — Exception hierarchy + package layering test

**Deliverable:** `math_tools/errors.py` and the AST-based layering test.

## Files

- Create: `src/math_tools/errors.py`
- Create: `tests/test_package_layering.py`
- Create: `tests/test_errors.py`

## Design constraints

1. `errors.py` defines exactly (each with a one-line docstring):
   `MathToolsError(Exception)`, `WaveformCompatibilityError(MathToolsError)`,
   `TimestampComparisonError(MathToolsError)`,
   `PolynomialSolveError(MathToolsError)`.
2. Layering test pattern: copy the approach of py-foundationTools
   `tests/test_package_layering.py` (AST-walk every module under `src/`,
   collect `import`/`from` roots). Assertions per templateConformance §Gap 5:
   `math_tools` imports neither `math_plot_helpers` nor `matplotlib`;
   only `math_plot_helpers` imports `matplotlib`.
3. Additionally assert `math_tools.otg` (once it exists) does not import
   `numpy` — write the rule now, guarded to skip if the package dir is
   absent, so OTG chunks inherit enforcement for free.

## TDD steps

1. Write `tests/test_errors.py` (hierarchy, catchability as `MathToolsError`)
   and `tests/test_package_layering.py`; watch errors test fail.
2. Implement `errors.py`; layering test must pass against the current tree.
3. Temporarily add `import matplotlib` to a `math_tools` module and confirm
   the layering test fails; revert. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All four exception classes exist and subclass as specified
- [x] Layering test fails on an injected `import matplotlib` in `math_tools` (verified then reverted)
- [x] `make uv-fullCheck` passes

## Out of scope

Any consumer of the exceptions; OTG's `OtgError` (lives in `otg/errors.py`,
chunk 31); README/CLAUDE.md.

## Resolution notes

- `errors.py` implements exactly the four classes from the spec, each a
  one-line docstring, no added behavior.
- `test_package_layering.py` follows the py-foundationTools AST-scan pattern
  (`tests/test_package_layering.py` there) rather than executing imports, so
  it can't be defeated by import side effects. Four checks: `math_tools` ↛
  `math_plot_helpers`, `math_tools` ↛ `matplotlib`, only `math_plot_helpers`
  → `matplotlib` (scans all of `src/` excluding that package), and the
  guarded `math_tools.otg` ↛ `numpy` rule (currently a no-op skip since
  `otg/` doesn't exist yet — will activate automatically once chunk 31 lands).
- Verification step 3 (inject `import matplotlib` into `math_tools/errors.py`,
  confirm two layering assertions fail, revert) was done live against the
  actual gate, not simulated; file diffed back to the original after.
- One ruff fix needed: the injected-violation assertion message exceeded the
  100-char line limit in `test_only_math_plot_helpers_imports_matplotlib`'s
  sibling test; wrapped the f-string across two lines.
- No spec changes were required — the chunk's design constraints matched the
  umbrella spec's Error semantics section exactly.
