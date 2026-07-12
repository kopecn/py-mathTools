---
plan: math-tools-port
status: pending
last_updated: 2026-07-11
semver: 0.0.1
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
   `in_progress` / `done` as you work; bump `last_updated`.
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
