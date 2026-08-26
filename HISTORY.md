# History

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
-

## [0.0.2] - 2026-08-26

Tier-3 math implementation layer built out on top of `pyFoundationTools`, plus a
full migration onto the project template. This release renames both packages;
see Changed for the import migration.

### Added
- `math_tools.precision_time`: `PrecisionTimeInterval` and `PrecisionTimestamp`
  — integer-backed nanosecond time arithmetic, comparison, and conversion.
- `math_tools.spatial`: `Position` and `SpatialPose` alongside the existing
  `Quaternion`, with tolerance-aware comparison and timestamp accessors.
- `math_tools.functional`: `UnivariatePolynomial` plus analytic root solvers
  (`solve_cubic`, `solve_quartic_monic`, `solve_resolvent`), derivative and
  evaluation kernels, and shared polynomial tolerances.
- `math_tools.waveforms`: `Waveform1D` core, operators, and generators, plus the
  aggregate containers `WaveformPosition`, `WaveformQuaternion`, and
  `WaveformSpatialPose` (and their component-waveform views).
- `math_tools.waveforms.dsp`: twelve scipy-backed DSP mixins composed onto
  `Waveform1D` — calc, correlation, envelope, filtering, peaks, phase,
  resampling, spectral, time alignment, triggers, windowing, and zero crossings
  — with a `WaveformProtocol` typing contract and a support-type surface
  (spectra, spectrograms, filter coefficients, triggers, peaks, enums).
- `math_tools.otg`: online trajectory generation ported from Ruckig — `Otg`
  driver, `InputParameter`, `OutputParameter`, `Trajectory`, `Profile`, block
  and brake computation, and first/second/third-order position and velocity
  step solvers, with `Result`, `Synchronization`, `ControlInterface`, and
  `DurationDiscretization` enums.
- Error hierarchy rooted at `MathToolsError`: `WaveformCompatibilityError`,
  `TimestampComparisonError`, `PolynomialSolveError`, and `OtgError`.
- Curated root re-export surface on `math_tools`, and `py.typed` markers on
  every distributed package.
- Test suite mirroring the package layout under `tests/`, including OTG oracle
  corpora (`tests/otg/data/`) validated against reference trajectories, plus
  governance, public-surface, and package-layering guard tests.
- `.claude/specs/` architecture and per-module contracts, and `.claude/CLAUDE.md`
  repo guidance.
- Template infrastructure: `.github/workflows/ci-cd.yml`, `.github/CODEOWNERS`,
  `.editorconfig`, `.python-version` (3.13), `.bumpversion.cfg`, and a
  hand-authored `requirements.txt`.

### Changed
- **Breaking:** `pyMathTools` renamed to `math_tools` and
  `pyMathToolsPlotHelpers` renamed to `math_plot_helpers`; modules and public
  functions moved to snake_case (e.g. `spherical.sphericalTransforms` →
  `spherical.spherical_transforms`, `plotUnitSpherical` helpers →
  `plot_unit_spherical_*`). Update imports accordingly.
- Layering is now one-way and enforced by test: `math_plot_helpers` →
  `math_tools` → `pyFoundationTools`; `math_tools` never imports matplotlib.
- Makefile reworked as the source of truth for tooling, with `uv-` targets and
  the `uv-fullCheck` CI gate (ruff + strict mypy + pytest).
- Linting and formatting moved to ruff; type checking is strict `mypy` over
  `src/` and `tests/`.
- Runtime dependencies in `pyproject.toml` are names-only; pins live in
  `requirements.txt`.
- Governance docs refreshed: `README.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `LICENSE`.

### Removed
- `.pylintrc` (superseded by ruff).

## [0.0.1] - 2026-06-29

### Added
- First release on PyPI.

[Unreleased]: https://github.com/kopecn/py_math_tools/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/kopecn/py_math_tools/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/kopecn/py_math_tools/releases/tag/v0.0.1
