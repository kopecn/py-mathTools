---
chunk: 13-waveform1d-generators
track: C
status: pending
depends_on: [11]
spec: ../specs/waveformCore.md §Waveform1D Constructors (generators), §Compliance 4
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 13 — `Waveform1D` signal generators

**Deliverable:** the 21 generator classmethods.

## Files

- Edit: `src/math_tools/waveforms/waveform1d.py` (or a
  `waveforms/_generators.py` helper module the classmethods delegate to, if
  the class file is getting long — your call, but the public surface is the
  classmethods)
- Create: `tests/waveforms/test_waveform1d_generators.py`

## Design constraints

1. Classmethods per spec: `sine`, `cosine`, `square`, `triangle`,
   `sawtooth`, `chirp`, `exponential_decay`, `exponential_growth`,
   `polynomial(coefficients)`, `linear_ramp`, `logarithm`, `logarithm10`,
   `square_root`, `heaviside`, `relu`, `sigmoid`, `white_noise(seed)`,
   `constant`, `impulse`, `damped_sinusoid`, `counter`, `digital_square`.
   Common signature prefix `(n: int, *, dt=None, dt_seconds=None, t0=None,
   t0_seconds=None, ...)` + per-shape params (frequency_hz, amplitude,
   phase, etc.).
2. Argument names/meanings follow the Swift reference
   (`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Generators.swift`); each
   body is a numpy one-liner over `time_axis()`.
3. `white_noise` uses `np.random.default_rng(seed)`; `square`/`sawtooth`/
   `triangle` may use `scipy.signal` waveforms.

## TDD steps

1. Failing tests (spec compliance 4): `sine` matches `np.sin(2π·f·t)` on the
   time axis; `white_noise(seed=k)` reproducible and differs for k+1;
   `impulse` sums to one amplitude; `counter` is `arange`; `chirp`
   instantaneous frequency endpoints (coarse check via zero-crossing counts
   in the first/last quarter).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] All 21+ generators exist with `n`/time-axis prefix signature and pass their shape test
- [ ] `Waveform1D.sine(n=1000)` works with no time args (dt = 1 s)
- [ ] `make uv-fullCheck` passes

## Out of scope

DSP analysis; generator variants Swift doesn't have.
