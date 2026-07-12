---
chunk: 09-univariate-polynomial
track: B
status: pending
depends_on: [02]
spec: ../specs/polynomials.md §UnivariatePolynomial, §Compliance 1, 7
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 09 — `UnivariatePolynomial`

**Deliverable:** the numpy-backed general polynomial class.

## Files

- Create: `src/math_tools/functional/__init__.py` (export),
  `src/math_tools/functional/py.typed`,
  `src/math_tools/functional/polynomial.py`
- Create: `tests/functional/__init__.py`,
  `tests/functional/test_polynomial.py`

## Design constraints

1. One immutable class per spec: ascending-degree `coefficients`
   (float64 ndarray, trailing zeros trimmed), `degree`, `coefficient_at`,
   `__call__` (scalar and array via
   `numpy.polynomial.polynomial.polyval`), `derivative`,
   `integrate(constant=0.0)`, `real_roots(tolerance=...)` (companion-matrix,
   imag-filtered, sorted ascending; zero polynomial →
   `PolynomialSolveError` from `math_tools.errors`; nonzero constant → `[]`),
   `==`, human-readable `repr`.
2. `real_roots` returns ALL real roots — the deliberate contrast with the
   OTG kernel (chunk 10) is stated in both docstrings.
3. Tolerance default is `POLYNOMIAL_ZERO_THRESHOLD`; import it from
   `math_tools.functional.roots` if chunk 10 has landed, else define the
   module constant here and chunk 10 re-homes it (note which happened).

## TDD steps

1. Failing tests: spec compliance 1 (`[−1, 0, 1]` → roots `[−1, 1]`,
   derivative/integrate round-trip, vector `__call__` vs Horner), trimming
   (`degree([1, 0, 0]) == 0`), zero-poly raise, repr shape, immutability.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Compliance item 1 tests pass; multiplicity case (e.g. `(x−1)²`) returns the duplicated root
- [ ] Zero polynomial raises `PolynomialSolveError`
- [ ] `make uv-fullCheck` passes

## Out of scope

The analytic root kernel (chunk 10); polynomial arithmetic between
polynomials (not in spec); fitting.
