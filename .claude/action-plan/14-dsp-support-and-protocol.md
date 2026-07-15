---
chunk: 14-dsp-support-and-protocol
track: C
status: complete
depends_on: [11]
spec: ../specs/waveformDsp.md §Support descriptor types, §Organization (protocol), §Compliance 3
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 14 — DSP support types + mixin protocol

**Deliverable:** the shared substrate every DSP mixin chunk builds on.

## Files

- Create: `src/math_tools/waveforms/support.py`,
  `src/math_tools/waveforms/dsp/__init__.py`,
  `src/math_tools/waveforms/dsp/py.typed`,
  `src/math_tools/waveforms/dsp/_protocol.py`,
  `src/math_tools/waveforms/dsp/_common.py`
- Edit: `src/math_tools/waveforms/__init__.py` (export support types)
- Create: `tests/waveforms/test_support.py`

## Design constraints

1. `support.py`: ALL enums and descriptor dataclasses listed in the spec
   §Support descriptor types — string-valued `Enum`s;
   `@dataclass(frozen=True, slots=True)` with **`eq=False` on every
   ndarray-bearing descriptor** (`WaveformSpectrum`, `WaveformSpectrogram`,
   `WaveformMelSpectrogram`, `WaveformInstantaneousFrequency`,
   `WaveformFilterCoefficients`); scalar-only descriptors keep default eq.
2. `_protocol.py`:

```python
class WaveformProtocol(Protocol):
    @property
    def values(self) -> npt.NDArray[Any]: ...
    @property
    def dt(self) -> PrecisionTimeInterval: ...
    @property
    def t0(self) -> PrecisionTimestamp: ...
    @property
    def sampling_frequency_hz(self) -> float: ...
    def _with_values(self, values: npt.NDArray[Any]) -> "Waveform1D": ...
```

   `_with_values(values)` (same dt/t0, new samples) must be added to
   `Waveform1D` here — the one edit to `waveform1d.py` this chunk makes.
   Adjust member names ONLY to match what `Waveform1D` actually exposes.
3. `_common.py`: `float_seconds(interval) -> float` and any helper two or
   more mixins would otherwise duplicate; starts minimal.

## TDD steps

1. Failing tests: every enum member exists; frozen mutation raises;
   ndarray descriptors — construct two equal-content instances, `==`
   evaluates without raising (compliance 3); `Waveform1D` structurally
   satisfies `WaveformProtocol` (assign to a protocol-typed variable under
   mypy + a runtime `isinstance` check via `runtime_checkable`).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All spec-listed enums/dataclasses exist; ndarray ones have `eq=False`
- [x] `Waveform1D._with_values` returns a new instance sharing dt/t0
- [x] `make uv-fullCheck` passes

## Out of scope

Any mixin; composing anything into `Waveform1D`.

## Resolution notes

- `support.py`: all 12 enums (11 from the spec's list + `WaveformTriggerType`,
  see below) as `str, enum.Enum` with snake_case string values, and all 15
  frozen dataclasses (`@dataclass(frozen=True, slots=True)`). `eq=False`
  applied to exactly the 5 ndarray-bearing descriptors the spec names
  (`WaveformSpectrum`, `WaveformSpectrogram`, `WaveformMelSpectrogram`,
  `WaveformInstantaneousFrequency`, `WaveformFilterCoefficients`); the
  remaining 10 scalar-only descriptors keep default `eq=True`, including
  `WaveformWithEvents` (wraps a `Waveform1D`, whose own `__eq__` already
  compares arrays safely and returns a plain `bool`, so the
  dataclass-generated tuple-eq never touches a raw ndarray directly).
- **`WaveformTriggerType` resolved via the Swift source, as instructed:**
  the Python spec text references `WaveformTrigger(kind:
  WaveformTriggerType, ...)` without enumerating that enum's members. The
  Swift original (`Support/WaveformTriggerType.swift`) is a generic enum
  with four associated-value cases (`edge`/`level`/`window`/`pattern`,
  each carrying its own thresholds). Flattened to a plain 4-member string
  enum (the case names) with the associated payload moved onto
  `WaveformTrigger`'s optional fields (`level`, `lower`, `upper`,
  `pattern`, `tolerance`, `minimum_interval`) — consistent with every
  other "kind" discriminator enum in this module. Documented inline in
  `support.py`'s module docstring and `WaveformTrigger`'s own docstring.
- `dsp/_protocol.py`: `WaveformProtocol` (`@runtime_checkable`) declares
  `values`, `dt`, `t0`, `sampling_frequency_hz`, `_with_values`. One
  judgment-call deviation from the chunk doc's literal code block:
  `_with_values` returns `WaveformProtocol` (self-type) rather than a
  quoted `"Waveform1D"` forward reference, since resolving that forward
  reference under mypy strict would require importing `Waveform1D` into
  `_protocol.py` (even under `TYPE_CHECKING`), reintroducing exactly the
  `dsp/` → `waveforms/waveform1d.py` coupling the Protocol pattern exists
  to avoid — and future mixins (which only ever need a
  `WaveformProtocol`-satisfying result) are unaffected either way.
  `Waveform1D._with_values -> Waveform1D` remains a valid covariant
  implementation of the protocol method. Verified this doesn't just
  typecheck but actually holds at runtime:
  `isinstance(Waveform1D(...), WaveformProtocol)` is `True`.
- `dsp/_common.py`: only `float_seconds(interval) -> float` (thin wrapper
  over the existing `PrecisionTimeInterval.seconds_as_float`), per "starts
  minimal."
- `waveform1d.py`'s only edit: added `_with_values(self, values) ->
  Waveform1D`, returning a new instance with the same `dt`/`t0`. Verified
  live: `w._with_values(new_array) is not w`, and the new instance's `dt`/
  `t0` equal the original's exactly.
- No spec change was needed; `WaveformTriggerType`'s flattening is
  documented in code (module + class docstrings) rather than requiring a
  spec edit, since the Python spec text never enumerated its members in
  the first place (no existing spec statement was contradicted).
- Verified live (beyond the test suite): frozen-dataclass mutation raises
  `dataclasses.FrozenInstanceError`; `WaveformSpectrum(...) ==
  WaveformSpectrum(...)` (equal-content, `eq=False`) evaluates to `False`
  without raising; `isinstance(Waveform1D(...), WaveformProtocol)` is
  `True`.
- Verified: 20 new tests in `tests/waveforms/test_support.py`, full suite
  618 tests green, ruff clean, mypy strict clean (`make uv-fullCheck`).
