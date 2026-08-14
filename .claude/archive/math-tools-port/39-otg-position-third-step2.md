---
chunk: 39-otg-position-third-step2
track: E
status: complete
depends_on: [34]
spec: ../specs/otg.md §Internal fidelity 2, 4, 5; §Module layout (chunking hints)
last_updated: 2026-07-21
semver: 0.0.2
author: Nicholas Bergantz
---

# 39 — `PositionThirdOrderStep2` (prescribed-duration)

**Deliverable:** `steps/position_third_order_step2.py` — faithful port of
`SWIFT_MATH/OTG/PositionThirdOrderStep2.swift` (~1,900 lines, the single
largest file in the port). Solves a profile hitting the target at an
EXACT prescribed duration (the synchronization workhorse).

## Files

- Create: `src/math_tools/otg/steps/position_third_order_step2.py`
- Create: `tests/otg/steps/test_position_third_step2.py`

## Design constraints

1. Same mechanical-translation rules as chunk 38. If a single session
   cannot finish, split at Swift function boundaries and leave the
   remaining functions raising `NotImplementedError` with the chunk noted
   `in_progress` — never merge a silently wrong branch.
2. Every polynomial solve routes through `functional.roots`; epsilon
   comparisons use the shared constants.

## TDD steps

1. Failing tests: take chunk 38's three analytic cases, compute their
   optimal durations, then ask Step2 for 1.25×, 1.5×, and 3× that duration —
   assert the returned profile (a) passes `Profile.check`, (b) reaches
   `pf/vf/af` (atol 1e-8), (c) has `t_sum[-1]` equal to the prescribed
   duration (atol 1e-9). Add one negative test: a duration BELOW optimal
   yields no valid profile.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All three scale factors × three cases pass; below-optimal rejected
- [x] `make uv-fullCheck` passes

## Out of scope

Step1 changes; TargetCalculator.

## Resolution notes

- Full mechanical port of all 10 Swift methods (`timeAcc0Acc1Vel`,
  `timeAcc1Vel`, `timeAcc0Vel`, `timeVel`, `timeAcc0Acc1`, `timeAcc1`,
  `timeAcc0`, `timeNone`, `timeNoneSmooth`, `getProfile`) as
  `PositionThirdOrderStep2` in
  `src/math_tools/otg/steps/position_third_order_step2.py`. No
  alias-mutation hazard here (unlike Step1): every method mutates the
  single caller-owned `Profile` directly and returns on first success,
  architecturally identical to `VelocityThirdOrderStep2` — no
  `copy.deepcopy` needed.
- Dropped the Swift `timeVel` method's `debugTimeVel`-gated `print(...)`
  block (a hardcoded-`false` developer tracing flag, permanently dead) —
  not part of the algorithm; every branch/root-search/Newton-step it
  wrapped is preserved exactly.
- `timeNoneSmooth` is never called from `getProfile` in the Swift source
  (grep-confirmed) — ported anyway per otg.md design constraint 2, same
  precedent as Step1's `*_two_step` methods.
- Preserved a genuine Swift source quirk verbatim in `_time_acc0`: the
  second `do` block is comment-labeled `// UDUD` but its
  `checkWithTiming` call actually passes `.UDDU`. Ported as literally
  executed, not "corrected" to match the comment.
- TDD surfaced a real fidelity gap beyond otg.md's `_ieee754_div`
  precedent: the "below-optimal duration is infeasible" negative test
  hit `math domain error` (Python `math.sqrt` on a negative argument)
  and, after the first site was patched, a `ZeroDivisionError` at two
  more sites. Traced the root cause: for a below-time-optimal prescribed
  duration, `get_profile` tries well over a dozen candidate branches in
  sequence, and a negative discriminant is the *generic* way each
  branch's algebra signals infeasibility — not a rare degenerate case.
  Added `_ieee754_sqrt` (Swift `sqrt(negative) == nan` semantics) and
  applied it at **every** `math.sqrt` call site in this one file
  (~30 sites) rather than iterating one failing-test-site at a time,
  since the hazard is structurally identical everywhere it appears; this
  intentionally goes beyond `_ieee754_div`'s narrower, per-site-only
  scoping (documented as a deliberate, file-scoped exception in both the
  module docstring and otg.md §Internal fidelity requirement 4, bumped
  to 0.0.4). Added `_ieee754_div` (identical to Step1's helper) and
  applied it only at the two sites the same test actually reached (T
  3456's `h0`/`t[3]` denominator, and the UZU 3-step profile's `t == 0`
  root), per the requirement's existing per-site scoping.
- `make uv-fullCheck` required hand-fixing ~46 `E501` line-too-long
  violations. Ran `ruff format` scoped to only this chunk's two files
  (not the Makefile's whole-tree `uv-format` target) per the chunk
  instructions barring a broad auto-formatter run; `git status` after
  confirms only the two new files changed.
- All three chunk-38 analytic cases (ACC0_ACC1_VEL long move, NONE short
  move, NONE moving-start) pass at 1.25×/1.5×/3× their Step1-optimal
  duration (`p`/`v`/`a` within 1e-8, `t_sum[-1] == tf` within 1e-9); the
  below-optimal negative test passes. Full gate:
  `make uv-fullCheck` — ruff clean, mypy strict clean (107 source
  files), 1318/1318 tests pass.
