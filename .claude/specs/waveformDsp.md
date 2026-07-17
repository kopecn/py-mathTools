---
version: 1.0
type: specification
name: waveformDsp
purpose: Behavioral contract for the Waveform1D DSP/analysis surface (scipy-backed)
spec: WaveformDsp
scope: project
status: accepted
applies_to: src/math_tools/waveforms/dsp/, src/math_tools/waveforms/support.py, tests/waveforms/dsp/
last_updated: 2026-07-17
semver: 0.0.6
author: Nicholas Bergantz
---

# Waveform DSP Surface

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md); extends
> `Waveform1D` from [waveformCore.md](waveformCore.md). Target: **capability
> parity** with the Swift `Waveform1D/Extensions/` DSP families, implemented
> as thin scipy/numpy wrappers. Parity is judged per capability, not per
> Swift overload — where scipy's algorithm is the better-tested equivalent,
> scipy semantics win and the divergence is documented in the method
> docstring.

## Organization — one mixin per family

Each family is a mixin class in its own module under
`math_tools/waveforms/dsp/`; `Waveform1D` composes them:

```python
# waveforms/waveform1d.py
class Waveform1D(
    CalcMixin, CorrelationMixin, EnvelopeMixin, SpectralMixin,
    FilteringMixin, PeakMixin, PhaseMixin, ResamplingMixin,
    TimeAlignmentMixin, TriggerMixin, WindowingMixin, ZeroCrossingMixin,
    Waveform1dABC,
):
```

Mixin rules: stateless; touch only the public `Waveform1D` surface
(`values`, `dt`, `t0`, constructors). Typing mechanism (load-bearing —
mypy strict rejects a bare mixin referencing `self.values`): each mixin is a
**plain class** (no runtime base beyond `object`) that types its `self`
parameter as `WaveformProtocol` on every method — mypy's documented "mixin
classes" idiom, e.g. `def integrate(self: WaveformProtocol, ...) ->
WaveformProtocol: ...` — where `WaveformProtocol` is a `typing.Protocol` in
`dsp/_protocol.py` declaring `values: npt.NDArray`, `dt`, `t0`,
`sampling_frequency_hz`, and the replace-values factory the mixins use to
build results. That makes every mixin independently mypy-strict-checkable
and independently testable. Methods return new objects or descriptor
types — never mutate.

**Do not nominally inherit `WaveformProtocol`** (`class CalcMixin
(WaveformProtocol)`) — that was the first design tried and it is broken at
runtime. Explicitly subclassing a `Protocol` (without also listing
`Protocol` itself as a base) turns its stub property bodies — literally
`...`, so the getter returns `None` — into concrete inherited
implementations. The DSP mixin test convention composes a mixin directly
with `Waveform1D` (`class _W(CalcMixin, Waveform1D): pass`, see below);
under C3 linearization that puts the inherited Protocol stub ahead of
`Waveform1D`'s real property, so `self.values` silently returns `None`
instead of the sample array — caught by chunk 18's own TDD steps, not by
inspection. Self-typing `self` avoids this: the mixin class carries no
runtime base beyond `object`, so composing it with `Waveform1D` never pulls
`WaveformProtocol` into the MRO, while mypy still resolves every `self.*`
access structurally through the `self: WaveformProtocol` annotation.

**Two result factories.** Every mixin through chunk 24 only ever produces
results that share `self`'s `dt`/`t0` (built via `_with_values(values)`, same
`dt`/`t0`, new samples). `ResamplingMixin` (chunk 25, `dsp/_resampling.py`)
is the first family whose results have a genuinely different sample
spacing (`decimated`/`interpolated`/`resampled`/`polyphase_resampled` all
compute a new `dt`), so `WaveformProtocol` gained a second factory,
`_with_axis(values, dt) -> WaveformProtocol` (new samples, a caller-supplied
`dt`, `t0` unchanged from `self`) — implemented alongside `_with_values` on
`Waveform1D`. `t0` is deliberately not a parameter of `_with_axis`: every
`ResamplingMixin` method keeps `t0` unchanged (see its family-contract row
below), so add a `t0` parameter only when a future mixin needs to vary it
too.

**Three result factories.** `TimeAlignmentMixin` (chunk 26,
`dsp/_time_alignment.py`) is that future mixin: `aligned`, `synchronize`,
`time_windows`, and `time_segments` all produce results with the same `dt`
as their source but a genuinely different `t0` (a detected/reference time
shift, an overlap window's start, or a sub-span's start). Neither existing
factory fits (`_with_values` pins `t0`; `_with_axis` also pins `t0` while
changing `dt`), so `WaveformProtocol` gained a third factory,
`_with_t0(values, t0) -> WaveformProtocol` (new samples, same `dt` as
`self`, a caller-supplied `t0`) — implemented alongside the other two on
`Waveform1D`. The three factories now form a complete same-dt/same-t0
triangle: `_with_values` (same `dt`, same `t0`), `_with_axis` (new `dt`,
same `t0`), `_with_t0` (same `dt`, new `t0`).

**Composition phasing** (mirrors waveformCore's "Instantiability" section):
the core `Waveform1D` ships with base `Waveform1dABC` only. Each mixin chunk
adds a module without touching `waveform1d.py`. A single final **compose
chunk** edits the base list to the form above, adds the MRO test, and pins
that the composed class is still concrete (empty `__abstractmethods__`,
bare construction succeeds). Compliance item 4 applies only from that chunk
onward.

**Chunking hint:** one action-plan chunk per mixin; `support.py`,
`dsp/_protocol.py`, and `dsp/_common.py` land first as a prerequisite chunk.

## Family contracts

For every family: the Swift extension file is the reference for the method
list and argument meanings; the table row states the required Python surface
and its backing implementation. Enum arguments use the support types below.

| Mixin (module) | Required methods | Backing |
|---|---|---|
| `CalcMixin` (`_calc.py`) | `integrate(initial_value=0.0)`, `derivative()` | cumulative trapezoid (`scipy.integrate.cumulative_trapezoid`) · `np.gradient`; both scale by `dt` seconds |
| `CorrelationMixin` (`_correlation.py`) | `auto_correlation(max_lag=None, normalized=True)`, `cross_correlation(other, ...)`, `find_max_correlation(other, ...) -> WaveformTimeLag` | `scipy.signal.correlate` / `correlation_lags` |
| `EnvelopeMixin` (`_envelope.py`) | `amplitude_envelope(...)`, `upper_lower_envelopes(...) -> tuple[Waveform1D, Waveform1D]`, `instantaneous_amplitude(method: WaveformInstantaneousMethod)` | `scipy.signal.hilbert`; peak-interp path via `find_peaks` + interp |
| `SpectralMixin` (`_spectral.py`) | `fft() -> WaveformSpectrum`, `power_spectral_density(...) -> WaveformSpectrum`, `spectrogram(...) -> WaveformSpectrogram`, `mel_spectrogram(...) -> WaveformMelSpectrogram`, `spectral_features() -> WaveformSpectralFeatures` | `np.fft.rfft` / `scipy.signal.welch` / `scipy.signal.ShortTimeFFT`; mel filterbank hand-built (numpy) |
| `FilteringMixin` (`_filtering.py`) | `filtered(filter_type: WaveformFilterType, order=4)`, `low_pass_filter(cutoff_hz, ...)`, `high_pass_filter(...)`, `band_pass_filter(low_hz, high_hz, ...)`, `moving_average_filter(window_size)`, `exponential_filter(alpha)`, `savitzky_golay_filter(window_length, polyorder, deriv=0)`, `whittaker_henderson_filter(lam, order=2)`, `frequency_response(...) -> WaveformSpectrum` | `scipy.signal.butter`+`filtfilt`, `savgol_filter`, `np.convolve`; Whittaker–Henderson via `scipy.sparse` difference-matrix solve |
| `PeakMixin` (`_peaks.py`) | `detect_peaks(...) -> list[WaveformPeak]`, `detect_valleys(...)`, `find_most_prominent_peaks(count, min_distance=None) -> list[WaveformPeakWithProminence]` | `scipy.signal.find_peaks` / `peak_prominences` |
| `PhaseMixin` (`_phase.py`) | `instantaneous_phase(...)`, `unwrap_phase(...)`, `instantaneous_frequency(...) -> WaveformInstantaneousFrequency`, `phase_difference(other, ...)`, `phase_coherence(other, ...)`, `phase_synchronization_index(other) -> float`, `group_delay(...)` | `scipy.signal.hilbert`, `np.unwrap` |
| `ResamplingMixin` (`_resampling.py`) | `decimated(factor, ...)`, `interpolated(factor, method: WaveformInterpolationMethod = ...)`, `resampled(target_frequency_hz, ...)`, `resampled_to_match(other)`, `polyphase_resampled(up, down)` | `scipy.signal.decimate` / `resample` / `resample_poly`; results carry recomputed `dt` (attosecond-exact where the ratio is rational) |
| `TimeAlignmentMixin` (`_time_alignment.py`) | `aligned(to, method: WaveformAlignmentMethod = ...)`, `time_lag(to, max_lag=None) -> WaveformTimeLag \| None`, `synchronize(waveforms: Sequence[Waveform1D]) -> list[Waveform1D]` (classmethod), `time_windows(...)`, `time_segments(...)` | correlation-lag via `CorrelationMixin` |
| `TriggerMixin` (`_triggers.py`) | `detect_triggers(trigger: WaveformTrigger) -> list[WaveformTriggerEvent]`, `detect_edge_triggers(level, edge: WaveformEdgeType)`, `detect_level_triggers(...)`, `detect_window_triggers(low, high, kind: WaveformWindowTriggerType)`, `detect_pattern_triggers(pattern, tolerance)`, `with_event_markers(events) -> WaveformWithEvents` | numpy comparisons + sign-change indexing |
| `WindowingMixin` (`_windowing.py`) | `windowed(window: WaveformWindowType)`, `generate_window(window, length) -> npt.NDArray` (staticmethod), `window_coherent_gain(window) -> float`, `window_processing_gain(window) -> float` | `scipy.signal.get_window` |
| `ZeroCrossingMixin` (`_zero_crossings.py`) | `zero_crossings(direction: WaveformZeroCrossingDirection = BOTH) -> list[WaveformZeroCrossing]`, `zero_crossing_count(...)`, `zero_crossing_rate(...) -> float`, `segments_between_zero_crossings(...) -> list[Waveform1D]` | numpy sign-change indexing, sub-sample linear interp |

## Support descriptor types — `waveforms/support.py`

Port from Swift `Waveform1D/Support/` **only the types consumed by the
methods above** (YAGNI on the rest; add with the method that needs them).

- **Enums** (`enum.Enum`, values = snake_case strings):
  `WaveformFilterType` (LOW_PASS/HIGH_PASS/BAND_PASS/BAND_STOP),
  `WaveformWindowType` (HANN/HAMMING/BLACKMAN/BARTLETT/KAISER/RECTANGULAR),
  `WaveformInterpolationMethod` (LINEAR/CUBIC/NEAREST/FOURIER),
  `WaveformInstantaneousMethod` (HILBERT/RMS/PEAK),
  `WaveformEdgeType` (RISING/FALLING/BOTH),
  `WaveformWindowTriggerType` (ENTER/EXIT),
  `WaveformAlignmentMethod` (CORRELATION/START_TIME),
  `WaveformZeroCrossingDirection` (POSITIVE/NEGATIVE/BOTH),
  `WaveformPaddingStrategy` (ZERO/EDGE/REFLECT/WRAP),
  `WaveformPSDScaling` (DENSITY/SPECTRUM),
  `WaveformSpectrogramScaling` (LINEAR/DB/MEL).
- **Frozen dataclasses** (all `@dataclass(frozen=True, slots=True)`).
  **ndarray hazard:** any descriptor holding numpy arrays
  (`WaveformSpectrum`, `WaveformSpectrogram`, `WaveformMelSpectrogram`,
  `WaveformInstantaneousFrequency`, `WaveformFilterCoefficients`, …) MUST
  use `@dataclass(frozen=True, slots=True, eq=False)` — the generated
  `__eq__`/`__hash__` raise/misbehave on arrays (`ValueError: ambiguous
  truth value`). Scalar-only descriptors keep the default `eq=True`.
  Descriptor types:
  `WaveformSpectrum(frequencies, magnitudes, phases)` (numpy arrays; replaces
  Swift's anonymous fft tuple), `WaveformSpectrogram(times, frequencies,
  magnitudes)`, `WaveformMelSpectrogram(...)`, `WaveformSpectralFeatures`
  (centroid, spread, rolloff, flatness, …, matching the Swift fields),
  `WaveformPeak(index, time_seconds, value)`,
  `WaveformPeakWithProminence(peak, prominence)`,
  `WaveformTimeLag(lag_samples, lag_seconds, correlation)`,
  `WaveformTrigger(kind: WaveformTriggerType, level, lower, upper, pattern,
  tolerance, minimum_interval, edge, window_kind)`,
  `WaveformTriggerEvent(index, time_seconds, value, kind)`,
  `WaveformEventMarker(index, label)`, `WaveformWithEvents(waveform:
  WaveformProtocol, events)`, `WaveformZeroCrossing(index, time_seconds,
  direction)`, `WaveformInstantaneousFrequency(frequencies_hz,
  times_seconds)`, `WaveformFrequencyRange(low_hz, high_hz)`,
  `WaveformFilterCoefficients(numerator, denominator)`.

  **`WaveformTrigger`'s `edge`/`window_kind` fields (chunk 27, semver
  0.0.6):** `edge: WaveformEdgeType | None = None` and `window_kind:
  WaveformWindowTriggerType | None = None`, both optional and defaulting to
  `None`. `TriggerMixin.detect_triggers` (the generic `WaveformTrigger`-
  driven dispatcher) needs a direction/enter-exit selector for `EDGE`/
  `LEVEL`/`WINDOW` kinds — the direct `detect_edge_triggers`/
  `detect_level_triggers`/`detect_window_triggers` methods take it as an
  explicit argument, but the dataclass had no field to carry it until this
  change. Dispatch falls back to `WaveformEdgeType.BOTH` (`EDGE`),
  `WaveformEdgeType.RISING` (`LEVEL`), and `WaveformWindowTriggerType.ENTER`
  (`WINDOW`) when the caller leaves the field unset — matching each direct
  method's own default — so this is backward-compatible with every
  pre-chunk-27 `WaveformTrigger(...)` call site.

  **`WaveformWithEvents.waveform`'s type (chunk 27, semver 0.0.6):** typed
  `WaveformProtocol` (`dsp/_protocol.py`), not the concrete `Waveform1D` it
  held through chunk 26. `TriggerMixin.with_event_markers` is the first
  mixin method that embeds `self` itself into a returned descriptor —
  every earlier descriptor holds only derived values (arrays, scalars,
  other descriptors). Mixins type `self` as `WaveformProtocol` and must
  never import `Waveform1D` (§Organization; not even under
  `TYPE_CHECKING` — see `dsp/_protocol.py`'s docstring), so a field typed
  concrete `Waveform1D` was unsatisfiable from a mixin method without that
  forbidden import. `Waveform1D` already satisfies `WaveformProtocol`
  structurally (both at runtime via `@runtime_checkable` and under mypy
  strict), so retyping the field is behavior-preserving for every caller —
  a real `Waveform1D` is still exactly what gets passed in and read back
  out — and removes `support.py`'s only import of `waveforms/waveform1d.py`,
  closing off what would otherwise become a circular import once the
  chunk-30 compose step makes `waveform1d.py` import every mixin (mixins
  already import `support.py`; `support.py` importing back into
  `waveform1d.py` would have completed the cycle).

## Numerical conventions

- Frequencies in Hz, times in float seconds (derived from the PrecisionTime
  axis at the boundary), phases in radians.
- Filters are zero-phase (`filtfilt`) unless a method exposes a `causal=`
  flag.
- Methods that need a minimum length raise `ValueError` with the requirement
  in the message (never a silent empty result), except detectors
  (`detect_*`, `zero_crossings`) which return empty lists on no-hit.

## Compliance requirements (test-checkable)

1. Every mixin method tested against an analytically known signal — e.g.
   `fft` of a pure 10 Hz sine peaks at 10 Hz bin; `low_pass_filter` on a
   5 Hz + 200 Hz mix attenuates the 200 Hz component by ≥ 40 dB;
   `derivative` of a linear ramp is constant to atol 1e-9;
   `integrate`∘`derivative` recovers a smooth signal (interior points,
   rtol 1e-6); `detect_peaks` on `sine` finds exactly `⌊n·f·dt⌋` peaks;
   `zero_crossing_rate` of a sine equals `2f` ±1 count; `unwrap_phase` of a
   chirp is monotone; `resampled` ×2 then ÷2 round-trips (rtol 1e-3, interior).
2. Each mixin module imports scipy/numpy only (no sibling mixin imports —
   shared helpers live in `dsp/_common.py`); pinned by a layering test.
3. Descriptor types are frozen (mutation raises); ndarray-bearing ones have
   `eq=False` (pin: constructing two equal-content instances and comparing
   does not raise); all mypy strict clean.
4. From the compose chunk onward: `Waveform1D` MRO composes every mixin
   exactly once (pinned by a test enumerating `Waveform1D.__mro__`), the
   class remains concrete, and a bare `Waveform1D(values)` constructs.
