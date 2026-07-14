---
chunk: 04-precision-time-interval
track: B
status: complete
depends_on: [02]
spec: ../specs/precisionTimeMath.md §Representation, §PrecisionTimeInterval, §Compliance 1–6, 10
last_updated: 2026-07-13
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

- [x] Spec compliance items 2, 3, 4, 5, 6 each have a named test and pass
- [x] Round-trip with `foundationTypes.mathTypes.MathTypes.PrecisionTimeIntervalType` wire dicts (compliance 1, interval half)
- [x] `isinstance(x, PrecisionTimeIntervalABC)` and `hash(x)` both work
- [x] `make uv-fullCheck` passes

## Out of scope

`PrecisionTimestamp` (chunk 05); waveform usage; any datetime interop.

## Resolution notes

- Storage is a single signed `int` (`_total_atto`) on `__slots__`; `seconds`,
  `attoseconds`, `sign` are all derived properties (single source of truth —
  the constructor never stores the caller's `sign` verbatim, it re-derives
  sign from the normalized magnitude so a contradictory input like
  `sign=NEGATIVE` with zero magnitude can't produce an inconsistent state).
- Scalar `*`/`/` by `float` round to nearest attosecond via exact
  `fractions.Fraction` arithmetic (`Fraction(value)` captures the float64
  value exactly, so no precision is lost beyond what the float already
  cost) and Python's built-in `round()` (round-half-to-even on `Fraction`)
  — pinned test cases use binary-exact scalars (`2.5`, `2.0`) so the
  half-to-even tie-break is deterministic and spelled out in the test.
  `int` scalar mult/div stays exact (no `Fraction` needed).
  `from_seconds(float)` uses the same `Fraction` approach.
  `from_string` raises `ValueError` (not truncate, unlike the Swift
  `secondsString:attosecondsString:` initializer) per the spec's explicit
  "ValueError if >18 digits or non-numeric" — the lossless behavior is
  Swift's separate `fractionalString` initializer, ported here as
  `from_string`.
  `__add__`/`__sub__`/`__lt__`/`__le__`/`__gt__`/`__ge__`/`__mul__`/
  `__rmul__` are typed to their real operand types (not bare `object`) so
  misuse is a static mypy error, matching the existing `Quaternion` idiom;
  `__eq__` stays typed `object` (narrowing it would violate the `object`
  override-compatibility check mypy enforces for `__eq__`/`__ne__`).
  `__truediv__` uses `@overload` (`PrecisionTimeInterval -> float`,
  `int | float -> PrecisionTimeInterval`) to type both return shapes
  precisely.
- **Session interruption**: this chunk was executed in two passes across a
  session boundary. Pass 1 wrote the implementation, tests, and reasoned
  through every test case by hand (a transient outage in the harness's Bash
  safety classifier blocked running the gate directly). Pass 2 (this
  resumption) found `make uv-lint` failing with 27 ruff errors — 26 UP037
  ("remove quotes from type annotation," since `from __future__ import
  annotations` makes the quoted forward-refs on `PrecisionTimeInterval`
  redundant) and 1 B015 ("pointless comparison" on the bare
  `interval < 1.0` statement inside `assertRaises(TypeError)`). Fixed via
  `ruff check --fix --unsafe-fixes` for the 26 UP037s, and by assigning the
  comparison to `_` (`_ = interval < 1.0  # type: ignore[operator]`) for the
  B015 — preserves the test's intent (still executes the comparison,
  mypy still flags the deliberate misuse, `assertRaises` still catches the
  resulting `TypeError`). A separate mypy `[type-arg]` error (bare `dict`
  in a test helper's signature) surfaced only under the full gate and was
  fixed by annotating `dict[str, Any]`. `make uv-fullCheck` is green: ruff
  clean, mypy strict clean (20 source files), 178 tests passed (71 new).
- No files were touched outside this chunk's file list.
