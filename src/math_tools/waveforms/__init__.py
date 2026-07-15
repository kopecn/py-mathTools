"""Waveform container types: :class:`Waveform1D` (and, in later chunks, the
aggregate spatial waveform containers) plus the DSP support descriptor
types and enums.

See ``.claude/specs/waveformCore.md`` and ``.claude/specs/waveformDsp.md``.
"""

from math_tools.waveforms.support import (
    WaveformAlignmentMethod,
    WaveformEdgeType,
    WaveformEventMarker,
    WaveformFilterCoefficients,
    WaveformFilterType,
    WaveformFrequencyRange,
    WaveformInstantaneousFrequency,
    WaveformInstantaneousMethod,
    WaveformInterpolationMethod,
    WaveformMelSpectrogram,
    WaveformPaddingStrategy,
    WaveformPeak,
    WaveformPeakWithProminence,
    WaveformPSDScaling,
    WaveformSpectralFeatures,
    WaveformSpectrogram,
    WaveformSpectrogramScaling,
    WaveformSpectrum,
    WaveformTimeLag,
    WaveformTrigger,
    WaveformTriggerEvent,
    WaveformTriggerType,
    WaveformWindowTriggerType,
    WaveformWindowType,
    WaveformWithEvents,
    WaveformZeroCrossing,
    WaveformZeroCrossingDirection,
)
from math_tools.waveforms.waveform1d import Waveform1D
from math_tools.waveforms.waveform_position import PositionComponentWaveforms, WaveformPosition

__all__ = [
    "PositionComponentWaveforms",
    "Waveform1D",
    "WaveformPosition",
    "WaveformAlignmentMethod",
    "WaveformEdgeType",
    "WaveformEventMarker",
    "WaveformFilterCoefficients",
    "WaveformFilterType",
    "WaveformFrequencyRange",
    "WaveformInstantaneousFrequency",
    "WaveformInstantaneousMethod",
    "WaveformInterpolationMethod",
    "WaveformMelSpectrogram",
    "WaveformPaddingStrategy",
    "WaveformPeak",
    "WaveformPeakWithProminence",
    "WaveformPSDScaling",
    "WaveformSpectralFeatures",
    "WaveformSpectrogram",
    "WaveformSpectrogramScaling",
    "WaveformSpectrum",
    "WaveformTimeLag",
    "WaveformTrigger",
    "WaveformTriggerEvent",
    "WaveformTriggerType",
    "WaveformWindowTriggerType",
    "WaveformWindowType",
    "WaveformWithEvents",
    "WaveformZeroCrossing",
    "WaveformZeroCrossingDirection",
]
