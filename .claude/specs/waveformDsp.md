---
version: 1.0
type: specification
name: waveformDsp
purpose: Behavioral contract for the Waveform1D DSP/analysis surface (scipy-backed)
scope: project
applies_to: src/math_tools/waveforms/dsp/, src/math_tools/waveforms/support.py, tests/waveforms/dsp/
last_updated: 2026-09-24
semver: 0.0.9
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

`WaveformProtocol` is structural typing only. Mixins MUST NOT nominally inherit it, because protocol stub properties would enter the runtime MRO; every mixin remains a plain class and annotates each `self` parameter as `WaveformProtocol`.

`WaveformProtocol` and `Waveform1D` expose three result factories:

- `_with_values(values)` returns new samples with the source `dt` and `t0`.
- `_with_axis(values, dt)` returns new samples with caller-supplied `dt` and the source `t0`.
- `_with_t0(values, t0)` returns new samples with the source `dt` and caller-supplied `t0`.

`waveform1d.py` imports all twelve mixin modules directly and composes each exactly once in the base-list order above. `dsp/__init__.py` re-exports all twelve mixins. Mixin modules MUST NOT import sibling mixins or `Waveform1D`; `support.py` may import `WaveformProtocol` only under `TYPE_CHECKING` so package initialization remains cycle-free.

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
| `WindowingMixin` (`_windowing.py`) | `windowed(window: WaveformWindowType)`, `generate_window(window, length, periodic: bool = False) -> npt.NDArray` (staticmethod), `window_coherent_gain(window, periodic: bool = False) -> float`, `window_processing_gain(window, periodic: bool = False) -> float` | `scipy.signal.get_window`; see §Window convention for the symmetric/periodic split with `SpectralMixin` |
| `ZeroCrossingMixin` (`_zero_crossings.py`) | `zero_crossings(direction: WaveformZeroCrossingDirection = BOTH) -> list[WaveformZeroCrossing]`, `zero_crossing_count(...)`, `zero_crossing_rate(...) -> float`, `segments_between_zero_crossings(...) -> list[Waveform1D]` | numpy sign-change indexing, sub-sample linear interp |

## Window convention

`WindowingMixin` and `SpectralMixin` both call `scipy.signal.get_window`, but
for genuinely different purposes, and each keeps its own default:

- **`WindowingMixin` default: symmetric** (`fftbins=False`). This matches the
  Swift reference's own `n - 1`-denominator formulas: a finite-length
  window's first and last samples are exactly the window's edge value, and
  (for odd length) the true midpoint sample is exactly the window's peak.
  This is the right convention for filter design, gain/coherent-gain
  analysis, and applying a window to a whole waveform (`windowed`).
- **`SpectralMixin` default: periodic** (`fftbins=True`, scipy's own
  default). This is the right convention for STFT frame tiling
  (`power_spectral_density` via `welch`, `spectrogram`), where the window
  must satisfy the constant-overlap-add condition across abutting frames —
  a symmetric window's duplicated edge sample breaks that condition.

`generate_window`, `window_coherent_gain`, and `window_processing_gain` accept `periodic: bool = False`. `periodic=False` selects the symmetric convention; `periodic=True` selects the periodic window used by `SpectralMixin`. `windowed` always uses the symmetric convention.

`dsp/_common.DEFAULT_KAISER_BETA = 14.0` is the single shape parameter used by `_windowing.py` and `_spectral.py`. Kaiser beta is not caller-configurable in the Python surface, unlike the Swift associated-value enum.

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

  `WaveformTrigger.edge: WaveformEdgeType | None = None` and `window_kind: WaveformWindowTriggerType | None = None` carry the selectors used by generic dispatch. Unset selectors default to `BOTH` for `EDGE`, `RISING` for `LEVEL`, and `ENTER` for `WINDOW`.

  `WaveformWithEvents.waveform` is typed as `WaveformProtocol`, which `Waveform1D` satisfies structurally. It MUST NOT introduce a runtime import of `Waveform1D` into `support.py`.

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
4. `Waveform1D` MRO composes every mixin exactly once (pinned by a test enumerating `Waveform1D.__mro__`), the
   class remains concrete, and a bare `Waveform1D(values)` constructs.
