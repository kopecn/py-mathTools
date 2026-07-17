---
chunk: 24-dsp-phase
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (PhaseMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.1
author: Nicholas Bergantz
---

# 24 — `PhaseMixin`

**Deliverable:** `dsp/_phase.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+PhaseAnalysis.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_phase.py`,
`tests/waveforms/dsp/test_phase.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `instantaneous_phase(unwrapped=True)` (Hilbert
  angle), `unwrap_phase(threshold=π)` (`np.unwrap` on already-phase data),
  `instantaneous_frequency() -> WaveformInstantaneousFrequency` (phase
  gradient / 2π), `phase_difference(other)`, `phase_coherence(other,
  window=...)`, `phase_synchronization_index(other) -> float` (PLV, in
  [0, 1]), `group_delay(...)`. dt mismatch on binary methods →
  `WaveformCompatibilityError`.

## TDD steps

1. Failing tests (spec compliance 1): unwrapped phase of a chirp is
   monotone increasing; instantaneous frequency of a pure f-Hz sine ≈ f on
   the interior (rtol 1e-2); PLV of a signal with itself == 1.0 and with an
   independent seeded-noise signal < 0.3; `phase_difference` of `sin` vs
   `cos` ≈ π/2 interior.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Chirp-monotone and PLV tests pass
- [x] `make uv-fullCheck` passes

## Out of scope

Envelope (20); spectral (21).

## Resolution notes

- Backed `instantaneous_phase`/`phase_difference`/`phase_coherence`/
  `phase_synchronization_index` with `scipy.signal.hilbert`'s analytic-signal
  angle rather than the Swift reference's hand-rolled "quadrature filter"
  finite-difference approximation — allowed explicitly by the spec's opening
  note ("parity is judged per capability... scipy semantics win").
- `phase_difference` wraps its result into `(-pi, pi]` via
  `np.angle(np.exp(1j * diff))` rather than a raw subtraction, avoiding a
  spurious near-±π discontinuity; verified against the sin-vs-cos ≈π/2
  compliance test.
- Binary methods (`phase_difference`, `phase_coherence`,
  `phase_synchronization_index`) raise `WaveformCompatibilityError` on
  **both** dt mismatch (per the chunk's explicit design constraint) and
  sample-count mismatch — the latter isn't literally named in the chunk
  text, but `errors.py`'s `WaveformCompatibilityError` docstring scopes it to
  "dt/shape mismatch", and these are element-wise phase-difference ops that
  are undefined across differing lengths.
- `phase_coherence(other, window=...)`: the chunk's design-constraint bullet
  gives only the two named parameters, so the implementation is a minimal
  non-overlapping-window PLV (no `overlap` parameter, unlike the Swift
  reference) — window size defaults to `min(256, max(1, n // 4))`, mirroring
  the Swift default. Its result reuses `self`'s `dt`/`t0` as inherited
  metadata (not physically accurate for the new, coarser sample spacing);
  this follows the precedent already set by `CorrelationMixin.auto_correlation`
  (chunk 19), which does the same for its differently-spaced lag output —
  `WaveformProtocol._with_values` has no other way to construct a result.
- `group_delay(...)`: the chunk's method-list bullet leaves the signature as
  `group_delay(...)`, and the Swift reference itself never touches
  `self.values` (it operates purely on caller-supplied `frequencies`/`phases`
  arrays). Ported as a `@staticmethod` taking exactly those two arrays and
  returning group delay in seconds (`-d(unwrap(phases))/d(frequencies) /
  (2*pi)`, via `np.gradient` — replacing the Swift version's manual
  central-difference-plus-duplicated-boundary loop with numpy's own
  boundary handling, a capability-preserving scipy/numpy-idiomatic
  simplification). No cross-mixin dependency on `SpectralMixin`/
  `FilteringMixin` was introduced (both are out of scope for this chunk).
- No spec changes were needed: `waveformDsp.md`'s `PhaseMixin` row and
  `WaveformInstantaneousFrequency` descriptor (already in `support.py` since
  chunk 14) matched the implementation as written.
- Gate: `make uv-fullCheck` green — ruff clean, mypy strict clean (66 source
  files), 999 tests passed (28 new in `tests/waveforms/dsp/test_phase.py`).
  The pre-existing generic sibling-import layering test
  (`tests/test_package_layering.py::test_dsp_mixins_do_not_import_sibling_mixins`)
  covers `_phase.py` automatically — no test-file changes were needed there.
