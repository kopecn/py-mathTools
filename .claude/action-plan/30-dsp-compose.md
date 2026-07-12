---
chunk: 30-dsp-compose
track: D
status: pending
depends_on: [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
spec: ../specs/waveformDsp.md §Organization (composition phasing), §Compliance 2, 4
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 30 — Compose the DSP mixins into `Waveform1D`

**Deliverable:** the one-time base-list edit plus the MRO/layering pins.
Runs ONLY after chunks 18–29 are all done.

## Files

- Edit: `src/math_tools/waveforms/waveform1d.py` (base list + imports only)
- Edit: `src/math_tools/waveforms/dsp/__init__.py` (export the 12 mixins)
- Create: `tests/waveforms/dsp/test_compose.py`
- Edit: `tests/waveforms/dsp/test_*.py` — remove the per-chunk local test
  subclasses (`class _W(XMixin, Waveform1D)`) in favor of plain `Waveform1D`
  (mechanical; assertions unchanged)

## Design constraints

1. Base list exactly as the spec's Organization block (12 mixins then
   `Waveform1dABC`); no other change to the class body.
2. `test_compose.py` pins: each of the 12 mixins appears in
   `Waveform1D.__mro__` exactly once; `Waveform1D.__abstractmethods__ ==
   frozenset()`; `Waveform1D([1.0, 2.0])` constructs; one smoke call per
   family on a short sine (e.g. `.fft()`, `.detect_peaks()`, …) succeeds.
3. Layering pin (spec compliance 2): each `dsp/_*.py` module's imports are
   scipy/numpy/stdlib/`_protocol`/`_common` only — extend
   `tests/test_package_layering.py` with this rule if chunk 02's version
   doesn't already cover `dsp/`.

## TDD steps

1. Write `test_compose.py` first (fails: mixins not composed).
2. Make the base-list edit; simplify the per-chunk test subclasses.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] MRO test passes; every DSP family callable directly on `Waveform1D`
- [ ] `grep -rn "class _W(" tests/waveforms/dsp/` → no hits
- [ ] `make uv-fullCheck` passes

## Out of scope

Any mixin behavior change — if a compose-time conflict (name collision
between mixins) appears, STOP and report; resolution is a spec decision.
