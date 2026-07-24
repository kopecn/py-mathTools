---
plan: math-tools-port
status: in_progress
last_updated: 2026-07-23
semver: 0.1.1
author: Nicholas Bergantz
---

# Action Plan — Template Migration + Swift Math Port

**Goal:** bring py-MathTools onto the py-foundationTools template conventions
and port the Swift `FoundationMathTypes` capability set (spatial SE(3) types,
precision time, waveforms + DSP, polynomials/roots, OTG trajectory
generation) as the Tier-3 math layer, per the accepted specs in
[`../specs/`](../specs/mathToolsArchitecture.md).

**Usability north star:** a robotics/DSP engineer in a notebook can build a
waveform or pose, do the obvious math, and reach scipy-grade analysis with
minimal ceremony — well-typed numpy-adjacent Python, not translated Swift.

## Conventions every chunk inherits (do not restate per chunk)

1. **Spec is authoritative.** Each chunk lists its governing spec section(s).
   If implementation forces a contract change, update the spec in the same
   chunk and bump its `semver`.
2. **TDD:** write the failing tests first, implement, then run the gate.
3. **Gate:** `make uv-fullCheck` (ruff lint + mypy strict + pytest) must pass
   at the end of every chunk. Test layout mirrors the package
   (`tests/<subpkg>/test_<module>.py`), `unittest.TestCase` style, `test_*`
   methods.
4. **Stay in scope:** touch ONLY the files the chunk lists. Adjacent
   problems get reported in the chunk's completion notes, not fixed.
5. **Frontmatter:** every chunk carries `status: pending` → set
   `in_progress` while working, then `complete` when done (not `done`
   — `complete` is the convention actually used across every chunk file
   in this repo); bump `last_updated`.
6. **Swift reference roots** (read-only, for faithful-port chunks):
   - `SWIFT_MATH` = `/Users/nbergantz/__Workspaces__/spmWorkspaces/spmMathTools/spm/Sources/spmMathTools/FoundationMathTypes`
   - `SWIFT_TYPES` = `/Users/nbergantz/__Workspaces__/spmWorkspaces/spmFoundationTools/spm/Sources/FoundationTypes`
   - `SWIFT_TESTS` = `/Users/nbergantz/__Workspaces__/spmWorkspaces/spmMathTools/spm/Tests/spmMathToolsTests`
7. **Shared API idioms** (umbrella spec "API idioms"): `normalized()` method
   / `normalize()` in-place; `isclose(rtol, atol)`; `__array__`;
   `__hash__ = None` on mutable numpy-backed classes; snake_case throughout.
8. Do not commit; the human reviews and commits per track.

## Dependency graph

```
Track A (template)      01 ──► 02 ──► 03
                         │
        ┌────────────────┴───────────────────────────────┐
Track B │  04 ─► 05          06 ─► 07 ─► 08      09   10 │ (02 before all B)
        │   └──────┬──────────┘└───┬────┘              │ │
Track C │          ▼               │                   │ │
        │  11 ─► {12, 13, 14}      │                   │ │
        │   │        │             ▼                   │ │
        │   │        │   15(◄06) 16(◄07) ─► 17(◄08,15,16)│
Track D │   │        ▼                                 │ │
        │   │   18..29 (one per mixin; 26 also ◄19)    │ │
        │   │        └────────► 30 (compose)           │ │
Track E │   └──────────────────────────────────────────┘ │
        │  31(◄10) ─► 32                                 │
        │  31 ─► 33 ─► 34 ─► {35, 36, 37, 38, 39}        │
        │  {32,35..39} ─► 40 ─► 41 ─► 42                 │
        └────────────────────────────────────────────────┘
```

Tracks B/C/D/E parallelize after 01–02; within a track, run in numeric
order unless the graph says otherwise. Chunk 43 (public surface) runs last,
after 09, 17, 30, and 42.

## Chunk index

| # | Chunk | Track | Depends on | Spec |
|---|---|---|---|---|
| 01 | [template-rename-and-refresh](01-template-rename-and-refresh.md) | A | — | templateConformance |
| 02 | [errors-and-layering](02-errors-and-layering.md) | A | 01 | umbrella, templateConformance §5 |
| 03 | [governance-and-readme](03-governance-and-readme.md) | A | 02 | templateConformance §3–4 |
| 04 | [precision-time-interval](04-precision-time-interval.md) | B | 02 | precisionTimeMath |
| 05 | [precision-timestamp](05-precision-timestamp.md) | B | 04 | precisionTimeMath |
| 06 | [position](06-position.md) | B | 02 | spatialMath |
| 07 | [quaternion-additions](07-quaternion-additions.md) | B | 06 | spatialMath |
| 08 | [spatial-pose](08-spatial-pose.md) | B | 07 | spatialMath |
| 09 | [univariate-polynomial](09-univariate-polynomial.md) | B | 02 | polynomials |
| 10 | [roots-kernel](10-roots-kernel.md) | B | 02 | polynomials |
| 11 | [waveform1d-core](11-waveform1d-core.md) | C | 05 | waveformCore |
| 12 | [waveform1d-operators](12-waveform1d-operators.md) | C | 11 | waveformCore |
| 13 | [waveform1d-generators](13-waveform1d-generators.md) | C | 11 | waveformCore |
| 14 | [dsp-support-and-protocol](14-dsp-support-and-protocol.md) | C | 11 | waveformDsp |
| 15 | [waveform-position](15-waveform-position.md) | C | 11, 06 | waveformCore |
| 16 | [waveform-quaternion](16-waveform-quaternion.md) | C | 11, 07 | waveformCore |
| 17 | [waveform-spatial-pose](17-waveform-spatial-pose.md) | C | 08, 15, 16 | waveformCore |
| 18 | [dsp-calc](18-dsp-calc.md) | D | 14 | waveformDsp |
| 19 | [dsp-correlation](19-dsp-correlation.md) | D | 14 | waveformDsp |
| 20 | [dsp-envelope](20-dsp-envelope.md) | D | 14 | waveformDsp |
| 21 | [dsp-spectral](21-dsp-spectral.md) | D | 14 | waveformDsp |
| 22 | [dsp-filtering](22-dsp-filtering.md) | D | 14 | waveformDsp |
| 23 | [dsp-peaks](23-dsp-peaks.md) | D | 14 | waveformDsp |
| 24 | [dsp-phase](24-dsp-phase.md) | D | 14 | waveformDsp |
| 25 | [dsp-resampling](25-dsp-resampling.md) | D | 14 | waveformDsp |
| 26 | [dsp-time-alignment](26-dsp-time-alignment.md) | D | 14, 19 | waveformDsp |
| 27 | [dsp-triggers](27-dsp-triggers.md) | D | 14 | waveformDsp |
| 28 | [dsp-windowing](28-dsp-windowing.md) | D | 14 | waveformDsp |
| 29 | [dsp-zero-crossings](29-dsp-zero-crossings.md) | D | 14 | waveformDsp |
| 30 | [dsp-compose](30-dsp-compose.md) | D | 18–29 | waveformDsp |
| 31 | [otg-enums-and-errors](31-otg-enums-and-errors.md) | E | 10 | otg |
| 32 | [otg-input-parameter](32-otg-input-parameter.md) | E | 31 | otg |
| 33 | [otg-profile](33-otg-profile.md) | E | 31 | otg |
| 34 | [otg-block-brake-bound](34-otg-block-brake-bound.md) | E | 33 | otg |
| 35 | [otg-trajectory-and-output](35-otg-trajectory-and-output.md) | E | 34 | otg |
| 36 | [otg-velocity-steps](36-otg-velocity-steps.md) | E | 34 | otg |
| 37 | [otg-position-first-second-steps](37-otg-position-first-second-steps.md) | E | 34 | otg |
| 38 | [otg-position-third-step1](38-otg-position-third-step1.md) | E | 34 | otg |
| 39 | [otg-position-third-step2](39-otg-position-third-step2.md) | E | 34 | otg |
| 40 | [otg-calculator-target](40-otg-calculator-target.md) | E | 32, 35–39 | otg |
| 41 | [otg-driver](41-otg-driver.md) | E | 40 | otg |
| 42 | [otg-oracle-suites](42-otg-oracle-suites.md) | E | 41 | otg |
| 43 | [public-surface](43-public-surface.md) | A | 30, 42, 09, 17 | umbrella |

---

# Corrective actions — 2026-07-22 post-audit

Chunks 01–43 were audited against their governing specs by five parallel
skeptical auditors (one per track), with the top findings independently
reproduced at runtime and source level before being recorded here.

**Verdict: substantially complete.** `make uv-fullCheck` is green (exit 0) and
the port is faithful in the large — the 31-case OTG numeric truth table was
re-derived from the Swift source with 0 mismatches, no test in the repo is
skipped or xfail'd, and no unsolved algorithm case, stub, or swallowed `None`
was found in the solvers. The confirmed gaps are specific and are chunked below.

Chunks 44–57 form **Track F**. They are corrective, not new capability.

## Confirmed defect summary

| Class | Count | Where |
|---|---|---|
| (c) drift / correctness | 8 | OTG solvers, spatial/time accessors, waveform indexing |
| (a) not implemented | 6 | aggregate API idioms, subpackage exports, roots degeneracy |
| (b) implemented, untested | ~45 | concentrated in DSP mixins and OTG oracles |
| (e) docs/convention drift | 14 | dead workflow refs, stale tolerances, boilerplate |
| (d) out-of-scope violations | **0** | — none found in any track |

The single most consequential finding is a **transcription defect** at
`position_third_order_step2.py:1731,1752,1763` (`j·tf⁴` where Swift has
`j·tf³`), confirmed by direct comparison against
`PositionThirdOrderStep2.swift:1279,1286,1289`. It changes profile-branch
selection in ~0.57% of prescribed-duration Step2 solves and is invisible to the
current gate — because the entire 1,784-case OTG oracle corpus is 1-DOF, which
takes a fast path that **never invokes Step2 at all** (measured: 0 invocations).

## Dependency graph

```
Track F (corrective)

  OTG code fixes        44   45   46
                         └────┴────┴──────► 56 (OTG oracle closure)

  Track B/C code fixes  47   48   49 ─► 50   51
                                    └────┴────┴─► 54 (B/C test closure)

  Surface / conventions 52        53 ─────────────► 55 (DSP test closure)

  Everything above ───────────────────────────────► 57 (docs sweep, last)
```

44–49, 51, 52, 53 are mutually independent and may run in parallel.
50 waits on 49. The three closure chunks wait on their code fixes. 57 runs last
so it reconciles docs against the post-fix repo.

## Corrective chunk index

| # | Chunk | Kind | Depends on | Origin |
|---|---|---|---|---|
| 44 | [otg-step2-udud-discriminant](44-otg-step2-udud-discriminant.md) | fix | — | E-1 |
| 45 | [otg-trivial-profile-length](45-otg-trivial-profile-length.md) | fix | — | E-2 |
| 46 | [otg-step1-sqrt-guard](46-otg-step1-sqrt-guard.md) | fix | — | E-3 |
| 47 | [position-tolerance-and-timestamp-accessors](47-position-tolerance-and-timestamp-accessors.md) | fix | — | B-1, B-2 |
| 48 | [roots-degenerate-cases](48-roots-degenerate-cases.md) | fix | — | B-7, B-14 |
| 49 | [waveform-spatial-pose-indexing](49-waveform-spatial-pose-indexing.md) | fix | — | C-4, C-5 |
| 50 | [aggregate-container-api-idioms](50-aggregate-container-api-idioms.md) | fix | 49 | C-1, C-2, C-3, C-7 |
| 51 | [waveform-generator-phase-conventions](51-waveform-generator-phase-conventions.md) | fix | — | C-15 |
| 52 | [subpackage-public-surface](52-subpackage-public-surface.md) | fix | — | A-1, A-2 |
| 53 | [window-convention-reconciliation](53-window-convention-reconciliation.md) | fix | — | D-windowing |
| 54 | [test-closure-tracks-bc](54-test-closure-tracks-bc.md) | tests | 47–51 | 11 (b) findings |
| 55 | [test-closure-dsp](55-test-closure-dsp.md) | tests | 53 | 23 (b) findings |
| 56 | [test-closure-otg-oracles](56-test-closure-otg-oracles.md) | tests | 44, 45, 46 | 8 (b) findings |
| 57 | [docs-and-convention-sweep](57-docs-and-convention-sweep.md) | docs | 44–56 | 14 (e) findings |

Findings deliberately **not** actioned (B-4, B-5, B-6, A-7, D-cross-cutting,
D-spectral-(c), E-10) are recorded with rationale in chunk 57's
"Recorded — no action" section, so the decisions are not relitigated.
