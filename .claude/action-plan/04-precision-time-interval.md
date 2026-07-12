---
chunk: 04-precision-time-interval
track: B
status: pending
depends_on: [02]
spec: ../specs/precisionTimeMath.md §Representation, §PrecisionTimeInterval, §Compliance 1–6, 10
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 04 — `PrecisionTimeInterval`

**Deliverable:** the immutable attosecond-exact interval type.

## Files

- Create: `src/math_tools/precision_time/__init__.py` (re-export
  `PrecisionTimeInterval`; `PrecisionTimestamp` added by chunk 05),
  `src/math_tools/precision_time/py.typed`,
  `src/math_tools/precision_time/precision_time_interval.py`
- Create: `tests/precision_time/__init__.py`,
  `tests/precision_time/test_precision_time_interval.py`

## Design constraints

1. Subclass `foundation_abc.math.precisionTimeABC.PrecisionTimeIntervalABC`;
   enums from `foundation_abc.math.mathEnums`. Use the ABC's
   `ATTOSECONDS_PER_SECOND`, never a new literal.
2. Storage: one private signed `int` of total attoseconds (spec
   §Representation shows the derived accessors — implement exactly that).
3. Immutable + hashable: no public setters; implement `__hash__` from the
   total; all arithmetic returns new instances; foreign operand types return
   `NotImplemented`.
4. Full surface per spec: constructors (`__init__` ABC-shaped with
   normalization/carry, `from_seconds`, `from_attoseconds`, `from_string`),
   constants (`ZERO`, `ONE_SECOND`, `ONE_DECISECOND`, `ONE_MILLISECOND`,
   `ONE_MICROSECOND`), accessors (`total_attoseconds`, `seconds_as_float`),
   arithmetic (`+ - neg pos abs`, scalar `* /` rounding to nearest
   attosecond, interval `/` interval → float), total ordering, `bool`,
   `to_dict`/`from_dict` on the ABC wire shape, `repr`.
5. Swift reference for semantics questions:
   `SWIFT_TYPES/PrecisionTime/PrecisionTimeInterval.swift` (+`+Arithmetic`)
   — but NO saturation/wrapping ops (spec divergence).

## TDD steps

1. Failing tests covering spec compliance items 2–6 and 10 (interval half)
   plus hashability and `NotImplemented` fallback (e.g. `interval + 1.0`
   raises `TypeError`).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Spec compliance items 2, 3, 4, 5, 6 each have a named test and pass
- [ ] Round-trip with `foundationTypes.mathTypes.MathTypes.PrecisionTimeIntervalType` wire dicts (compliance 1, interval half)
- [ ] `isinstance(x, PrecisionTimeIntervalABC)` and `hash(x)` both work
- [ ] `make uv-fullCheck` passes

## Out of scope

`PrecisionTimestamp` (chunk 05); waveform usage; any datetime interop.
