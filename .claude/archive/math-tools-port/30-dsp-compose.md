---
chunk: 30-dsp-compose
track: D
status: complete
depends_on: [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
spec: ../specs/waveformDsp.md §Organization (composition phasing), §Compliance 2, 4
last_updated: 2026-07-17
semver: 0.0.2
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

- [x] MRO test passes; every DSP family callable directly on `Waveform1D`
- [x] `grep -rn "class _W(" tests/waveforms/dsp/` → no hits
- [x] `make uv-fullCheck` passes

## Out of scope

Any mixin behavior change — if a compose-time conflict (name collision
between mixins) appears, STOP and report; resolution is a spec decision.

## Resolution notes

- Base-list edit landed exactly as the spec's Organization block (12
  mixins, `Waveform1dABC` last); `waveform1d.py` imports each mixin module
  directly (not via `dsp/__init__.py`), keeping the compose step's own
  import graph minimal.
- `dsp/__init__.py` now imports and re-exports all twelve mixins (`__all__`)
  per this chunk's file list — this surfaced a genuine circular import (not
  the one chunks 19/26/27 had already preempted): populating
  `dsp/__init__.py` means importing *any* `dsp/_*` submodule now also runs
  `dsp/__init__.py` first, which imports every mixin, several of which
  import back into `waveforms/support.py`; `support.py` itself imports
  `dsp._protocol.WaveformProtocol` at module scope (chunk 27, for the
  `WaveformWithEvents.waveform` field annotation only). That produced
  `import support.py` → `dsp/__init__.py` → `dsp/_correlation.py` →
  `support.py` (still mid-import) → `ImportError: cannot import name
  'WaveformTimeLag' from partially initialized module`.
  - **Fix:** moved `support.py`'s `WaveformProtocol` import under `if
    TYPE_CHECKING:`. Safe because `support.py` already has `from
    __future__ import annotations`, so the field annotation that uses
    `WaveformProtocol` is never evaluated at runtime — only mypy needs the
    import, and mypy resolves `TYPE_CHECKING` imports without executing
    them. This is the *opposite* direction from the import `dsp/_protocol.py`
    forbids even under `TYPE_CHECKING` (a mixin importing `Waveform1D`); a
    support module importing the mixins' shared protocol under
    `TYPE_CHECKING` isn't that case and doesn't reopen it.
- `tests/test_package_layering.py::test_dsp_mixins_do_not_import_sibling_mixins`
  globs `dsp/_*.py`, which also matches `dsp/__init__.py` (`__` starts with
  `_`) — before this chunk that was harmless (the file was import-free), but
  once it re-exports every mixin the test flagged it as a "sibling-mixin
  import" violation. `dsp/__init__.py` is not a mixin module — from this
  chunk onward it is *expected* to import every mixin — so the test now
  explicitly excludes `__init__.py` from that specific check. The mixin
  modules themselves are still fully covered (unchanged).
- No mixin name collisions found composing all twelve; no mixin behavior
  was touched.
- `waveformDsp.md` bumped to semver 0.0.7 documenting both resolutions;
  `tests/waveforms/dsp/test_*.py` (12 files) mechanically dropped their
  local `class _W(XMixin, Waveform1D): pass` subclasses in favor of plain
  `Waveform1D` (assertions unchanged), matching the now-composed class.
