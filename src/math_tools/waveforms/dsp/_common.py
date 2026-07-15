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


__all__ = ["float_seconds"]
