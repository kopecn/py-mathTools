"""Unit tests for ``PrecisionTimestamp``.

Covers precisionTimeMath.md §Compliance requirements 1 (timestamp half), 7, 8,
9, 10, plus construction, accessors, arithmetic, ordering, hash/eq-with-metadata,
and serialization round-trip.
"""

import datetime
import unittest
from typing import Any

from foundation_abc.math.mathEnums import NumericSign, ReferenceFrame, Timescale
from foundation_abc.math.precisionTimeABC import (
    ATTOSECONDS_PER_SECOND,
    PrecisionTimestampABC,
)
from foundationTypes.mathTypes.MathTypes import PrecisionTimestampType

from math_tools.errors import TimestampComparisonError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp


class TestConstruction(unittest.TestCase):
    def test_default_is_epoch(self) -> None:
        ts = PrecisionTimestamp()
        self.assertEqual(ts.seconds, 0)
        self.assertEqual(ts.attoseconds, 0)
        self.assertEqual(ts.sign, NumericSign.ZERO)
        self.assertIsNone(ts.timescale)
        self.assertIsNone(ts.reference_frame)
        self.assertIsNone(ts.uncertainty)

    def test_basic_seconds_and_attoseconds(self) -> None:
        ts = PrecisionTimestamp(seconds=5, attoseconds=250, sign=NumericSign.POSITIVE)
        self.assertEqual(ts.seconds, 5)
        self.assertEqual(ts.attoseconds, 250)
        self.assertEqual(ts.sign, NumericSign.POSITIVE)

    def test_metadata_kwargs(self) -> None:
        ts = PrecisionTimestamp(
            seconds=1,
            timescale=Timescale.TAI,
            reference_frame=ReferenceFrame.EARTH_CENTER,
            uncertainty=10,
        )
        self.assertEqual(ts.timescale, Timescale.TAI)
        self.assertEqual(ts.reference_frame, ReferenceFrame.EARTH_CENTER)
        self.assertEqual(ts.uncertainty, 10)


class TestFromInterval(unittest.TestCase):
    def test_from_interval_basic(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(5)
        ts = PrecisionTimestamp.from_interval(interval)
        self.assertEqual(ts.interval, interval)

    def test_from_interval_with_metadata(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(5)
        ts = PrecisionTimestamp.from_interval(interval, timescale=Timescale.UTC)
        self.assertEqual(ts.timescale, Timescale.UTC)

    def test_from_interval_negative(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(-5)
        ts = PrecisionTimestamp.from_interval(interval)
        self.assertEqual(ts.sign, NumericSign.NEGATIVE)
        self.assertEqual(ts.seconds, 5)


class TestFromDatetime(unittest.TestCase):
    def test_naive_datetime_raises(self) -> None:
        naive = datetime.datetime(2020, 1, 1)
        with self.assertRaises(ValueError):
            PrecisionTimestamp.from_datetime(naive)

    def test_aware_datetime_after_epoch(self) -> None:
        dt = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        ts = PrecisionTimestamp.from_datetime(dt)
        self.assertEqual(ts.sign, NumericSign.POSITIVE)
        expected_seconds = int(dt.timestamp())
        self.assertEqual(ts.seconds, expected_seconds)

    def test_aware_datetime_pre_epoch(self) -> None:
        dt = datetime.datetime(1960, 1, 1, tzinfo=datetime.timezone.utc)
        ts = PrecisionTimestamp.from_datetime(dt)
        self.assertEqual(ts.sign, NumericSign.NEGATIVE)

    def test_aware_datetime_non_utc_tz(self) -> None:
        tz = datetime.timezone(datetime.timedelta(hours=5))
        dt = datetime.datetime(2020, 1, 1, tzinfo=tz)
        ts = PrecisionTimestamp.from_datetime(dt)
        expected = datetime.datetime(2020, 1, 1, tzinfo=tz).astimezone(datetime.timezone.utc)
        self.assertEqual(ts.seconds, int(expected.timestamp()))


class TestNow(unittest.TestCase):
    def test_now_is_after_epoch(self) -> None:
        ts = PrecisionTimestamp.now()
        self.assertTrue(ts.is_after_epoch)

    def test_now_carries_metadata(self) -> None:
        ts = PrecisionTimestamp.now(timescale=Timescale.TAI)
        self.assertEqual(ts.timescale, Timescale.TAI)


class TestFromDays(unittest.TestCase):
    def test_from_days_basic(self) -> None:
        ts = PrecisionTimestamp.from_days(1)
        self.assertEqual(ts.seconds, 86_400)

    def test_from_days_with_attoseconds_of_day(self) -> None:
        ts = PrecisionTimestamp.from_days(1, attoseconds_of_day=ATTOSECONDS_PER_SECOND * 5)
        self.assertEqual(ts.seconds, 86_405)

    def test_from_days_negative_sign(self) -> None:
        ts = PrecisionTimestamp.from_days(1, sign=NumericSign.NEGATIVE)
        self.assertEqual(ts.sign, NumericSign.NEGATIVE)
        self.assertEqual(ts.seconds, 86_400)


class TestEpochConstant(unittest.TestCase):
    def test_epoch_is_epoch(self) -> None:
        """Acceptance: EPOCH.is_epoch is True."""
        self.assertTrue(PrecisionTimestamp.EPOCH.is_epoch)

    def test_epoch_has_no_metadata(self) -> None:
        self.assertIsNone(PrecisionTimestamp.EPOCH.timescale)
        self.assertIsNone(PrecisionTimestamp.EPOCH.reference_frame)
        self.assertIsNone(PrecisionTimestamp.EPOCH.uncertainty)


class TestAccessors(unittest.TestCase):
    def test_days_since_epoch(self) -> None:
        ts = PrecisionTimestamp(seconds=86_400 * 3 + 10)
        self.assertEqual(ts.days_since_epoch, 3)

    def test_seconds_of_day(self) -> None:
        ts = PrecisionTimestamp(seconds=86_400 * 3 + 10)
        self.assertEqual(ts.seconds_of_day, 10)

    def test_as_datetime_round_trip_to_microsecond(self) -> None:
        """Compliance 9: as_datetime/from_datetime round-trips to microsecond
        precision."""
        dt = datetime.datetime(2020, 6, 15, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc)
        ts = PrecisionTimestamp.from_datetime(dt)
        self.assertEqual(ts.as_datetime, dt)

    def test_as_datetime_round_trip_pre_epoch(self) -> None:
        """Compliance 9: round-trip including a pre-epoch instant."""
        dt = datetime.datetime(1955, 11, 12, 6, 0, 0, 654321, tzinfo=datetime.timezone.utc)
        ts = PrecisionTimestamp.from_datetime(dt)
        self.assertEqual(ts.as_datetime, dt)

    def test_as_datetime_is_utc(self) -> None:
        ts = PrecisionTimestamp.EPOCH
        self.assertEqual(ts.as_datetime.tzinfo, datetime.timezone.utc)


class TestArithmetic(unittest.TestCase):
    def test_timestamp_plus_interval(self) -> None:
        ts = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(5))
        result = ts + PrecisionTimeInterval.from_seconds(3)
        self.assertEqual(result.seconds, 8)

    def test_interval_plus_timestamp(self) -> None:
        ts = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(5))
        result = PrecisionTimeInterval.from_seconds(3) + ts
        self.assertEqual(result.seconds, 8)

    def test_timestamp_minus_interval(self) -> None:
        ts = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(5))
        result = ts - PrecisionTimeInterval.from_seconds(3)
        self.assertEqual(result.seconds, 2)

    def test_timestamp_minus_timestamp_is_interval(self) -> None:
        a = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(5))
        b = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(3))
        result = a - b
        self.assertIsInstance(result, PrecisionTimeInterval)
        self.assertEqual(result, PrecisionTimeInterval.from_seconds(2))

    def test_timestamp_minus_timestamp_across_epoch_is_exact(self) -> None:
        """Compliance 7: timestamp - timestamp across the epoch (one
        pre-1970 operand) is exact."""
        after = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(5))
        before = PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(-3))
        result = after - before
        self.assertEqual(result, PrecisionTimeInterval.from_seconds(8))

    def test_metadata_carried_from_timestamp_on_add(self) -> None:
        """Metadata propagation on ts +/- interval: carried from the
        timestamp."""
        ts = PrecisionTimestamp(
            seconds=5,
            timescale=Timescale.TAI,
            reference_frame=ReferenceFrame.EARTH_CENTER,
            uncertainty=7,
        )
        result = ts + PrecisionTimeInterval.from_seconds(1)
        self.assertEqual(result.timescale, Timescale.TAI)
        self.assertEqual(result.reference_frame, ReferenceFrame.EARTH_CENTER)
        self.assertEqual(result.uncertainty, 7)

    def test_metadata_carried_from_timestamp_on_sub(self) -> None:
        ts = PrecisionTimestamp(seconds=5, timescale=Timescale.UTC)
        result = ts - PrecisionTimeInterval.from_seconds(1)
        self.assertEqual(result.timescale, Timescale.UTC)

    def test_metadata_carried_when_interval_plus_timestamp(self) -> None:
        ts = PrecisionTimestamp(seconds=5, timescale=Timescale.UTC)
        result = PrecisionTimeInterval.from_seconds(1) + ts
        self.assertEqual(result.timescale, Timescale.UTC)


class TestOrdering(unittest.TestCase):
    def test_equality_includes_metadata(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=1, timescale=Timescale.UTC)
        self.assertNotEqual(a, b)

    def test_equality_same_metadata(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        self.assertEqual(a, b)

    def test_equality_ignores_uncertainty_difference_fails(self) -> None:
        """Uncertainty IS part of eq's metadata per spec (all metadata
        included in hash/eq)."""
        a = PrecisionTimestamp(seconds=1, uncertainty=5)
        b = PrecisionTimestamp(seconds=1, uncertainty=6)
        self.assertNotEqual(a, b)

    def test_ordering_compares_offsets_only(self) -> None:
        """< / <= / > / >= compare offsets only (numeric ordering, ignoring
        metadata)."""
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=2, timescale=Timescale.UTC)
        self.assertTrue(a < b)
        self.assertTrue(b > a)
        self.assertTrue(a <= b)
        self.assertTrue(b >= a)

    def test_total_ordering_sortable(self) -> None:
        values = [
            PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(2)),
            PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(-1)),
            PrecisionTimestamp.from_interval(PrecisionTimeInterval.from_seconds(0)),
        ]
        ordered = sorted(values)
        self.assertEqual(
            [v.interval.total_attoseconds for v in ordered],
            [-ATTOSECONDS_PER_SECOND, 0, 2 * ATTOSECONDS_PER_SECOND],
        )


class TestCanCompare(unittest.TestCase):
    def test_both_none_metadata_can_compare(self) -> None:
        a = PrecisionTimestamp(seconds=1)
        b = PrecisionTimestamp(seconds=2)
        self.assertTrue(a.can_compare(b))

    def test_one_none_one_set_can_compare(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=2)
        self.assertTrue(a.can_compare(b))

    def test_same_timescale_can_compare(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=2, timescale=Timescale.TAI)
        self.assertTrue(a.can_compare(b))

    def test_differing_timescale_cannot_compare(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=2, timescale=Timescale.UTC)
        self.assertFalse(a.can_compare(b))

    def test_differing_reference_frame_cannot_compare(self) -> None:
        a = PrecisionTimestamp(seconds=1, reference_frame=ReferenceFrame.EARTH_CENTER)
        b = PrecisionTimestamp(seconds=2, reference_frame=ReferenceFrame.LUNAR_CENTER)
        self.assertFalse(a.can_compare(b))

    def test_can_compare_ignores_uncertainty(self) -> None:
        """can_compare is True when either side's metadata is None and
        ignores uncertainty entirely."""
        a = PrecisionTimestamp(seconds=1, uncertainty=1000)
        b = PrecisionTimestamp(seconds=1, uncertainty=1)
        self.assertTrue(a.can_compare(b))


class TestCompareValidated(unittest.TestCase):
    """Compliance 8: compare_validated raises TimestampComparisonError on
    differing timescale (both set), differing frame (both set), and
    overlapping uncertainty (both set, delta <= combined -- boundary case
    delta == combined raises). Returns -1/0/1 otherwise."""

    def test_returns_negative_one_when_less(self) -> None:
        a = PrecisionTimestamp(seconds=1)
        b = PrecisionTimestamp(seconds=2)
        self.assertEqual(a.compare_validated(b), -1)

    def test_returns_zero_when_equal(self) -> None:
        a = PrecisionTimestamp(seconds=1)
        b = PrecisionTimestamp(seconds=1)
        self.assertEqual(a.compare_validated(b), 0)

    def test_returns_positive_one_when_greater(self) -> None:
        a = PrecisionTimestamp(seconds=2)
        b = PrecisionTimestamp(seconds=1)
        self.assertEqual(a.compare_validated(b), 1)

    def test_raises_on_differing_timescale(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=2, timescale=Timescale.UTC)
        with self.assertRaises(TimestampComparisonError):
            a.compare_validated(b)

    def test_raises_on_differing_reference_frame(self) -> None:
        a = PrecisionTimestamp(seconds=1, reference_frame=ReferenceFrame.EARTH_CENTER)
        b = PrecisionTimestamp(seconds=2, reference_frame=ReferenceFrame.LUNAR_CENTER)
        with self.assertRaises(TimestampComparisonError):
            a.compare_validated(b)

    def test_raises_on_overlapping_uncertainty(self) -> None:
        a = PrecisionTimestamp(seconds=1, uncertainty=ATTOSECONDS_PER_SECOND)
        b = PrecisionTimestamp(seconds=2, uncertainty=ATTOSECONDS_PER_SECOND)
        with self.assertRaises(TimestampComparisonError):
            a.compare_validated(b)

    def test_boundary_delta_equals_combined_uncertainty_raises(self) -> None:
        """Pinned boundary: delta == combined uncertainty raises (not <)."""
        a = PrecisionTimestamp(seconds=1, uncertainty=1)
        b = PrecisionTimestamp(
            seconds=1, attoseconds=2, uncertainty=1
        )  # delta = 2 atto, combined = 2 atto
        with self.assertRaises(TimestampComparisonError):
            a.compare_validated(b)

    def test_delta_just_outside_combined_uncertainty_does_not_raise(self) -> None:
        a = PrecisionTimestamp(seconds=1, uncertainty=1)
        b = PrecisionTimestamp(
            seconds=1, attoseconds=3, uncertainty=1
        )  # delta = 3 atto, combined = 2 atto
        self.assertEqual(a.compare_validated(b), -1)

    def test_uncertainty_only_checked_when_both_set(self) -> None:
        a = PrecisionTimestamp(seconds=1, uncertainty=ATTOSECONDS_PER_SECOND * 100)
        b = PrecisionTimestamp(seconds=1, attoseconds=1)
        self.assertEqual(a.compare_validated(b), -1)


class TestHashability(unittest.TestCase):
    def test_hash_includes_metadata(self) -> None:
        a = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        b = PrecisionTimestamp(seconds=1, timescale=Timescale.TAI)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_usable_in_set(self) -> None:
        values = {
            PrecisionTimestamp(seconds=1, timescale=Timescale.TAI),
            PrecisionTimestamp(seconds=1, timescale=Timescale.TAI),
        }
        self.assertEqual(len(values), 1)


class TestNotImplementedFallback(unittest.TestCase):
    def test_equality_with_foreign_type_is_false(self) -> None:
        ts = PrecisionTimestamp(seconds=1)
        self.assertFalse(ts == 1.0)
        self.assertNotEqual(ts, object())

    def test_ordering_with_foreign_type_raises_type_error(self) -> None:
        ts = PrecisionTimestamp(seconds=1)
        with self.assertRaises(TypeError):
            _ = ts < 1.0  # type: ignore[operator]

    def test_addition_with_foreign_type_raises_type_error(self) -> None:
        ts = PrecisionTimestamp(seconds=1)
        with self.assertRaises(TypeError):
            ts + 1.0  # type: ignore[operator]

    def test_subtraction_with_foreign_type_raises_type_error(self) -> None:
        ts = PrecisionTimestamp(seconds=1)
        with self.assertRaises(TypeError):
            ts - "not valid"  # type: ignore[operator]


class TestIsinstanceAndAbc(unittest.TestCase):
    def test_isinstance_of_abc(self) -> None:
        """Compliance 10: isinstance(x, PrecisionTimestampABC)."""
        ts = PrecisionTimestamp(seconds=1)
        self.assertIsInstance(ts, PrecisionTimestampABC)


class TestSerializationRoundTrip(unittest.TestCase):
    """Compliance 1 (timestamp half): round-trip with PrecisionTimestampType
    wire dicts (camelCase optional keys)."""

    def _round_trip(self, payload: dict[str, Any]) -> None:
        wire = PrecisionTimestampType.from_dict(payload).to_dict()
        result = PrecisionTimestamp.from_dict(wire).to_dict()
        self.assertEqual(result, payload)

    def test_round_trip_minimal(self) -> None:
        self._round_trip({"attoseconds": 0, "seconds": 5, "sign": "positive"})

    def test_round_trip_with_all_metadata(self) -> None:
        self._round_trip(
            {
                "attoseconds": 123,
                "seconds": 5,
                "sign": "positive",
                "referenceFrame": "EarthCenter",
                "timescale": "TAI",
                "uncertainty": 42,
            }
        )

    def test_round_trip_negative(self) -> None:
        self._round_trip({"attoseconds": 1, "seconds": 0, "sign": "negative"})

    def test_from_dict_rejects_non_dict(self) -> None:
        with self.assertRaises(TypeError):
            PrecisionTimestamp.from_dict("not a dict")


class TestRepr(unittest.TestCase):
    def test_repr_contains_components(self) -> None:
        ts = PrecisionTimestamp(seconds=3, attoseconds=7)
        text = repr(ts)
        self.assertIn("3", text)
        self.assertIn("7", text)
        self.assertIn("PrecisionTimestamp", text)


if __name__ == "__main__":
    unittest.main()
