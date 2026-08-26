"""Exception hierarchy for domain failures raised by ``math_tools``.

Programmer errors (wrong type, wrong shape, invalid argument) raise stdlib
``TypeError``/``ValueError``; domain failures raise a ``MathToolsError``
subtype defined here (see mathToolsArchitecture.md §Error semantics).
"""


class MathToolsError(Exception):
    """Base class for all domain-level errors raised by math_tools."""


class WaveformCompatibilityError(MathToolsError):
    """Raised when waveform operands are incompatible (dt/shape mismatch)."""


class TimestampComparisonError(MathToolsError):
    """Raised when comparing timestamps with mismatched timescale/frame."""


class PolynomialSolveError(MathToolsError):
    """Raised when a polynomial root request is unsolvable or ill-posed."""
