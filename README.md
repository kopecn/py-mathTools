# py-MathTools

The Tier 3 math implementation layer for `pyFoundationTools`: numpy-backed
math classes (quaternions today, spatial poses / waveforms / polynomials /
trajectory generation as the port lands) that subclass the Tier-2
`foundation_abc.math.*` ABCs and interoperate with the Tier-1
`foundationTypes.mathTypes` data carriers, plus a separate `matplotlib`
plotting helper package.

## Features

- **`math_tools.spatial.quaternion.Quaternion`** — fully-typed OOP wrapper
  around the `numpy-quaternion` library: arithmetic (`+ - * /`, scalar and
  quaternion operands), `conjugate`/`inverse`/`normalized`/`norm`,
  rotation-matrix and axis/angle conversions, and conversion to/from the
  spherical small-circle representation.
- **`math_tools.spherical`** — spherical-arc and small-circle utilities
  (great-circle construction between two points, endpoint computation,
  Plate Carrée / Cartesian coordinate transforms) built on the ISO physics
  spherical convention, using the Tier-1 `UnitSphericalArcType` /
  `UnitSphericalSmallCircleType` carriers.
- **`math_tools.errors`** — the `MathToolsError` domain exception hierarchy
  (`WaveformCompatibilityError`, `TimestampComparisonError`,
  `PolynomialSolveError`); programmer errors still raise stdlib
  `TypeError`/`ValueError`.
- **`math_plot_helpers.plot_unit_spherical`** — matplotlib visualizations
  (Plate Carrée, polar, and 3D multiplot views) for spherical arcs, small
  circles, and quaternions. This is the only package in the repo permitted
  to import `matplotlib` (`tests/test_package_layering.py` enforces the
  one-way `math_plot_helpers → math_tools` dependency).

See [`.claude/specs/mathToolsArchitecture.md`](.claude/specs/mathToolsArchitecture.md)
for the full architecture and the module map for capability still being
ported (spatial pose, waveforms/DSP, polynomials, OTG trajectory
generation).

## Installation

```bash
pip install py_math_tools
```

## Quick Start

### Quaternions

```python
from math_tools.spatial.quaternion import Quaternion

identity = Quaternion.from_components(1, 0, 0, 0)
rotated = Quaternion.from_unit_x_to_vector([0, 1, 0])

print((identity * rotated).normalized())
print(rotated.to_rotation_matrix())
```

### Spherical arcs

```python
import numpy as np
from math_tools.spherical.constructors import arc_from_two_points
from math_tools.spherical.spherical_transforms import compute_spherical_arc_endpoint

arc = arc_from_two_points(azimuth1=0, polar1=0, azimuth2=0, polar2=np.pi / 2)
end_azimuth, end_polar = compute_spherical_arc_endpoint(arc)
```

### Plotting

```bash
uv run python examples/sphericalPlotting/plotArcs.py
uv run python examples/sphericalPlotting/plotQuatUnitCircles.py
```

Both scripts call `plot_unit_spherical_multiplot(..., show_plot=True)`; run
with an interactive matplotlib backend to see the figures, or with
`MPLBACKEND=Agg` to just exercise the code path non-interactively.

## Development Workflows

All workflows go through the Makefile (`make help` lists every target); it
is the source of truth for tooling, not this README.

```bash
make uv-sync        # create/refresh .venv from pyproject + requirements.txt
make uv-fullCheck   # gate: ruff lint + strict mypy + pytest
make uv-format       # ruff format + autofix
```

`make uv-refresh` is required after the `pyFoundationTools` pin in
`requirements.txt` changes — a stale `.venv` makes the gate meaningless.

## Requirements

- Python >= 3.10
- `pyFoundationTools`, `numpy`, `scipy`, `numpy-quaternion`, `matplotlib`
  (see [`pyproject.toml`](pyproject.toml) for the names-only dependency
  declaration and [`requirements.txt`](requirements.txt) for the pinned
  `pyFoundationTools` source)
