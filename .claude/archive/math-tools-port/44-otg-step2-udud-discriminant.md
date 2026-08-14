---
chunk: 44-otg-step2-udud-discriminant
track: F
status: complete
depends_on: []
spec: ../specs/otg.md §Internal fidelity 2
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 44 — Fix UDUD T0246 discriminant transcription drift (Step2)

## Origin

Post-audit finding E-1 (class **c**, spec/Swift drift). Confirmed firsthand by
side-by-side read of the Swift source against the port.

`SWIFT_MATH/OTG/position/PositionThirdOrderStep2.swift:1279,1286,1289` computes
`jMax * tfP2 * tf` — that is **j·tf³**. The port at
`src/math_tools/otg/steps/position_third_order_step2.py:1731,1752,1763`
computes `j_max * self.tf_p3 * self.tf` — that is **j·tf⁴**, because `tf_p3`
is already `tf*tf*tf` (`:174`). One power too many, at three sites inside
`_time_none`'s UDUD T0246 branch.

Impact: ~0.57% of prescribed-duration Step2 solves select a different profile
branch. Both branches pass `Profile.check`, so the existing gate cannot see it.

## Files

- Edit: `src/math_tools/otg/steps/position_third_order_step2.py`
- Edit: `tests/otg/steps/test_position_third_step2.py`

## Design constraints

1. The fix is mechanical: at each of the three sites, `self.tf_p3 * self.tf`
   becomes `self.tf_p2 * self.tf`. Do **not** "simplify" this to `self.tf_p3`
   — keep the Swift's literal `tfP2 * tf` shape so the next auditor can diff
   token-for-token against the Swift line.
2. Change **only** those three multiplications. Every other expression in
   `_time_none` was token-diffed against the Swift source during the audit and
   is correct; do not touch it.
3. Do not alter `tf_p3`'s definition at `:174` — it is used correctly
   elsewhere.

## TDD steps

1. Write a failing regression test that pins the corrected branch selection.
   Use this boundary condition, which the audit confirmed diverges between the
   two variants:
   `(p0, v0, a0, pf, vf, af) = (0.4524, 0, 0.4983, 0.2324, 0.2779, 0, 0)`-style
   inputs — construct a Step2 solve with a prescribed `tf` and assert the
   resulting profile's segment times match the **j·tf³** result. Derive the
   expected values by running the corrected formula, and record in the test
   docstring that these came from the Swift-faithful form.
2. Apply the three-site fix.
3. Confirm the new test passes and the full existing OTG suite still passes —
   in particular `tests/otg/test_otg_truth_table.py` (31 cases) must remain
   green, since it is the strongest existing oracle.
4. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All three sites read `self.tf_p2 * self.tf`
- [x] New regression test fails before the fix, passes after
- [x] `tests/otg/test_otg_truth_table.py` still passes unchanged (no tolerance loosening)
- [x] Full `tests/otg/` suite green
- [x] `make uv-fullCheck` passes

## Out of scope

Broadening Step2 oracle coverage — that is chunk 56. Any other Step1/Step2
arithmetic (audited clean).

## Resolution notes

- The three sites (`:1731,1752,1763`) each changed `j_max * self.tf_p3 *
  self.tf` to `j_max * self.tf_p2 * self.tf` per design constraint 1 (kept
  the Swift's literal `tfP2 * tf` shape, did not collapse to `self.tf_p3`).
  `tf_p3`'s definition (`:174`) and all its other call sites (`:1642, 1997,
  2019, 2036, 2052, 2204, 2222, 2229, 2265`) were left untouched.
- The hardest part of this chunk was TDD step 1: finding a concrete
  boundary condition that actually reaches the "UDUD T0246" branch (needs
  `a0 != 0`, which the plan's example inputs matched) *and* where the buggy
  vs. Swift-faithful discriminant diverge enough to flip which
  `control_signs` branch `_time_none` selects (both pass
  `Profile.check_with_timing`, so most random inputs do NOT diverge in a
  test-detectable way — this matches the origin note's measured ~0.57%
  rate). Found by an in-process random search: loaded the source twice
  (unpatched, and with the three sites mechanically patched to
  `tf_p2 * self.tf` in an in-memory copy of the module text), ran both
  against ~200k random rest-unconstrained boundary conditions with
  `a0 != 0`, and kept the first divergent case. Landed on
  `p0=0.0, v0=-0.5237, a0=2.7015, pf=-1.7271, vf=-1.9901, af=1.6448,
  tf=11.2581` (v_max/a_max=10, j_max=1): pre-fix selects UDDU with a
  4-nonzero-segment profile, Swift-faithful selects UDUD T0246 (`t[1]=t[3]=
  t[5]=0`). The expected `t[]` values hardcoded in the test are the
  Swift-faithful run's output at full float precision, verified to reach
  `pf/vf/af` and sum to `tf`.
- Confirmed red/green manually: reverted the fix via `git apply -R` on a
  scratch patch, ran the new test (failed on `control_signs` mismatch:
  `UDDU != UDUD`), then reapplied the fix and reran (passed). This
  reproduces the TDD-step-1/3 cycle without polluting the git history with
  an intermediate failing commit.
- No spec change was needed — `otg.md`'s "Internal fidelity requirements"
  §2 already mandates mechanical, token-faithful translation; this chunk
  brings the code into conformance with the existing contract rather than
  changing it.
