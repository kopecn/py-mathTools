"""Small helpers shared by two or more DSP mixins.

See ``.claude/specs/waveformDsp.md`` §Organization ("shared helpers live in
``dsp/_common.py``"). Starts minimal -- only what chunk 14 itself needs;
later mixin chunks add to this module rather than duplicating logic or
importing a sibling mixin.
"""

from __future__ import annotations

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval


def float_seconds(interval: PrecisionTimeInterval) -> float:
    """``interval`` as float seconds (thin wrapper over ``seconds_as_float``)."""
    return interval.seconds_as_float


# Single source for the Kaiser-window shape parameter used by both
# ``dsp/_windowing.py`` (user-facing window utilities) and ``dsp/_spectral.py``
# (internal STFT/PSD window arrays). Before chunk 53 each module hardcoded its
# own ``14.0`` literal independently -- individually defensible but with no
# test pinning them equal and no shared source, so the two could silently
# drift apart. ``WaveformWindowType`` is a flat ``str`` enum with no ``beta``
# field (unlike the Swift reference's ``.kaiser(beta:)`` associated value),
# so exposing a caller-supplied beta would force an enum redesign; per
# waveformDsp.md's window-convention section this chunk keeps the flat enum
# and records the narrowed capability here rather than reopening the enum
# shape. 14.0 gives comparable sidelobe suppression to a Blackman window.
DEFAULT_KAISER_BETA = 14.0

__all__ = ["float_seconds", "DEFAULT_KAISER_BETA"]
