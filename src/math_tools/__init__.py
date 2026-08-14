"""``math_tools``: Tier-3 numpy-backed math implementation layer.

Curated root re-exports so ``import math_tools as mt`` is coherent. Consumers
needing the wider per-subpackage surface (DSP support types, OTG enums,
polynomial solver helpers, ...) import from the subpackage directly, e.g.
``from math_tools.waveforms import WaveformSpectrum``.

See ``.claude/specs/mathToolsArchitecture.md`` §Shared conventions (Public
surface). This module contains re-exports only -- no logic.
"""

from math_tools.errors import (
    MathToolsError,
    PolynomialSolveError,
    TimestampComparisonError,
    WaveformCompatibilityError,
)
from math_tools.functional import UnivariatePolynomial
from math_tools.otg import InputParameter, Otg, OutputParameter, Result, Trajectory
from math_tools.precision_time import PrecisionTimeInterval, PrecisionTimestamp
from math_tools.spatial import Position, Quaternion, SpatialPose
from math_tools.waveforms import (
    Waveform1D,
    WaveformPosition,
    WaveformQuaternion,
    WaveformSpatialPose,
)

__all__ = [
    "Position",
    "Quaternion",
    "SpatialPose",
    "PrecisionTimeInterval",
    "PrecisionTimestamp",
    "Waveform1D",
    "WaveformPosition",
    "WaveformQuaternion",
    "WaveformSpatialPose",
    "UnivariatePolynomial",
    "Otg",
    "InputParameter",
    "OutputParameter",
    "Trajectory",
    "Result",
    "MathToolsError",
    "WaveformCompatibilityError",
    "TimestampComparisonError",
    "PolynomialSolveError",
]
