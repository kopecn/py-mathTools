"""Unit tests for ``PrecisionTimeInterval``.

Covers precisionTimeMath.md §Compliance requirements 2, 3, 4, 5, 6, 10 (the
interval half), plus construction, accessors, full arithmetic/comparison
surface, hashability, and ``NotImplemented`` fallback to ``TypeError``.
"""

import unittest
from typing import Any

from foundation_abc.math.mathEnums import NumericSign
from foundation_abc.math.precisionTimeABC import (
    ATTOSECONDS_PER_SECOND,
    PrecisionTimeIntervalABC,
)
from foundationTypes.mathTypes.MathTypes import PrecisionTimeIntervalType

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval


class TestConstruction(unittest.TestCase):
    def test_default_is_zero(self) -> None:
        interval = PrecisionTimeInterval()
        self.assertEqual(interval.seconds, 0)
        self.assertEqual(interval.attoseconds, 0)
        self.assertEqual(interval.sign, NumericSign.ZERO)

    def test_basic_seconds_and_attoseconds(self) -> None:
        interval = PrecisionTimeInterval(seconds=5, attoseconds=250, sign=NumericSign.POSITIVE)
        self.assertEqual(interval.seconds, 5)
        self.assertEqual(interval.attoseconds, 250)
        self.assertEqual(interval.sign, NumericSign.POSITIVE)

    def test_negative_seconds_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval(seconds=-1)

    def test_negative_attoseconds_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval(attoseconds=-1)

    def test_carry_normalization(self) -> None:
        """Compliance 4: attoseconds >= 10**18 carries into seconds."""
        interval = PrecisionTimeInterval(
            seconds=0, attoseconds=ATTOSECONDS_PER_SECOND + 5, sign=NumericSign.POSITIVE
        )
        self.assertEqual(interval.seconds, 1)
        self.assertEqual(interval.attoseconds, 5)

    def test_carry_normalization_multiple_seconds(self) -> None:
        interval = PrecisionTimeInterval(
            seconds=2, attoseconds=3 * ATTOSECONDS_PER_SECOND + 7, sign=NumericSign.POSITIVE
        )
        self.assertEqual(interval.seconds, 5)
        self.assertEqual(interval.attoseconds, 7)

    def test_zero_magnitude_forces_zero_sign(self) -> None:
        interval = PrecisionTimeInterval(seconds=0, attoseconds=0, sign=NumericSign.NEGATIVE)
        self.assertEqual(interval.sign, NumericSign.ZERO)


class TestFromSeconds(unittest.TestCase):
    def test_from_int_seconds(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(3)
        self.assertEqual(interval.total_attoseconds, 3 * ATTOSECONDS_PER_SECOND)

    def test_from_negative_int_seconds(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(-3)
        self.assertEqual(interval.total_attoseconds, -3 * ATTOSECONDS_PER_SECOND)
        self.assertEqual(interval.sign, NumericSign.NEGATIVE)

    def test_from_float_seconds(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1.5)
        self.assertEqual(interval.total_attoseconds, 1_500_000_000_000_000_000)

    def test_from_negative_float_seconds(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(-2.25)
        self.assertEqual(interval.total_attoseconds, -2_250_000_000_000_000_000)

    def test_from_zero_seconds_is_zero_sign(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(0)
        self.assertEqual(interval.sign, NumericSign.ZERO)

    def test_from_non_finite_float_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval.from_seconds(float("inf"))
        with self.assertRaises(ValueError):
            PrecisionTimeInterval.from_seconds(float("nan"))


class TestFromAttoseconds(unittest.TestCase):
    def test_positive_total(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(ATTOSECONDS_PER_SECOND + 1)
        self.assertEqual(interval.seconds, 1)
        self.assertEqual(interval.attoseconds, 1)
        self.assertEqual(interval.sign, NumericSign.POSITIVE)

    def test_negative_total(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(-(ATTOSECONDS_PER_SECOND + 1))
        self.assertEqual(interval.seconds, 1)
        self.assertEqual(interval.attoseconds, 1)
        self.assertEqual(interval.sign, NumericSign.NEGATIVE)

    def test_zero_total(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(0)
        self.assertEqual(interval.sign, NumericSign.ZERO)


class TestFromString(unittest.TestCase):
    def test_from_string_one_point_five(self) -> None:
        """Compliance 2: from_string("1", "5") equals 1.5s exactly."""
        interval = PrecisionTimeInterval.from_string("1", "5")
        self.assertEqual(interval.total_attoseconds, 1_500_000_000_000_000_000)

    def test_from_string_one_attosecond(self) -> None:
        """Compliance 2: from_string("0", "000000000000000001") is 1 attosecond."""
        interval = PrecisionTimeInterval.from_string("0", "000000000000000001")
        self.assertEqual(interval.total_attoseconds, 1)

    def test_from_string_negative(self) -> None:
        interval = PrecisionTimeInterval.from_string("-2", "5")
        self.assertEqual(interval.total_attoseconds, -2_500_000_000_000_000_000)
        self.assertEqual(interval.sign, NumericSign.NEGATIVE)

    def test_from_string_empty_fractional(self) -> None:
        interval = PrecisionTimeInterval.from_string("7", "")
        self.assertEqual(interval.total_attoseconds, 7 * ATTOSECONDS_PER_SECOND)

    def test_from_string_too_many_fractional_digits_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval.from_string("0", "1" * 19)

    def test_from_string_non_numeric_seconds_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval.from_string("abc", "5")

    def test_from_string_non_numeric_fractional_raises(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionTimeInterval.from_string("1", "abc")


class TestConstants(unittest.TestCase):
    def test_zero(self) -> None:
        self.assertEqual(PrecisionTimeInterval.ZERO.total_attoseconds, 0)

    def test_one_second(self) -> None:
        self.assertEqual(PrecisionTimeInterval.ONE_SECOND.total_attoseconds, ATTOSECONDS_PER_SECOND)

    def test_one_decisecond(self) -> None:
        self.assertEqual(
            PrecisionTimeInterval.ONE_DECISECOND.total_attoseconds, ATTOSECONDS_PER_SECOND // 10
        )

    def test_one_millisecond(self) -> None:
        self.assertEqual(
            PrecisionTimeInterval.ONE_MILLISECOND.total_attoseconds,
            ATTOSECONDS_PER_SECOND // 1_000,
        )

    def test_one_microsecond(self) -> None:
        self.assertEqual(
            PrecisionTimeInterval.ONE_MICROSECOND.total_attoseconds,
            ATTOSECONDS_PER_SECOND // 1_000_000,
        )


class TestAccessors(unittest.TestCase):
    def test_total_attoseconds_signed(self) -> None:
        interval = PrecisionTimeInterval(seconds=1, attoseconds=0, sign=NumericSign.NEGATIVE)
        self.assertEqual(interval.total_attoseconds, -ATTOSECONDS_PER_SECOND)

    def test_seconds_as_float(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(2.5)
        self.assertAlmostEqual(interval.seconds_as_float, 2.5)

    def test_seconds_as_float_negative(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(-2.5)
        self.assertAlmostEqual(interval.seconds_as_float, -2.5)


class TestArithmeticExactness(unittest.TestCase):
    def test_attosecond_exactness(self) -> None:
        """Compliance 3: ONE_SECOND - from_attoseconds(1) has seconds=0,
        attoseconds=10**18 - 1."""
        result = PrecisionTimeInterval.ONE_SECOND - PrecisionTimeInterval.from_attoseconds(1)
        self.assertEqual(result.seconds, 0)
        self.assertEqual(result.attoseconds, ATTOSECONDS_PER_SECOND - 1)

    def test_addition(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_seconds(2)
        self.assertEqual((a + b).total_attoseconds, 3 * ATTOSECONDS_PER_SECOND)

    def test_subtraction_crossing_zero(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_seconds(3)
        result = a - b
        self.assertEqual(result.total_attoseconds, -2 * ATTOSECONDS_PER_SECOND)
        self.assertEqual(result.sign, NumericSign.NEGATIVE)

    def test_unary_neg_and_pos(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(4)
        self.assertEqual((-interval).total_attoseconds, -4 * ATTOSECONDS_PER_SECOND)
        self.assertEqual((+interval).total_attoseconds, 4 * ATTOSECONDS_PER_SECOND)

    def test_abs(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(-4)
        self.assertEqual(abs(interval).total_attoseconds, 4 * ATTOSECONDS_PER_SECOND)


class TestSignAlgebra(unittest.TestCase):
    def test_negating_flips_sign(self) -> None:
        """Compliance 5: negating flips sign; zero is NumericSign.ZERO and bool False."""
        interval = PrecisionTimeInterval.from_seconds(3)
        self.assertEqual(interval.sign, NumericSign.POSITIVE)
        negated = -interval
        self.assertEqual(negated.sign, NumericSign.NEGATIVE)
        self.assertEqual((-negated).sign, NumericSign.POSITIVE)

    def test_zero_sign_and_bool(self) -> None:
        zero = PrecisionTimeInterval.ZERO
        self.assertEqual(zero.sign, NumericSign.ZERO)
        self.assertFalse(bool(zero))

    def test_nonzero_bool_is_true(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        self.assertTrue(bool(interval))

    def test_negating_zero_is_still_zero(self) -> None:
        self.assertEqual((-PrecisionTimeInterval.ZERO).sign, NumericSign.ZERO)


class TestScalarRounding(unittest.TestCase):
    def test_scalar_multiplication_rounds_to_nearest_attosecond(self) -> None:
        """Compliance 6: pinned mult case — 3 atto * 2.5 (exact tie) rounds
        half-to-even to 8."""
        interval = PrecisionTimeInterval.from_attoseconds(3)
        result = interval * 2.5
        self.assertEqual(result.total_attoseconds, 8)

    def test_scalar_multiplication_is_commutative(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(3)
        self.assertEqual((interval * 2.5).total_attoseconds, (2.5 * interval).total_attoseconds)

    def test_scalar_int_multiplication_is_exact(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(7)
        self.assertEqual((interval * 3).total_attoseconds, 21)
        self.assertEqual((3 * interval).total_attoseconds, 21)

    def test_scalar_division_rounds_to_nearest_attosecond(self) -> None:
        """Compliance 6: pinned div case — 7 atto / 2.0 (exact tie) rounds
        half-to-even to 4."""
        interval = PrecisionTimeInterval.from_attoseconds(7)
        result = interval / 2.0
        self.assertEqual(result.total_attoseconds, 4)

    def test_scalar_int_division(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(9)
        self.assertEqual((interval / 3).total_attoseconds, 3)

    def test_scalar_division_by_zero_raises(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(9)
        with self.assertRaises(ZeroDivisionError):
            interval / 0

    def test_scalar_multiplication_by_zero_is_zero(self) -> None:
        interval = PrecisionTimeInterval.from_attoseconds(9)
        self.assertEqual((interval * 0).sign, NumericSign.ZERO)


class TestIntervalDivision(unittest.TestCase):
    def test_interval_divided_by_interval_is_float_ratio(self) -> None:
        numerator = PrecisionTimeInterval.from_attoseconds(10)
        denominator = PrecisionTimeInterval.from_attoseconds(4)
        result = numerator / denominator
        self.assertIsInstance(result, float)
        self.assertEqual(result, 2.5)

    def test_interval_divided_by_zero_interval_raises(self) -> None:
        numerator = PrecisionTimeInterval.from_attoseconds(10)
        with self.assertRaises(ZeroDivisionError):
            numerator / PrecisionTimeInterval.ZERO


class TestOrdering(unittest.TestCase):
    def test_equality(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_attoseconds(ATTOSECONDS_PER_SECOND)
        self.assertEqual(a, b)

    def test_less_than(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_seconds(2)
        self.assertTrue(a < b)
        self.assertFalse(b < a)

    def test_less_than_or_equal(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_seconds(1)
        self.assertTrue(a <= b)

    def test_greater_than(self) -> None:
        a = PrecisionTimeInterval.from_seconds(2)
        b = PrecisionTimeInterval.from_seconds(1)
        self.assertTrue(a > b)

    def test_greater_than_or_equal(self) -> None:
        a = PrecisionTimeInterval.from_seconds(2)
        b = PrecisionTimeInterval.from_seconds(2)
        self.assertTrue(a >= b)

    def test_negative_orders_below_positive(self) -> None:
        a = PrecisionTimeInterval.from_seconds(-1)
        b = PrecisionTimeInterval.from_seconds(1)
        self.assertTrue(a < b)

    def test_total_ordering_sortable(self) -> None:
        values = [
            PrecisionTimeInterval.from_seconds(2),
            PrecisionTimeInterval.from_seconds(-1),
            PrecisionTimeInterval.from_seconds(0),
        ]
        ordered = sorted(values)
        self.assertEqual(
            [v.total_attoseconds for v in ordered],
            [-ATTOSECONDS_PER_SECOND, 0, 2 * ATTOSECONDS_PER_SECOND],
        )


class TestHashability(unittest.TestCase):
    def test_hash_is_consistent_with_equality(self) -> None:
        a = PrecisionTimeInterval.from_seconds(1)
        b = PrecisionTimeInterval.from_attoseconds(ATTOSECONDS_PER_SECOND)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_usable_as_dict_key(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        mapping = {interval: "one second"}
        self.assertEqual(mapping[PrecisionTimeInterval.from_seconds(1)], "one second")

    def test_usable_in_set(self) -> None:
        values = {
            PrecisionTimeInterval.from_seconds(1),
            PrecisionTimeInterval.from_attoseconds(ATTOSECONDS_PER_SECOND),
        }
        self.assertEqual(len(values), 1)


class TestNotImplementedFallback(unittest.TestCase):
    def test_addition_with_foreign_type_raises_type_error(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        with self.assertRaises(TypeError):
            interval + 1.0  # type: ignore[operator]

    def test_subtraction_with_foreign_type_raises_type_error(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        with self.assertRaises(TypeError):
            interval - "not an interval"  # type: ignore[operator]

    def test_equality_with_foreign_type_is_false(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        self.assertFalse(interval == 1.0)
        self.assertNotEqual(interval, object())

    def test_ordering_with_foreign_type_raises_type_error(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        with self.assertRaises(TypeError):
            _ = interval < 1.0  # type: ignore[operator]

    def test_division_by_foreign_type_raises_type_error(self) -> None:
        interval = PrecisionTimeInterval.from_seconds(1)
        with self.assertRaises(TypeError):
            interval / "not a number"  # type: ignore[operator]


class TestIsinstanceAndAbc(unittest.TestCase):
    def test_structural_conformance_to_abc(self) -> None:
        """Compliance 10: PrecisionTimeInterval structurally conforms to
        PrecisionTimeIntervalABC.

        The Tier-2 ABC is a non-runtime_checkable ``typing.Protocol``, so
        conformance is verified by member presence rather than ``isinstance``.
        """
        interval = PrecisionTimeInterval.from_seconds(1)
        for member in PrecisionTimeIntervalABC.__abstractmethods__:
            self.assertTrue(hasattr(interval, member), member)


class TestSerializationRoundTrip(unittest.TestCase):
    """Compliance 1 (interval half): round-trip with the Tier-1 wire dict."""

    def _round_trip(self, payload: dict[str, Any]) -> None:
        wire = PrecisionTimeIntervalType.from_dict(payload).to_dict()
        result = PrecisionTimeInterval.from_dict(wire).to_dict()
        self.assertEqual(result, payload)

    def test_round_trip_positive(self) -> None:
        self._round_trip({"attoseconds": 123456789012345678, "seconds": 42, "sign": "positive"})

    def test_round_trip_negative(self) -> None:
        self._round_trip({"attoseconds": 1, "seconds": 0, "sign": "negative"})

    def test_round_trip_zero(self) -> None:
        self._round_trip({"attoseconds": 0, "seconds": 0, "sign": "zero"})

    def test_round_trip_large_seconds(self) -> None:
        self._round_trip(
            {"attoseconds": 999999999999999999, "seconds": 10_000_000_000, "sign": "positive"}
        )

    def test_to_dict_matches_abc_shape(self) -> None:
        interval = PrecisionTimeInterval(seconds=3, attoseconds=7, sign=NumericSign.POSITIVE)
        self.assertEqual(
            interval.to_dict(), {"attoseconds": 7, "seconds": 3, "sign": "positive"}
        )

    def test_from_dict_rejects_non_dict(self) -> None:
        with self.assertRaises(TypeError):
            PrecisionTimeInterval.from_dict("not a dict")


class TestRepr(unittest.TestCase):
    def test_repr_contains_components(self) -> None:
        interval = PrecisionTimeInterval(seconds=3, attoseconds=7, sign=NumericSign.POSITIVE)
        text = repr(interval)
        self.assertIn("3", text)
        self.assertIn("7", text)
        self.assertIn("PrecisionTimeInterval", text)


if __name__ == "__main__":
    unittest.main()
