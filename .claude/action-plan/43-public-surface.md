---
chunk: 43-public-surface
track: A
status: pending
depends_on: [30, 42, 09, 17]
spec: ../specs/mathToolsArchitecture.md §Shared conventions (Public surface)
last_updated: 2026-07-11
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

- [ ] `import math_tools as mt; mt.Waveform1D.sine(n=8)` works in a fresh interpreter
- [ ] `__all__` pin test passes; no extra public names
- [ ] `make uv-fullCheck` passes

## Out of scope

Adding names beyond the spec list (that requires an umbrella spec bump).
