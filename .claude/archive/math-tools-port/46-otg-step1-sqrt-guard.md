---
chunk: 46-otg-step1-sqrt-guard
track: F
status: complete
depends_on: []
spec: ../specs/otg.md §Internal fidelity 4
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 46 — Apply the IEEE-754 sqrt guard to Step1

## Origin

Post-audit finding E-3 (class **c**). Confirmed by grep:
`position_third_order_step2.py` uses `_ieee754_sqrt` at **32** sites;
`position_third_order_step1.py` uses bare `math.sqrt` at **8+** sites
(`:239, :283, :325, :396, :832, :891, :942, :991`).

Swift's `Double.sqrt` returns `nan` on a negative radicand and lets the `nan`
propagate into `Profile.check`, which rejects the branch. Python's
`math.sqrt` raises `ValueError: math domain error` instead. The audit
reproduced the raise in 6,718/30,000 direct Step1 fuzz calls.

otg.md §Internal fidelity 4 already mandates `_ieee754_sqrt` file-wide for
exactly this reason; Step1 was simply left unwrapped.

**Severity: latent, not live.** The audit drove 51,733 `validate()`-passing
1-DOF inputs through `Otg.calculate` and triggered **zero** exceptions — brake
pre-processing appears to shield the path. Fix it as hardening, not as an
outage.

## Files

- Edit: `src/math_tools/otg/steps/position_third_order_step1.py`
- Edit: `tests/otg/steps/test_position_first_second.py` (or the Step1 test file)

## Design constraints

1. Replace every bare `math.sqrt` in this file with the same `_ieee754_sqrt`
   helper Step2 imports. Do not write a second helper — import the existing one.
2. Replacement must be mechanical and total: after the change,
   `grep -n "math.sqrt" src/math_tools/otg/steps/position_third_order_step1.py`
   returns nothing.
3. Do not restructure surrounding branch logic. The point is that a negative
   radicand yields `nan` and the branch is then rejected by `Profile.check`,
   exactly as in Swift — no new explicit guards, no early returns.

## TDD steps

1. Write a failing test that calls a Step1 solver directly with a boundary
   condition producing a negative radicand, and asserts it returns/propagates
   without raising `ValueError` (branch rejected, not crashed). The audit found
   these via fuzzing; pick one concrete reproducing case and hard-code it.
2. Apply the replacement.
3. Re-run the full OTG suite; truth table and comprehensive suites must stay green.
4. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Zero `math.sqrt` occurrences remain in the file
- [x] `_ieee754_sqrt` imported from its existing location, not redefined
- [x] Negative-radicand test fails before (ValueError), passes after
- [x] Full `tests/otg/` suite green
- [x] `make uv-fullCheck` passes

## Out of scope

Auditing other modules for bare `math.sqrt`. `functional/roots.py` has its own
divide-by-zero issue — that is chunk 48.

## Resolution notes

- `_ieee754_sqrt` lives in `position_third_order_step2.py` (module-private,
  no `__all__` export) and was never previously imported cross-module;
  `position_third_order_step1.py` now imports it directly
  (`from math_tools.otg.steps.position_third_order_step2 import
  _ieee754_sqrt`). Verified no circular-import risk: `step2.py` imports
  nothing from `step1.py` (only `calculator_target.py` imports both, as
  siblings). No second helper was written, per the design constraint.
- All 8 sites replaced mechanically via a scoped `sed` pass matching only
  `math.sqrt(` — `math.nan`, `math.copysign`, `math.inf` (used by the
  file's existing `_ieee754_div`) were untouched, and the bare `import
  math` stays because those calls remain.
- Reproducing test: `PositionThirdOrderStep1(a0=af=-1.0, v0=vf=0.0, pd=1.0,
  j_max=0.0)` routes `get_profile` to the zero-limits special case
  (`_time_all_single_step`), where `q = sqrt(2*a0*pd + v0**2) =
  sqrt(-2)` was the failing call. Confirmed raising `ValueError: math
  domain error` before the fix; after the fix `_ieee754_sqrt` returns
  `nan`, `profile.t[3] = nan` fails the immediately-following `>= 0.0`
  guard (Python's `nan >= 0.0` is `False`), so the branch is silently
  rejected and `get_profile` returns `False` — `Profile.check` is never
  even reached for this particular case, an even earlier rejection point
  than the audit's general nan-propagation account, but consistent with
  it (the candidate is discarded, not crashed).
- Added test class `TestPositionThirdOrderStep1NegativeRadicandGuard` to
  `tests/otg/steps/test_position_third_step1.py` (the existing Step1 test
  file; `test_position_first_second.py` covers the first/second-order
  interfaces, not this file, so the chunk's file list's parenthetical
  alternative was resolved in favor of the file that actually matches).
- No branch logic restructured; no new explicit guards added, per design
  constraint 3. Full `tests/otg/` (226 tests) and the repo-wide gate
  (1360 tests + ruff + mypy) are green.
