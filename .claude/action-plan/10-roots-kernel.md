---
chunk: 10-roots-kernel
track: B
status: pending
depends_on: [02]
spec: ../specs/polynomials.md §functional/roots.py, §Compliance 2–6
last_updated: 2026-07-11
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

- [ ] Compliance items 2a, 2b, 3, 4, 5 pass
- [ ] `grep -E "import (numpy|scipy)" src/math_tools/functional/roots.py` → no hits (compliance 6)
- [ ] `solve_resolvent` returns the count; quartic honors it (a test with a 1-real-root resolvent case)
- [ ] `make uv-fullCheck` passes

## Out of scope

OTG modules; `UnivariatePolynomial` changes beyond the constant re-home;
performance work.
