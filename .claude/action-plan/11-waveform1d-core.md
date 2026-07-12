---
chunk: 11-waveform1d-core
track: C
status: pending
depends_on: [05]
spec: ../specs/waveformCore.md §ABC accessor, §Instantiability, §Time axis, §Waveform1D (constructors/statistics/indexing/mutation), §Compliance 1, 3, 5–7, 11
last_updated: 2026-07-11
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

- [ ] Named tests for compliance 1, 3, 5, 6, 7, 11 pass
- [ ] `w[2:5].t0 - w.t0 == w.dt * 2` exactly (PrecisionTime equality, not float)
- [ ] Integer-dtype input preserves dtype; float input is float64
- [ ] `make uv-fullCheck` passes

## Out of scope

Arithmetic/comparison operators (12), generators (13), DSP (18–30),
aggregate containers (15–17).
