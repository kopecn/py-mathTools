"""Attosecond-exact, epoch-referenced timestamp, the Tier-3 subclass of
``PrecisionTimestampABC``.

See ``.claude/specs/precisionTimeMath.md`` (§PrecisionTimestamp). Storage is a
``PrecisionTimeInterval`` offset from the Unix epoch (1970-01-01 00:00:00 UTC)
plus optional ``timescale``/``reference_frame``/``uncertainty`` metadata, which
is carried (never interpreted) and included in equality/hash.
"""

from __future__ import annotations

import datetime
from fractions import Fraction
from typing import Any, ClassVar, overload

from foundation_abc.math.mathEnums import NumericSign, ReferenceFrame, Timescale
from foundation_abc.math.precisionTimeABC import (
    ATTOSECONDS_PER_SECOND,
    PrecisionTimestampABC,
)

from math_tools.errors import TimestampComparisonError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval

_SECONDS_PER_DAY = 86_400
_ATTOSECONDS_PER_MICROSECOND = ATTOSECONDS_PER_SECOND // 1_000_000
_UNIX_EPOCH_UTC = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


class PrecisionTimestamp(PrecisionTimestampABC):
    """An immutable, hashable, attosecond-exact point in time.

    Represented internally as a signed ``PrecisionTimeInterval`` offset from
    the Unix epoch, plus optional metadata. Every operation returns a new
    instance; foreign operand types raise ``TypeError`` (via ``NotImplemented``
    and Python's fallback protocol).
    """

    __slots__ = ("_interval", "_timescale", "_reference_frame", "_uncertainty")

    EPOCH: ClassVar[PrecisionTimestamp]

    # MARK: - Construction

    def __init__(
        self,
        seconds: int = 0,
        attoseconds: int = 0,
        sign: NumericSign = NumericSign.POSITIVE,
        *,
        timescale: Timescale | None = None,
        reference_frame: ReferenceFrame | None = None,
        uncertainty: int | None = None,
    ) -> None:
        """Construct from an unsigned ``(seconds, attoseconds)`` magnitude and
        sign, offset from the Unix epoch, plus optional metadata.

        Raises:
            ValueError: If ``seconds``/``attoseconds`` is negative (see
                ``PrecisionTimeInterval``), or ``uncertainty`` is negative.
        """
        if uncertainty is not None and uncertainty < 0:
            raise ValueError(f"uncertainty must be a non-negative magnitude, got {uncertainty}")
        self._interval = PrecisionTimeInterval(seconds=seconds, attoseconds=attoseconds, sign=sign)
        self._timescale = timescale
        self._reference_frame = reference_frame
        self._uncertainty = uncertainty

    @classmethod
    def from_interval(
        cls,
        interval: PrecisionTimeInterval,
        *,
        timescale: Timescale | None = None,
        reference_frame: ReferenceFrame | None = None,
        uncertainty: int | None = None,
    ) -> PrecisionTimestamp:
        """Construct from a ``PrecisionTimeInterval`` offset from the epoch."""
        return cls(
            seconds=interval.seconds,
            attoseconds=interval.attoseconds,
            sign=interval.sign,
            timescale=timescale,
            reference_frame=reference_frame,
            uncertainty=uncertainty,
        )

    @classmethod
    def from_datetime(
        cls,
        dt: datetime.datetime,
        *,
        timescale: Timescale | None = None,
        reference_frame: ReferenceFrame | None = None,
        uncertainty: int | None = None,
    ) -> PrecisionTimestamp:
        """Construct from a timezone-aware ``datetime`` (pre-epoch supported).

        Converts to UTC and computes the exact integer microsecond offset from
        the Unix epoch (``datetime`` subtraction is exact; no float involved).

        Raises:
            ValueError: If ``dt`` is naive (no timezone).
        """
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("from_datetime requires a timezone-aware datetime")
        dt_utc = dt.astimezone(datetime.timezone.utc)
        delta = dt_utc - _UNIX_EPOCH_UTC
        total_microseconds = (
            delta.days * _SECONDS_PER_DAY * 1_000_000
            + delta.seconds * 1_000_000
            + delta.microseconds
        )
        total_attoseconds = total_microseconds * _ATTOSECONDS_PER_MICROSECOND
        interval = PrecisionTimeInterval.from_attoseconds(total_attoseconds)
        return cls.from_interval(
            interval,
            timescale=timescale,
            reference_frame=reference_frame,
            uncertainty=uncertainty,
        )

    @classmethod
    def now(
        cls,
        *,
        timescale: Timescale | None = None,
        reference_frame: ReferenceFrame | None = None,
        uncertainty: int | None = None,
    ) -> PrecisionTimestamp:
        """Construct from the current wall-clock time (UTC)."""
        return cls.from_datetime(
            datetime.datetime.now(datetime.timezone.utc),
            timescale=timescale,
            reference_frame=reference_frame,
            uncertainty=uncertainty,
        )

    @classmethod
    def from_days(
        cls,
        days_since_epoch: int,
        attoseconds_of_day: int = 0,
        sign: NumericSign = NumericSign.POSITIVE,
        *,
        timescale: Timescale | None = None,
        reference_frame: ReferenceFrame | None = None,
        uncertainty: int | None = None,
    ) -> PrecisionTimestamp:
        """Construct from a whole-day count plus an attosecond offset within
        that day.

        Raises:
            ValueError: If ``days_since_epoch`` or ``attoseconds_of_day`` is
                negative (both are unsigned magnitude components).
        """
        if days_since_epoch < 0:
            raise ValueError(
                f"days_since_epoch must be a non-negative magnitude, got {days_since_epoch}"
            )
        if attoseconds_of_day < 0:
            raise ValueError(
                f"attoseconds_of_day must be a non-negative magnitude, got {attoseconds_of_day}"
            )
        carry_seconds, remaining_attoseconds = divmod(attoseconds_of_day, ATTOSECONDS_PER_SECOND)
        total_seconds = days_since_epoch * _SECONDS_PER_DAY + carry_seconds
        return cls(
            seconds=total_seconds,
            attoseconds=remaining_attoseconds,
            sign=sign,
            timescale=timescale,
            reference_frame=reference_frame,
            uncertainty=uncertainty,
        )

    @classmethod
    def from_dict(cls, obj: Any) -> PrecisionTimestamp:
        """Construct from the ABC wire shape (camelCase optional keys)."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        sign_value = obj["sign"]
        sign = NumericSign(sign_value) if isinstance(sign_value, str) else sign_value
        if not isinstance(sign, NumericSign):
            raise TypeError(f"expected a NumericSign or str, got {type(sign_value).__name__}")

        reference_frame_value = obj.get("referenceFrame")
        reference_frame: ReferenceFrame | None = None
        if reference_frame_value is not None:
            reference_frame = (
                ReferenceFrame(reference_frame_value)
                if isinstance(reference_frame_value, str)
                else reference_frame_value
            )

        timescale_value = obj.get("timescale")
        timescale: Timescale | None = None
        if timescale_value is not None:
            timescale = (
                Timescale(timescale_value) if isinstance(timescale_value, str) else timescale_value
            )

        uncertainty_value = obj.get("uncertainty")
        uncertainty = int(uncertainty_value) if uncertainty_value is not None else None

        return cls(
            seconds=int(obj["seconds"]),
            attoseconds=int(obj["attoseconds"]),
            sign=sign,
            timescale=timescale,
            reference_frame=reference_frame,
            uncertainty=uncertainty,
        )

    # MARK: - Properties (ABC-required)

    @property
    def seconds(self) -> int:
        return self._interval.seconds

    @property
    def attoseconds(self) -> int:
        return self._interval.attoseconds

    @property
    def sign(self) -> NumericSign:
        return self._interval.sign

    @property
    def timescale(self) -> Timescale | None:
        return self._timescale

    @property
    def reference_frame(self) -> ReferenceFrame | None:
        return self._reference_frame

    @property
    def uncertainty(self) -> int | None:
        return self._uncertainty

    # MARK: - Accessors (beyond the ABC)

    @property
    def interval(self) -> PrecisionTimeInterval:
        """This timestamp's signed offset from the Unix epoch."""
        return self._interval

    @property
    def days_since_epoch(self) -> int:
        """Whole days since the Unix epoch (magnitude only)."""
        return self.seconds // _SECONDS_PER_DAY

    @property
    def seconds_of_day(self) -> int:
        """Seconds within the current day (0 .. 86_399, magnitude only)."""
        return self.seconds % _SECONDS_PER_DAY

    @property
    def as_datetime(self) -> datetime.datetime:
        """This timestamp as a UTC ``datetime``, lossy to microseconds.

        Rounds to the nearest microsecond (half-to-even, matching the
        interval's scalar-rounding convention) when the underlying offset
        isn't already microsecond-aligned.
        """
        microseconds_total = round(
            Fraction(self._interval.total_attoseconds, _ATTOSECONDS_PER_MICROSECOND)
        )
        return _UNIX_EPOCH_UTC + datetime.timedelta(microseconds=microseconds_total)

    # MARK: - Arithmetic

    def __add__(self, other: PrecisionTimeInterval) -> PrecisionTimestamp:
        if not isinstance(other, PrecisionTimeInterval):
            return NotImplemented
        return PrecisionTimestamp.from_interval(
            self._interval + other,
            timescale=self._timescale,
            reference_frame=self._reference_frame,
            uncertainty=self._uncertainty,
        )

    def __radd__(self, other: PrecisionTimeInterval) -> PrecisionTimestamp:
        return self.__add__(other)

    @overload
    def __sub__(self, other: PrecisionTimestamp) -> PrecisionTimeInterval: ...
    @overload
    def __sub__(self, other: PrecisionTimeInterval) -> PrecisionTimestamp: ...

    def __sub__(
        self, other: PrecisionTimestamp | PrecisionTimeInterval
    ) -> PrecisionTimeInterval | PrecisionTimestamp:
        if isinstance(other, PrecisionTimestamp):
            return self._interval - other._interval
        if isinstance(other, PrecisionTimeInterval):
            return PrecisionTimestamp.from_interval(
                self._interval - other,
                timescale=self._timescale,
                reference_frame=self._reference_frame,
                uncertainty=self._uncertainty,
            )
        return NotImplemented

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrecisionTimestamp):
            return NotImplemented
        return (
            self._interval == other._interval
            and self._timescale == other._timescale
            and self._reference_frame == other._reference_frame
            and self._uncertainty == other._uncertainty
        )

    def __lt__(self, other: PrecisionTimestamp) -> bool:
        if not isinstance(other, PrecisionTimestamp):
            return NotImplemented
        return self._interval < other._interval

    def __le__(self, other: PrecisionTimestamp) -> bool:
        if not isinstance(other, PrecisionTimestamp):
            return NotImplemented
        return self._interval <= other._interval

    def __gt__(self, other: PrecisionTimestamp) -> bool:
        if not isinstance(other, PrecisionTimestamp):
            return NotImplemented
        return self._interval > other._interval

    def __ge__(self, other: PrecisionTimestamp) -> bool:
        if not isinstance(other, PrecisionTimestamp):
            return NotImplemented
        return self._interval >= other._interval

    def __hash__(self) -> int:
        return hash((self._interval, self._timescale, self._reference_frame, self._uncertainty))

    def can_compare(self, other: PrecisionTimestamp) -> bool:
        """Whether ``self`` and ``other`` are safe to compare.

        ``False`` only when both sides specify a ``timescale`` and they
        differ, or both specify a ``reference_frame`` and they differ. A
        ``None`` on either side is compatible with anything. Uncertainty is
        NOT part of this check (Swift parity: ``canCompare(to:)``).
        """
        if (
            self._timescale is not None
            and other._timescale is not None
            and self._timescale != other._timescale
        ):
            return False
        if (
            self._reference_frame is not None
            and other._reference_frame is not None
            and self._reference_frame != other._reference_frame
        ):
            return False
        return True

    def compare_validated(self, other: PrecisionTimestamp) -> int:
        """Validated three-way comparison: -1/0/1.

        Raises:
            TimestampComparisonError: If both sides specify differing
                timescales, both specify differing reference frames, or both
                carry ``uncertainty`` and the absolute offset difference is
                less than or equal to the sum of the two uncertainties
                (overlap; boundary equality raises).
        """
        if (
            self._timescale is not None
            and other._timescale is not None
            and self._timescale != other._timescale
        ):
            raise TimestampComparisonError(
                f"incompatible timescale: {self._timescale} vs {other._timescale}"
            )
        if (
            self._reference_frame is not None
            and other._reference_frame is not None
            and self._reference_frame != other._reference_frame
        ):
            raise TimestampComparisonError(
                f"incompatible reference frame: {self._reference_frame} vs {other._reference_frame}"
            )
        if self._uncertainty is not None and other._uncertainty is not None:
            delta = abs(self._interval - other._interval)
            combined = PrecisionTimeInterval.from_attoseconds(
                self._uncertainty
            ) + PrecisionTimeInterval.from_attoseconds(other._uncertainty)
            if delta <= combined:
                raise TimestampComparisonError("overlapping uncertainty windows")

        if self._interval < other._interval:
            return -1
        if self._interval > other._interval:
            return 1
        return 0

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(seconds={self.seconds}, attoseconds={self.attoseconds}, "
            f"sign={self.sign.name}, timescale={self._timescale}, "
            f"reference_frame={self._reference_frame}, uncertainty={self._uncertainty})"
        )


PrecisionTimestamp.EPOCH = PrecisionTimestamp()
