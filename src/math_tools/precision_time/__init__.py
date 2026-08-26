"""Precision time math types: attosecond-exact intervals and timestamps.

See ``.claude/specs/precisionTimeMath.md``.
"""

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp

__all__ = ["PrecisionTimeInterval", "PrecisionTimestamp"]
