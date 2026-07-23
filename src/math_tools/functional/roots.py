"""OTG analytic root kernel -- a faithful port of ``Roots.swift`` / ``Utils.swift``.

See ``.claude/specs/polynomials.md`` (§functional/roots.py). This module is
the numeric substrate for the online trajectory generator (OTG, see
``otg.md``) and translates the Swift control flow and arithmetic as directly
as possible; it does NOT substitute numpy/scipy or closed-form
"improvements" for the ported algorithms.

**This is NOT a general root finder.** Swift's ``insertIfPositive``
(``Utils.swift:33``) means :func:`solve_cubic` / :func:`solve_quartic_monic`
return only **non-negative** real roots -- they solve for time >= 0. General
root finding is :meth:`math_tools.functional.polynomial.UnivariatePolynomial.real_roots`;
the two contracts are deliberately different.

Imports are ``math`` + ``sys`` + stdlib ONLY -- no numpy, no scipy (numpy is
allowed in this module's test file only, for the ``np.roots`` cross-check).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence

#: Machine epsilon scaled by 16, matching Swift's ``eps16 = 16 * .ulpOfOne``.
#: NOT ``1e-16`` -- see polynomials.md design constraint 1.
EPS16: float = 16 * sys.float_info.epsilon

#: Standard tolerance for polynomial root finding (Swift ``polynomialTolerance``).
POLYNOMIAL_TOLERANCE: float = 1e-14

#: Threshold below which a value (e.g. a companion-matrix root's imaginary
#: part) is treated as zero (Swift ``polynomialZeroThreshold``).
POLYNOMIAL_ZERO_THRESHOLD: float = 1e-9

# Swift's `.ulpOfOne` for Double == Python's sys.float_info.epsilon (2^-52).
# Most tolerance checks in Roots.swift compare against this raw ulp, not
# EPS16 (16x larger) -- the two are used inconsistently in the Swift source
# and that inconsistency is preserved here faithfully (see solve_quartic_monic).
_ULP = sys.float_info.epsilon

#: Cosine/sine of 120 degrees, used to rotate among the three cube-root
#: branches of a depressed cubic (Swift ``cos120`` / ``sin120``).
_COS_120 = -0.50
_SIN_120 = 0.866025403784438646764

#: Maximum iterations for shrink_interval's safe-Newton loop (Swift ``maxIts``).
_MAX_ITS = 128

#: Scale-relative degeneracy threshold for solve_cubic's leading coefficient.
#: An *absolute* threshold (the original ``_ULP``) cannot be right across the
#: coefficient scales this module sees: e.g. ``solve_cubic(1e-10, 2.0, -3.0,
#: -2.0)`` has ``abs(a) == 1e-10 >> _ULP``, so it took the cubic branch, whose
#: ``1/a**3`` scaling amplifies rounding error catastrophically as ``a``
#: shrinks (empirically: the closed-form root error grows past the
#: quadratic-fallback's ``O(a)`` error once ``abs(a)`` drops below roughly
#: ``1e-6`` of the other coefficients' magnitude -- see polynomials.md
#: design constraint 1 and the decade sweep in test_roots.py). Below this
#: relative threshold, `a` is treated as zero and the cubic degrades to the
#: quadratic branch, matching Swift's degenerate-leading-coefficient rule.
_CUBIC_LEADING_COEFF_EPS = 1e-6


def _cbrt(x: float) -> float:
    """Real cube root, defined for negative ``x`` (matches C/Swift ``cbrt``)."""
    if x < 0.0:
        return -float((-x) ** (1.0 / 3.0))
    return float(x ** (1.0 / 3.0))


def _insert_if_positive(collected: list[float], value: float) -> None:
    """Append ``value`` only if non-negative (Swift ``insertIfPositive``, ``val >= 0``).

    This is the load-bearing time-domain filter: :func:`solve_cubic` and
    :func:`solve_quartic_monic` solve for time >= 0, so negative real roots
    are dropped, not returned.
    """
    if value >= 0:
        collected.append(value)


def solve_cubic(a: float, b: float, c: float, d: float) -> list[float]:
    """Non-negative real roots of ``a*x^3 + b*x^2 + c*x + d = 0``.

    OTG time-domain kernel; NOT a general root finder -- see
    ``UnivariatePolynomial.real_roots``. Coefficients are ordered highest to
    lowest degree, matching ``Roots.swift:solveCubic``.
    """
    roots: list[float] = []

    if abs(d) < _ULP:
        # First solution is x = 0; convert the remainder to a quadratic.
        _insert_if_positive(roots, 0.0)
        d = c
        c = b
        b = a
        a = 0.0

    if abs(a) <= _CUBIC_LEADING_COEFF_EPS * max(abs(b), abs(c), abs(d)):
        if abs(b) < _ULP:
            # Linear equation.
            if abs(c) > _ULP:
                _insert_if_positive(roots, -d / c)
        else:
            # Quadratic equation.
            discriminant = c * c - 4 * b * d
            if discriminant >= 0:
                inv2b = 1.0 / (2 * b)
                y = math.sqrt(discriminant)
                _insert_if_positive(roots, (-c + y) * inv2b)
                _insert_if_positive(roots, (-c - y) * inv2b)
    else:
        # Cubic equation.
        inva = 1.0 / a
        invaa = inva * inva
        bb = b * b
        bover3a = b * inva / 3
        p = (a * c - bb / 3) * invaa
        # NOTE: deliberate deviation from the literal Swift source. Roots.swift:70
        # scales halfq by `invaa * invaa` (1/a**4); the correct scaling for the
        # standard depressed-cubic resolvent (R = (2A**3 - 9AB + 27C) / 54 with
        # A=b/a, B=c/a, C=d/a) is 1/a**3, i.e. `inva * invaa`. The Swift bug is
        # inert at both of its call sites (PositionThirdOrderStep2.swift,
        # PolynomialUnivariateFunction.swift) because they always pass a monic
        # cubic (a == 1), where 1/a**3 == 1/a**4 == 1 -- so it was never
        # observed upstream. It is NOT inert here: polynomials.md Compliance 2b
        # requires solve_cubic to match np.roots for general (non-monic)
        # random coefficients, which the literal 1/a**4 scaling fails for any
        # a != 1. See polynomials.md §functional/roots.py rules for the
        # accepted spec deviation.
        halfq = (2 * bb * b - 9 * a * b * c + 27 * a * a * d) / 54 * inva * invaa
        yy = p * p * p / 27 + halfq * halfq

        if yy > _ULP:
            # Sqrt is positive: one real solution.
            y = math.sqrt(yy)
            uuu = -halfq + y
            vvv = -halfq - y
            www = uuu if abs(uuu) > abs(vvv) else vvv
            w = _cbrt(www)
            _insert_if_positive(roots, w - p / (3 * w) - bover3a)
        elif yy < -_ULP:
            # Sqrt is negative: three real solutions.
            x = -halfq
            y = math.sqrt(-yy)
            if abs(x) > _ULP:
                theta = math.atan(y / x) if x > 0.0 else math.atan(y / x) + math.pi
                r = math.sqrt(x * x - yy)
            else:
                # Vertical line.
                theta = math.pi / 2
                r = y
            theta /= 3
            r = 2 * _cbrt(r)
            ux = math.cos(theta) * r
            uyi = math.sin(theta) * r

            _insert_if_positive(roots, ux - bover3a)
            _insert_if_positive(roots, ux * _COS_120 - uyi * _SIN_120 - bover3a)
            _insert_if_positive(roots, ux * _COS_120 + uyi * _SIN_120 - bover3a)
        else:
            # Sqrt is zero: two real solutions.
            www = -halfq
            w = 2 * _cbrt(www)
            _insert_if_positive(roots, w - bover3a)
            _insert_if_positive(roots, w * _COS_120 - bover3a)

    return roots


def solve_resolvent(a: float, b: float, c: float) -> tuple[list[float], int]:
    """Roots of the cubic resolvent ``y^3 + a*y^2 + b*y + c = 0`` for a quartic.

    Coefficients are ordered highest to lowest degree (monic cubic), matching
    ``Roots.swift:solveResolvent``.

    Returns:
        A 3-element list of scratch/root values plus the REAL-root count.
        In the 1-real-root case, slot 0 holds the real root and slot 2 holds
        an imaginary-part scratch value, NOT a root -- callers
        (:func:`solve_quartic_monic`) must consult the count before reading
        slots 1 and 2 (Swift ``Roots.swift:234`` guard).
    """
    x = [0.0, 0.0, 0.0]

    a = a / 3
    a2 = a * a
    q = a2 - b / 3
    r = (a * (2 * a2 - b) + c) / 2
    r2 = r * r
    q3 = q * q * q

    if r2 < q3:
        qsqrt = math.sqrt(q)
        t = min(max(r / (q * qsqrt), -1.0), 1.0)
        q = -2 * qsqrt

        theta = math.acos(t) / 3
        ux = math.cos(theta) * q
        uyi = math.sin(theta) * q
        x[0] = ux - a
        x[1] = ux * _COS_120 - uyi * _SIN_120 - a
        x[2] = ux * _COS_120 + uyi * _SIN_120 - a
        return x, 3

    big_a = -_cbrt(abs(r) + math.sqrt(r2 - q3))
    if r < 0.0:
        big_a = -big_a
    big_b = 0.0 if big_a == 0.0 else q / big_a

    x[0] = (big_a + big_b) - a
    x[1] = -(big_a + big_b) / 2 - a
    x[2] = math.sqrt(3) * (big_a - big_b) / 2
    if abs(x[2]) < _ULP:
        x[2] = x[1]
        return x, 2

    return x, 1


def solve_quartic_monic(a: float, b: float, c: float, d: float) -> list[float]:
    """Non-negative real roots of the monic quartic ``x^4 + a*x^3 + b*x^2 + c*x + d = 0``.

    OTG time-domain kernel; NOT a general root finder -- see
    ``UnivariatePolynomial.real_roots``. Coefficients are ordered highest to
    lowest degree (excluding the implicit leading ``1``), matching
    ``Roots.swift:solveQuarticMonic``.
    """
    roots: list[float] = []

    if abs(d) < _ULP:
        if abs(c) < _ULP:
            _insert_if_positive(roots, 0.0)
            disc = a * a - 4 * b
            if abs(disc) < _ULP:
                _insert_if_positive(roots, -a / 2)
            elif disc > 0.0:
                sqrt_disc = math.sqrt(disc)
                _insert_if_positive(roots, (-a - sqrt_disc) / 2)
                _insert_if_positive(roots, (-a + sqrt_disc) / 2)
            return roots

        if abs(a) < _ULP and abs(b) < _ULP:
            _insert_if_positive(roots, 0.0)
            _insert_if_positive(roots, -_cbrt(c))
            return roots

    a3 = -b
    b3 = a * c - 4 * d
    c3 = -a * a * d - c * c + 4 * b * d

    x3, number_of_zeroes = solve_resolvent(a3, b3, c3)

    y = x3[0]
    # Choosing y with maximal absolute value. Consult the real-root count
    # before reading slots 1-2: in the 1-real-root case slot 2 is an
    # imaginary-part scratch value, not a root (Swift Roots.swift:234).
    if number_of_zeroes != 1:
        if abs(x3[1]) > abs(y):
            y = x3[1]
        if abs(x3[2]) > abs(y):
            y = x3[2]

    disc = y * y - 4 * d
    if abs(disc) < _ULP:
        q1 = y / 2
        q2 = q1
        disc = a * a - 4 * (b - y)
        if abs(disc) < _ULP:
            p1 = a / 2
            p2 = p1
        else:
            sqrt_disc = math.sqrt(disc)
            p1 = (a + sqrt_disc) / 2
            p2 = (a - sqrt_disc) / 2
    else:
        sqrt_disc = math.sqrt(disc)
        q1 = (y + sqrt_disc) / 2
        q2 = (y - sqrt_disc) / 2
        p1 = (a * q1 - c) / (q1 - q2)
        p2 = (c - a * q2) / (q1 - q2)

    disc = p1 * p1 - 4 * q1
    if abs(disc) < EPS16:
        _insert_if_positive(roots, -p1 / 2)
    elif disc > 0.0:
        sqrt_disc = math.sqrt(disc)
        _insert_if_positive(roots, (-p1 - sqrt_disc) / 2)
        _insert_if_positive(roots, (-p1 + sqrt_disc) / 2)

    disc = p2 * p2 - 4 * q2
    if abs(disc) < EPS16:
        _insert_if_positive(roots, -p2 / 2)
    elif disc > 0.0:
        sqrt_disc = math.sqrt(disc)
        _insert_if_positive(roots, (-p2 - sqrt_disc) / 2)
        _insert_if_positive(roots, (-p2 + sqrt_disc) / 2)

    return roots


def evaluate_polynomial(coefficients: Sequence[float], x: float) -> float:
    """Evaluate a polynomial at ``x`` via Horner's method.

    ``coefficients`` are ordered highest to lowest degree (Swift
    ``evaluatePolynomial``), which differs from
    ``UnivariatePolynomial``'s ascending-degree convention.
    """
    if not coefficients:
        return 0.0
    result = coefficients[0]
    for i in range(1, len(coefficients)):
        result = result * x + coefficients[i]
    return result


def polynomial_derivative(coefficients: Sequence[float]) -> list[float]:
    """Return the derivative's coefficients, highest to lowest degree.

    Matches ``Roots.swift:polynomialDerivative``; ``coefficients`` are
    ordered highest to lowest degree.
    """
    if len(coefficients) <= 1:
        return []
    count = len(coefficients) - 1
    deriv = [0.0] * count
    for i in range(count):
        deriv[i] = float(count - i) * coefficients[i]
    return deriv


def polynomial_monic_derivative(coefficients: Sequence[float]) -> list[float]:
    """Return the monic-normalized derivative's coefficients, highest to lowest degree.

    Matches ``Roots.swift:polynomialMonicDerivative``; ``coefficients`` are
    ordered highest to lowest degree and assumed monic (leading coefficient 1).
    """
    if len(coefficients) <= 1:
        return []
    n = len(coefficients)
    deriv = [0.0] * (n - 1)
    deriv[0] = 1.0
    for i in range(1, n - 1):
        deriv[i] = float(n - 1 - i) * coefficients[i] / float(n - 1)
    return deriv


def shrink_interval(coefficients: Sequence[float], left: float, right: float) -> float:
    """Shrink ``[left, right]`` to converge on a bracketed root of ``coefficients``.

    Safe-Newton (Newton-Raphson with bisection fallback) iteration, matching
    ``Roots.swift:shrinkInterval``. ``coefficients`` are ordered highest to
    lowest degree and must bracket exactly the root of interest.
    """
    lo = left
    hi = right

    f_lo = evaluate_polynomial(coefficients, lo)
    if f_lo == 0.0:
        return lo

    f_hi = evaluate_polynomial(coefficients, hi)
    if f_hi == 0.0:
        return hi

    if f_lo > 0.0:
        lo, hi = hi, lo

    rts = (lo + hi) / 2
    dx_old = abs(hi - lo)
    dx = dx_old
    deriv = polynomial_derivative(coefficients)
    f = evaluate_polynomial(coefficients, rts)
    df = evaluate_polynomial(deriv, rts)

    for _ in range(_MAX_ITS):
        if (((rts - hi) * df - f) * ((rts - lo) * df - f) > 0.0) or (
            abs(2 * f) > abs(dx_old * df)
        ):
            dx_old = dx
            dx = (hi - lo) / 2
            rts = lo + dx
            if lo == rts:
                break
        else:
            if f == 0.0:
                # f == 0 (regardless of df) means rts is already the root;
                # dividing (0.0 / df) is either 0 or, when df is also 0.0,
                # a ZeroDivisionError trap. Swift's untyped division would
                # silently produce NaN/inf here and the safe-Newton loop
                # would exit via the dx-tolerance check below; returning the
                # already-found root directly is the guard called out in
                # polynomials.md design constraint 2.
                return rts
            dx_old = dx
            dx = f / df
            temp = rts
            rts -= dx
            if temp == rts:
                break

        if abs(dx) < POLYNOMIAL_TOLERANCE:
            break

        f = evaluate_polynomial(coefficients, rts)
        df = evaluate_polynomial(deriv, rts)

        if f < 0.0:
            lo = rts
        else:
            hi = rts

    return rts


def integrate_jerk(
    t: float, p0: float, v0: float, a0: float, j: float
) -> tuple[float, float, float]:
    """Constant-jerk kinematic step: ``(p, v, a)`` after duration ``t``.

    Matches ``Utils.swift:integrate``.

    Args:
        t: Duration in seconds.
        p0: Initial position.
        v0: Initial velocity.
        a0: Initial acceleration.
        j: Applied (constant) jerk over the interval.

    Returns:
        The ``(position, velocity, acceleration)`` tuple after time ``t``.
    """
    return (
        p0 + t * (v0 + t * (a0 / 2 + t * j / 6)),
        v0 + t * (a0 + t * j / 2),
        a0 + t * j,
    )
