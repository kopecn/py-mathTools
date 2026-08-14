---
chunk: 56-test-closure-otg-oracles
track: F
status: complete
depends_on: [44, 45, 46]
spec: ../specs/otg.md §Oracle, §Internal fidelity 3
last_updated: 2026-07-23
semver: 0.1.0
author: Nicholas Bergantz
---

# 56 — Test-coverage closure: OTG oracles

## Origin

Post-audit class **(b)** findings for Track E. This is the most consequential
coverage chunk in the set: the audit established that the OTG oracle corpus is
far narrower than its size suggests.

Runs after the three OTG code fixes so new oracles pin corrected behavior.

**Tests and test data only. No `src/` changes.**

## The headline gap

`tests/otg/data/successful_trajectories.json` + `failed_trajectories.json` —
1,784 cases, and **every single one** is 1-DOF / Position / Time-sync /
Continuous / no waypoints. Confirmed:

```
successful: 1682   dofs {1: 1682}  Position 1682  Time 1682  Continuous 1682
failed:      102   dofs {1: 102}   Position 102   Time 102   Continuous 102
```

Combined with the 1-DOF fast path at `calculator_target.py:546`, the audit
instrumented `PositionThirdOrderStep2.get_profile` and confirmed it is invoked
**exactly 0 times across all 1,784 corpus cases**. The 2,744-line Step2 module —
the largest, hardest file in the port, and the one chunk 44 just fixed a
transcription defect in — has no oracle coverage. Its only tests are 3 boundary
conditions × 3 scale factors.

## Files

- Edit: `tests/otg/test_otg_continuity.py`, `test_otg_driver.py`,
  `test_otg_invariants.py`, `test_otg_comprehensive.py`
- Edit: `tests/otg/test_calculator_target.py`
- Edit: `tests/otg/steps/test_position_third_step2.py`
- Create: multi-DOF corpus data under `tests/otg/data/`

## Gaps to close

1. **Multi-DOF corpus (E-4).** Generate a corpus that actually reaches Step2:
   ≥2 DOF, so the 1-DOF fast path is bypassed. Verify reach by instrumenting
   `PositionThirdOrderStep2.get_profile` and asserting a non-zero invocation
   count — do not assume coverage, measure it, and record the count in the
   resolution notes. This is the acceptance signal for the whole chunk.
2. **Phase synchronization (E-5).** `_is_input_collinear`
   (`calculator_target.py:154`) has **0% statement coverage (0/50)**, measured
   by `sys.settrace` over all 222 passing OTG tests. `Synchronization.PHASE`
   appears only as an enum-value assertion and a field assignment; it is never
   driven through `calculate`. otg.md §Internal fidelity 3 requires this path.
3. **Discrete duration (E-6).** `calculator_target.py:543` never exercised
   end-to-end. Same for `minimum_duration` (never passed to `calculate`),
   `Synchronization.TIME_IF_NECESSARY`, and `ControlInterface.VELOCITY` (never
   driven through `calculate`/`update` — only `InputParameter.validate`).
   `TargetCalculator.calculate` overall sits at **45% (89/198 statements)**.
4. **Continuity across `update` cycles (E-7).** `test_otg_continuity.py:33`
   never calls `update()` and never crosses a section boundary; all 5 cases call
   `Otg.calculate`. The file's own docstring concedes it is "a self-consistency
   check on the profile's internal bookkeeping, not a comparison against an
   external oracle." Chunk 42 design constraint 3 and otg.md §Oracle 3 both
   require continuity across consecutive `update` cycles *including at section
   changes*. Add real cross-cycle continuity, asserting across a
   `did_section_change` transition.
5. **New target mid-trajectory (E-8).** No test pins it. The audit verified the
   behavior works (retarget at cycle 11 of a 90-cycle move triggers exactly one
   extra recalculation and converges to `-3.000000000000001`), but
   `TestUpdateLoopReachesFinishedWithinBound` drives an unchanging input, and the
   `new_calculation` assertion (`:109-110`) asserts the *absence* of
   recalculation, never its presence on a genuine mid-flight change.
6. **Intra-cycle limit violations (E-9).** `test_otg_invariants.py:142` samples
   `new_velocity`/`new_acceleration`/`new_jerk` only at control-cycle instants,
   1-DOF, 50 cases — intra-cycle peaks are invisible. Sample the trajectory
   densely *within* cycles. Also: invariant (2) is evaluated on the last
   re-planned trajectory (after `pass_to_input` at `:163` re-plans every cycle),
   not the originally planned one, which substantially weakens "at_time(duration)
   hits the target". Assert against the originally planned trajectory.
7. **Under-covered Step2 branches (E-10).** `check_root_udud` (`:1041`) at
   **3% (1/29)** and live (reachable from `_time_vel`'s UDUD branch);
   `_time_acc0_vel` 34%, `_time_acc1_vel` 44%, `_time_acc0_acc1` 48%. The
   multi-DOF corpus (gap 1) should reach these — measure and report which
   remain uncovered. `_time_none_smooth` (`:2415`, 0%) is dead in Swift too and
   documented as such: **no action, recorded**.
8. **Missing Swift case (E-11).** Swift `OTGComprehensiveTests.swift:312`
   defines **5** `testBugFix_*` cases; the port lands **4**.
   `testBugFix_NegativeTimeInterval_Case3` is silently absent, and both the
   module docstring (`test_otg_comprehensive.py:12`) and chunk 42:134 claim all
   4/all cases are ported. It matters: the only port of that input
   (`test_otg_failure_fixes.py:169`) wraps every assertion in `if result >= 0:`,
   so a regression to an error `Result` would assert nothing, whereas the
   comprehensive contract requires unconditional success. The audit ran it —
   it passes today (`result=0`, `dur=3.5809`, target hit, `maxv=6.279 ≤ 6.282`,
   `maxa=9.128 ≤ 9.974`). Port it and fix both docstring claims.

## Design constraints

1. **Measure, don't assume.** Gaps 1, 2, 3, 7 are coverage claims — report
   before/after statement coverage for `_is_input_collinear`,
   `TargetCalculator.calculate`, `check_root_udud`, and Step2's
   `get_profile` invocation count.
2. Do not loosen any tolerance. The existing 1e-6 segment-time atol was
   human-approved with a recorded rationale and stays as is.
3. No `pytest.skip`, `xfail`, or `expectedFailure` in new tests. If a case
   cannot be made to pass, report it as a defect — do not park it.
4. Generated corpus data must be reproducible: commit the generator script or a
   fixed seed alongside the data.

## Acceptance criteria

- [x] Multi-DOF corpus lands; Step2 `get_profile` invocation count > 0, measured and reported
- [x] `_is_input_collinear` coverage > 0%, measured and reported
- [x] Discrete-duration, `minimum_duration`, `TIME_IF_NECESSARY`, and VELOCITY interface each driven through `calculate`/`update`
- [x] Continuity asserted across `update` cycles including a `did_section_change` transition
- [x] Mid-trajectory retarget test pins the recalculation *and* convergence
- [x] Limits checked intra-cycle, not only at cycle instants; invariant (2) against the originally planned trajectory
- [x] `testBugFix_NegativeTimeInterval_Case3` ported; docstring and chunk 42 claims corrected
- [x] `TargetCalculator.calculate` coverage materially above 45%; report the number
- [x] No skips/xfails; no tolerance loosened
- [x] `make uv-fullCheck` passes

## Out of scope

`_time_none_smooth` coverage — dead in Swift, recorded as no-action.

## Resolution notes

**Files touched.** `tests/otg/test_calculator_target.py`,
`tests/otg/test_otg_continuity.py`, `tests/otg/test_otg_driver.py`,
`tests/otg/test_otg_invariants.py`, `tests/otg/test_otg_comprehensive.py`,
`tests/otg/steps/test_position_third_step2.py` (docstring-only coverage
note, no new cases), `tests/otg/data/generate_multi_dof_corpus.py` (new),
`tests/otg/data/successful_trajectories_multi_dof.json` (new, 450 cases),
and `.claude/action-plan/42-otg-oracle-suites.md` (correcting its "all 4"
`testBugFix_*` claim per gap 8's explicit instruction — the only `src/`-free,
doc-only touch outside this chunk's own file). No `src/` files were changed.

**Gap 1 — multi-DOF corpus (E-4).** `generate_multi_dof_corpus.py` combines
1-DOF `successful_trajectories.json` cases (fixed seed `20260722`) into
150×2-DOF + 150×3-DOF + 150×4-DOF cases (450 total, 1,350 of the 1,682
source cases consumed) under default `Synchronization.TIME`, filtering to
only combinations `Otg.calculate` itself verifies succeed at generation
time (450/450 kept, 0 rejected in the committed run — re-running the
generator against the unmodified source corpus reproduces the JSON
byte-for-byte, verified). `TestMultiDofCorpusReachesStep2` drives all 450
cases through `Otg.calculate` with `PositionThirdOrderStep2.get_profile`
instrumented: **900 invocations across 450 cases**, all succeed (0
errors) — this is the chunk's acceptance signal, and it was measured, not
assumed.

**Gap 2 — phase synchronization (E-5).** Two new tests drive
`Synchronization.PHASE` through `calculate()` for real:
`TestPhaseSynchronizationCollinear` (proportional rest-to-rest targets,
`_is_input_collinear` returns `True`, 0 Step2 calls — phase sync reuses the
limiting DOF's own timing) and `TestPhaseSynchronizationFallsBackToTime`
(a current-velocity ratio that doesn't match the position-delta ratio,
`_is_input_collinear` returns `False`, falls back to per-DOF `TIME` sync
via Step2 — confirming otg.md's "phase synchronize when possible, else fall
back to TIME" contract). Statement coverage of `_is_input_collinear`,
measured via `sys.settrace` over the full OTG suite: **0% (0/61) before →
59% (36/61) after**. The remaining uncovered lines are the
velocity/acceleration-driven scale-vector fallback branches (used only
when the PHASE-tagged DOFs' position deltas are ~0), the "no scale vector
found → return False" trivial path, the `math.isinf(max_jerk)` branch, and
the second loop's `continue` for a non-PHASE DOF mixed with PHASE DOFs —
recorded, not chased further (design constraint 1 asks for >0% measured
and reported, not 100%).

**Gap 3 — discrete duration / minimum_duration / TIME_IF_NECESSARY /
VELOCITY (E-6).** Four new test classes, each driven through
`TargetCalculator.calculate` (three) or `Otg.calculate` (the VELOCITY
case): `TestDiscreteDuration` (a non-multiple-of-`delta_time` natural
optimum gets rounded up to the next multiple), `TestMinimumDuration` (a
1-DOF move stretched to 2x its natural optimum lands exactly on
`minimum_duration`, via a real Step2 solve — confirmed the 1-DOF fast path
is bypassed whenever `minimum_duration is not None`), and
`TestTimeIfNecessarySynchronization` (both branches: a zero-target-velocity
DOF keeps its own short unstretched duration and just holds at the target
early, non-zero-target-velocity forces a Step2 stretch to the synchronized
duration), `TestVelocityControlInterface` (a pure velocity-interface move
reaches the target velocity through `set_boundary_for_velocity` +
`VelocityThirdOrderStep1`/`Step2`).
`TargetCalculator.calculate` statement coverage, measured the same way:
**41.8% (167/400) before → 58.5% (234/400) after** (absolute line counts
differ from the original post-audit's own tooling — no `coverage.py` in
this project's venv, so an ad hoc `sys.settrace` line-counter was used
instead; the audit's own baseline numbers also predate chunks 44-46's own
regression tests, which already moved some of these numbers before this
chunk started). Materially above the pre-chunk 45% figure either way.

**Gap 4 — cross-cycle continuity (E-7).**
`TestUpdateCycleContinuity` drives a real `Otg.update()` control loop to
`FINISHED` and asserts, every cycle: `output.new_*` matches an independent
`trajectory.at_time(output.time)` query, and the cycle-to-cycle state jump
is bounded. A single-section (no-waypoint) trajectory has exactly one real
`did_section_change` transition — the cycle `output.time` first crosses
`trajectory.duration` (`Trajectory._state_to_integrate_from`'s branch
switch) — confirmed to coincide exactly with the `FINISHED` cycle; the test
asserts this transition occurs exactly once, at the `FINISHED` cycle, and
that the state at that transition matches the target within `1e-6`.

**Gap 5 — mid-trajectory retarget (E-8).**
`TestMidTrajectoryRetarget` (in `test_otg_driver.py`) mutates
`inp.target_position` at cycle 11 of a run that finishes at cycle 86 (target
6.0 → -3.0), and asserts `new_calculation` is `True` on exactly cycles `[1,
11]` (the initial calculation plus exactly one recalculation, never more)
and that the loop converges to the new target (`-3.000000000000002`,
matching the audit's own empirical observation almost to the ULP) rather
than the original one.

**Gap 6 — intra-cycle limits + invariant (2) (E-9).** Each cycle in
`TestRandomizedValidInputInvariants` now additionally samples
`trajectory.at_time` at 11 points across the just-elapsed cycle interval
(not just the single control-cycle instant) and checks velocity/
acceleration limits there too (jerk is piecewise-constant per profile
segment, so it has no intra-segment peak the cycle-instant sample could
miss, unlike velocity/acceleration). Investigated the premise behind
"`pass_to_input` re-plans every cycle": empirically, for these 50 seeded
random cases, `Otg.update()`'s change-detection sees the caller's
`pass_to_input`-updated `current_*` state as identical to the driver's own
internally-updated cached copy (`otg.py:173`'s own `output.pass_to_input(
self._current_input)`), so **no case recalculates more than once** — the
post-loop `output.trajectory` was, in every observed case, already the
originally-planned trajectory, not a re-planned one. This doesn't
contradict the spec (no violation to report) — but per the gap's literal
ask, and to make the test robust to any future change in that
change-detection behavior, invariant (2) now explicitly snapshots
(`copy.deepcopy`) the trajectory immediately after the first
(`new_calculation`) cycle and asserts against that snapshot, rather than
relying on the post-loop `output.trajectory` reference remaining
unmutated.

**Gap 7 — under-covered Step2 branches (E-10).** No new cases added to
`test_position_third_step2.py`; the multi-DOF corpus (gap 1) reaches these
branches through realistic synchronized multi-DOF inputs. Measured via
`sys.settrace`, before → after: `check_root_udud` 82% → 98% (1/55 lines
unreached — a `linecache`/`dis` measurement artifact inside a nested
function, not chased further), `_time_acc0_vel` 39% → 99% (the one
"uncovered" line is the `def` line itself), `_time_acc1_vel` 41% → 99%
(same artifact), `_time_acc0_acc1` 98% → 98% unchanged (one substantive
branch remains unreached: the `check_with_timing(..., ReachedLimits.
ACC0_ACC1, ...)` success path at `position_third_order_step2.py:1267`;
recorded, not pursued further — design constraint 1 asks for measurement
and reporting, not 100%). `_time_none_smooth` (0%, dead in Swift) is out of
this chunk's scope per its own "Out of scope" section, unchanged.

**Gap 8 — `testBugFix_NegativeTimeInterval_Case3` (E-11).** Ported into
`TestBugFixNegativeTimeInterval.test_case_3` with the file's unconditional-
success contract (unlike `test_otg_failure_fixes.py`'s existing port of the
same input, which wraps every assertion in `if result >= 0:`). Both the
module docstring ("Ported (4 cases)" → "Ported (5 cases)") and
`.claude/action-plan/42-otg-oracle-suites.md`'s "All 4 of the Swift file's
`testBugFix_*` cases are ported case-for-case" claim were corrected in
place (with a note explaining the correction, not a silent edit).

**Gate.** `make uv-fullCheck`: `uv-lint` clean, `uv-typecheck` clean (mypy
strict, 120 source files), `uv-test` 1,548 passed (0 failures, 0 errors,
0 skips). Full `tests/otg` suite: 237 top-level tests / 90 subtests, all
passing, ~14s.

**Deviations from the plan as written.** None functionally; the chunk 42
doc correction (gap 8) was made as a small in-place edit with an
explanatory note rather than a rewrite, since it is itself an
already-committed action-plan artifact and the instruction was to correct
a specific factual claim, not restructure the file.
