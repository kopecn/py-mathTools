---
version: 1.0
type: specification
name: polynomials
purpose: Behavioral contract for the univariate polynomial type and the analytic root solvers
spec: Polynomials
scope: project
status: accepted
applies_to: src/math_tools/functional/, tests/functional/
last_updated: 2026-07-23
semver: 0.0.4
author: Nicholas Bergantz
---

# Polynomials and Root Solvers

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). Two
> deliberately different fidelity levels: a **pythonic polynomial class**
> (numpy-backed, replaces the Swift subclass-per-degree hierarchy) and a
> **faithful port of the analytic root kernel** (`Roots.swift` /
> `Utils.swift`), because the OTG solver ([otg.md](otg.md)) depends on that
> kernel's exact semantics and tolerances.

## `functional/polynomial.py` — `UnivariatePolynomial`

One class; the Swift `PolynomialUnivariateOrder` enum + eleven subclasses
collapse (documented divergence — composition over inheritance; numpy's
companion-matrix roots supersede per-degree closed forms for the general
API).

- Storage: `coefficients: npt.NDArray` float64, **ascending degree order**
  (`c[0] + c[1]·x + …`, numpy convention; the Swift ordering is mapped at
  construction — pin with a test).
- `UnivariatePolynomial(coefficients: Sequence[float])` — `ValueError` on
  empty; trailing (highest-degree) zeros trimmed, so `degree` is exact.
- `degree: int`; `coefficient_at(degree: int) -> float` (0.0 beyond degree).
- `__call__(x: float | npt.NDArray) -> float | npt.NDArray` — Horner/
  `np.polynomial.polynomial.polyval`.
- `derivative -> UnivariatePolynomial`,
  `integrate(constant: float = 0.0) -> UnivariatePolynomial`.
- `real_roots(tolerance: float = POLYNOMIAL_ZERO_THRESHOLD) -> list[float]`
  — companion-matrix roots (`np.roots` equivalent), imaginary parts within
  tolerance treated as real, sorted ascending. Degree-0: empty list
  (constant ≠ 0) or `PolynomialSolveError` (zero polynomial — infinitely
  many roots).
- `==` (trimmed-coefficient equality), `repr` (human-readable
  `"3.0·x² − 1.0"` style), immutable (frozen dataclass or read-only
  property).

## `functional/roots.py` — analytic kernel (faithful port)

Free functions and constants, semantics matching `Roots.swift` /
`Utils.swift` exactly (this module is the OTG's numeric substrate — do not
"improve" it).

**This is NOT a general root finder.** Swift's `insertIfPositive`
(`Utils.swift:33`) means `solve_cubic` / `solve_quartic_monic` return only
**non-negative** real roots (they solve for time ≥ 0). This MUST be stated in
the module docstring and each function docstring; general root finding is
`UnivariatePolynomial.real_roots` above — the two contracts are deliberately
different.

```python
import sys

EPS16: float = 16 * sys.float_info.epsilon   # Swift: 16 * .ulpOfOne ≈ 3.5527e-15 (NOT 1e-16)
POLYNOMIAL_TOLERANCE: float = 1e-14
POLYNOMIAL_ZERO_THRESHOLD: float = 1e-9

def solve_cubic(a: float, b: float, c: float, d: float) -> list[float]: ...
def solve_resolvent(a: float, b: float, c: float) -> tuple[list[float], int]:
    """Roots of the cubic resolvent plus the REAL-root count (Swift returns Int).

    In the 1-real-root case the third slot holds the imaginary part, not a
    root — callers (solve_quartic_monic) must consult the count before
    reading slots 1..2.
    """
def solve_quartic_monic(a: float, b: float, c: float, d: float) -> list[float]:
    """Non-negative real roots of the monic quartic x⁴ + a·x³ + b·x² + c·x + d."""
def evaluate_polynomial(coefficients: Sequence[float], x: float) -> float: ...
def polynomial_derivative(coefficients: Sequence[float]) -> list[float]: ...
def polynomial_monic_derivative(coefficients: Sequence[float]) -> list[float]: ...
def shrink_interval(coefficients: Sequence[float], left: float, right: float) -> float: ...

def integrate_jerk(t: float, p0: float, v0: float, a0: float, j: float) -> tuple[float, float, float]:
    """Constant-jerk kinematic step → (p, v, a) after t. Swift Utils.integrate."""
```

Rules:

1. Real-root **multiplicity, ordering, and the non-negative filter** match
   the Swift implementation (translate the algorithm, then pin with test
   vectors; where Swift returns duplicated roots for multiplicity, so does
   this).
2. Coefficient argument ordering matches the Swift functions (document per
   function in the docstring; it differs from `UnivariatePolynomial`'s
   ascending convention).
3. Pure `math`-module scalar code — **no numpy** in this module (called
   per-cycle by OTG; keep it allocation-light).
4. Degenerate leading coefficients degrade exactly as Swift does (cubic with
   `a ≈ 0` within tolerance solves the quadratic, etc.) -- with one accepted
   deviation from the literal Swift source: `solve_cubic`'s leading-
   coefficient degeneracy check (`Roots.swift:37`'s `abs(a) < .ulpOfOne`) is
   an **absolute** threshold, which is wrong across the coefficient scales
   this module sees. A coefficient like `a = 1e-10` against `b, c, d` of
   order 1 is negligible, but `1e-10 >> ulpOfOne`, so the literal port took
   the cubic branch, whose `1/a**3` scaling amplifies rounding error until
   the solve collapses (confirmed: `solve_cubic(1e-10, 2.0, -3.0, -2.0)`
   returned `[]` instead of the root near `2.0`). `roots.py` instead uses a
   **scale-relative** threshold:
   `abs(a) <= 1e-6 * max(abs(b), abs(c), abs(d))` (constant
   `_CUBIC_LEADING_COEFF_EPS`). `1e-6` is chosen empirically as the
   crossover where the closed-form cubic formula's error (which grows as
   `a` shrinks, due to the `1/a**3` scaling) exceeds the quadratic
   fallback's error (which shrinks as `a` shrinks, `O(a)` by dropping the
   cubic term) -- pinned by the decade sweep in
   `TestSolveCubicNearZeroLeadingCoefficient` (`tests/functional/test_roots.py`),
   `a` from `1e-4` to `1e-14` against `b, c, d` of order 1-5.
5. **Accepted deviation from the literal Swift source:** `solve_cubic`'s
   `halfq` (the depressed-cubic resolvent term `R`) is scaled by `inva *
   invaa` (`1/a³`), not `Roots.swift:70`'s literal `invaa * invaa` (`1/a⁴`).
   The standard resolvent `R = (2A³ − 9AB + 27C) / 54` (`A=b/a, B=c/a,
   C=d/a`) scales as `1/a³`; the Swift source's `1/a⁴` is a latent scaling
   bug, inert at both of its call sites (`PositionThirdOrderStep2.swift`,
   `PolynomialUnivariateFunction.swift`) because they always pass a monic
   cubic (`a == 1`, where `1/a³ == 1/a⁴`). It is not inert for general
   coefficients: Compliance 2b (below) requires agreement with `np.roots`
   for randomized non-monic cubics, which the literal `1/a⁴` scaling fails
   for any `a != 1`. This is the one intentional arithmetic correction in
   this otherwise line-by-line port; it is called out inline in
   `roots.py`'s `solve_cubic`.

## Compliance requirements (test-checkable)

1. `UnivariatePolynomial([−1, 0, 1]).real_roots() == [−1.0, 1.0]`; derivative
   /integrate round-trip up to the constant; `__call__` matches Horner
   evaluation on a vector input.
2. Kernel functions pinned two ways, entirely within this repo (no Swift
   toolchain required):
   a. **Literal vectors** — ≥ 15 hand-computed cases as test literals
      spanning distinct roots, repeated roots, complex pairs, all-negative
      real roots (→ empty result, pinning the non-negative filter), and
      degenerate leading coefficient (`a ≈ 0` cubic → quadratic fallback).
      Agreement: atol 1e-9 per root, identical root counts.
   b. **Cross-check** — for randomized (seeded) coefficient sets, results
      equal the non-negative real subset of `np.roots` (imaginary part <
      `POLYNOMIAL_ZERO_THRESHOLD`), atol 1e-8; numpy is a test-only import.
3. `shrink_interval` converges on a bracketed root of a quintic to
   `POLYNOMIAL_TOLERANCE`.
4. `integrate_jerk` pinned analytically: `t=1, p0=0, v0=0, a0=0, j=6` →
   `(1.0, 3.0, 6.0)`.
5. `EPS16 == 16 * sys.float_info.epsilon` pinned by test (guards against the
   1e-16 transcription error).
6. `roots.py` imports nothing beyond `math`/`sys`/stdlib (grep-pinned).
7. mypy strict clean.
