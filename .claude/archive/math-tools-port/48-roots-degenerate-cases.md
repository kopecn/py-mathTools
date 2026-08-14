---
chunk: 48-roots-degenerate-cases
track: F
status: complete
depends_on: []
spec: ../specs/polynomials.md rules 3-4
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 48 — Roots: near-zero leading coefficient and the 0/0 Newton trap

## Origin

Post-audit findings B-7 and B-14. Both live in `functional/roots.py`, which the
OTG calls per control cycle.

**B-7 (class a/b)** — confirmed at runtime:
`solve_cubic(1e-10, 2.0, -3.0, -2.0)` returns `[]`; `np.roots` finds a real
root at `2.0`. polynomials.md rule 4 names near-zero leading coefficient as a
required degenerate case, but the fallback threshold at
`src/math_tools/functional/roots.py:86` is `_ULP` (2.2e-16), so a coefficient
of 1e-10 takes the cubic branch and the solve collapses. The test that looks
like it covers this (`tests/functional/test_roots.py:104`) passes `a = 0.0`
*exactly*, and the randomized cross-check at `:208` explicitly `continue`s on
`abs(a) < 1e-6` — so the gap is masked from both directions.

**B-14 (class a)** — `roots.py:374` computes `dx = f / df` and raises
`ZeroDivisionError` when `f == 0.0 and df == 0.0`: the bisection guard at
`:364` evaluates `0 > 0` and `abs(0) > abs(0)` as both false and falls through.
Swift produces NaN/inf here rather than trapping. Untested.

## Files

- Edit: `src/math_tools/functional/roots.py`
- Edit: `tests/functional/test_roots.py`
- Possibly edit: `.claude/specs/polynomials.md` (see constraint 3)

## Design constraints

1. B-7: raise the degeneracy threshold from `_ULP` to a scale-relative test —
   compare `abs(a)` against the other coefficients' magnitude (e.g.
   `abs(a) <= eps * max(abs(b), abs(c), abs(d))`), not against an absolute
   constant. An absolute threshold cannot be right across the coefficient
   scales this module sees. Pick the epsilon, justify it in a comment, and
   state it in the spec.
2. B-14: guard the `f == 0.0 and df == 0.0` case before the division. `f == 0`
   means the root is already found — return it. Do **not** paper over this with
   a blanket `try/except ZeroDivisionError`.
3. If constraint 1 changes the documented threshold semantics, update
   `.claude/specs/polynomials.md` rule 4 in this same chunk and bump its
   `semver` (00-overview convention 1).
4. Keep the module stdlib-only — `tests/functional/test_roots.py` has an AST
   test pinning this. Use `numpy` only inside tests, as the existing
   cross-check already does.

## TDD steps

1. Failing tests first:
   - `solve_cubic(1e-10, 2.0, -3.0, -2.0)` returns a root ≈ 2.0 (cross-check
     against `np.roots`, filtering to finite real roots).
   - Sweep the leading coefficient across several decades (1e-4 … 1e-14) and
     assert agreement with `np.roots` at each — this is what the `continue` at
     `:208` was suppressing. Remove that `continue`, do not widen it.
   - A Newton call reaching `f == 0.0 and df == 0.0` returns the root instead
     of raising `ZeroDivisionError`.
   - Cover the `solve_resolvent` `count == 2` branch (`roots.py:201-203`),
     currently unexercised (finding B-8).
2. Apply both fixes.
3. Re-run the OTG suite as well — this module is on the OTG hot path and a
   threshold change can move OTG branch selection. Truth table must stay green.
4. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Near-zero leading coefficient agrees with `np.roots` across 1e-4…1e-14
- [x] The `abs(a) < 1e-6` `continue` at test_roots.py:208 is gone, not widened
- [x] The 0/0 Newton case returns a root; no `ZeroDivisionError`
- [x] `solve_resolvent` `count == 2` branch covered
- [x] Spec updated + `semver` bumped if the threshold contract changed
- [x] `tests/otg/` still green (hot-path regression check)
- [x] `make uv-fullCheck` passes

## Out of scope

`shrink_interval`'s loose 1e-9 test tolerance (finding B-9) — that is chunk 54.

## Resolution notes

- **B-7 fix** (`roots.py:86`, `_CUBIC_LEADING_COEFF_EPS = 1e-6`): replaced
  the absolute `abs(a) < _ULP` leading-coefficient degeneracy check with
  `abs(a) <= 1e-6 * max(abs(b), abs(c), abs(d))`. `1e-6` was picked
  empirically, not arbitrarily: measured the closed-form cubic branch's
  error vs. `np.roots` and the quadratic-fallback's error vs. `np.roots`
  across `a` from `1e-4` to `1e-14` (fixed `b=2, c=-3, d=-2`, the B-7 repro
  coefficients) — the cubic branch's error grows as `a` shrinks (the
  `1/a**3` scaling amplifies rounding error, reaching total failure by
  `a≈1e-9`), while the quadratic fallback's error shrinks as `a` shrinks
  (`O(a)`, since it's exactly the term being dropped); the two cross near
  `a / max(|b|,|c|,|d|) ≈ 1e-6`. Below that ratio the quadratic branch is
  strictly more accurate, so that's where the switch happens. This is
  documented in the module (constant docstring) and in polynomials.md rule
  4 (semver bumped 0.0.3 → 0.0.4).
- **Test tolerance for the decade sweep**: since the quadratic fallback's
  error is `O(a)`, a fixed `atol` across the 1e-4…1e-14 sweep would either
  be too loose at the small end or fail at the large end. Used
  `atol = max(2.0 * a, 1e-9)`, empirically bounding the observed error
  (worst case ~1.6× the fallback's ratio) with margin.
- **B-14 fix** (`shrink_interval`, `roots.py:372-380`): added
  `if f == 0.0: return rts` immediately before the `dx = f / df` Newton
  step, inside the `else` branch (the one the bisection guard falls through
  to). No blanket `try/except` — the guard is unconditional on `f == 0.0`
  because `f == 0` already means the root is found regardless of `df`;
  computing `dx = 0.0 / df` is redundant work at best and a
  `ZeroDivisionError` at worst (`df == 0.0` too, e.g. at a root of
  multiplicity ≥ 2). Repro test brackets `(x-2)^3` on `[1, 3]`: the initial
  midpoint guess lands exactly on the triple root, where both `f` and `f'`
  are `0.0` on the very first iteration.
- **`solve_resolvent` `count == 2` coverage (B-8)**: added
  `TestSolveResolvent.test_two_real_roots_case` using the resolvent of
  `(y-2)^2(y+1) = y^3 - 3y^2 + 4`, which takes the `r2 >= q3` branch and
  collapses `x[2]` to within `_ULP` of `x[1]`. This is a coverage-only
  addition — no code change was needed for this path (it already worked;
  it was just untested), consistent with "implemented, untested" finding
  class (b).
- **No behavioral surprises** beyond the tolerance-scaling question above.
  `tests/otg/` (226 tests, 90 subtests) and the full suite (1372 tests)
  are green; the leading-coefficient threshold change does not visibly
  move OTG branch selection in the existing oracle corpus.
