---
chunk: 09-univariate-polynomial
track: B
status: complete
depends_on: [02]
spec: ../specs/polynomials.md §UnivariatePolynomial, §Compliance 1, 7
last_updated: 2026-07-13
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

- [x] Compliance item 1 tests pass; multiplicity case (e.g. `(x−1)²`) returns the duplicated root
- [x] Zero polynomial raises `PolynomialSolveError`
- [x] `make uv-fullCheck` passes

## Out of scope

The analytic root kernel (chunk 10); polynomial arithmetic between
polynomials (not in spec); fitting.

## Resolution notes

- `POLYNOMIAL_ZERO_THRESHOLD` is defined in `functional/polynomial.py`
  (chunk 10 / `functional/roots.py` had not landed at execution time). The
  module docstring and the constant's own docstring both note that chunk 10
  will re-home it and that this module should then import it from there
  instead of defining it — per design constraint 3.
- `real_roots` uses `np.roots` on the descending-order coefficients
  (`coefficients[::-1]`), filters by `abs(root.imag) <= tolerance`, and
  returns `sorted(...)` ascending; the zero-polynomial case
  (`degree == 0 and coefficients[0] == 0.0`) raises `PolynomialSolveError`
  before ever calling `np.roots`; nonzero-constant (`degree == 0`, nonzero)
  returns `[]` without calling `np.roots`.
- `__call__` normalizes `x` via `np.asarray(x, dtype=np.float64)` before
  calling `numpy.polynomial.polynomial.polyval`, then branches on
  `arr.ndim == 0` to return a plain `float` for scalar input vs. an
  `npt.NDArray[np.float64]` for array input — this was required to satisfy
  mypy strict against numpy's `_FuncVal` overload set (a bare
  `float | ArrayLike` union does not resolve cleanly against
  `numpy.polynomial.polynomial.polyval`'s overloads).
- `__init__` accepts `Sequence[float] | npt.NDArray[np.floating[Any]]`
  (rather than `Sequence[float]` alone, as sketched in the design
  constraints) because `derivative`/`integrate` construct new instances
  directly from `numpy.polynomial.polynomial.polyder`/`polyint` output,
  whose mypy-inferred dtype is `floating[Any]`, not concretely `float64`.
  Storage itself is still always coerced/copied to `float64` internally, so
  behavior is unaffected — this is a type-signature widening only, not a
  spec/contract change.
- Immutability: `__slots__ = ("_coefficients",)`, no property setters; the
  `coefficients` property and the constructor both copy the array
  (`np.array(..., dtype=np.float64)` / `np.asarray(...)` followed by
  trimming into a fresh array) so neither construction-time aliasing nor
  post-hoc mutation of a returned array can affect internal state.
  `__hash__ = None` per the repo-wide mutable/immutable numpy-backed idiom
  (documented as "only the immutable precision-time types are hashable" in
  the umbrella spec, but every existing numpy-backed class sets
  `__hash__ = None` regardless of the class's own immutability, so this
  class follows the same idiom rather than special-casing itself as
  hashable).
- `repr` follows the spec's literal example format (`"3.0·x² − 1.0"`) —
  bare expression text, no `UnivariatePolynomial(...)` wrapper — using the
  Unicode minus sign `−` (U+2212, not ASCII hyphen) and Unicode superscript
  digits for degree ≥ 2. Pinned by five new tests (constant, linear,
  two-term, negative-leading-term, zero-polynomial).
- No spec change was needed; implementation matches `polynomials.md`
  §UnivariatePolynomial as written.
- Verified: 38 new tests in `tests/functional/test_polynomial.py`, full
  suite 418 tests green, ruff clean, mypy strict clean
  (`make uv-fullCheck`).
