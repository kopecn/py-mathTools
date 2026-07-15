"""Unit tests for ``Waveform1D`` operators (arithmetic, bitwise, comparison).

Covers waveformCore.md §Waveform1D Operators and §Compliance requirement 2
(dt/length mismatch -> ``WaveformCompatibilityError``).
"""

import unittest

import numpy as np

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.waveforms.waveform1d import Waveform1D


class TestSpecCompliance2Compatibility(unittest.TestCase):
    """§Compliance 2: dt/length mismatch on a binary op raises WaveformCompatibilityError."""

    def test_dt_mismatch_raises(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5)
        with self.assertRaises(WaveformCompatibilityError):
            a + b

    def test_length_mismatch_raises(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        with self.assertRaises(WaveformCompatibilityError):
            a + b

    def test_equal_dt_and_length_path_is_exact(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([10.0, 20.0, 30.0], dt_seconds=1.0)
        result = a + b
        np.testing.assert_array_equal(result.values, np.array([11.0, 22.0, 33.0]))

    def test_dt_mismatch_raises_for_all_binary_ops(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5)
        with self.assertRaises(WaveformCompatibilityError):
            _ = a - b
        with self.assertRaises(WaveformCompatibilityError):
            _ = a * b
        with self.assertRaises(WaveformCompatibilityError):
            _ = a / b
        with self.assertRaises(WaveformCompatibilityError):
            _ = a // b
        with self.assertRaises(WaveformCompatibilityError):
            _ = a % b


class TestScalarBothOrders(unittest.TestCase):
    def test_waveform_plus_scalar(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        result = w + 1.0
        np.testing.assert_array_equal(result.values, np.array([2.0, 3.0, 4.0]))

    def test_scalar_plus_waveform(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        result = 1.0 + w
        np.testing.assert_array_equal(result.values, np.array([2.0, 3.0, 4.0]))

    def test_waveform_minus_scalar(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        result = w - 1.0
        np.testing.assert_array_equal(result.values, np.array([0.0, 1.0, 2.0]))

    def test_scalar_minus_waveform_is_reflected_not_forward(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        result = 10.0 - w
        np.testing.assert_array_equal(result.values, np.array([9.0, 8.0, 7.0]))

    def test_waveform_times_scalar_and_reflected(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        np.testing.assert_array_equal((w * 2.0).values, np.array([2.0, 4.0, 6.0]))
        np.testing.assert_array_equal((2.0 * w).values, np.array([2.0, 4.0, 6.0]))

    def test_result_carries_dt_and_t0_from_left_operand(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=2.0, t0_seconds=5.0)
        result = w + 1.0
        self.assertEqual(result.t0, w.t0)
        self.assertEqual(result.dt, w.dt)
        self.assertIsNot(result, w)

    def test_foreign_type_returns_not_implemented_and_raises_type_error(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        with self.assertRaises(TypeError):
            _ = w + "not a number"

    def test_numpy_scalar_reflected_add_returns_waveform_not_bare_ndarray(self) -> None:
        # Regression guard: without __array_ufunc__ = None, numpy's ufunc
        # machinery unwraps `w` via __array__ before Python's operator
        # protocol gets a chance to call w.__radd__, silently discarding
        # dt/t0 and returning a bare ndarray instead of a Waveform1D.
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=2.0, t0_seconds=5.0)
        result = np.float64(2.0) + w
        self.assertIsInstance(result, Waveform1D)
        self.assertEqual(result.t0, w.t0)
        self.assertEqual(result.dt, w.dt)
        np.testing.assert_array_equal(result.values, np.array([3.0, 4.0, 5.0]))


class TestInPlaceOperators(unittest.TestCase):
    def test_iadd_mutates_and_returns_same_object(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        x = w
        w += 1.0
        self.assertIs(w, x)
        np.testing.assert_array_equal(w.values, np.array([2.0, 3.0, 4.0]))

    def test_isub_mutates_in_place(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        x = w
        w -= 1.0
        self.assertIs(w, x)
        np.testing.assert_array_equal(w.values, np.array([0.0, 1.0, 2.0]))

    def test_imul_mutates_in_place(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        x = w
        w *= 2.0
        self.assertIs(w, x)
        np.testing.assert_array_equal(w.values, np.array([2.0, 4.0, 6.0]))

    def test_itruediv_mutates_in_place(self) -> None:
        w = Waveform1D([2.0, 4.0, 6.0])
        x = w
        w /= 2.0
        self.assertIs(w, x)
        np.testing.assert_array_equal(w.values, np.array([1.0, 2.0, 3.0]))


class TestBitwiseOperators(unittest.TestCase):
    def test_bitwise_on_float_dtype_raises_type_error(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        with self.assertRaises(TypeError):
            w & 1

    def test_bitwise_and_between_int_waveforms(self) -> None:
        a = Waveform1D(np.array([0b110, 0b101], dtype=np.int64))
        b = Waveform1D(np.array([0b011, 0b110], dtype=np.int64))
        result = a & b
        np.testing.assert_array_equal(result.values, np.array([0b010, 0b100]))

    def test_int_modulo_works(self) -> None:
        w = Waveform1D(np.array([5, 6, 7], dtype=np.int64))
        result = w % 3
        np.testing.assert_array_equal(result.values, np.array([2, 0, 1]))

    def test_int_left_shift_works(self) -> None:
        w = Waveform1D(np.array([1, 2, 3], dtype=np.int64))
        result = w << 1
        np.testing.assert_array_equal(result.values, np.array([2, 4, 6]))

    def test_invert_on_int_waveform(self) -> None:
        w = Waveform1D(np.array([0, 1], dtype=np.int64))
        result = ~w
        np.testing.assert_array_equal(result.values, np.array([-1, -2]))

    def test_invert_on_float_waveform_raises_type_error(self) -> None:
        w = Waveform1D([1.0, 2.0])
        with self.assertRaises(TypeError):
            _ = ~w


class TestUnaryOperators(unittest.TestCase):
    def test_negation(self) -> None:
        w = Waveform1D([1.0, -2.0, 3.0])
        np.testing.assert_array_equal((-w).values, np.array([-1.0, 2.0, -3.0]))

    def test_unary_plus(self) -> None:
        w = Waveform1D([1.0, -2.0, 3.0])
        np.testing.assert_array_equal((+w).values, np.array([1.0, -2.0, 3.0]))

    def test_abs(self) -> None:
        w = Waveform1D([1.0, -2.0, 3.0])
        np.testing.assert_array_equal(abs(w).values, np.array([1.0, 2.0, 3.0]))


class TestComparisonProducers(unittest.TestCase):
    def test_elements_equal(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([1.0, 5.0, 3.0])
        np.testing.assert_array_equal(a.elements_equal(b), np.array([True, False, True]))

    def test_elements_less_than(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([2.0, 2.0, 2.0])
        np.testing.assert_array_equal(a.elements_less_than(b), np.array([True, False, False]))

    def test_elements_greater_than(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([2.0, 2.0, 2.0])
        np.testing.assert_array_equal(a.elements_greater_than(b), np.array([False, False, True]))

    def test_comparison_producers_raise_on_dt_mismatch(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5)
        with self.assertRaises(WaveformCompatibilityError):
            a.elements_equal(b)


class TestIscloseElementwise(unittest.TestCase):
    def test_within_tolerance_passes(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([1.0000000001, 2.0, 3.0])
        result = a.isclose_elementwise(b, rtol=1e-6, atol=0.0)
        np.testing.assert_array_equal(result, np.array([True, True, True]))

    def test_outside_tolerance_fails(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([1.1, 2.0, 3.0])
        result = a.isclose_elementwise(b, rtol=1e-6, atol=0.0)
        np.testing.assert_array_equal(result, np.array([False, True, True]))


class TestIscloseWholeWaveform(unittest.TestCase):
    def test_equal_waveforms_are_close(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0, t0_seconds=0.0)
        b = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0, t0_seconds=0.0)
        self.assertTrue(a.isclose(b))

    def test_false_when_only_t0_differs(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0, t0=PrecisionTimestamp.EPOCH)
        b = Waveform1D(
            [1.0, 2.0, 3.0], dt_seconds=1.0, t0=PrecisionTimestamp.EPOCH + a.dt
        )
        self.assertFalse(a.isclose(b))

    def test_false_when_dt_differs(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        b = Waveform1D([1.0, 2.0, 3.0], dt_seconds=2.0)
        self.assertFalse(a.isclose(b))

    def test_false_when_samples_differ_beyond_tolerance(self) -> None:
        a = Waveform1D([1.0, 2.0, 3.0])
        b = Waveform1D([1.0, 2.0, 3.5])
        self.assertFalse(a.isclose(b))


if __name__ == "__main__":
    unittest.main()
