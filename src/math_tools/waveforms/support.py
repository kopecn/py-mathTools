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

**Forced contract change (chunk 27, semver 0.0.6):** :class:`WaveformTrigger`
gained two optional fields, ``edge: WaveformEdgeType | None`` and
``window_kind: WaveformWindowTriggerType | None`` -- needed for
``TriggerMixin.detect_triggers`` (the generic ``WaveformTrigger``-driven
dispatcher) to forward the same direction/enter-exit selector its direct
``detect_edge_triggers``/``detect_level_triggers``/``detect_window_triggers``
siblings take as an explicit argument; without a field to read, the generic
path had no way to know which direction/selector the caller wanted. Both
default to ``None`` (dispatch falls back to ``WaveformEdgeType.BOTH`` for
``EDGE``, ``WaveformEdgeType.RISING`` for ``LEVEL``, and
``WaveformWindowTriggerType.ENTER`` for ``WINDOW`` -- see
``dsp/_triggers.py``), so this is backward-compatible with every existing
``WaveformTrigger(...)`` call site.

**Forced contract change (chunk 27, semver 0.0.6):**
:class:`WaveformWithEvents`'s ``waveform`` field is typed
``WaveformProtocol`` (``dsp/_protocol.py``), not the concrete ``Waveform1D``
the field held through chunk 26. ``TriggerMixin.with_event_markers``
(``dsp/_triggers.py``) is the first mixin method that has to embed ``self``
itself into a descriptor -- every earlier descriptor holds only *derived*
values (arrays, scalars, other descriptors), never the host waveform. Mixins
type ``self`` as ``WaveformProtocol`` and must not import ``Waveform1D``
(waveformDsp.md §Organization; see ``dsp/_protocol.py``'s docstring for why
even a ``TYPE_CHECKING``-only import is disallowed), so a field typed
concrete ``Waveform1D`` was never satisfiable from a mixin method without
that forbidden import. Retyping the field as the structural
``WaveformProtocol`` -- which ``Waveform1D`` already satisfies, both at
runtime (``@runtime_checkable``) and under mypy strict, per
``tests/waveforms/test_support.py::TestWaveformProtocol`` -- resolves this
without touching the import-direction rule, and as a side effect removes
this module's only import of ``waveforms/waveform1d.py`` (a real ``Waveform1D``
instance is still exactly what every caller passes in and reads back out).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval

if TYPE_CHECKING:
    # Deferred to type-checking only (chunk 30, semver 0.0.7): a module-level import
    # here forces Python to fully execute `waveforms/dsp/__init__.py` -- which, from
    # this chunk onward, eagerly imports every mixin to re-export it (see that
    # module's docstring) -- before this module (`support.py`) finishes executing.
    # Several mixins (e.g. `dsp/_correlation.py`) import types back out of
    # `support.py`, so that eager chain landed here mid-import and raised
    # `ImportError: cannot import name 'WaveformTimeLag' from partially initialized
    # module`. `WaveformProtocol` is only ever used as a dataclass field annotation
    # below (`WaveformWithEvents.waveform`), and `from __future__ import
    # annotations` (above) already defers every annotation in this module to a
    # string -- so the import is never needed at runtime, only for mypy, which
    # resolves `TYPE_CHECKING` imports without executing them. This is the opposite
    # direction from the forbidden case in `dsp/_protocol.py`'s docstring (a DSP
    # mixin importing `Waveform1D`, forbidden even under `TYPE_CHECKING` because a
    # mixin must stay import-cycle-free with the class it composes onto); a support
    # module importing the mixins' own protocol under `TYPE_CHECKING` carries no
    # such restriction.
    from math_tools.waveforms.dsp._protocol import WaveformProtocol

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
    ``EDGE``/``LEVEL`` (direction via ``edge``, defaulting to ``BOTH``/
    ``RISING`` respectively when unset), ``lower``/``upper`` for ``WINDOW``
    (enter/exit via ``window_kind``, defaulting to ``ENTER`` when unset),
    ``pattern``/``tolerance`` for ``PATTERN`` -- mirroring the Swift
    associated-value cases collapsed into ``WaveformTriggerType`` (see
    module docstring). ``edge``/``window_kind`` were added in chunk 27 (see
    module docstring "Forced contract change") so the generic
    ``detect_triggers`` dispatcher can forward the same direction/selector
    its direct ``detect_edge_triggers``/``detect_level_triggers``/
    ``detect_window_triggers`` siblings take explicitly.
    """

    kind: WaveformTriggerType
    level: float | None = None
    lower: float | None = None
    upper: float | None = None
    pattern: tuple[float, ...] | None = None
    tolerance: float | None = None
    minimum_interval: PrecisionTimeInterval | None = None
    edge: WaveformEdgeType | None = None
    window_kind: WaveformWindowTriggerType | None = None


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
    """A waveform paired with its event markers (``TriggerMixin.with_event_markers``).

    ``waveform`` is typed ``WaveformProtocol`` rather than the concrete
    ``Waveform1D`` (see module docstring "Forced contract change", chunk 27)
    -- callers always pass and read back an actual ``Waveform1D``, since it
    is the only type that ever composes ``TriggerMixin``.
    """

    waveform: WaveformProtocol
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
