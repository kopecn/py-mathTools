---
chunk: 18-dsp-calc
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (CalcMixin), §Numerical conventions, §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
author: Nicholas Bergantz
---

# 18 — `CalcMixin` (integrate / derivative)

**Deliverable:** `math_tools/waveforms/dsp/_calc.py` + tests. Swift
reference: `SWIFT_MATH/Waveform1D/Extensions/Waveform1D+Calc.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_calc.py`,
`tests/waveforms/dsp/__init__.py`, `tests/waveforms/dsp/test_calc.py`.
Do NOT touch `waveform1d.py` (mixins compose in chunk 30). Tests exercise
the mixin via a local test subclass `class _W(CalcMixin, Waveform1D): pass`
— this pattern applies to every DSP chunk.

## Design constraints

- `class CalcMixin(WaveformProtocol)`; methods per spec table:
  `integrate(initial_value=0.0) -> Waveform1D` (cumulative trapezoid scaled
  by `dt` seconds, first sample = initial_value),
  `derivative() -> Waveform1D` (`np.gradient` over the time axis).
- Results built via `self._with_values(...)`; imports: scipy/numpy +
  `._protocol`/`._common` only (no sibling mixin imports — repo layering
  test extended here if not already covering `dsp/`).

## TDD steps

1. Failing tests (spec compliance 1): derivative of a linear ramp is
   constant (atol 1e-9); `integrate` of a constant is a ramp;
   `integrate().derivative()` recovers a smooth signal interior
   (rtol 1e-6).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] The three analytic tests pass
- [x] `grep "from math_tools.waveforms.dsp._" src/math_tools/waveforms/dsp/_calc.py` shows only `_protocol`/`_common`
- [x] `make uv-fullCheck` passes

## Out of scope

Any other mixin; composing into `Waveform1D`.

## Resolution notes

- **Real runtime bug found in chunk 14's design, fixed here (spec bumped
  0.0.2 → 0.0.3):** the chunk's literal design constraint `class CalcMixin
  (WaveformProtocol)` combined with its own mandated test pattern
  `class _W(CalcMixin, Waveform1D): pass` is broken at runtime. Explicitly
  subclassing a `typing.Protocol` (without also listing `Protocol` as a
  base) turns its stub property bodies (`...`, so the getter implicitly
  returns `None`) into concrete inherited implementations; C3
  linearization for `_W(CalcMixin, Waveform1D)` places `WaveformProtocol`
  (reached via `CalcMixin`) ahead of `Waveform1D` in the MRO, so
  `self.values` silently returned `None` instead of the sample array —
  caught immediately by the TDD tests (`AttributeError: 'NoneType' object
  has no attribute 'shape'`), not by inspection. Fixed by switching to
  mypy's documented "mixin classes" idiom: `CalcMixin` is now a plain class
  (`class CalcMixin:`, no runtime base) that types `self` as
  `WaveformProtocol` on each method (`def integrate(self: WaveformProtocol,
  ...) -> WaveformProtocol`). Verified this composes correctly at runtime
  (`_W(CalcMixin, Waveform1D)`'s MRO no longer contains `WaveformProtocol`,
  `self.values` resolves to `Waveform1D`'s real property) and still passes
  `mypy --strict`. `waveformDsp.md` §Organization and
  `dsp/_protocol.py`'s module docstring were both updated to document the
  corrected pattern so chunks 19–29 don't repeat it.
- **`integrate`/`derivative` return `WaveformProtocol`, not `Waveform1D`:**
  both are built via `self._with_values(...)`, whose declared return type
  is `WaveformProtocol` (chunk 14's own established pattern, to avoid
  importing `Waveform1D` into `dsp/`). A consequence for the mandated
  `_W(CalcMixin, Waveform1D)` test pattern: `Waveform1D._with_values`
  always constructs a bare `Waveform1D` (not `type(self)(...)`), so a
  single-mixin test subclass loses `CalcMixin`'s methods on the result of
  its own method — `w.integrate()` cannot be chained directly into
  `.derivative()`. Tests rewrap the intermediate result into `_W` before
  calling the next mixin method (see `_wrap` helper in `test_calc.py`);
  this is an inherent property of the "one mixin composed at a time" test
  pattern the chunk doc itself specifies, not something chunk 18 changes.
- **`integrate`:** cumulative trapezoid via
  `scipy.integrate.cumulative_trapezoid(values, dx=dt_seconds, initial=0.0)`,
  then the whole result is offset by `+ initial_value` (this scipy version
  rejects a nonzero `initial=`; `ValueError: initial must be None or 0`).
  This reproduces the Swift semantics exactly: `first sample ==
  initial_value`, each subsequent sample is `initial_value +` the
  accumulated trapezoidal area — pinned by an exact (`atol=1e-9`, not just
  `rtol`) test against a constant signal, where the closed form is exact.
  Raises `ValueError` on an empty waveform (0 samples) per waveformDsp.md
  §Numerical conventions ("methods that need a minimum length raise
  ValueError... except detectors"); a single-sample waveform is valid
  (result is `[initial_value]`).
- **`derivative`:** `np.gradient(values, dt_seconds)` (central differences
  interior, one-sided at the edges) — this differs from the Swift source's
  hand-rolled central-difference loop only in the boundary formula
  (`np.gradient` uses a second-order-accurate one-sided estimate at the
  edges; Swift uses a first-order forward/backward difference), which is a
  documented, deliberate divergence per waveformDsp.md's preamble ("scipy
  semantics win... documented in the method docstring") rather than an
  oversight. Raises `ValueError` for fewer than 2 samples (`np.gradient`'s
  own minimum), including the empty case, rather than the Swift source's
  silent-empty-result.
- **`make uv-fullCheck` surfaced two gaps unrelated to `_calc.py` itself,
  both fixed in this chunk since nothing downstream of this DSP-mixin
  track could pass the gate otherwise:**
  1. `scipy` ships no inline type stubs (first scipy import in this repo);
     `mypy --install-types` offers `scipy-stubs`, but the latest published
     version (1.15.3.0) lags the pinned scipy (1.16.3) enough that pinning
     it felt like trading one type-safety gap for a version-skew one for no
     real benefit this chunk. Added a narrowly-scoped
     `[[tool.mypy.overrides]] module = "scipy.*"` /
     `ignore_missing_imports = true` block to `pyproject.toml` instead —
     every other third-party import stays strict/unignored. Every future
     scipy-backed DSP chunk (19–29) inherits this for free.
  2. waveformDsp.md §Compliance 2 ("no sibling mixin imports... pinned by a
     layering test") and chunk 18's own design constraint ("repo layering
     test extended here if not already covering `dsp/`") were not yet
     satisfied — `tests/test_package_layering.py` had no `dsp/`-specific
     check. Added `test_dsp_mixins_do_not_import_sibling_mixins` (guarded
     to skip if `waveforms/dsp` doesn't exist, mirroring the existing
     `test_otg_does_not_import_numpy` pattern): scans every `dsp/_*.py`
     module's `ast.ImportFrom` nodes (absolute and relative forms) for
     sibling `dsp/_*` imports outside `{_protocol, _common}`. Currently
     vacuous for `_calc.py` (it only imports `_protocol`/`_common`) but
     enforced going forward for chunks 19–29.
- Verified live (beyond the test suite): `_W([1.0,2.0,3.0]).integrate()`
  and the resulting value's `.values`/`.dt`/`.t0` before writing this note
  reproduced the `NoneType` bug pre-fix and its absence post-fix;
  `_W.__mro__` post-fix no longer contains `WaveformProtocol`/`Protocol`.
- Full suite: 848 tests green (12 new in `tests/waveforms/dsp/test_calc.py`),
  ruff clean, mypy strict clean (`make uv-fullCheck`).
