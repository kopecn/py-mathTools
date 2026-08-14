---
chunk: 47-position-tolerance-and-timestamp-accessors
track: F
status: complete
depends_on: []
spec: ../specs/spatialMath.md, ../specs/precisionTimeMath.md
last_updated: 2026-07-23
semver: 0.0.1
author: Nicholas Bergantz
---

# 47 — Fix `Position.is_unit` tolerance and pre-epoch timestamp accessors

## Origin

Post-audit findings B-1 and B-2 (class **c**), both confirmed at runtime:

```
Position(1.00001, 0, 0).is_unit                  -> True    (should be False)
from_datetime(1969-12-31T23:59:50Z).seconds_of_day -> 10     (should be 86390)
from_datetime(1960-01-01Z).days_since_epoch        -> +3653  (should be -3653)
```

Two independent defects, grouped because both are one-line arithmetic fixes in
Track B accessors with the same test-blindness root cause (only the easy side
of the boundary was ever tested).

**B-1** — `src/math_tools/spatial/position.py:234` calls
`np.isclose(self.magnitude, 1.0, atol=1e-12)` but leaves numpy's default
`rtol=1e-5`, so the effective tolerance is ~1e-5, not the spec's 1e-12.

**B-2** — `src/math_tools/precision_time/precision_timestamp.py:250,255`
compute `days_since_epoch` / `seconds_of_day` from the **magnitude**
(`self.seconds`), so pre-epoch timestamps report positive, wrong-direction
values. The spec declares these as plain accessors on a *signed* epoch offset.

## Files

- Edit: `src/math_tools/spatial/position.py`
- Edit: `src/math_tools/precision_time/precision_timestamp.py`
- Edit: `tests/spatial/test_position.py`
- Edit: `tests/precision_time/test_precision_timestamp.py`

## Design constraints

1. B-1: pass `rtol=0.0` alongside `atol=1e-12` so the spec's absolute
   tolerance is the only one in effect.
2. B-2: compute both accessors from the signed offset. `days_since_epoch` must
   be negative for pre-epoch instants. `seconds_of_day` must be the
   **wall-clock second within the UTC day**, i.e. always in `[0, 86400)` — use
   a floor-division/modulo pair, not `abs()`, so 1969-12-31T23:59:50Z yields
   `86390` and its day index is `-1`.
3. Do not change the storage representation or any constructor. These are
   read-side fixes only.

## TDD steps

1. Failing tests first:
   - `Position(1.00001, 0, 0).is_unit is False`; keep the existing 1.0/2.0
     cases; add a just-inside case (`1 + 1e-13`) that must stay `True`.
   - `seconds_of_day` and `days_since_epoch` for a pre-epoch instant
     (1969-12-31T23:59:50Z → 86390, day −1) and a far pre-epoch instant
     (1960-01-01Z → days −3653), plus the existing post-epoch case unchanged.
   - Assert `0 <= seconds_of_day < 86400` holds for both signs.
2. Apply both fixes.
3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] `is_unit` rejects 1.00001 and accepts 1 + 1e-13
- [x] Pre-epoch `days_since_epoch` is negative; `seconds_of_day` ∈ [0, 86400) for both signs
- [x] All new tests fail before, pass after
- [x] Existing post-epoch and unit-magnitude tests unchanged and still green
- [x] `make uv-fullCheck` passes

## Out of scope

The generic-constructor degradation (`Position.from_vector` hardcoding, finding
B-6) — recorded, no action; see chunk 57's "Recorded — no action" section.

## Resolution notes

Both fixes were exactly the one-liners the plan predicted:

- **B-1** (`src/math_tools/spatial/position.py:234`): added `rtol=0.0` to
  the `np.isclose` call in `is_unit`, so the spec's `atol=1e-12` is the only
  tolerance in effect.
- **B-2** (`src/math_tools/precision_time/precision_timestamp.py:247-258`):
  `days_since_epoch` / `seconds_of_day` now derive from
  `self._interval.total_attoseconds` (the signed offset) via a floor-division
  (`//`) / modulo (`%`) pair against `ATTOSECONDS_PER_SECOND` and
  `_SECONDS_PER_DAY`, instead of the old `self.seconds` magnitude accessor.
  Python's `//`/`%` are floor-based for negative operands, which gives the
  wall-clock-second semantics the spec calls for for free (e.g. `-10 // 86400
  == -1`, `-10 % 86400 == 86390`) — no `abs()` or explicit sign branching
  needed.

TDD: added 2 new tests to `tests/spatial/test_position.py`
(`test_is_unit_false_just_outside_tolerance`,
`test_is_unit_true_just_inside_tolerance`) and 6 new tests to
`tests/precision_time/test_precision_timestamp.py` (pre-epoch
`days_since_epoch`/`seconds_of_day` at the 10s boundary, the far pre-epoch
1960-01-01 case matching the origin finding, and `[0, 86400)` bound checks
for both signs). Verified all new tests failed against the pre-fix code
before applying either fix, then verified green after. No existing test was
modified. `make uv-fullCheck` (ruff + mypy strict + full 1368-test pytest
suite) passes clean.
