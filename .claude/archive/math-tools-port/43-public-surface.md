---
chunk: 43-public-surface
track: A
status: complete
depends_on: [30, 42, 09, 17]
spec: ../specs/mathToolsArchitecture.md §Shared conventions (Public surface)
last_updated: 2026-07-22
semver: 0.0.1
author: Nicholas Bergantz
---

# 43 — Curated top-level public surface (final chunk)

**Deliverable:** the flat `import math_tools as mt` working set. Runs last —
after every exporting track is done.

## Files

- Edit: `src/math_tools/__init__.py`
- Create: `tests/test_public_surface.py`

## Design constraints

1. Root `__all__` is EXACTLY the umbrella spec's list: `Position`,
   `Quaternion`, `SpatialPose`, `PrecisionTimeInterval`,
   `PrecisionTimestamp`, `Waveform1D`, `WaveformPosition`,
   `WaveformQuaternion`, `WaveformSpatialPose`, `UnivariatePolynomial`,
   `Otg`, `InputParameter`, `OutputParameter`, `Trajectory`, `Result`,
   `MathToolsError`, `WaveformCompatibilityError`,
   `TimestampComparisonError`, `PolynomialSolveError`. Re-exports only —
   no logic in `__init__.py`.
2. The test pins `set(math_tools.__all__)` to that literal list, imports
   every name, and asserts each resolves to the subpackage-defined class
   (identity check, e.g. `math_tools.Position is
   math_tools.spatial.Position`).

## TDD steps

1. Write the failing `__all__` pin test. 2. Wire the re-exports.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] `import math_tools as mt; mt.Waveform1D.sine(n=8)` works in a fresh interpreter
- [x] `__all__` pin test passes; no extra public names
- [x] `make uv-fullCheck` passes

## Out of scope

Adding names beyond the spec list (that requires an umbrella spec bump).

## Resolution notes

- `src/math_tools/__init__.py` was empty (stub) prior to this chunk; wired it
  to re-export the umbrella spec's 19 names only, sourced from each
  subpackage's already-curated `__all__` (`spatial`, `precision_time`,
  `waveforms`, `functional`, `otg`, `errors`) — no new logic, pure
  re-export, matching design constraint 1.
- `Result` resolves to `math_tools.otg.Result` (the OTG result enum defined
  in `otg/enums.py`); no naming collision with anything else in scope.
- `tests/test_public_surface.py` (new) has three cases: (1) `__all__` pins
  to the exact literal spec set via `assertEqual` on the `set` plus a
  length check (catches accidental duplicates); (2) every name is checked
  by identity (`assertIs`) against the subpackage-qualified source, per the
  chunk's stated test shape; (3) the whole-plan smoke deliverable
  `math_tools.Waveform1D.sine(n=8)`.
- TDD order followed exactly: wrote the test against the empty
  `__init__.py` first, confirmed 21 failures (`AttributeError` on every
  pinned name), then wired the re-exports, then reran — 3 passed / 19
  subtests passed.
- `make uv-fullCheck` green: ruff clean, mypy strict clean (117 source
  files), pytest 1356 passed (0 failed) including the new file.
- No deviations from the chunk as written; no scope creep — only the two
  listed files were touched.
