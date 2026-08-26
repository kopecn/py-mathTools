"""Unit tests for ``UnivariatePolynomial``.

Covers polynomials.md §Compliance requirement 1, plus construction/trimming,
accessors, calculus, roots (including multiplicity and the zero-polynomial
raise), equality, repr, and immutability.
"""

import unittest

import numpy as np

from math_tools.errors import PolynomialSolveError
from math_tools.functional.polynomial import POLYNOMIAL_ZERO_THRESHOLD, UnivariatePolynomial


class TestConstruction(unittest.TestCase):
    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            UnivariatePolynomial([])

    def test_trims_trailing_zeros(self) -> None:
        p = UnivariatePolynomial([1.0, 0.0, 0.0])
        self.assertEqual(p.degree, 0)
        np.testing.assert_array_equal(p.coefficients, np.array([1.0]))

    def test_no_trim_when_leading_nonzero(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0, 3.0])
        self.assertEqual(p.degree, 2)

    def test_zero_polynomial_degree_zero(self) -> None:
        p = UnivariatePolynomial([0.0])
        self.assertEqual(p.degree, 0)

    def test_all_zero_input_trims_to_single_zero(self) -> None:
        p = UnivariatePolynomial([0.0, 0.0, 0.0])
        self.assertEqual(p.degree, 0)
        np.testing.assert_array_equal(p.coefficients, np.array([0.0]))


class TestAccessors(unittest.TestCase):
    def test_coefficient_at(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0, 3.0])
        self.assertEqual(p.coefficient_at(0), 1.0)
        self.assertEqual(p.coefficient_at(1), 2.0)
        self.assertEqual(p.coefficient_at(2), 3.0)

    def test_coefficient_at_beyond_degree_is_zero(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0])
        self.assertEqual(p.coefficient_at(5), 0.0)

    def test_coefficient_at_negative_is_zero(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0])
        self.assertEqual(p.coefficient_at(-1), 0.0)


class TestImmutability(unittest.TestCase):
    def test_coefficients_property_is_a_copy(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0, 3.0])
        out = p.coefficients
        out[0] = 999.0
        self.assertEqual(p.coefficient_at(0), 1.0)

    def test_construction_does_not_alias_input(self) -> None:
        source = np.array([1.0, 2.0, 3.0])
        p = UnivariatePolynomial(source)
        source[0] = 999.0
        self.assertEqual(p.coefficient_at(0), 1.0)

    def test_no_public_setters(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0])
        with self.assertRaises(AttributeError):
            p.coefficients = np.array([9.0])  # type: ignore[misc]


class TestCall(unittest.TestCase):
    def test_scalar_call_matches_horner(self) -> None:
        # p(x) = 1 + 2x + 3x^2
        p = UnivariatePolynomial([1.0, 2.0, 3.0])

        def horner(x: float) -> float:
            result = 0.0
            for coeff in reversed([1.0, 2.0, 3.0]):
                result = result * x + coeff
            return result

        for x in (-2.0, -0.5, 0.0, 1.0, 3.25):
            self.assertAlmostEqual(float(p(x)), horner(x), places=12)

    def test_scalar_call_returns_python_float(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0])
        result = p(2.0)
        self.assertIsInstance(result, float)

    def test_vector_call_matches_horner_elementwise(self) -> None:
        coeffs = [1.0, 2.0, 3.0]
        p = UnivariatePolynomial(coeffs)
        xs = np.array([-2.0, -0.5, 0.0, 1.0, 3.25])

        def horner(x: float) -> float:
            result = 0.0
            for coeff in reversed(coeffs):
                result = result * x + coeff
            return result

        expected = np.array([horner(x) for x in xs])
        actual = p(xs)
        np.testing.assert_allclose(actual, expected, atol=1e-12)

    def test_vector_call_returns_ndarray(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0])
        result = p(np.array([1.0, 2.0, 3.0]))
        self.assertIsInstance(result, np.ndarray)


class TestCalculus(unittest.TestCase):
    def test_derivative_of_linear_is_constant(self) -> None:
        p = UnivariatePolynomial([5.0, 3.0])  # 5 + 3x
        d = p.derivative()
        self.assertEqual(d.degree, 0)
        self.assertEqual(d.coefficient_at(0), 3.0)

    def test_derivative_of_constant_is_zero(self) -> None:
        p = UnivariatePolynomial([7.0])
        d = p.derivative()
        self.assertEqual(d.degree, 0)
        self.assertEqual(d.coefficient_at(0), 0.0)

    def test_integrate_default_constant(self) -> None:
        p = UnivariatePolynomial([3.0])  # constant 3
        integral = p.integrate()
        # antiderivative: 3x
        self.assertEqual(integral.coefficient_at(0), 0.0)
        self.assertEqual(integral.coefficient_at(1), 3.0)

    def test_integrate_with_constant(self) -> None:
        p = UnivariatePolynomial([3.0])
        integral = p.integrate(constant=2.0)
        self.assertEqual(integral.coefficient_at(0), 2.0)
        self.assertEqual(integral.coefficient_at(1), 3.0)

    def test_derivative_integrate_round_trip_up_to_constant(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0, 3.0, 4.0])
        round_tripped = p.derivative().integrate(constant=p.coefficient_at(0))
        self.assertEqual(round_tripped, p)

    def test_integrate_derivative_round_trip(self) -> None:
        p = UnivariatePolynomial([1.0, 2.0, 3.0])
        round_tripped = p.integrate().derivative()
        self.assertEqual(round_tripped, p)


class TestRealRoots(unittest.TestCase):
    def test_compliance_1_simple_roots(self) -> None:
        """polynomials.md Compliance 1: [-1, 0, 1] -> roots [-1.0, 1.0]."""
        p = UnivariatePolynomial([-1.0, 0.0, 1.0])  # x^2 - 1
        self.assertEqual(p.real_roots(), [-1.0, 1.0])

    def test_multiplicity_root_duplicated(self) -> None:
        """(x - 1)^2 = x^2 - 2x + 1 -> duplicated root [1.0, 1.0]."""
        p = UnivariatePolynomial([1.0, -2.0, 1.0])
        roots = p.real_roots()
        self.assertEqual(len(roots), 2)
        for root in roots:
            self.assertAlmostEqual(root, 1.0, places=6)

    def test_zero_polynomial_raises(self) -> None:
        p = UnivariatePolynomial([0.0])
        with self.assertRaises(PolynomialSolveError):
            p.real_roots()

    def test_nonzero_constant_has_no_roots(self) -> None:
        p = UnivariatePolynomial([5.0])
        self.assertEqual(p.real_roots(), [])

    def test_complex_pair_filtered_out(self) -> None:
        # x^2 + 1 -> roots +-i, no real roots
        p = UnivariatePolynomial([1.0, 0.0, 1.0])
        self.assertEqual(p.real_roots(), [])

    def test_cubic_one_real_two_complex(self) -> None:
        # x^3 + 1 -> one real root at x = -1
        p = UnivariatePolynomial([1.0, 0.0, 0.0, 1.0])
        roots = p.real_roots()
        self.assertEqual(len(roots), 1)
        self.assertAlmostEqual(roots[0], -1.0, places=9)

    def test_roots_sorted_ascending(self) -> None:
        # (x+2)(x-1)(x-3) -> roots -2, 1, 3
        coeffs_descending = np.poly([-2.0, 1.0, 3.0])  # descending, numpy.poly convention
        coeffs_ascending = coeffs_descending[::-1]
        p = UnivariatePolynomial(coeffs_ascending)
        roots = p.real_roots()
        self.assertEqual(len(roots), 3)
        np.testing.assert_allclose(roots, [-2.0, 1.0, 3.0], atol=1e-8)

    def test_default_tolerance_is_module_constant(self) -> None:
        p = UnivariatePolynomial([-1.0, 0.0, 1.0])
        self.assertEqual(p.real_roots(), p.real_roots(tolerance=POLYNOMIAL_ZERO_THRESHOLD))


class TestEquality(unittest.TestCase):
    def test_equal_trimmed_coefficients(self) -> None:
        self.assertEqual(UnivariatePolynomial([1.0, 2.0]), UnivariatePolynomial([1.0, 2.0, 0.0]))

    def test_not_equal_different_coefficients(self) -> None:
        self.assertNotEqual(UnivariatePolynomial([1.0, 2.0]), UnivariatePolynomial([1.0, 3.0]))

    def test_not_equal_to_other_type(self) -> None:
        self.assertNotEqual(UnivariatePolynomial([1.0]), "not a polynomial")

    def test_hash_is_none(self) -> None:
        p = UnivariatePolynomial([1.0])
        with self.assertRaises(TypeError):
            hash(p)


class TestRepr(unittest.TestCase):
    def test_repr_two_term_shape(self) -> None:
        # 3x^2 - 1 => coefficients ascending [-1.0, 0.0, 3.0]
        p = UnivariatePolynomial([-1.0, 0.0, 3.0])
        self.assertEqual(repr(p), "3.0·x² − 1.0")

    def test_repr_constant(self) -> None:
        p = UnivariatePolynomial([5.0])
        self.assertEqual(repr(p), "5.0")

    def test_repr_linear_term_no_superscript(self) -> None:
        p = UnivariatePolynomial([0.0, 2.0])
        self.assertEqual(repr(p), "2.0·x")

    def test_repr_zero_polynomial(self) -> None:
        p = UnivariatePolynomial([0.0])
        self.assertEqual(repr(p), "0.0")

    def test_repr_negative_leading_term(self) -> None:
        p = UnivariatePolynomial([0.0, 0.0, -1.0])
        self.assertEqual(repr(p), "−1.0·x²")


if __name__ == "__main__":
    unittest.main()
