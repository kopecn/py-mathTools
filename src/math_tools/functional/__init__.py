"""Polynomials and analytic root solvers.

See ``.claude/specs/polynomials.md``.
"""

from math_tools.functional.polynomial import UnivariatePolynomial
from math_tools.functional.roots import (
    EPS16,
    POLYNOMIAL_TOLERANCE,
    POLYNOMIAL_ZERO_THRESHOLD,
    evaluate_polynomial,
    integrate_jerk,
    polynomial_derivative,
    polynomial_monic_derivative,
    shrink_interval,
    solve_cubic,
    solve_quartic_monic,
    solve_resolvent,
)

__all__ = [
    "EPS16",
    "POLYNOMIAL_TOLERANCE",
    "POLYNOMIAL_ZERO_THRESHOLD",
    "UnivariatePolynomial",
    "evaluate_polynomial",
    "integrate_jerk",
    "polynomial_derivative",
    "polynomial_monic_derivative",
    "shrink_interval",
    "solve_cubic",
    "solve_quartic_monic",
    "solve_resolvent",
]
