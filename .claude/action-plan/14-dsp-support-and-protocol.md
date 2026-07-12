---
chunk: 14-dsp-support-and-protocol
track: C
status: pending
depends_on: [11]
spec: ../specs/waveformDsp.md §Support descriptor types, §Organization (protocol), §Compliance 3
last_updated: 2026-07-11
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

- [ ] All spec-listed enums/dataclasses exist; ndarray ones have `eq=False`
- [ ] `Waveform1D._with_values` returns a new instance sharing dt/t0
- [ ] `make uv-fullCheck` passes

## Out of scope

Any mixin; composing anything into `Waveform1D`.
