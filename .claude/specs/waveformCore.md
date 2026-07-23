---
version: 1.0
type: specification
name: waveformCore
purpose: Behavioral contract for Waveform1D and the aggregate spatial waveform containers
spec: WaveformCore
scope: project
status: accepted
applies_to: src/math_tools/waveforms/, tests/waveforms/
last_updated: 2026-07-23
semver: 0.0.4
author: Nicholas Bergantz
---

# Waveform Core Types

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). Ports Swift
> `Waveform1D` / `WaveformPosition` / `WaveformQuaternion` /
> `WaveformSpatialPose` container behavior (storage, stats, operators,
> slicing, mutation, component decomposition). The DSP/analysis surface is a
> separate contract: [waveformDsp.md](waveformDsp.md).

## Modules and base contracts

| Class | Module | Subclasses | Sample storage |
|---|---|---|---|
| `Waveform1D` | `waveforms/waveform1d.py` | `Waveform1dABC` | `np.ndarray` 1-D (dtype preserved; float64 default) |
| `WaveformPosition` | `waveforms/waveform_position.py` | `PositionWaveformABC` | `np.ndarray` `(n, 3)` float64 |
| `WaveformQuaternion` | `waveforms/waveform_quaternion.py` | `QuaternionWaveformABC` | `np.ndarray` `(n, 4)` float64, order `(w, x, y, z)` |
| `WaveformSpatialPose` | `waveforms/waveform_spatial_pose.py` | `WaveformSpatialABC` | parallel `(n,3)` + `(n,4)` arrays |

Element access materializes `Position` / `Quaternion` / `SpatialPose`
([spatialMath.md](spatialMath.md)) on demand; bulk storage stays numpy
(vectorized ops never round-trip through per-element objects).

## ABC accessor vs numpy storage (load-bearing)

The ABCs' abstract accessors have fixed names and types that MUST be
implemented or the classes stay abstract:

| Class | ABC accessor implemented | Returns | numpy bulk accessor |
|---|---|---|---|
| `Waveform1D` | `waveform` | `Sequence[float]` (the samples) | `values: npt.NDArray` |
| `WaveformPosition` | `positions` | `Sequence[PositionABC]` (materialized `Position` list, built on access) | `positions_array: npt.NDArray (n,3)` |
| `WaveformQuaternion` | `quaternions` | `Sequence[QuaternionABC]` | `quaternions_array: npt.NDArray (n,4)` |
| `WaveformSpatialPose` | `positions` + `quaternions` | both of the above | `positions_array` + `quaternions_array` |

The inherited ABC `to_dict` therefore emits the correct wire keys
(`"waveform"`, `"positions"`, `"quaternions"`) for free. Implementation code
and the DSP mixins use the numpy accessors; the ABC accessors exist for the
contract and serialization.

## Instantiability / DSP phasing (load-bearing)

The core chunk ships `class Waveform1D(Waveform1dABC)` with **no DSP mixin
bases**. The mixin base list is added in a single later "compose" chunk after
every mixin exists ([waveformDsp.md](waveformDsp.md)); until then the class
is complete and the gate stays green. A test pins that `Waveform1D` is
concrete (`Waveform1D.__abstractmethods__ == frozenset()` and a bare
construction succeeds).

## Time axis (shared by all four)

- `dt: PrecisionTimeInterval` — required, `ValueError` unless strictly
  positive ([precisionTimeMath.md](precisionTimeMath.md)).
- `t0: PrecisionTimestamp` — **defaults to `PrecisionTimestamp.EPOCH`**.
  Divergence from Swift's optional `t0`, forced by the ABC's non-optional
  `t0` contract; a waveform with unspecified start simply starts at epoch.
- Shared computed properties: `duration: PrecisionTimeInterval`
  (`dt * (n-1)`, ZERO when `n <= 1`), `duration_seconds: float`,
  `sampling_frequency_hz: float`, `nyquist_frequency_hz: float`,
  `sample_count: int` (also `__len__`), `time_axis() -> npt.NDArray`
  (float64 seconds relative to `t0`).
- Convenience constructor parameters on every class:
  `dt_seconds: float = 1.0` (**the default when `dt` is omitted** — so
  `Waveform1D(values)` and `Waveform1D.sine(n=1000)` are legal and mean
  one sample per second; `TypeError` if both `dt` and `dt_seconds` given)
  and `t0_seconds: float` (offset from epoch; mutually exclusive with `t0`).

## `Waveform1D`

**Constructors**: `Waveform1D(values, dt=..., t0=...)` (`values`: any 1-D
array-like; copied), plus signal generator classmethods (all take
`n: int, dt/dt_seconds, t0` and shape parameters; seeded determinism where
random): `sine`, `cosine`, `square`, `triangle`, `sawtooth`, `chirp`,
`exponential_decay`, `exponential_growth`, `polynomial(coefficients)`,
`linear_ramp`, `logarithm`, `logarithm10`, `square_root`, `heaviside`,
`relu`, `sigmoid`, `white_noise(seed)`, `constant`, `impulse`,
`damped_sinusoid`, `counter`, `digital_square`. Each maps to a one-line
numpy expression; the Swift parameterization is the reference for argument
names/meaning.

**Generators — span convention (load-bearing).** For an `n`-sample
waveform starting at `t0`, the sample span is `[0, (n-1)*dt]`
(endpoint-inclusive) — consistent with `duration` above, NOT `n*dt`. Any
generator parameter that scales by or defaults to "the waveform's total
duration" or "the midpoint of the waveform" MUST derive it from `(n-1)*dt`:
`chirp`'s sweep rate (so the **final** sample's instantaneous frequency is
exactly `end_frequency`), `heaviside`'s default `step_time`, and
`sigmoid`'s default `center` (both default to the span midpoint,
`(n-1)*dt/2`). `n <= 1` is a zero-length span (`0`), not a
division-by-zero — every affected generator must guard it explicitly.
Generators whose math does not depend on total duration (e.g. `sine`'s
`frequency`, `exponential_decay`'s `time_constant`) are unaffected and keep
using the raw per-sample time axis `np.arange(n) * dt`.

**Statistics** (properties; `None` on empty where Swift is optional):
`minimum`, `maximum`, `peak_to_peak`, `mean`, `rms`, `standard_deviation`,
`variance`, `sum`, `absolute_sum`.

**Operators** (elementwise; operands `Waveform1D | scalar`; both scalar
orders; in-place variants mutate):
- `+ - * /` (and `//`, `%` — meaningful for integer dtype); waveform⊕waveform
  requires equal `dt` and length else `WaveformCompatibilityError`.
- Bitwise `& | ^ << >> ~` — integer dtype only (`TypeError` otherwise,
  numpy's natural behavior surfaced with a clear message).
- Unary `-`, `+`, `abs()`.
- Comparison producers: `elements_equal(other) -> npt.NDArray[np.bool_]`,
  `elements_less_than`, `elements_greater_than`,
  `isclose_elementwise(other, rtol=1e-9, atol=0.0)` (numpy `rtol`/`atol`
  vocabulary, consistent with the spatial types — not Swift's single
  `tolerance`).
- `isclose(other, rtol=1e-9, atol=0.0) -> bool` — whole-waveform: same `dt`,
  same `t0`, all samples close.
- `==` — full equality: samples (exact), `dt`, `t0`.
- `__iter__` (yields scalars), `__array__(dtype=None)` (→ the samples), so
  `for x in w`, `np.asarray(w)`, `np.mean(w)`, `plt.plot(w)` all work.

**Indexing / slicing / sampling**
- `w[i] -> scalar`; `w[a:b] -> Waveform1D` (t0 advanced by `a * dt`;
  step != 1 is `ValueError` — resampling is the explicit API). Index
  slicing is the only index-range API (Swift's `subset(start:end:)` is
  redundant with it and not ported).
- `subset_time(start_time, end_time)` (PrecisionTimestamp or float seconds
  relative to t0) — half-open, `ValueError` on empty/invalid range.
- `value_at_index(i: float) -> float`, `value_at_time(t) -> float` — linear
  interpolation; `ValueError` outside `[0, n-1]` / the time span.

**Mutation API** (the only in-place surface besides in-place operators) —
Python list vocabulary, not Swift's:
`append(x)`, `append_values(iterable)`, `prepend(x)`,
`prepend_values(iterable)` (t0 shifts back by `k * dt`), `insert(i, x)`,
`replace(i, x)`, `replace_range(slice, values)`,
`pop(i=-1) -> float` (`IndexError` on empty/out-of-range — stdlib
semantics, not Swift's Optional), `clear()`.

## Aggregate containers

All three share (with `Element` = `Position` / `Quaternion` / `SpatialPose`):

- **Constructors**: from element arrays/lists; `from_components(...)` from
  per-component `Waveform1D`s (`None`-safe: `ValueError` unless counts and
  `dt` all match — Swift returned nil); `WaveformSpatialPose` additionally
  `from_poses(list[SpatialPose], dt/dt_seconds, t0)` and
  `from_waveforms(position_waveform, quaternion_waveform)`.
- **Element access**: `w[i] -> Element`, `w[a:b] -> Self`, `get(i) ->
  Element | None` (Swift's `subscript(safe:)`), `__iter__` yielding
  materialized `Element`s.
- **Component decomposition**: `component_waveforms` returning a `NamedTuple`
  of `Waveform1D`s — `(x, y, z)` for positions, **`(w, x, y, z)`** for
  quaternions (w-first, matching storage, `from_components`, and the
  incumbent `Quaternion.to_components()`; the Swift x-first tuple order is
  NOT kept), nested position+quaternion tuple for poses;
  `WaveformSpatialPose` also `position_waveform` and `quaternion_waveform`.
- **Normalization**: predicate stem is `unit` everywhere —
  `WaveformPosition.are_all_unit`, `WaveformQuaternion.are_all_unit`,
  `WaveformSpatialPose.are_all_positions_unit` /
  `are_all_quaternions_unit`; `normalize()` in place, `normalized()` copy.
  Zero-magnitude elements raise `ValueError` (parity with
  `Position.normalize`).
- **Mutation**: same verbs as `Waveform1D` with `Element` payloads, plus
  `extend(other: Self)` and `concatenate(other: Self) -> Self` — both raise
  `WaveformCompatibilityError` on `dt` mismatch (Swift `throws` parity).
- `WaveformSpatialPose.is_valid` (parallel arrays equal length) and
  `sample_count == min(len(positions), len(quaternions))` — both subtle Swift
  behaviors, kept.
- `==`, `repr`, `to_dict`/`from_dict` per the ABC wire shapes.
- **Shared API idioms** (mathToolsArchitecture.md §API idioms, chunk 50): all
  three aggregates additionally implement `__array__` and
  `isclose(other, rtol, atol)`, mirroring the umbrella idiom already required
  of `Waveform1D`, `Position`, and `Quaternion`.
  - `__array__(dtype=None, copy=None)`: `WaveformPosition` returns the
    `(sample_count, 3)` position array; `WaveformQuaternion` returns the
    `(sample_count, 4)` `(w, x, y, z)` array; `WaveformSpatialPose` returns a
    **`(sample_count, 7)`** array, columns `[x, y, z, w, i, j, k]` (position
    `xyz` then quaternion `wxyz`, both truncated to `sample_count` — the
    "valid prefix" per §Compliance 9, not either raw array's own length).
    All three raise `ValueError` when `copy=False` is requested, since a copy
    is always required (the returned array must never alias the mutable
    backing store) — the same contract `Waveform1D.__array__` follows.
  - `isclose(other, rtol=1e-9, atol=...)`: `False` on differing
    `sample_count` or differing `dt`/`t0`; otherwise elementwise
    `np.isclose` over the backing array(s) (`atol` default mirrors the
    wrapped element type: `0.0` for `WaveformPosition`/the position half of
    `WaveformSpatialPose`, matching `Position.isclose`; `1e-11` for
    `WaveformQuaternion`, matching `Quaternion.isclose`).
    `WaveformQuaternion` and the quaternion half of `WaveformSpatialPose` are
    double-cover aware **per sample**: each row independently may match
    either `other`'s row or its negation (`q` and `-q` are the same
    rotation).
  - `WaveformSpatialPose.from_components(position_x, position_y, position_z,
    quaternion_w, quaternion_x, quaternion_y, quaternion_z)`: the third
    aggregate's `from_components`, dropped in chunk 17 and restored in chunk
    50 — seven per-component `Waveform1D`s (three position, four quaternion),
    following `WaveformPosition.from_components`/
    `WaveformQuaternion.from_components`'s shape; `ValueError` unless all
    seven share length and `dt`.

## Compliance requirements (test-checkable)

1. All four classes: `isinstance` of their ABC; `to_dict` output loads via
   the matching `foundationTypes` generated Type and round-trips equal —
   exact target names on the pinned branch: `Waveform1D` ↔
   `ScalarWaveformType`, `WaveformPosition` ↔ `PositionWaveformType`,
   `WaveformQuaternion` ↔ `QuaternionWaveformType`, `WaveformSpatialPose` ↔
   `SpatialTransformWaveformType`.
2. `dt` mismatch on any binary/extend/concat op raises
   `WaveformCompatibilityError`; equal-`dt` path is exact.
3. Slicing adjusts `t0` by exactly `start * dt` (attosecond-exact via
   PrecisionTime, not float).
4. Generators pinned analytically: `sine` matches `np.sin` on the time axis;
   `white_noise(seed=k)` reproducible; `impulse` sums to 1 sample of
   amplitude.
5. Stats match numpy references on a fixed vector (`rms` =
   `sqrt(mean(x**2))`, `variance` population variance — pin Swift's ddof
   choice with a literal expected value).
6. `value_at_time` midpoint between two samples returns their average.
7. Mutation verbs match stdlib list semantics (pin `prepend` t0 shift;
   `pop()` on empty raises `IndexError`; `clear()` empties).
8. Aggregate `component_waveforms` → `from_components` round-trips exactly
   (quaternion tuple order `(w, x, y, z)` pinned).
9. `WaveformSpatialPose` with unequal arrays: `is_valid` False,
   `sample_count` = min — both pinned.
10. Bulk ops never construct per-element objects (pin with a 1e6-sample
    smoke test completing under a generous bound, guarding the vectorized
    design).
11. `Waveform1D(values)` with no time arguments constructs (dt = 1 s);
    `Waveform1D.__abstractmethods__` is empty; `np.asarray(w)` equals the
    samples; `for x in w` iterates them.
12. mypy strict clean.
