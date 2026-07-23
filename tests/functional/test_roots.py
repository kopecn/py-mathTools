"""Unit tests for the OTG analytic root kernel (``math_tools.functional.roots``).

Covers polynomials.md §functional/roots.py Compliance requirements 2-6: a
faithful port of ``Roots.swift`` / ``Utils.swift`` (Swift source under
``spmMathTools/FoundationMathTypes/Functional/``). All test vectors below are
either hand-computed and independently verifiable by factoring, or (for
Compliance 2b) cross-checked against ``numpy.roots`` -- numpy is a test-only
import per design constraint 4; ``roots.py`` itself imports only
``math``/``sys``.
"""

from __future__ import annotations

import ast
import sys
import unittest

import numpy as np

from math_tools.functional import roots


class TestConstants(unittest.TestCase):
    def test_eps16_pinned_to_16_times_float_epsilon(self) -> None:
        """Compliance 5: guards against the 1e-16 transcription error."""
        self.assertEqual(roots.EPS16, 16 * sys.float_info.epsilon)

    def test_polynomial_tolerance_value(self) -> None:
        self.assertEqual(roots.POLYNOMIAL_TOLERANCE, 1e-14)

    def test_polynomial_zero_threshold_value(self) -> None:
        self.assertEqual(roots.POLYNOMIAL_ZERO_THRESHOLD, 1e-9)


class TestRootsModuleImportsOnlyStdlib(unittest.TestCase):
    def test_no_numpy_or_scipy_import(self) -> None:
        """Compliance 6: roots.py imports nothing beyond math/sys/stdlib."""
        source_path = roots.__file__
        assert source_path is not None
        with open(source_path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=source_path)

        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_roots.add(node.module.split(".")[0])

        # `__future__` isn't in sys.stdlib_module_names but is a language
        # construct, not a dependency; allow it explicitly.
        allowed = set(sys.stdlib_module_names) | {"__future__"}
        self.assertTrue(
            imported_roots.issubset(allowed),
            f"roots.py imports outside stdlib: {imported_roots - allowed}",
        )
        self.assertNotIn("numpy", imported_roots)
        self.assertNotIn("scipy", imported_roots)


class TestSolveCubicLiteralVectors(unittest.TestCase):
    """Compliance 2a: hand-computed cubic vectors, atol 1e-9."""

    def test_three_distinct_positive_roots(self) -> None:
        # (x-1)(x-2)(x-3) = x^3 - 6x^2 + 11x - 6
        found = sorted(roots.solve_cubic(1.0, -6.0, 11.0, -6.0))
        np.testing.assert_allclose(found, [1.0, 2.0, 3.0], atol=1e-9)

    def test_mixed_sign_roots_drops_negative(self) -> None:
        # (x+1)(x-2)(x-3) = x^3 - 4x^2 + x + 6 -> roots -1, 2, 3
        found = sorted(roots.solve_cubic(1.0, -4.0, 1.0, 6.0))
        np.testing.assert_allclose(found, [2.0, 3.0], atol=1e-9)

    def test_repeated_root_via_discriminant_zero_quadratic_branch(self) -> None:
        # a=0 forces the quadratic branch: x^2 - 2x + 1 = (x-1)^2, discriminant
        # 0 -> both (-c+y)*inv2b and (-c-y)*inv2b formulas evaluate identically
        # and are each inserted, so the double root IS duplicated in the output
        # here (unlike the cubic "yy==0" branch below, which is not).
        found = sorted(roots.solve_cubic(0.0, 1.0, -2.0, 1.0))
        self.assertEqual(len(found), 2)
        np.testing.assert_allclose(found, [1.0, 1.0], atol=1e-9)

    def test_double_plus_simple_root_cubic_branch(self) -> None:
        # (x-1)^2 (x-4) = x^3 - 6x^2 + 9x - 4 -> roots 1 (double), 4 (simple).
        # The cubic "yy==0" branch (Roots.swift:107-114) emits each of its two
        # closed-form values once, so the double root is NOT duplicated here
        # (contrast with the quadratic-branch case above).
        found = sorted(roots.solve_cubic(1.0, -6.0, 9.0, -4.0))
        self.assertEqual(len(found), 2)
        np.testing.assert_allclose(found, [1.0, 4.0], atol=1e-9)

    def test_complex_pair_leaves_single_positive_real_root(self) -> None:
        # x^3 - 8 = 0 -> real root 2, complex pair discarded
        found = roots.solve_cubic(1.0, 0.0, 0.0, -8.0)
        np.testing.assert_allclose(found, [2.0], atol=1e-9)

    def test_all_negative_roots_filtered_to_empty(self) -> None:
        # (x+1)(x+2)(x+3) = x^3 + 6x^2 + 11x + 6 -> roots -1, -2, -3
        found = roots.solve_cubic(1.0, 6.0, 11.0, 6.0)
        self.assertEqual(found, [])

    def test_a_near_zero_falls_back_to_quadratic(self) -> None:
        # a = 0: 2x^2 - 3x - 2 = 0 -> roots 2, -0.5 -> filtered to [2.0]
        found = roots.solve_cubic(0.0, 2.0, -3.0, -2.0)
        np.testing.assert_allclose(found, [2.0], atol=1e-9)

    def test_d_near_zero_peels_off_x_equals_zero_root(self) -> None:
        # x(x-1)(x-2) = x^3 - 3x^2 + 2x -> roots 0, 1, 2
        found = sorted(roots.solve_cubic(1.0, -3.0, 2.0, 0.0))
        np.testing.assert_allclose(found, [0.0, 1.0, 2.0], atol=1e-9)

    def test_linear_degenerate_case(self) -> None:
        # a=b=0, c=2, d=-4 -> linear: 2x - 4 = 0 -> x = 2
        found = roots.solve_cubic(0.0, 0.0, 2.0, -4.0)
        np.testing.assert_allclose(found, [2.0], atol=1e-9)


class TestSolveCubicNearZeroLeadingCoefficient(unittest.TestCase):
    """B-7: scale-relative degeneracy threshold for the leading coefficient.

    polynomials.md rule 4 requires ``a ~= 0`` cubics to degrade to the
    quadratic branch; the original ``_ULP`` (absolute) threshold let a
    coefficient like ``1e-10`` take the cubic branch, whose ``1/a**3``
    scaling collapses the solve (empirically confirmed: it returned []
    instead of the real root near 2.0).
    """

    def test_a_1e10_matches_np_roots(self) -> None:
        # Post-audit B-7 repro case.
        found = roots.solve_cubic(1e-10, 2.0, -3.0, -2.0)
        expected = np.roots([1e-10, 2.0, -3.0, -2.0])
        mask = np.abs(expected.imag) < roots.POLYNOMIAL_ZERO_THRESHOLD
        real_positive = sorted(
            float(v) for v in expected.real[mask] if v >= 0.0
        )
        np.testing.assert_allclose(sorted(found), real_positive, atol=1e-8)

    def test_leading_coefficient_decade_sweep_matches_np_roots(self) -> None:
        """Sweep a across 1e-4..1e-14 -- this is what test_random_cubics's
        old ``continue`` was suppressing. Below the degeneracy threshold,
        solve_cubic drops to the quadratic branch, which introduces an
        O(a) error relative to the true (a != 0) root -- so the tolerance
        is scaled with `a` rather than fixed.
        """
        b, c, d = 2.0, -3.0, -2.0
        for exponent in range(4, 15):
            a = 10.0**-exponent
            with self.subTest(a=a):
                expected = np.roots([a, b, c, d])
                mask = np.abs(expected.imag) < roots.POLYNOMIAL_ZERO_THRESHOLD
                real_positive = sorted(
                    float(v) for v in expected.real[mask] if v >= 0.0
                )
                found = sorted(roots.solve_cubic(a, b, c, d))
                self.assertEqual(len(found), len(real_positive), msg=a)
                np.testing.assert_allclose(
                    found, real_positive, atol=max(2.0 * a, 1e-9)
                )


class TestSolveResolvent(unittest.TestCase):
    """Design constraint 3 / acceptance criterion: the real-root count guard."""

    def test_three_real_roots_case(self) -> None:
        # Resolvent of Q1 (x^4-10x^3+35x^2-50x+24): y^3-35y^2+404y-1540
        # factors as (y-10)(y-11)(y-14) -> 3 real roots.
        found, count = roots.solve_resolvent(-35.0, 404.0, -1540.0)
        self.assertEqual(count, 3)
        np.testing.assert_allclose(sorted(found), [10.0, 11.0, 14.0], atol=1e-9)

    def test_one_real_root_case(self) -> None:
        # Resolvent of Q4 (x^4+x^2-2): y^3-y^2+8y-8 = (y-1)(y^2+8)
        # -> exactly 1 real root (y=1); slot 2 holds imaginary-part scratch,
        # not a root (Swift Roots.swift:234 guard).
        found, count = roots.solve_resolvent(-1.0, 8.0, -8.0)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(found[0], 1.0, places=9)

    def test_two_real_roots_case(self) -> None:
        # (y-2)^2(y+1) = y^3 -3y^2 +0y +4 -> roots -1, 2 (double). This
        # takes the r2 >= q3 branch (roots.py:193-203); the repeated pair
        # makes x[2] cancel to within _ULP, so the branch collapses to the
        # count == 2 case (finding B-8, previously unexercised).
        found, count = roots.solve_resolvent(-3.0, 0.0, 4.0)
        self.assertEqual(count, 2)
        np.testing.assert_allclose(sorted(found), [-1.0, 2.0, 2.0], atol=1e-9)


class TestSolveQuarticMonicLiteralVectors(unittest.TestCase):
    """Compliance 2a: hand-computed monic-quartic vectors, atol 1e-9."""

    def test_four_distinct_positive_roots(self) -> None:
        # (x-1)(x-2)(x-3)(x-4) = x^4 -10x^3 +35x^2 -50x +24
        found = sorted(roots.solve_quartic_monic(-10.0, 35.0, -50.0, 24.0))
        np.testing.assert_allclose(found, [1.0, 2.0, 3.0, 4.0], atol=1e-9)

    def test_mixed_sign_roots_drops_negative(self) -> None:
        # (x+1)(x-2)(x-3)(x-4) = x^4 -8x^3 +17x^2 +2x -24 -> roots -1,2,3,4
        found = sorted(roots.solve_quartic_monic(-8.0, 17.0, 2.0, -24.0))
        np.testing.assert_allclose(found, [2.0, 3.0, 4.0], atol=1e-9)

    def test_repeated_roots(self) -> None:
        # (x-1)^2(x-2)^2 = x^4 -6x^3 +13x^2 -12x +4 -> roots 1,1,2,2.
        # A multiplicity-2 root is inherently ill-conditioned for a
        # closed-form solver (error ~ sqrt(eps) ~ 1.5e-8, not eps itself), so
        # this case alone uses a looser atol than the other literal vectors.
        found = sorted(roots.solve_quartic_monic(-6.0, 13.0, -12.0, 4.0))
        self.assertEqual(len(found), 4)
        np.testing.assert_allclose(found, [1.0, 1.0, 2.0, 2.0], atol=1e-6)

    def test_complex_pair_and_one_real_resolvent_root(self) -> None:
        # x^4 + x^2 - 2 = (x^2-1)(x^2+2) -> real roots +-1, complex +-i*sqrt(2)
        # non-negative filter keeps only 1.0. Resolvent of this quartic has
        # exactly 1 real root (see TestSolveResolvent.test_one_real_root_case).
        found = roots.solve_quartic_monic(0.0, 1.0, 0.0, -2.0)
        np.testing.assert_allclose(found, [1.0], atol=1e-9)

    def test_all_negative_roots_filtered_to_empty(self) -> None:
        # (x+1)(x+2)(x+3)(x+4) = x^4 +10x^3 +35x^2 +50x +24
        found = roots.solve_quartic_monic(10.0, 35.0, 50.0, 24.0)
        self.assertEqual(found, [])

    def test_d_and_c_near_zero_biquadratic_branch(self) -> None:
        # x^2(x-2)(x-3) = x^4 -5x^3 +6x^2 -> roots 0 (single insertion), 2, 3
        found = sorted(roots.solve_quartic_monic(-5.0, 6.0, 0.0, 0.0))
        np.testing.assert_allclose(found, [0.0, 2.0, 3.0], atol=1e-9)

    def test_d_and_c_near_zero_repeated_quadratic_factor(self) -> None:
        # x^2(x-2)^2 = x^4 -4x^3 +4x^2 -> roots 0 (single insertion), 2
        found = sorted(roots.solve_quartic_monic(-4.0, 4.0, 0.0, 0.0))
        np.testing.assert_allclose(found, [0.0, 2.0], atol=1e-9)

    def test_d_near_zero_a_and_b_near_zero_branch(self) -> None:
        # x^4 - 8x = x(x-2)(x^2+2x+4) -> roots 0, 2 (real); complex pair discarded
        found = sorted(roots.solve_quartic_monic(0.0, 0.0, -8.0, 0.0))
        np.testing.assert_allclose(found, [0.0, 2.0], atol=1e-9)


class TestCrossCheckAgainstNumpyRoots(unittest.TestCase):
    """Compliance 2b: seeded-random cross-check against np.roots, atol 1e-8.

    numpy is a test-only import (design constraint 4 forbids it in roots.py
    itself).
    """

    def _non_negative_real_roots(self, coefficients_descending: list[float]) -> list[float]:
        found = np.roots(coefficients_descending)
        mask = np.abs(found.imag) < roots.POLYNOMIAL_ZERO_THRESHOLD
        real_part = found.real[mask]
        return sorted(float(value) for value in real_part if value >= 0.0)

    def test_random_cubics(self) -> None:
        rng = np.random.default_rng(1234)
        for _ in range(30):
            a, b, c, d = rng.uniform(-5.0, 5.0, size=4)
            expected = self._non_negative_real_roots([a, b, c, d])
            actual = sorted(roots.solve_cubic(a, b, c, d))
            self.assertEqual(len(actual), len(expected), msg=(a, b, c, d))
            np.testing.assert_allclose(actual, expected, atol=1e-8)

    def test_random_monic_quartics(self) -> None:
        rng = np.random.default_rng(5678)
        for _ in range(30):
            a, b, c, d = rng.uniform(-5.0, 5.0, size=4)
            expected = self._non_negative_real_roots([1.0, a, b, c, d])
            actual = sorted(roots.solve_quartic_monic(a, b, c, d))
            self.assertEqual(len(actual), len(expected), msg=(a, b, c, d))
            np.testing.assert_allclose(actual, expected, atol=1e-8)


class TestEvaluatePolynomial(unittest.TestCase):
    def test_horner_evaluation_highest_to_lowest(self) -> None:
        # x^2 - 3x + 2 at x=5 -> 25-15+2=12
        self.assertAlmostEqual(roots.evaluate_polynomial([1.0, -3.0, 2.0], 5.0), 12.0)

    def test_empty_coefficients_is_zero(self) -> None:
        self.assertEqual(roots.evaluate_polynomial([], 3.0), 0.0)

    def test_constant_polynomial(self) -> None:
        self.assertEqual(roots.evaluate_polynomial([7.0], -100.0), 7.0)


class TestPolynomialDerivative(unittest.TestCase):
    def test_derivative_of_quadratic(self) -> None:
        # x^2 - 3x + 2 -> derivative 2x - 3
        self.assertEqual(roots.polynomial_derivative([1.0, -3.0, 2.0]), [2.0, -3.0])

    def test_derivative_of_constant_is_empty(self) -> None:
        self.assertEqual(roots.polynomial_derivative([5.0]), [])

    def test_derivative_of_empty_is_empty(self) -> None:
        self.assertEqual(roots.polynomial_derivative([]), [])


class TestPolynomialMonicDerivative(unittest.TestCase):
    def test_monic_derivative_of_cube_plus_one(self) -> None:
        # (x+1)^3 = x^3+3x^2+3x+1 -> monic-normalized derivative (x+1)^2 = x^2+2x+1
        result = roots.polynomial_monic_derivative([1.0, 3.0, 3.0, 1.0])
        np.testing.assert_allclose(result, [1.0, 2.0, 1.0], atol=1e-12)

    def test_monic_derivative_of_linear_is_empty(self) -> None:
        self.assertEqual(roots.polynomial_monic_derivative([1.0]), [])


class TestShrinkInterval(unittest.TestCase):
    def test_quintic_bracket_converges_to_root(self) -> None:
        """Compliance 3: shrink_interval converges on a bracketed quintic root."""
        # x^5 - 32 = 0 -> root at x=2, bracketed by [1, 3]
        found = roots.shrink_interval([1.0, 0.0, 0.0, 0.0, 0.0, -32.0], 1.0, 3.0)
        self.assertAlmostEqual(found, 2.0, delta=roots.POLYNOMIAL_TOLERANCE)

    def test_root_exactly_at_left_bound(self) -> None:
        found = roots.shrink_interval([1.0, -2.0], 2.0, 5.0)  # x - 2, root at x=2
        self.assertEqual(found, 2.0)

    def test_root_exactly_at_right_bound(self) -> None:
        found = roots.shrink_interval([1.0, -2.0], -1.0, 2.0)  # x - 2, root at x=2
        self.assertEqual(found, 2.0)

    def test_multiple_root_hits_f_and_df_both_zero_without_raising(self) -> None:
        """B-14: the Newton branch's dx = f / df traps as ZeroDivisionError
        when f(rts) == 0.0 and df(rts) == 0.0. (x-2)^3 = x^3 -6x^2 +12x -8
        bracketed by [1, 3] lands the initial guess exactly on the triple
        root x=2, where both f and its derivative vanish -- the bisection
        guard (roots.py:364-366) evaluates to False here, so it falls
        through to the Newton branch on the very first iteration.
        """
        found = roots.shrink_interval([1.0, -6.0, 12.0, -8.0], 1.0, 3.0)
        self.assertEqual(found, 2.0)


class TestIntegrateJerk(unittest.TestCase):
    def test_compliance_4_analytic_vector(self) -> None:
        """Compliance 4: t=1, p0=0, v0=0, a0=0, j=6 -> (1.0, 3.0, 6.0)."""
        p, v, a = roots.integrate_jerk(1.0, 0.0, 0.0, 0.0, 6.0)
        self.assertAlmostEqual(p, 1.0)
        self.assertAlmostEqual(v, 3.0)
        self.assertAlmostEqual(a, 6.0)

    def test_zero_time_is_identity(self) -> None:
        p, v, a = roots.integrate_jerk(0.0, 1.0, 2.0, 3.0, 4.0)
        self.assertEqual((p, v, a), (1.0, 2.0, 3.0))

    def test_constant_jerk_matches_kinematics(self) -> None:
        # p0=1, v0=2, a0=3, j=0, t=2 -> pure constant-acceleration kinematics
        p, v, a = roots.integrate_jerk(2.0, 1.0, 2.0, 3.0, 0.0)
        self.assertAlmostEqual(p, 1.0 + 2.0 * 2.0 + 0.5 * 3.0 * 2.0**2)
        self.assertAlmostEqual(v, 2.0 + 3.0 * 2.0)
        self.assertAlmostEqual(a, 3.0)


if __name__ == "__main__":
    unittest.main()
