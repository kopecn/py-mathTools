---
chunk: 49-waveform-spatial-pose-indexing
track: F
status: complete
depends_on: []
spec: ../specs/waveformCore.md §Compliance 9
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 49 — `WaveformSpatialPose` negative indexing must respect `sample_count`

## Origin

Post-audit findings C-4 and C-5 (correctness, untested). Confirmed at runtime.

`WaveformSpatialPose` holds `positions` and `quaternions` that may differ in
length; `sample_count` is the min. `__getitem__(int)` at
`src/math_tools/waveforms/waveform_spatial_pose.py:471-474` indexes both raw
arrays directly instead of the `sample_count` prefix. On the unequal-length
state that waveformCore.md §Compliance 9 explicitly contemplates:

```
len(w) == 2
w[-1].position == [2,2,2]     # pairs positions[2] with quaternions[1]
w[1].position  == [1,1,1]     # a pose that never existed
```

`w[-1]` and `w[1]` disagree despite `len(w) == 2`, and `get(-1)` (`:476`,
correctly bounded) disagrees with `w[-1]`. The module's own docstring
(`:27-30`) claims every index path derives from `sample_count`.

`pop` has the same defect (`:542-556`): `pop(-1)` on an unequal instance
deletes `positions[-1]` and `quaternions[-1]` — two rows that are not the same
sample.

## Files

- Edit: `src/math_tools/waveforms/waveform_spatial_pose.py`
- Edit: `tests/waveforms/test_waveform_spatial_pose.py`

## Design constraints

1. Normalize the index against `sample_count` **once**, at the top of each
   entry point, then index the raw arrays with the normalized non-negative
   index. `get()` at `:476` already does this correctly — reuse its helper
   rather than writing a third copy.
2. Out-of-range must raise `IndexError` consistently with `get()`.
3. Audit the remaining index paths in this file for the same bug while you are
   in it (slicing, iteration, `__setitem__` if present) — but only fix what is
   genuinely the same defect; do not restructure the class.
4. `WaveformPosition` and `WaveformQuaternion` are single-array containers and
   are not affected. Do not touch them.

## TDD steps

1. Failing tests first, all on a deliberately unequal-length instance
   (3 positions, 2 quaternions, `sample_count == 2`):
   - `w[-1] == w[1]` (the two must agree)
   - `w[-1] == w.get(-1)` (bracket and `get` must agree)
   - `w[2]` raises `IndexError` (past `sample_count`, though `positions[2]` exists)
   - `pop(-1)` removes the sample at index 1 from both arrays and leaves
     `sample_count == 1`
2. Apply the fix.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] All four tests fail before, pass after (three of four; see Resolution
      notes for the one that already passed pre-fix for an unrelated reason)
- [x] Single shared index-normalization helper; no duplicated bounds logic
- [x] Docstring at `:27-30` is now true
- [x] `make uv-fullCheck` passes

## Out of scope

Adding `from_components` / `__array__` / `isclose` to the aggregates — that is
chunk 50.

## Resolution notes

- Added `WaveformSpatialPose._resolve_index(index: int) -> int`
  (`src/math_tools/waveforms/waveform_spatial_pose.py`), the single shared
  helper that normalizes an int index against `sample_count` and raises
  `IndexError` out of range. `__getitem__(int)`, `get()`, and `pop()` all now
  call it instead of indexing `_positions`/`_quaternions` with the raw index.
  `get()` wraps the call in `try/except IndexError` to preserve its
  `None`-on-out-of-range contract.
- `pop()`'s empty-check now tests `sample_count == 0` (was
  `len(_positions) == 0 or len(_quaternions) == 0`), consistent with treating
  `sample_count` as the single source of truth for valid range.
- Audited slicing (`__getitem__(slice)`) and `__iter__`: both already derive
  bounds from `sample_count` (`index.indices(self.sample_count)` and
  `range(self.sample_count)` respectively) — no defect, no change. No
  `__setitem__` exists on this class (only named mutation verbs
  `replace`/`replace_range`/`insert`, which the chunk's audit list did not
  name); left untouched per "do not restructure the class" / stay-in-scope.
- Deviation from the TDD steps: the 3rd failing test (`w[2]` raises
  `IndexError` past `sample_count` though the longer raw array has index 2)
  already passed *before* the fix. `sample_count = min(len(positions),
  len(quaternions))` guarantees at least one raw array is exactly
  `sample_count` long, so any index `>= sample_count` always overruns that
  shorter array and numpy raises `IndexError` on it regardless of the
  indexing bug — there is no reachable state where a positive
  beyond-`sample_count` index is in-bounds on both raw arrays. The test is
  kept (it is still the correct behavioral pin, now true by design rather
  than by accident) but only 3 of the 4 tests actually demonstrated a
  pre-fix failure.
- No spec change: `waveformCore.md` §Compliance 9 and the module docstring
  already specified sample_count-derived indexing; this chunk closes an
  implementation gap, not a contract gap.
