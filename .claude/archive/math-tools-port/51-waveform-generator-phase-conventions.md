---
chunk: 51-waveform-generator-phase-conventions
track: F
status: complete
depends_on: []
spec: ../specs/waveformCore.md §Generators
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 51 — `Waveform1D` generator span off-by-one

## Origin

Post-audit finding C-15 (class **c**). Confirmed at runtime:
`Waveform1D.heaviside(n=4, dt_seconds=1.0)` → `[0, 0, 1, 1]`, stepping at
index 2 rather than the midpoint of the sample span `[0, 3]`.

Three generators compute their span as `duration = n * dt_s` when the actual
sample span of an `n`-sample waveform is `(n-1) * dt_s`:

- `chirp` — `waveform1d.py:292-293`: `sweep_rate` is scaled by `n * dt_s`, so
  the final sample's instantaneous frequency is not `end_frequency`.
- `heaviside` — `:443`: default `step_time = n * dt_s / 2.0`.
- `sigmoid` — `:480`: default `center = n * dt_s / 2.0`.

The only chirp test (`tests/waveforms/test_waveform1d_generators.py:102`) is a
coarse quarter-vs-quarter zero-crossing comparison that cannot resolve a
one-sample error.

## Files

- Edit: `src/math_tools/waveforms/waveform1d.py`
- Edit: `tests/waveforms/test_waveform1d_generators.py`
- Possibly edit: `.claude/specs/waveformCore.md`

## Design constraints

1. Decide the span convention **once**, explicitly, and apply it to all three:
   for an `n`-sample waveform starting at `t0`, the last sample is at
   `t0 + (n-1)*dt`. Endpoint-inclusive. State this in waveformCore.md's
   generator section — the spec is currently silent, which is why the drift
   went unnoticed — and bump its `semver`.
2. Fix the three sites to use `(n - 1) * dt_s`. Guard `n == 1` (span 0) so no
   generator divides by zero.
3. Check the remaining generators for the same pattern while you are in the
   file, but change only ones genuinely affected by the span convention. Do not
   touch generators whose math does not depend on total duration.
4. This changes output values for existing callers. That is the point — but
   call it out in the resolution notes.

## TDD steps

1. Failing tests first:
   - `heaviside(n=4, dt_seconds=1.0)` steps at the midpoint of `[0, 3]`
   - `sigmoid`'s default `center` sits at the span midpoint (assert the value
     at the midpoint sample is 0.5)
   - `chirp`'s instantaneous frequency at the **final** sample equals
     `end_frequency` — measure via the final-interval zero-crossing spacing or
     the analytic phase derivative; the existing quarter-comparison test is not
     sufficient, so add a real one rather than tightening it
   - `n == 1` does not raise for all three
2. Apply the fixes.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All three generators use the `(n-1)*dt` span
- [x] Endpoint convention documented in waveformCore.md; `semver` bumped
- [x] `n == 1` handled for all three
- [x] New tests fail before, pass after
- [x] Resolution notes list the changed output values
- [x] `make uv-fullCheck` passes

## Out of scope

Value-level tests for the other 13 under-tested generators (finding C-9) —
that is chunk 54.

## Resolution notes

- Added a shared `_span_seconds(n, dt_s) -> (n-1)*dt_s if n > 1 else 0.0`
  helper in `waveform1d.py` and switched all three sites to it: `chirp`'s
  `duration` (line ~292), `heaviside`'s default `step_time` (~443),
  `sigmoid`'s default `center` (~480). `chirp`'s existing
  `if duration != 0.0 else 0.0` guard already covers the new `n == 1`
  zero-duration case (previously only reachable at `n == 0`); `heaviside`/
  `sigmoid` need no extra guard since halving `0.0` isn't a division by
  zero — verified `n == 1` does not raise for any of the three either way.
- Confirmed the other 19 generators do not depend on total duration/midpoint
  and were left untouched (scanned for the `n * dt_s` pattern; only the
  three named sites matched).
- Checked pre-fix failure by `git stash`-ing the source fix and running the
  four new tests against the old code: all four failed, confirming they are
  real regression tests, not tautologies. Restored the fix and reran full
  suite green.
- **Changed output values** (both examples use `dt_seconds=1.0`):
  - `heaviside(n=5)`: old `[0, 0, 0, 1, 1]` (`step_time=2.5`) → new
    `[0, 0, 1, 1, 1]` (`step_time=2.0`).
  - `sigmoid(n=5)`: old `values[2] ≈ 0.3775` (`center=2.5`) → new
    `values[2] == 0.5` (`center=2.0`).
  - `chirp(n=201, start_frequency=5, end_frequency=50, dt_seconds=0.001)`
    (the regression-test case): the realized sweep rate moves from
    `(50-5)/(201*0.001) ≈ 223.88` Hz/s (old) to `(50-5)/(200*0.001) = 225`
    Hz/s (new); the final-sample instantaneous frequency, recovered from
    the generated samples' interpolated zero crossings, moves accordingly
    from ≈49.78 Hz (old, ~0.45% low) to ≈50.00 Hz (new, matches
    `end_frequency` exactly as designed). Note `n=4` (the post-audit
    origin example) happens to produce an *identical* array under both
    conventions, because the true continuous midpoint (`1.5`) and the old
    formula's midpoint (`2.0`) both round up to the same first qualifying
    sample index (`2`) for that specific `n`; the regression tests
    therefore use `n=5` (heaviside/sigmoid) and `n=201` (chirp), where the
    conventions diverge at the sample level, per "add a real one rather
    than tightening it."
  - As called out in the plan's design constraint 4, this is an intentional
    behavior change for existing `heaviside`/`sigmoid`/`chirp` callers that
    relied on the previous (incorrect) `n*dt` span.
- No spec sections beyond the new "Generators — span convention" paragraph
  needed changes; `waveformCore.md` bumped `0.0.3` → `0.0.4`.
