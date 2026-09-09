"""Attosecond-exact time interval, the Tier-3 subclass of
``PrecisionTimeIntervalABC``.

See ``.claude/specs/precisionTimeMath.md`` (§Representation,
§PrecisionTimeInterval). Storage is a single signed Python ``int`` of total
attoseconds (exact, unbounded); the ABC's ``(seconds, attoseconds, sign)``
triple is derived on access. Unlike the Swift source, there is no
saturating/wrapping arithmetic — Python ints are unbounded and exact
(mathToolsArchitecture.md non-goal 3).
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, ClassVar, overload

from foundation_abc.math.mathEnums import NumericSign
from foundation_abc.math.precisionTimeABC import (
    ATTOSECONDS_PER_SECOND,
    PrecisionTimeIntervalABC,
)


class PrecisionTimeInterval(PrecisionTimeIntervalABC):
    """An immutable, hashable, attosecond-exact time interval.

    Internally stored as a single signed total-attosecond ``int``; every
    arithmetic operation returns a new instance. Foreign operand types raise
    ``TypeError`` (via ``NotImplemented`` and Python's fallback protocol).
    """

    __slots__ = ("_total_atto",)

    ZERO: ClassVar[PrecisionTimeInterval]
    ONE_SECOND: ClassVar[PrecisionTimeInterval]
    ONE_DECISECOND: ClassVar[PrecisionTimeInterval]
    ONE_MILLISECOND: ClassVar[PrecisionTimeInterval]
    ONE_MICROSECOND: ClassVar[PrecisionTimeInterval]

    # MARK: - Construction

    def __init__(
        self,
        seconds: int = 0,
        attoseconds: int = 0,
        sign: NumericSign = NumericSign.POSITIVE,
    ) -> None:
        """Construct from an unsigned ``(seconds, attoseconds)`` magnitude and sign.

        Attosecond overflow (``attoseconds >= ATTOSECONDS_PER_SECOND``)
        carries into seconds. The resulting sign is always derived from the
        normalized magnitude: zero magnitude is always ``NumericSign.ZERO``
        regardless of the ``sign`` argument (single source of truth — the
        stored total is the only state).

        Raises:
            ValueError: If ``seconds`` or ``attoseconds`` is negative (both
                are unsigned magnitude components).
        """
        if seconds < 0:
            raise ValueError(f"seconds must be a non-negative magnitude, got {seconds}")
        if attoseconds < 0:
            raise ValueError(f"attoseconds must be a non-negative magnitude, got {attoseconds}")
        carry_seconds, normalized_attoseconds = divmod(attoseconds, ATTOSECONDS_PER_SECOND)
        magnitude = (seconds + carry_seconds) * ATTOSECONDS_PER_SECOND + normalized_attoseconds
        self._total_atto = -magnitude if sign == NumericSign.NEGATIVE else magnitude

    @classmethod
    def from_seconds(cls, seconds: float | int) -> PrecisionTimeInterval:
        """Construct from a (possibly fractional) number of seconds.

        The float path converts via an exact ``Fraction`` of the float64
        value, then rounds to the nearest attosecond — no more precision is
        lost than is already inherent in the float64 representation.
        """
        if isinstance(seconds, int):
            return cls.from_attoseconds(seconds * ATTOSECONDS_PER_SECOND)
        if not math.isfinite(seconds):
            raise ValueError(f"seconds must be finite, got {seconds}")
        total_attoseconds = round(Fraction(seconds) * ATTOSECONDS_PER_SECOND)
        return cls.from_attoseconds(total_attoseconds)

    @classmethod
    def from_attoseconds(cls, total: int) -> PrecisionTimeInterval:
        """Construct from a signed total-attosecond count."""
        if total == 0:
            return cls(seconds=0, attoseconds=0, sign=NumericSign.ZERO)
        sign = NumericSign.POSITIVE if total > 0 else NumericSign.NEGATIVE
        seconds, attoseconds = divmod(abs(total), ATTOSECONDS_PER_SECOND)
        return cls(seconds=seconds, attoseconds=attoseconds, sign=sign)

    @classmethod
    def from_string(cls, seconds: str, fractional: str) -> PrecisionTimeInterval:
        """Lossless decimal-string constructor.

        ``fractional`` is right-padded to 18 digits (attosecond precision).

        Raises:
            ValueError: If ``fractional`` has more than 18 digits, or either
                string is non-numeric.
        """
        seconds_text = seconds.strip()
        is_negative = seconds_text.startswith("-")
        if is_negative:
            seconds_text = seconds_text[1:]
        if not seconds_text.isdigit():
            raise ValueError(f"invalid seconds string: {seconds!r}")

        fractional_text = fractional.strip()
        if fractional_text and not fractional_text.isdigit():
            raise ValueError(f"invalid fractional string: {fractional!r}")
        if len(fractional_text) > 18:
            raise ValueError(
                f"fractional string exceeds attosecond precision (18 digits): {fractional!r}"
            )
        padded_fractional = fractional_text.ljust(18, "0")

        seconds_value = int(seconds_text)
        attoseconds_value = int(padded_fractional)
        sign = (
            NumericSign.NEGATIVE
            if is_negative and (seconds_value or attoseconds_value)
            else NumericSign.POSITIVE
        )
        return cls(seconds=seconds_value, attoseconds=attoseconds_value, sign=sign)

    @classmethod
    def from_dict(cls, obj: Any) -> PrecisionTimeInterval:
        """Construct from the ABC wire shape ``{"seconds", "attoseconds", "sign"}``."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        sign_value = obj["sign"]
        sign = NumericSign(sign_value) if isinstance(sign_value, str) else sign_value
        if not isinstance(sign, NumericSign):
            raise TypeError(f"expected a NumericSign or str, got {type(sign_value).__name__}")
        return cls(
            seconds=int(obj["seconds"]),
            attoseconds=int(obj["attoseconds"]),
            sign=sign,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the ABC wire shape ``{"attoseconds", "seconds", "sign"}``.

        Emits exactly what ``foundationTypes`` ``PrecisionTimeIntervalType.to_dict()``
        emits (``sign`` as its string value), so the payload round-trips through
        either carrier.
        """
        return {
            "attoseconds": self.attoseconds,
            "seconds": self.seconds,
            "sign": self.sign.value,
        }

    # MARK: - Properties (ABC-required)

    @property
    def seconds(self) -> int:
        return abs(self._total_atto) // ATTOSECONDS_PER_SECOND

    @property
    def attoseconds(self) -> int:
        return abs(self._total_atto) % ATTOSECONDS_PER_SECOND

    @property
    def sign(self) -> NumericSign:
        if self._total_atto == 0:
            return NumericSign.ZERO
        return NumericSign.POSITIVE if self._total_atto > 0 else NumericSign.NEGATIVE

    # MARK: - Accessors (beyond the ABC)

    @property
    def total_attoseconds(self) -> int:
        """The signed total-attosecond count (the type's canonical storage)."""
        return self._total_atto

    @property
    def seconds_as_float(self) -> float:
        """This interval's duration in seconds, as a (lossy) float."""
        return self._total_atto / ATTOSECONDS_PER_SECOND

    @property
    def is_zero(self) -> bool:
        """Whether this interval is exactly zero."""
        return self._total_atto == 0

    # MARK: - Arithmetic

    def __add__(self, other: PrecisionTimeInterval) -> PrecisionTimeInterval:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return PrecisionTimeInterval.from_attoseconds(self._total_atto + other._total_atto)

    def __sub__(self, other: PrecisionTimeInterval) -> PrecisionTimeInterval:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return PrecisionTimeInterval.from_attoseconds(self._total_atto - other._total_atto)

    def __neg__(self) -> PrecisionTimeInterval:
        return PrecisionTimeInterval.from_attoseconds(-self._total_atto)

    def __pos__(self) -> PrecisionTimeInterval:
        return PrecisionTimeInterval.from_attoseconds(self._total_atto)

    def __abs__(self) -> PrecisionTimeInterval:
        return PrecisionTimeInterval.from_attoseconds(abs(self._total_atto))

    def __mul__(self, other: int | float) -> PrecisionTimeInterval:
        if isinstance(other, int):
            return PrecisionTimeInterval.from_attoseconds(self._total_atto * other)
        if isinstance(other, float):
            product = Fraction(self._total_atto) * Fraction(other)
            return PrecisionTimeInterval.from_attoseconds(round(product))
        return NotImplemented

    def __rmul__(self, other: int | float) -> PrecisionTimeInterval:
        return self.__mul__(other)

    @overload
    def __truediv__(self, other: PrecisionTimeInterval) -> float: ...
    @overload
    def __truediv__(self, other: int | float) -> PrecisionTimeInterval: ...

    def __truediv__(
        self, other: PrecisionTimeInterval | int | float
    ) -> PrecisionTimeInterval | float:
        if isinstance(other, PrecisionTimeInterval):
            if other._total_atto == 0:
                raise ZeroDivisionError("division by a zero-length PrecisionTimeInterval")
            return self._total_atto / other._total_atto
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("division by zero")
            quotient = Fraction(self._total_atto) / Fraction(other)
            return PrecisionTimeInterval.from_attoseconds(round(quotient))
        return NotImplemented

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return self._total_atto == other._total_atto

    def __lt__(self, other: PrecisionTimeInterval) -> bool:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return self._total_atto < other._total_atto

    def __le__(self, other: PrecisionTimeInterval) -> bool:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return self._total_atto <= other._total_atto

    def __gt__(self, other: PrecisionTimeInterval) -> bool:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return self._total_atto > other._total_atto

    def __ge__(self, other: PrecisionTimeInterval) -> bool:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return self._total_atto >= other._total_atto

    def __hash__(self) -> int:
        return hash(self._total_atto)

    def __bool__(self) -> bool:
        return not self.is_zero

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(seconds={self.seconds}, "
            f"attoseconds={self.attoseconds}, sign={self.sign.name})"
        )


PrecisionTimeInterval.ZERO = PrecisionTimeInterval()
PrecisionTimeInterval.ONE_SECOND = PrecisionTimeInterval(seconds=1)
PrecisionTimeInterval.ONE_DECISECOND = PrecisionTimeInterval(
    attoseconds=ATTOSECONDS_PER_SECOND // 10
)
PrecisionTimeInterval.ONE_MILLISECOND = PrecisionTimeInterval(
    attoseconds=ATTOSECONDS_PER_SECOND // 1_000
)
PrecisionTimeInterval.ONE_MICROSECOND = PrecisionTimeInterval(
    attoseconds=ATTOSECONDS_PER_SECOND // 1_000_000
)
