---
chunk: 11-waveform1d-core
track: C
status: complete
depends_on: [05]
spec: ../specs/waveformCore.md §ABC accessor, §Instantiability, §Time axis, §Waveform1D (constructors/statistics/indexing/mutation), §Compliance 1, 3, 5–7, 11
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 11 — `Waveform1D` core container

**Deliverable:** the scalar waveform container (no operators, no generators,
no DSP — those are chunks 12, 13, 18–30).

## Files

- Create: `src/math_tools/waveforms/__init__.py` (export `Waveform1D`),
  `src/math_tools/waveforms/py.typed`,
  `src/math_tools/waveforms/waveform1d.py`
- Create: `tests/waveforms/__init__.py`,
  `tests/waveforms/test_waveform1d_core.py`

## Design constraints

1. `class Waveform1D(Waveform1dABC)` — base list is EXACTLY this (DSP mixins
   are composed by chunk 30, not here). Implement the ABC accessor
   `waveform -> Sequence[float]`; numpy bulk on `values: npt.NDArray`
   (copy-in on construction; dtype preserved, float64 default).
2. Time axis per spec: `dt: PrecisionTimeInterval` (strictly positive),
   `t0: PrecisionTimestamp = EPOCH`; `dt_seconds: float = 1.0` is the
   default path so `Waveform1D(values)` is legal; `t0_seconds` convenience;
   `TypeError` when both a precision and a seconds form are given.
   Computed: `duration` (`dt * (n-1)`, ZERO when n ≤ 1),
   `duration_seconds`, `sampling_frequency_hz`, `nyquist_frequency_hz`,
   `sample_count`/`__len__`, `time_axis()`.
3. Statistics properties (None-on-empty per spec), indexing/slicing
   (`w[i]`, `w[a:b]` with attosecond-exact t0 shift, step≠1 `ValueError`),
   `subset_time`, `value_at_index`/`value_at_time` (linear interp,
   `ValueError` out of range), mutation API (`append`, `append_values`,
   `prepend`, `prepend_values` with t0 back-shift, `insert`, `replace`,
   `replace_range`, `pop(i=-1)` → `IndexError` on empty, `clear()`),
   `==` (samples exact + dt + t0), `__iter__`, `__array__`, `repr`,
   `to_dict`/`from_dict`.
4. Pin the population-variance choice: implement `variance` as ddof=0 and
   pin with a literal expected value (spec compliance 5).

## TDD steps

1. Failing tests for spec compliance 1 (`ScalarWaveformType` round-trip),
   3 (slice t0 attosecond-exact), 5 (stats literals), 6 (value_at_time
   midpoint), 7 (mutation semantics), 11 (`Waveform1D(values)` constructs;
   `__abstractmethods__` empty; `np.asarray`; iteration).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Named tests for compliance 1, 3, 5, 6, 7, 11 pass
- [x] `w[2:5].t0 - w.t0 == w.dt * 2` exactly (PrecisionTime equality, not float)
- [x] Integer-dtype input preserves dtype; float input is float64
- [x] `make uv-fullCheck` passes

## Out of scope

Arithmetic/comparison operators (12), generators (13), DSP (18–30),
aggregate containers (15–17).

## Resolution notes

- `class Waveform1D(Waveform1dABC)` with no DSP mixin bases; pinned by a
  test asserting `Waveform1D.__abstractmethods__ == frozenset()` and that a
  bare `Waveform1D(values)` construction succeeds.
- Time axis is attosecond-exact throughout: `dt`/`t0` are the Tier-3
  `PrecisionTimeInterval`/`PrecisionTimestamp` types, not floats. `dt`
  strictly positive (`ValueError`), `t0` defaults to
  `PrecisionTimestamp.EPOCH`, `dt_seconds`/`t0_seconds` are the seconds
  convenience forms, each pair mutually exclusive (`TypeError`). Verified
  live: `w[2:5].t0 - w.t0 == w.dt * 2` holds via exact
  `PrecisionTimeInterval` equality (`PrecisionTimeInterval(seconds=2,
  attoseconds=0, ...)` on both sides), not float comparison.
- Dtype policy, verified live and by dedicated tests: an ndarray with an
  explicit integer dtype (e.g. `np.array([1,2,3], dtype=np.int32)`)
  preserves that exact dtype; a Python list of ints (e.g. `[1, 2, 3]`) is
  also treated as integer-dtype input (via `np.asarray`'s natural int64
  inference) and preserved as integer, not upcast; any non-integer input
  (Python floats, or an explicit float ndarray) becomes float64. This is a
  literal reading of "integer-dtype input preserves dtype" — the dtype the
  input resolves to via `np.asarray`, not merely "explicitly-typed numpy
  arrays" — and is pinned by
  `test_python_list_of_ints_preserves_integer_dtype`.
  `counter()`'s output is integer when `start_value`/`increment` are
  integers, matching this policy.
  `constant()` similarly does not force a dtype, so `Waveform1D.constant(n,
  value=5)` yields an integer-dtype waveform (int follows the same rule).
- All 22 generator classmethods are sample-count (`n`) based, matching this
  repo's other constructors — a deliberate, documented departure from the
  Swift duration/samplingRate-based generator API (module docstring + chunk
  spec explicitly call this a "fresh numpy-idiomatic implementation," not a
  faithful port).
- `variance`/`standard_deviation` pinned to population statistics
  (`ddof=0`, i.e. plain `np.var`/`np.std`); spec compliance 5 requires a
  literal expected value in the test, not just agreement with a numpy
  reference — verified live: `Waveform1D([1,2,3,4]).variance == 1.25`
  exactly.
- `value_at_time`/`value_at_index` linear interpolation verified live at an
  exact midpoint (`value_at_time(0.5)` between samples `0.0` and `10.0`
  spaced 1s apart returns `5.0`).
- `subset_time` is half-open (`start <= t < end`) via
  `np.searchsorted(..., side="left")` on both bounds, raising `ValueError`
  on an empty or invalid (`end <= start`) range.
- Wire round-trip verified live end-to-end:
  `Waveform1D.to_dict()`/`.from_dict()` round-trips to an equal instance,
  and `foundationTypes.mathTypes.MathTypes.ScalarWaveformType.from_dict()`
  accepts the same dict without error (spec compliance 1).
- One spec/reality collision flagged by the implementing agent, not a bug:
  waveformCore.md's Operators section says `__array__` support makes
  `np.mean(w)` "work," but numpy's `np.mean()` tries `w.mean` as a callable
  before falling back to `__array__`, and the spec also mandates `mean` as
  a *property* — so `np.mean(w)` directly raises `TypeError` for this and
  every other stats-named property (`sum`, etc). `np.asarray(w)` (the form
  chunk 11's own compliance item 11 actually pins) is unaffected and is the
  correct interop path. No acceptance criterion here requires bare
  `np.mean(w)` to work, so no code changed; worth a one-line spec
  clarification if the DSP chunks (12+) run into the same collision.
- No spec change was needed; implementation matches waveformCore.md's core
  (non-aggregate, non-DSP) sections as written.
- Verified: 91 new tests in `tests/waveforms/test_waveform1d_core.py`, full
  suite 555 tests green, ruff clean, mypy strict clean
  (`make uv-fullCheck`).
