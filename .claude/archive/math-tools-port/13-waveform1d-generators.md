---
chunk: 13-waveform1d-generators
track: C
status: complete
depends_on: [11]
spec: ../specs/waveformCore.md §Waveform1D Constructors (generators), §Compliance 4
last_updated: 2026-07-14
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

- [x] All 21+ generators exist with `n`/time-axis prefix signature and pass their shape test
- [x] `Waveform1D.sine(n=1000)` works with no time args (dt = 1 s)
- [x] `make uv-fullCheck` passes

## Out of scope

DSP analysis; generator variants Swift doesn't have.

## Resolution notes

- **This chunk's deliverable (the 22 generator classmethods themselves) was
  already implemented in chunk 11**, not here. The umbrella spec
  (waveformCore.md §`Waveform1D`) groups the generators under
  "Constructors" alongside the base `__init__`, and this chunk's own
  supervising delegation for chunk 11 included the full generator list in
  that scope by extension (a scope-widening judgment call made at that
  time, since chunk 11's design constraints didn't name generators
  explicitly but the spec section it cites does). Rather than
  re-implementing or duplicating shape-test coverage that already exists
  and passes in `tests/waveforms/test_waveform1d_core.py::TestGenerators`,
  this chunk's actual incremental work was: (1) a real bug fix — see below
  — and (2) the dedicated `tests/waveforms/test_waveform1d_generators.py`
  file this chunk's "Files" section calls for, scoped to the specific
  named compliance-4 checks (sine vs. `np.sin`, seeded white-noise
  reproducibility/divergence, impulse summation, counter as
  `arange`-based, chirp instantaneous-frequency endpoints via zero-crossing
  count) plus an all-22-generators existence check — not a duplicate of
  chunk 11's broader per-generator shape tests.
- **One real bug found and fixed:** both waveformCore.md's §Time axis
  section and this chunk's own acceptance criteria literally pin
  `Waveform1D.sine(n=1000)` as legal with no other arguments (`dt = 1 s`
  implied). The chunk-11 implementation gave `sine`'s `frequency` parameter
  no default, so that exact call raised `TypeError: missing 1 required
  positional argument: 'frequency'`. Fixed by giving `frequency: float =
  1.0` a default on `sine` only (the one generator the criterion literally
  names) — not applied blanket-style to the other frequency-taking
  generators (`cosine`, `square`, `triangle`, `sawtooth`, `chirp`,
  `digital_square`), since no acceptance criterion pins those, and the
  Swift reference (`Waveform1D-Generators.swift`) requires `frequency` on
  all of them with no default, matching this repo's existing choice for
  those. Verified live: `Waveform1D.sine(n=1000)` now constructs a
  1000-sample, 1 Hz waveform; regression-covered by
  `TestSineNoTimeArgs.test_sine_n_only_constructs_with_dt_one_second`.
- Verified live: `sine` matches `2*np.sin(2*pi*3.0*t)` for
  `amplitude=2.0, frequency=3.0` exactly (atol 1e-12); `white_noise(seed=7)`
  reproducible, `seed=8` differs; `impulse` sums to exactly one sample of
  the given amplitude at the given index; `counter` matches
  `start + increment * arange(n)`; `chirp` shows more zero-crossings in its
  last quarter than its first (low-to-high sweep).
- No spec change was needed; the generators as built (chunk 11 + this
  chunk's one default-value fix) match waveformCore.md's Constructors
  section and Compliance 4 as written.
- Verified: 8 new tests in `tests/waveforms/test_waveform1d_generators.py`,
  full suite 598 tests green, ruff clean, mypy strict clean
  (`make uv-fullCheck`).
