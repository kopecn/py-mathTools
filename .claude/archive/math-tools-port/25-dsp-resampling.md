---
chunk: 25-dsp-resampling
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (ResamplingMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
author: Nicholas Bergantz
---

# 25 — `ResamplingMixin`

**Deliverable:** `dsp/_resampling.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Resampling.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_resampling.py`,
`tests/waveforms/dsp/test_resampling.py`. Test-subclass pattern per
chunk 18.

## Design constraints

- Methods per spec table: `decimated(factor)` (`scipy.signal.decimate`),
  `interpolated(factor, method: WaveformInterpolationMethod = LINEAR)`,
  `resampled(target_frequency_hz)` (`scipy.signal.resample` /
  `resample_poly`), `resampled_to_match(other)`,
  `polyphase_resampled(up, down)` (`resample_poly`).
- **dt bookkeeping is the tricky bit:** integer factor paths compute the new
  `dt` exactly in PrecisionTime (`dt * factor` / `dt / factor` rounding to
  nearest attosecond); `resampled(hz)` derives dt from the achieved rate.
  New `t0` is unchanged.
- `factor < 1` or non-int factor → `ValueError`.

## TDD steps

1. Failing tests (spec compliance 1): `interpolated(2).decimated(2)`
   round-trips a smooth signal interior (rtol 1e-3); `decimated(4).dt ==
   dt * 4` exactly (PrecisionTime equality); `resampled_to_match` yields
   matching `dt` and length within ±1; polyphase 3:2 length check.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Round-trip and exact-dt tests pass
- [x] `make uv-fullCheck` passes

## Out of scope

Time alignment (26); `value_at_time` (already in core).

## Resolution notes

- **Forced contract change: `WaveformProtocol` gained a second factory,
  `_with_axis(values, dt) -> WaveformProtocol`.** Every mixin through chunk
  24 builds its results via `_with_values(values)`, which carries `self`'s
  `dt`/`t0` forward unchanged — sufficient because none of those families
  ever change the sample spacing. `ResamplingMixin` is the first that does
  (`decimated`/`interpolated`/`resampled`/`polyphase_resampled` all compute
  a new `dt`), and the acceptance criterion "`decimated(4).dt == dt * 4`
  exactly" is unsatisfiable through `_with_values` alone. Added `_with_axis`
  to `dsp/_protocol.py`'s `WaveformProtocol` and implemented it on
  `Waveform1D` (`waveforms/waveform1d.py`, alongside `_with_values`); `t0`
  is not a parameter (every method here leaves `t0` unchanged, per the
  design constraints). Per the 00-overview.md convention ("if implementation
  forces a contract change, update the spec in the same chunk and bump its
  semver"), `waveformDsp.md` §Organization documents the addition and its
  semver was bumped 0.0.3 → 0.0.4. This is the only file touched outside
  this chunk's own `Files` list.
- **`decimated` uses `scipy.signal.decimate(..., ftype="fir")`, not the
  default `ftype="iir"`.** The default Chebyshev-I IIR anti-alias filter's
  ~0.05 dB passband ripple, doubled by zero-phase `sosfiltfilt`, produced
  ~1.1% amplitude error even deep in the passband on a 5 Hz sine sampled at
  1 kHz — enough to blow the `interpolated(2).decimated(2)` round-trip's
  `rtol=1e-3` acceptance bound. The FIR variant (linear-phase, near-flat
  passband) round-trips to ~1e-6 on the same signal and, as a side benefit,
  tolerates much shorter inputs (its padding requirement scales with taps
  rather than a fixed ~27-sample IIR minimum). `decimated(factor)`'s public
  signature is unchanged — this is an internal default choice, not an
  exposed parameter — so it stays within the spec's `decimated(factor)`
  surface.
- **`interpolated`'s four kernels:** `LINEAR`/`NEAREST` use `np.interp`-style
  sample-index interpolation directly; `CUBIC` uses
  `scipy.interpolate.CubicSpline`; `FOURIER` uses `scipy.signal.resample`.
  All four produce `(n - 1) * factor + 1` samples (endpoints preserved),
  matching the Swift reference's insert-between-samples scheme rather than
  `scipy.signal.resample`'s periodic/`n * factor` convention.
  `resampled`/`resampled_to_match`/`polyphase_resampled` are unaffected
  (they always use FFT/polyphase resampling per the spec's Backing column).
- **`resampled(target_frequency_hz)`** computes the achieved sample count as
  `round(sample_count * target_frequency_hz / sampling_frequency_hz)` and
  derives `dt` from that achieved count (`dt * sample_count /
  achieved_count`) rather than `1 / target_frequency_hz` — matches the
  design constraint ("`resampled(hz)` derives dt from the achieved rate")
  and the `scipy.signal.resample` input/output-length/sample-rate
  relationship. `resampled_to_match(other)` is a thin wrapper calling the
  same helper with `other.sampling_frequency_hz`.
- All TDD-step scenarios pass as written: `interpolated(2).decimated(2)`
  round-trips a 2000-sample, 5 Hz sine's interior to `rtol=1e-3` (both
  `LINEAR` and `CUBIC` kernels tested); `decimated(4).dt == dt * 4` exactly
  (`PrecisionTimeInterval` equality); `resampled_to_match` yields matching
  `dt` (6 decimal places) and length within ±1 of `other`'s; polyphase 3:2
  length matches `ceil(n * 3 / 2)` against `scipy.signal.resample_poly`'s
  actual output.
- 30 new tests in `tests/waveforms/dsp/test_resampling.py`; full gate
  (`make uv-fullCheck`) green at 1029 passed, ruff clean, mypy strict clean.
