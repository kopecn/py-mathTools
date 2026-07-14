"""Numpy-backed general polynomial type: :class:`UnivariatePolynomial`.

See ``.claude/specs/polynomials.md`` (§UnivariatePolynomial).

Coefficients are stored in **ascending-degree order** (numpy convention:
``c[0] + c[1]·x + c[2]·x² + ...``), collapsing the Swift
``PolynomialUnivariateOrder`` enum + eleven per-degree subclasses into one
class (composition over inheritance; numpy's companion-matrix root solver
supersedes the closed-form per-degree solvers for this general-purpose API).

:meth:`UnivariatePolynomial.real_roots` returns **all** real roots of the
polynomial. This is a deliberate contrast with the OTG analytic root kernel
(``math_tools.functional.roots``, chunk 10), which returns only
**non-negative** real roots because it solves for time >= 0 -- the two
contracts are intentionally different; see that module's docstring.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.polynomial.polynomial as npoly
import numpy.typing as npt

from math_tools.errors import PolynomialSolveError

#: Imaginary-part tolerance for treating a companion-matrix root as real; also
#: the default ``tolerance`` for :meth:`UnivariatePolynomial.real_roots`.
#:
#: Defined here because chunk 10 (the OTG analytic root kernel,
#: ``math_tools.functional.roots``) has not landed yet. Per polynomials.md
#: design constraint 3, that module will re-home this constant when it lands;
#: this module will then import it from there instead of defining it.
POLYNOMIAL_ZERO_THRESHOLD: float = 1e-9

_SUPERSCRIPT_DIGITS = str.maketrans(
    "0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"
)


def _superscript(power: int) -> str:
    return str(power).translate(_SUPERSCRIPT_DIGITS)


def _trim_trailing_zeros(coefficients: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Trim highest-degree zero coefficients, keeping at least one entry."""
    last = len(coefficients) - 1
    while last > 0 and coefficients[last] == 0.0:
        last -= 1
    return np.array(coefficients[: last + 1], dtype=np.float64)


class UnivariatePolynomial:
    """An immutable univariate polynomial with float64 coefficients.

    Coefficients are ascending-degree (``coefficients[0]`` is the constant
    term), matching numpy's convention -- the Swift ordering is descending
    and is mapped at construction boundaries, never here.
    """

    __slots__ = ("_coefficients",)

    def __init__(self, coefficients: Sequence[float] | npt.NDArray[np.floating[Any]]) -> None:
        """Construct from ascending-degree coefficients.

        Args:
            coefficients: ``[c0, c1, ..., cn]`` such that the polynomial is
                ``c0 + c1*x + ... + cn*x**n``. Trailing (highest-degree)
                zeros are trimmed so :attr:`degree` is exact.

        Raises:
            ValueError: If ``coefficients`` is empty.
        """
        if len(coefficients) == 0:
            raise ValueError("UnivariatePolynomial requires at least one coefficient")
        arr = np.asarray(coefficients, dtype=np.float64)
        self._coefficients: npt.NDArray[np.float64] = _trim_trailing_zeros(arr)

    # MARK: - Accessors

    @property
    def coefficients(self) -> npt.NDArray[np.float64]:
        """Ascending-degree coefficients, copied out (immutable storage)."""
        return np.array(self._coefficients, dtype=np.float64)

    @property
    def degree(self) -> int:
        """The polynomial's degree (index of the highest nonzero coefficient)."""
        return int(len(self._coefficients) - 1)

    def coefficient_at(self, degree: int) -> float:
        """Return the coefficient of ``x**degree`` (``0.0`` beyond :attr:`degree`)."""
        if degree < 0 or degree >= len(self._coefficients):
            return 0.0
        return float(self._coefficients[degree])

    # MARK: - Evaluation

    def __call__(self, x: float | npt.ArrayLike) -> float | npt.NDArray[np.float64]:
        """Evaluate the polynomial at ``x`` (scalar or array) via Horner's method."""
        arr = np.asarray(x, dtype=np.float64)
        result = npoly.polyval(arr, self._coefficients)
        if arr.ndim == 0:
            return float(result)
        return np.asarray(result, dtype=np.float64)

    # MARK: - Calculus

    def derivative(self) -> UnivariatePolynomial:
        """Return the derivative polynomial."""
        return UnivariatePolynomial(npoly.polyder(self._coefficients))

    def integrate(self, constant: float = 0.0) -> UnivariatePolynomial:
        """Return the antiderivative with the given integration constant."""
        return UnivariatePolynomial(npoly.polyint(self._coefficients, k=constant))

    # MARK: - Roots

    def real_roots(self, tolerance: float = POLYNOMIAL_ZERO_THRESHOLD) -> list[float]:
        """Return all real roots, sorted ascending.

        Unlike ``math_tools.functional.roots`` (the OTG analytic kernel,
        which returns only non-negative real roots because it solves for
        time >= 0), this returns **every** real root of the polynomial.

        Roots are found via the companion matrix (``numpy.roots``
        equivalent); a root is treated as real when its imaginary part's
        magnitude is within ``tolerance`` of zero.

        Args:
            tolerance: Imaginary-part magnitude below which a companion-matrix
                root is treated as real.

        Raises:
            PolynomialSolveError: If this is the zero polynomial (every
                coefficient is zero) -- it has infinitely many roots.
        """
        if self.degree == 0:
            if self._coefficients[0] == 0.0:
                raise PolynomialSolveError(
                    "cannot solve for roots of the zero polynomial (infinitely many roots)"
                )
            return []

        # numpy.roots expects descending-degree coefficients.
        descending = self._coefficients[::-1]
        roots = np.roots(descending)
        real_mask = np.abs(roots.imag) <= tolerance
        return sorted(float(value) for value in roots.real[real_mask])

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Check equality of trimmed coefficients."""
        if isinstance(other, UnivariatePolynomial):
            return bool(np.array_equal(self._coefficients, other._coefficients))
        return False

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Return a human-readable representation, e.g. ``"3.0·x² − 1.0"``."""
        pieces: list[str] = []
        for index, power in enumerate(range(self.degree, -1, -1)):
            coeff = float(self._coefficients[power])
            if coeff == 0.0 and self.degree > 0:
                continue
            magnitude = abs(coeff)
            if power == 0:
                term = f"{magnitude}"
            elif power == 1:
                term = f"{magnitude}·x"
            else:
                term = f"{magnitude}·x{_superscript(power)}"

            if index == 0:
                sign = "−" if coeff < 0 else ""
                pieces.append(f"{sign}{term}")
            else:
                sign = " − " if coeff < 0 else " + "
                pieces.append(f"{sign}{term}")
        return "".join(pieces)
