"""Support enums and descriptor dataclasses for the ``Waveform1D`` DSP surface.

See ``.claude/specs/waveformDsp.md`` §Support descriptor types. Ported from
the Swift ``Waveform1D/Support/`` types, but only the members/fields the
Python mixin contracts (chunks 18-30) actually consume -- YAGNI on the rest.

Every enum is a string-valued ``enum.Enum`` (snake_case values) so descriptor
instances serialize/repr predictably. Every dataclass is
``@dataclass(frozen=True, slots=True)``; descriptors holding numpy arrays
additionally set ``eq=False`` because the dataclass-generated ``__eq__``
would compare arrays with ``==`` and raise ``ValueError: ambiguous truth
value`` (waveformDsp.md §Compliance 3). Scalar-only descriptors keep the
default generated ``__eq__``.

``WaveformTriggerType`` is not enumerated in the Python spec's enum list --
the Swift source (``Support/WaveformTriggerType.swift``) defines it as a
generic enum with associated values (``edge``, ``level``, ``window``,
``pattern`` cases carrying thresholds/bounds). This module flattens it to a
plain string-valued discriminator enum (its four case names) and moves the
associated payload onto :class:`WaveformTrigger`'s optional fields --
consistent with every other "kind" enum here and with
``WaveformTrigger(kind: WaveformTriggerType, level, ...)`` in the spec text.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.waveforms.waveform1d import Waveform1D

# MARK: - Enums

class WaveformFilterType(str, enum.Enum):
    """Filter family selector for ``FilteringMixin.filtered``."""

    LOW_PASS = "low_pass"
    HIGH_PASS = "high_pass"
    BAND_PASS = "band_pass"
    BAND_STOP = "band_stop"


class WaveformWindowType(str, enum.Enum):
    """Window function selector for ``WindowingMixin``."""

    HANN = "hann"
    HAMMING = "hamming"
    BLACKMAN = "blackman"
    BARTLETT = "bartlett"
    KAISER = "kaiser"
    RECTANGULAR = "rectangular"


class WaveformInterpolationMethod(str, enum.Enum):
    """Interpolation kernel for ``ResamplingMixin.interpolated``."""

    LINEAR = "linear"
    CUBIC = "cubic"
    NEAREST = "nearest"
    FOURIER = "fourier"


class WaveformInstantaneousMethod(str, enum.Enum):
    """Estimator for ``EnvelopeMixin.instantaneous_amplitude``."""

    HILBERT = "hilbert"
    RMS = "rms"
    PEAK = "peak"


class WaveformEdgeType(str, enum.Enum):
    """Edge direction for ``TriggerMixin.detect_edge_triggers``."""

    RISING = "rising"
    FALLING = "falling"
    BOTH = "both"


class WaveformWindowTriggerType(str, enum.Enum):
    """Enter/exit selector for ``TriggerMixin.detect_window_triggers``."""

    ENTER = "enter"
    EXIT = "exit"


class WaveformAlignmentMethod(str, enum.Enum):
    """Alignment strategy for ``TimeAlignmentMixin.aligned``."""

    CORRELATION = "correlation"
    START_TIME = "start_time"


class WaveformZeroCrossingDirection(str, enum.Enum):
    """Direction filter for ``ZeroCrossingMixin.zero_crossings``."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOTH = "both"


class WaveformPaddingStrategy(str, enum.Enum):
    """Edge-padding strategy shared by resampling/filtering helpers."""

    ZERO = "zero"
    EDGE = "edge"
    REFLECT = "reflect"
    WRAP = "wrap"


class WaveformPSDScaling(str, enum.Enum):
    """Scaling mode for ``SpectralMixin.power_spectral_density``."""

    DENSITY = "density"
    SPECTRUM = "spectrum"


class WaveformSpectrogramScaling(str, enum.Enum):
    """Magnitude scaling for ``SpectralMixin.spectrogram``."""

    LINEAR = "linear"
    DB = "db"
    MEL = "mel"


class WaveformTriggerType(str, enum.Enum):
    """Trigger-kind discriminator for :class:`WaveformTrigger` / :class:`WaveformTriggerEvent`.

    Flattened from the Swift generic ``WaveformTriggerType<T>`` enum's four
    associated-value cases (``edge``, ``level``, ``window``, ``pattern``) --
    see the module docstring.
    """

    EDGE = "edge"
    LEVEL = "level"
    WINDOW = "window"
    PATTERN = "pattern"


# MARK: - Descriptor dataclasses (ndarray-bearing -- eq=False)


@dataclass(frozen=True, slots=True, eq=False)
class WaveformSpectrum:
    """A one-sided frequency-domain view: bin frequencies, magnitudes, phases.

    Replaces the Swift ``fft`` extension's anonymous tuple return.
    """

    frequencies: npt.NDArray[np.float64]
    magnitudes: npt.NDArray[np.float64]
    phases: npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class WaveformSpectrogram:
    """Time-frequency magnitude surface (``magnitudes[time, frequency]``)."""

    times: npt.NDArray[np.float64]
    frequencies: npt.NDArray[np.float64]
    magnitudes: npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class WaveformMelSpectrogram:
    """Mel-scale analogue of :class:`WaveformSpectrogram`."""

    times: npt.NDArray[np.float64]
    mel_frequencies: npt.NDArray[np.float64]
    magnitudes: npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class WaveformInstantaneousFrequency:
    """Instantaneous-frequency track over time (``PhaseMixin.instantaneous_frequency``)."""

    frequencies_hz: npt.NDArray[np.float64]
    times_seconds: npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class WaveformFilterCoefficients:
    """IIR/FIR coefficients: ``numerator`` (feedforward) / ``denominator`` (feedback)."""

    numerator: npt.NDArray[np.float64]
    denominator: npt.NDArray[np.float64]


# MARK: - Descriptor dataclasses (scalar-only -- default eq)


@dataclass(frozen=True, slots=True)
class WaveformSpectralFeatures:
    """Whole-spectrum summary statistics (``SpectralMixin.spectral_features``)."""

    centroid: float
    spread: float
    rolloff: float
    flatness: float


@dataclass(frozen=True, slots=True)
class WaveformPeak:
    """A single detected peak/valley sample."""

    index: int
    time_seconds: float
    value: float


@dataclass(frozen=True, slots=True)
class WaveformPeakWithProminence:
    """A peak plus its ``scipy.signal.peak_prominences`` value."""

    peak: WaveformPeak
    prominence: float


@dataclass(frozen=True, slots=True)
class WaveformTimeLag:
    """Best-correlation lag between two waveforms."""

    lag_samples: int
    lag_seconds: float
    correlation: float


@dataclass(frozen=True, slots=True)
class WaveformTrigger:
    """Trigger configuration passed to ``TriggerMixin.detect_triggers``.

    Only the fields relevant to ``kind`` are meaningful: ``level`` for
    ``EDGE``/``LEVEL``, ``lower``/``upper`` for ``WINDOW``, ``pattern``/
    ``tolerance`` for ``PATTERN`` -- mirroring the Swift associated-value
    cases collapsed into ``WaveformTriggerType`` (see module docstring).
    """

    kind: WaveformTriggerType
    level: float | None = None
    lower: float | None = None
    upper: float | None = None
    pattern: tuple[float, ...] | None = None
    tolerance: float | None = None
    minimum_interval: PrecisionTimeInterval | None = None


@dataclass(frozen=True, slots=True)
class WaveformTriggerEvent:
    """A single fired trigger."""

    index: int
    time_seconds: float
    value: float
    kind: WaveformTriggerType


@dataclass(frozen=True, slots=True)
class WaveformEventMarker:
    """A labeled point of interest for annotating a waveform."""

    index: int
    label: str


@dataclass(frozen=True, slots=True)
class WaveformWithEvents:
    """A waveform paired with its event markers (``TriggerMixin.with_event_markers``)."""

    waveform: Waveform1D
    events: tuple[WaveformEventMarker, ...]


@dataclass(frozen=True, slots=True)
class WaveformZeroCrossing:
    """A single zero crossing."""

    index: int
    time_seconds: float
    direction: WaveformZeroCrossingDirection


@dataclass(frozen=True, slots=True)
class WaveformFrequencyRange:
    """An inclusive ``[low_hz, high_hz]`` band, e.g. for band-pass filtering."""

    low_hz: float
    high_hz: float


__all__ = [
    "WaveformFilterType",
    "WaveformWindowType",
    "WaveformInterpolationMethod",
    "WaveformInstantaneousMethod",
    "WaveformEdgeType",
    "WaveformWindowTriggerType",
    "WaveformAlignmentMethod",
    "WaveformZeroCrossingDirection",
    "WaveformPaddingStrategy",
    "WaveformPSDScaling",
    "WaveformSpectrogramScaling",
    "WaveformTriggerType",
    "WaveformSpectrum",
    "WaveformSpectrogram",
    "WaveformMelSpectrogram",
    "WaveformSpectralFeatures",
    "WaveformPeak",
    "WaveformPeakWithProminence",
    "WaveformTimeLag",
    "WaveformTrigger",
    "WaveformTriggerEvent",
    "WaveformEventMarker",
    "WaveformWithEvents",
    "WaveformZeroCrossing",
    "WaveformInstantaneousFrequency",
    "WaveformFrequencyRange",
    "WaveformFilterCoefficients",
]
