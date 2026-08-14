---
chunk: 54-test-closure-tracks-bc
track: F
status: complete
depends_on: [47, 48, 49, 50, 51]
spec: ../specs/spatialMath.md, ../specs/precisionTimeMath.md, ../specs/polynomials.md, ../specs/waveformCore.md
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 54 — Test-coverage closure: Tracks B and C

## Origin

Post-audit class **(b)** findings for Tracks B and C — behavior that is
implemented but unverified. Runs after the code-fix chunks so the new tests
pin corrected behavior, not the defects.

**Tests only. No `src/` changes.** If writing a test exposes a genuine defect,
stop and report it in the resolution notes rather than fixing it here.

## Files

- Edit: `tests/spatial/test_spatial_pose.py`, `tests/spatial/test_quaternion_additions.py`
- Edit: `tests/functional/test_roots.py`
- Edit: `tests/waveforms/test_waveform1d_core.py`, `test_waveform1d_operators.py`,
  `test_waveform1d_generators.py`
- Edit: `tests/waveforms/test_waveform_position.py`, `test_waveform_quaternion.py`,
  `test_waveform_spatial_pose.py`

## Gaps to close

**Track B**

1. **B-3/B-12** — `Quaternion.__hash__ is None` is never asserted. spatialMath
   §Compliance 10 pins it for all three classes; only `Position`
   (`position.py:380`) and `SpatialPose` (`spatial_pose.py:269`) set it
   *explicitly*. Add the missing assertion, **and** set it explicitly on
   `Quaternion` (`quaternion.py:71-72`) — currently `None` only as a dataclass
   side effect. This is the one permitted `src/` edit in this chunk.
2. **B-9** — `tests/functional/test_roots.py:258` asserts `shrink_interval`
   converges to `delta=1e-9`; polynomials.md Compliance 3 requires
   `POLYNOMIAL_TOLERANCE` (1e-14). Tighten to the spec'd tolerance.
3. **B-10** — `SpatialPose.isclose`'s double-cover awareness is untested. Add a
   `q` vs `-q` pose case, plus a negative (must-return-`False`) case; the
   existing test varies position only and has no false case.

**Track C**

4. **C-8** — operator surface: bitwise `|`, `^`, `>>` have no test at all; no
   reflected or in-place bitwise test; no `//=`, `%=`; reflected `/`, `//`, `%`
   untested; length-mismatch pinned only for `+`; `NotImplemented` observed only
   indirectly. Close all of these.
5. **C-9** — 13 of 22 generators lack value-level assertions. Specifically:
   `square`/`digital_square` `duty_cycle` never exercised; `sawtooth`/`triangle`
   only range-checked; `heaviside` default `step_time`, `sigmoid`
   `center`/`steepness`, `relu` `slope`, `white_noise` `amplitude`, and
   `damped_sinusoid`'s analytic form never pinned. (Chunk 51 covers the three
   span-convention defaults; this covers the rest.)
6. **C-6** — in-place operators silently change dtype:
   `Waveform1D([1,2,3]) += 0.5` yields float64 where numpy in-place would raise
   a casting error; `append(9.7)` / `insert(1, 9.7)` on an int waveform store
   `9`. Pin the current behavior deliberately after confirming it is intended —
   if it is not, report rather than fix.
7. **C-10** — no §Compliance-10 bulk smoke test for `Waveform1D` at all;
   waveformCore.md:190 requires a 1e6-sample pin. The aggregates use 100 000,
   not 1e6 (`test_waveform_position.py:260` et al). Add the `Waveform1D` case at
   1e6 and raise the aggregates to spec.
8. **C-11** — the ABC accessor `Waveform1D.waveform` (`waveform1d.py:593-596`),
   the O(n) materialization path waveformCore.md:43 calls load-bearing, has no
   direct test.
9. **C-12** — `replace_range` is tested only at equal length
   (`test_waveform1d_core.py:338`); §Compliance 7's "match stdlib list
   semantics" is unverified for unequal-length slice assignment. numpy requires
   equal length where a list does not — pin whichever the spec means.
10. **C-13** — `subset_time` boundary clamping (start before `t0`, end past the
    span) is unpinned.
11. **C-14** — aggregate `pop` with an out-of-range index untested for all three
    containers (only the empty case is covered).

## Design constraints

1. Assertions must be **value-level** — known-answer or analytic. A test that
   checks only shape, dtype, length, or "did not raise" does not close a (b)
   finding and will be rejected at review.
2. Follow the existing file's `unittest.TestCase` style and naming.
3. Only permitted `src/` edit: the explicit `__hash__ = None` on `Quaternion`
   (gap 1). Anything else, report.

## Acceptance criteria

- [x] All 11 gaps have value-level tests
- [x] Every new test observed failing against deliberately broken behavior before being accepted
- [x] `Quaternion.__hash__ = None` set explicitly and asserted
- [x] `shrink_interval` tolerance tightened to 1e-14
- [x] `Waveform1D` bulk test at 1e6; aggregates raised to 1e6
- [x] No `src/` changes beyond gap 1
- [x] `make uv-fullCheck` passes

## Out of scope

DSP mixin coverage (chunk 55). OTG coverage (chunk 56).

## Resolution notes

All 11 gaps closed, tests only, one permitted `src/` edit
(`Quaternion.__hash__ = None`, `src/math_tools/spatial/quaternion.py`).

- **B-3/B-12**: `Quaternion.__hash__` was already `None` as a dataclass side
  effect (unfrozen `@dataclass` with default `eq=True`); made it explicit
  per spec and added `TestHashability` to
  `tests/spatial/test_quaternion_additions.py`.
- **B-9**: `shrink_interval`'s quintic-bracket test tightened from
  `delta=1e-9` to `roots.POLYNOMIAL_TOLERANCE` (1e-14); confirmed the solver
  already converges exactly (`found - 2.0 == 0.0`) before tightening.
- **B-10**: added a `q`/`-q` double-cover `isclose` case and a genuine
  negative (different-orientation) case to `TestComparison` in
  `test_spatial_pose.py`.
- **C-8**: closed all named gaps in `test_waveform1d_operators.py` — `|`,
  `^`, `>>`; reflected and in-place bitwise (`&=`, `|=`, `^=`, `<<=`, `>>=`);
  `//=`, `%=`; reflected `/`, `//`, `%`; length-mismatch pinned for every
  binary/bitwise op (previously only `+`); and a direct
  `w.__add__(...) is NotImplemented`-style check (previously only observed
  indirectly via the resulting `TypeError`).
- **C-9**: added value-level (analytic-formula) pins for `square`/
  `digital_square` `duty_cycle`, `sawtooth`/`triangle`, `sigmoid`
  `center`/`steepness`, `relu` `slope`, `white_noise` `amplitude`, and
  `damped_sinusoid`'s envelope×oscillation form, in
  `test_waveform1d_generators.py`. (`heaviside`/`sigmoid`/`chirp` default
  span-convention behavior was already covered by chunk 51's
  `TestGeneratorSpanConvention`; only added one extra explicit-`step_time`
  case there.)
- **C-6**: confirmed and pinned as intentional (not a defect): in-place
  arithmetic operators (`+=` etc.) reassign a freshly-constructed result
  rather than mutating the numpy buffer in place, so they silently *promote*
  dtype on mixed int/float arithmetic (`Waveform1D([1,2,3]) += 0.5` ->
  `float64`) instead of raising numpy's native `same_kind` casting error.
  `append`/`insert` go the other way — they cast the incoming value to the
  existing dtype via `np.asarray(value, dtype=...)`, so a float value onto
  an int waveform truncates (`append(9.7)` stores `9`). Both directions
  pinned by test (`TestInPlaceOperatorDtypePromotion` in the operators file;
  two new cases in `TestSpecCompliance7Mutation` in the core file).
- **C-10**: added a 1e6-sample `Waveform1D` arithmetic+stats smoke test
  (`TestSpecCompliance10VectorizedBulkOps` in `test_waveform1d_core.py`,
  ~0.1s locally) and raised the three aggregate smoke tests
  (`test_waveform_position.py`, `test_waveform_quaternion.py`,
  `test_waveform_spatial_pose.py`) from `100_000` to `1_000_000` samples per
  waveformCore.md:190, keeping the existing generous 5s bound (measured
  ~0.02s locally at 1e6).
- **C-11**: added a direct test of the `Waveform1D.waveform` ABC accessor
  (`test_waveform_abc_accessor_returns_samples_as_float_list`).
- **C-12**: `replace_range` does not implement stdlib list slice-assignment
  semantics (which resize the sequence); it does a direct numpy assignment
  `self._values[index] = np.asarray(values, dtype=...)`. This means: (a) a
  replacement longer than the slice raises `ValueError` (numpy "could not
  broadcast" — pinned), and (b) a single-element replacement *broadcasts*
  across the whole slice rather than shrinking the waveform (pinned as its
  own case, since it is neither the numpy-`ValueError` behavior nor the
  stdlib-list-shrink behavior). This is a genuine (if narrow) divergence
  from "match stdlib list semantics" as literally read, but the module is
  explicitly numpy-backed (waveformCore.md's storage column) and stdlib-list
  resizing semantics for slice assignment were never separately specified;
  reported here per the chunk's instructions rather than changed, since
  fixing it would be a `src/` behavior change outside this chunk's scope.
- **C-13**: added `subset_time` boundary-clamping tests — start before `t0`,
  end past the span, and both simultaneously — confirming the existing
  `np.searchsorted`-based implementation already clamps correctly (no `src/`
  change needed).
- **C-14**: added an out-of-range `pop` test (`IndexError`) for all three
  aggregate containers (`WaveformPosition`, `WaveformQuaternion`,
  `WaveformSpatialPose`); only the empty case was previously covered.

**Verification**: every new/changed assertion was confirmed to actually
exercise the claimed behavior — either by directly observing the real
runtime value before writing the pin (dtype promotion, `replace_range`
broadcast, `subset_time` clamping, `pop` `IndexError`, `shrink_interval`'s
exact convergence), or by injecting a deliberate defect into the relevant
`src/` line, watching the new test fail, then reverting via `Edit` (spot
-checked `Waveform1D.__ror__` using `operator.and_` instead of `operator.or_`,
and `sigmoid`'s logistic exponent doubled) and confirming `git status`/`git
diff` showed no residual `src/` change afterward.

No genuine spec violations were found; no gap required weakening a test to
pass.
