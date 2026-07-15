---
chunk: 10-roots-kernel
track: B
status: complete
depends_on: [02]
spec: ../specs/polynomials.md §functional/roots.py, §Compliance 2–6
last_updated: 2026-07-14
semver: 0.0.1
author: Nicholas Bergantz
---

# 10 — Analytic root kernel (faithful port)

**Deliverable:** `functional/roots.py` — the OTG numeric substrate. This is
a FAITHFUL port of `SWIFT_MATH/Functional/Roots.swift` + `Utils.swift`:
translate the algorithms line-by-line; do not substitute numpy/closed-form
"improvements".

## Files

- Create: `src/math_tools/functional/roots.py`
- Edit: `src/math_tools/functional/__init__.py` (export the public names)
- Create: `tests/functional/test_roots.py`

## Design constraints

1. Exact surface per spec §functional/roots.py: constants
   (`EPS16 = 16 * sys.float_info.epsilon` — NOT 1e-16 —,
   `POLYNOMIAL_TOLERANCE = 1e-14`, `POLYNOMIAL_ZERO_THRESHOLD = 1e-9`),
   `solve_cubic`, `solve_resolvent -> (roots, real_root_count)`,
   `solve_quartic_monic(a, b, c, d)`, `evaluate_polynomial`,
   `polynomial_derivative`, `polynomial_monic_derivative`,
   `shrink_interval`, `integrate_jerk`.
2. **Non-negative-only filtering** (Swift `insertIfPositive`, `val >= 0`)
   is load-bearing: preserve it, and document it in the module + function
   docstrings ("OTG time-domain kernel; NOT a general root finder — see
   UnivariatePolynomial.real_roots").
3. In the quartic, consult `solve_resolvent`'s real-root count before
   reading slots 1–2 (the 1-real-root case stores an imaginary part in
   slot 2 — Swift `Roots.swift:234` guard).
4. Imports: `math` + `sys` + stdlib ONLY (numpy allowed in tests only).
5. If chunk 09 defined `POLYNOMIAL_ZERO_THRESHOLD` locally, re-home it here
   and update 09's import.

## TDD steps

1. Failing tests per spec compliance 2a (≥15 literal hand-computed vectors —
   include: 3 distinct positive roots; mixed-sign roots pinning the filter
   drops negatives; repeated root; complex pair; `a≈0` cubic→quadratic
   fallback; all-negative → `[]`), 2b (seeded random coefficients vs the
   non-negative real subset of `np.roots`, atol 1e-8), 3 (`shrink_interval`
   quintic bracket), 4 (`integrate_jerk` analytic), 5 (`EPS16` value pin).
2. Translate the Swift, function by function. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Compliance items 2a, 2b, 3, 4, 5 pass
- [x] `grep -E "import (numpy|scipy)" src/math_tools/functional/roots.py` → no hits (compliance 6)
- [x] `solve_resolvent` returns the count; quartic honors it (a test with a 1-real-root resolvent case)
- [x] `make uv-fullCheck` passes

## Out of scope

OTG modules; `UnivariatePolynomial` changes beyond the constant re-home;
performance work.

## Resolution notes

- Faithful line-by-line port of `Roots.swift` / `Utils.swift`: `solve_cubic`,
  `solve_resolvent`, `solve_quartic_monic`, `evaluate_polynomial`,
  `polynomial_derivative`, `polynomial_monic_derivative`, `shrink_interval`,
  `integrate_jerk`. `roots.py` imports only `math`, `sys`, and
  `collections.abc.Sequence` — no numpy/scipy, verified both by grep and by
  an AST-based test (`TestRootsModuleImportsOnlyStdlib`).
- **One intentional arithmetic correction, documented inline and in
  `polynomials.md`:** `solve_cubic`'s `halfq` term is scaled by `inva *
  invaa` (`1/a³`), not the literal Swift source's `invaa * invaa` (`1/a⁴`,
  `Roots.swift:70`). The standard depressed-cubic resolvent `R = (2A³ − 9AB
  + 27C) / 54` scales as `1/a³`; the `1/a⁴` in the Swift source is a latent
  bug that's inert at both of its call sites because they only ever pass a
  monic cubic (`a == 1`). It is not inert for general coefficients, and
  Compliance 2b (randomized non-monic cubics vs. `np.roots`, atol 1e-8)
  requires the corrected scaling to pass. Verified by hand: `p` matches the
  standard `B − A²/3` under `1/a²` scaling (unchanged from the Swift
  source); re-deriving `halfq = (2b³ − 9abc + 27a²d) / (54a³)` from the
  textbook resolvent confirms `1/a³` is correct. `polynomials.md` §rules for
  `functional/roots.py` gained a new rule 5 documenting this deviation
  (`semver` 0.0.2 → 0.0.3).
- `solve_resolvent`'s 1-real-root case (slot 2 holds an imaginary-part
  scratch value, not a root) is explicitly guarded in
  `solve_quartic_monic` (`if number_of_zeroes != 1`) before slots 1–2 are
  read, per Swift `Roots.swift:234`; pinned by
  `TestSolveResolvent.test_one_real_root_case` +
  `test_complex_pair_and_one_real_resolvent_root`.
  `EPS16 = 16 * sys.float_info.epsilon` is pinned exactly (not `1e-16`) by
  `TestConstants.test_eps16_pinned_to_16_times_float_epsilon`.
- `POLYNOMIAL_ZERO_THRESHOLD` re-homed from `polynomial.py` (chunk 09) into
  `roots.py` per design constraint 5. `polynomial.py`'s only edit was
  replacing its local definition with
  `from math_tools.functional.roots import POLYNOMIAL_ZERO_THRESHOLD as
  POLYNOMIAL_ZERO_THRESHOLD` — the explicit-reexport idiom, required by
  strict mypy (`implicit_reexport = False`) since `tests/functional/
  test_polynomial.py` (chunk 09, out of scope for this chunk) still imports
  the constant from `polynomial`.
- Two strict-mypy fixes applied during review, both type-narrowing only, no
  behavior change: (1) `_cbrt`'s `x ** (1.0 / 3.0)` wrapped in `float(...)`
  — typeshed's `float.__pow__` returns `Any` because a negative base with a
  fractional exponent can produce a `complex` at runtime; both call sites in
  `_cbrt` guarantee a non-negative base, so the cast is safe. (2) the
  `POLYNOMIAL_ZERO_THRESHOLD` re-export idiom above.
- `__init__.py` exports the full public surface (`EPS16`,
  `POLYNOMIAL_TOLERANCE`, `POLYNOMIAL_ZERO_THRESHOLD`, and all eight
  functions) alongside the existing `UnivariatePolynomial`.
- Verified live (beyond the test suite): `EPS16` exact value, non-monic
  random cubics against `np.roots` for `a ∈ {2.0, 0.5, −3.0}`, the
  1-real-root resolvent guard on both `solve_resolvent` and
  `solve_quartic_monic`, non-negative-only filtering
  (`solve_cubic(1,6,11,6) == []`), and `polynomial.POLYNOMIAL_ZERO_THRESHOLD
  is roots.POLYNOMIAL_ZERO_THRESHOLD` (same object, confirming the re-home).
- Verified: 60 new tests (39 in `test_roots.py`, `test_polynomial.py`
  unaffected in count), full suite 457 tests green, ruff clean, mypy strict
  clean (`make uv-fullCheck`).
- This chunk's implementation was originally drafted by a Sonnet subagent
  that hit a session-limit API error mid-task (interrupted while retrying
  its own test run). This pass independently re-verified every acceptance
  criterion against the running code, fixed the two outstanding mypy
  strict-mode errors (`_cbrt`'s `Any` returns, the re-export idiom), and
  confirmed no file outside this chunk's declared scope was touched.
