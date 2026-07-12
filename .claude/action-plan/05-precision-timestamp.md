---
chunk: 05-precision-timestamp
track: B
status: pending
depends_on: [04]
spec: ../specs/precisionTimeMath.md §PrecisionTimestamp, §Compliance 1, 7–10
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 05 — `PrecisionTimestamp`

**Deliverable:** the attosecond-exact epoch-referenced timestamp with
metadata-validated comparison.

## Files

- Create: `src/math_tools/precision_time/precision_timestamp.py`
- Edit: `src/math_tools/precision_time/__init__.py` (add export)
- Create: `tests/precision_time/test_precision_timestamp.py`

## Design constraints

1. Subclass `PrecisionTimestampABC`; composes a `PrecisionTimeInterval`
   offset plus `timescale`/`reference_frame`/`uncertainty` (all optional,
   `None` default). Immutable + hashable (metadata included in hash/eq).
2. Full surface per spec: constructors (`__init__`, `from_interval`,
   `from_datetime` — tz-aware required, `ValueError` on naive —, `now`,
   `from_days`, `EPOCH`), accessors (`interval`, `days_since_epoch`,
   `seconds_of_day`, `as_datetime` UTC lossy-to-µs), arithmetic
   (`ts ± interval`, `interval + ts`, `ts - ts → interval`), ordering
   (offsets only), `==` (includes metadata).
3. `can_compare` / `compare_validated` semantics EXACTLY per spec (verified
   against `SWIFT_TYPES/PrecisionTime/Extensions/PrecisionTimestamp+Comparable.swift`):
   `can_compare` = both-specified timescale/frame equality only;
   `compare_validated` additionally raises `TimestampComparisonError`
   (from `math_tools.errors`) on uncertainty overlap when BOTH carry
   uncertainty and `|delta| <= u1 + u2` (boundary equality raises).
4. Metadata propagation on `ts ± interval`: carried from the timestamp.

## TDD steps

1. Failing tests: spec compliance 7 (cross-epoch subtraction exact), 8 (all
   `compare_validated` branches incl. the `delta == combined` boundary and
   the None-metadata compatibility rules), 9 (datetime round-trip incl.
   pre-epoch), plus hash/eq-with-metadata.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Spec compliance items 7, 8, 9 each have named tests and pass
- [ ] Round-trip with `PrecisionTimestampType` wire dicts (camelCase optional keys)
- [ ] `isinstance` of the ABC; `EPOCH.is_epoch` is True
- [ ] `make uv-fullCheck` passes

## Out of scope

Waveform usage; timezone conversion beyond UTC; leap-second/timescale math
(metadata is carried, never interpreted).
