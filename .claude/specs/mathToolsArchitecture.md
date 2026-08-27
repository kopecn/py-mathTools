---
version: 1.0
type: umbrella-architecture
name: mathToolsArchitecture
purpose: Layering, package layout, dependency policy, and shared conventions for py-MathTools
spec: MathToolsArchitecture
scope: project
status: draft
applies_to: src/, tests/, pyproject.toml
last_updated: 2026-08-26
semver: 0.1.0
author: Nicholas Bergantz
---

# py-MathTools Architecture

> Umbrella spec. Each module's behavioral contract lives in a sibling spec
> (index at the bottom); this spec owns the layering, the package layout, the
> dependency policy, and the conventions every sibling inherits. On conflict
> within this repo, this spec wins for structure; the sibling wins for its own
> module's behavior.

## Role — Tier 3 of the foundation math tiers

py-MathTools is the **math implementation tier** ("`Xxxx`") of the tier system
defined in py-foundationTools' `.claude/specs/mathTypeTiers.md`:

- **Tier 1** (`XxxxType`, `foundationTypes.mathTypes.MathTypes`) — codegen data
  carriers. Serialization/validation only. Owned by py-foundationTools.
- **Tier 2** (`XxxxABC`, `foundation_abc.math.*`) — stdlib-only accessor +
  serialization contracts. Owned by py-foundationTools.
- **Tier 3** (this repo) — rich math classes that subclass the Tier-2 ABCs,
  choose their own storage (numpy), and implement arithmetic, composition,
  interpolation, DSP, and trajectory generation.

Rules that follow:

1. Every py-MathTools class whose concept has a Tier-2 ABC **MUST subclass that
   ABC** and satisfy its accessor and `to_dict`/`from_dict` contract
   (`PositionABC`, `QuaternionABC`, `SpatialTransformABC`, `Waveform1dABC`,
   `PositionWaveformABC`, `QuaternionWaveformABC`, `WaveformSpatialABC`,
   `PrecisionTimeIntervalABC`, `PrecisionTimestampABC`).
2. py-MathTools **never re-implements storage/data-carrier types** that
   foundation already generates; it interoperates with them via
   `to_dict`/`from_dict` (wire-format parity is the compatibility contract).
3. Dependency direction is one-way: py-MathTools → pyFoundationTools. Nothing
   in foundation may import this package. The foundation-side `XxxxMathLike`
   modules referenced by `mathTypeTiers.md` do not exist yet; when foundation
   adds them, tightening our base classes is a follow-on task in that repo's
   cadence — not assumed here.

## Dependency policy (differs from foundation)

Foundation is zero-dependency by policy; **this repo is not**. A mature pip
package that covers a scope SHALL be preferred over reimplementation:

| Dependency | Used for | Rule |
|---|---|---|
| `pyFoundationTools` | ABCs, generated Types, enums | required, git/tag pin in `requirements.txt` |
| `numpy` | array storage, linear algebra, FFT | required |
| `scipy` | signal processing (filters, PSD, spectrogram, peaks, resampling) | required; every DSP method wraps scipy/numpy when an equivalent exists |
| `numpy-quaternion` | quaternion backend | required (already in use) |
| `matplotlib` | plotting | **only** importable from `math_plot_helpers` |

Wrappers MUST present a typed, ABC-conformant surface — the pip package is an
implementation detail, never part of the public API (no scipy/numpy types leak
into signatures except `np.ndarray` / `npt.NDArray[...]` where arrays are the
natural currency). Names go in `pyproject.toml`, pins in `requirements*.txt`,
per the template BKM (see [templateConformance.md](templateConformance.md)).

## Packages and layering

Two top-level snake_case packages under `src/` (naming rules in
[templateConformance.md](templateConformance.md) §Package and module naming):

```
math_plot_helpers  →  math_tools  →  pyFoundationTools  →  stdlib
       (matplotlib)      (numpy, scipy, numpy-quaternion)
```

No reverse imports. `matplotlib` never appears in `math_tools`.

### `math_tools` module map

```
src/math_tools/
  __init__.py            # curated public re-exports (see Public surface)
  py.typed
  hints.py               # shared type aliases
  errors.py              # exception hierarchy (see Error semantics)
  precision_time/        # PrecisionTimeInterval, PrecisionTimestamp   → precisionTimeMath.md
  spatial/               # Position, Quaternion, SpatialPose           → spatialMath.md
  spherical/             # unit-sphere arcs/circles/transforms       → sphericalGeometry.md
  waveforms/             # Waveform1D + aggregates                     → waveformCore.md
    dsp/                 # DSP mixin per family                        → waveformDsp.md
    support.py           # DSP descriptor dataclasses/enums            → waveformDsp.md
  functional/            # polynomials + analytic root solvers         → polynomials.md
  otg/                   # online trajectory generation (Ruckig port)  → otg.md
```

`src/math_plot_helpers/` holds the plotting module(s).

## Shared conventions (inherited by every sibling spec)

- **Naming:** pythonic `snake_case` methods/functions; `PascalCase` classes.
  Swift's camelCase API maps mechanically (`durationInSeconds` →
  `duration_seconds`). The Swift name is never kept for its own sake.
- **Storage:** numpy-backed (`float64` default). Scalar-generic Swift
  duplication (Float/Double/Int specializations) collapses to one
  implementation; dtype is preserved where the input dtype is meaningful
  (integer waveforms).
- **Public surface:** each package and subpackage `__init__.py` re-exports its
  public API with `__all__`; consumers import from the subpackage
  (`from math_tools.spatial import Position`), never deep module paths. Every
  package ships `py.typed`. Additionally the **root** `math_tools/__init__.py`
  curates a flat working set so `import math_tools as mt` is coherent:
  `Position`, `Quaternion`, `SpatialPose`, `PrecisionTimeInterval`,
  `PrecisionTimestamp`, `Waveform1D`, `WaveformPosition`,
  `WaveformQuaternion`, `WaveformSpatialPose`, `UnivariatePolynomial`,
  `Otg`, `InputParameter`, `OutputParameter`, `Trajectory`, `Result`, and
  the `errors` exception types (pinned by an `__all__` test; grows only via
  a spec update).
- **API idioms (repo-wide):** `normalized()` is a method returning a copy,
  `normalize()` mutates; approximate comparison is
  `isclose(..., rtol, atol)` (numpy vocabulary — never a bare `tolerance`
  argument); array-like classes implement `__array__` so `np.asarray(x)`
  works; mutable numpy-backed classes set `__hash__ = None` explicitly
  (only the immutable precision-time types are hashable).
- **Typing:** mypy `strict` clean (the gate). Explicit signatures everywhere.
- **Immutability of results:** analysis/DSP/transform methods return new
  objects; only the explicitly-named mutation APIs (`append`, `insert`, …)
  mutate in place.
- **Error semantics:** see below.
- **Testing:** `unittest.TestCase` style run under pytest (repo convention,
  `tests/test*.py`); tests mirror the package layout
  (`tests/spatial/test_position.py`, …).
- **Docstrings:** every public symbol; module docstrings state conventions
  (e.g. the ISO spherical convention doc in the existing `spherical/` module
  stays canonical).

## Error semantics

`math_tools/errors.py` defines:

```python
class MathToolsError(Exception): ...
class WaveformCompatibilityError(MathToolsError): ...   # dt/shape mismatch on waveform ops
class TimestampComparisonError(MathToolsError): ...     # timescale/frame mismatch in validated compare
class PolynomialSolveError(MathToolsError): ...         # unsolvable/ill-posed root requests
```

- Programmer errors (wrong type, wrong shape, invalid argument) raise stdlib
  `TypeError`/`ValueError`.
- Domain failures raise the `MathToolsError` subtype above.
- **Exception:** the OTG control loop reports via its `Result` code enum and
  does not raise per cycle (real-time contract, see [otg.md](otg.md)).

## Explicit non-goals (decided divergences from the Swift source)

1. **No `Complex` type.** Python's native `complex` / numpy complex dtypes
   cover Swift's `Complex<T>` + its arithmetic/analysis extensions entirely.
2. **No cached `_isNormalized` flag.** Swift caches normalization and
   invalidates on mutation; here `is_unit` is recomputed on access
   (correctness > performance; optimize later with evidence).
3. **No saturating/wrapping integer arithmetic** in precision time. Swift's
   `UInt64` clamping (`&+`, `&-`) is a representation constraint, not domain
   behavior; Python ints are unbounded and exact.
4. **Swift stubs are not ported:** `Waveform1D+Custom`, the empty
   `SpatialWaveforms/Operators/*+Arithmetic` files, and the empty
   `PrecisionTime/Extensions` files define no behavior.
5. **No serialization file I/O helpers.** Wire interop is
   `to_dict`/`from_dict`; foundation's `DataModelHelper` owns file I/O
   patterns.

## Sibling spec index

| Spec | Contract |
|---|---|
| [templateConformance.md](templateConformance.md) | packaging, dependency resolvability, CI parity, governance artifacts |
| [precisionTimeMath.md](precisionTimeMath.md) | `PrecisionTimeInterval`, `PrecisionTimestamp` |
| [spatialMath.md](spatialMath.md) | `Position`, `Quaternion`, `SpatialPose` |
| [sphericalGeometry.md](sphericalGeometry.md) | unit-sphere arcs/small circles, transforms, `orient` convention |
| [waveformCore.md](waveformCore.md) | `Waveform1D` + aggregate waveform containers |
| [waveformDsp.md](waveformDsp.md) | DSP families, scipy mapping, support types |
| [polynomials.md](polynomials.md) | polynomial type + analytic root solvers |
| [otg.md](otg.md) | online trajectory generation (Ruckig port) |
