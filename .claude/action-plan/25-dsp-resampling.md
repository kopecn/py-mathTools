---
chunk: 25-dsp-resampling
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (ResamplingMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] Round-trip and exact-dt tests pass
- [ ] `make uv-fullCheck` passes

## Out of scope

Time alignment (26); `value_at_time` (already in core).
