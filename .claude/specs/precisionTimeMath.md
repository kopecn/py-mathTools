---
version: 1.0
type: specification
name: precisionTimeMath
purpose: Behavioral contract for the Tier-3 PrecisionTimeInterval and PrecisionTimestamp math types
spec: PrecisionTimeMath
scope: project
status: accepted
applies_to: src/math_tools/precision_time/, tests/precision_time/
last_updated: 2026-09-08
semver: 0.0.3
author: Nicholas Bergantz
---

# Precision Time Math Types

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). Ports the
> behavior of Swift `PrecisionTimeInterval` / `PrecisionTimestamp`
> (spmFoundationTools `FoundationTypes/PrecisionTime/`, including
> `+Arithmetic`) as Tier-3 classes over the foundation ABCs. These are the
> time axis of every waveform type ([waveformCore.md](waveformCore.md)).

## Base contracts

- `PrecisionTimeInterval(PrecisionTimeIntervalABC)` — from
  `foundation_abc.math.precisionTimeABC`.
- `PrecisionTimestamp(PrecisionTimestampABC)` — same module.
- Enums come from `foundation_abc.math.mathEnums` (`NumericSign`,
  `Timescale`, `ReferenceFrame`) — never redefined here.

## Representation

Internal storage is a **single signed Python `int` of total attoseconds**
(exact, unbounded). The ABC's `(seconds, attoseconds, sign)` triple is derived
on access:

```python
@property
def seconds(self) -> int:      return abs(self._total_atto) // ATTOSECONDS_PER_SECOND
@property
def attoseconds(self) -> int:  return abs(self._total_atto) % ATTOSECONDS_PER_SECOND
@property
def sign(self) -> NumericSign: # ZERO when _total_atto == 0, else POSITIVE/NEGATIVE
```

Divergence from Swift (per umbrella non-goal 3): no `UInt64` saturation, no
wrapping operators — arithmetic is exact.

## `PrecisionTimeInterval`

Immutable (instances are hashable; all operations return new instances).

**Constructors**
- `PrecisionTimeInterval(seconds: int = 0, attoseconds: int = 0, sign: NumericSign = POSITIVE)` — ABC-shaped; normalizes (attosecond carry into seconds); `ValueError` on negative magnitude components.
- `from_seconds(seconds: float | int) -> PrecisionTimeInterval` — sign inferred; float path loses no more than float64 precision.
- `from_attoseconds(total: int) -> PrecisionTimeInterval` — signed total.
- `from_string(seconds: str, fractional: str) -> PrecisionTimeInterval` — lossless decimal-string constructor (fractional right-padded to 18 digits; `ValueError` if >18 digits or non-numeric).
- Class constants: `ZERO`, `ONE_SECOND`, `ONE_DECISECOND`, `ONE_MILLISECOND`, `ONE_MICROSECOND`.

**Accessors** (beyond ABC): `total_attoseconds: int` (signed),
`seconds_as_float: float`.

**Arithmetic / comparison** (all with `PrecisionTimeInterval` operands unless
noted; `NotImplemented` for foreign types so Python falls back correctly):
- `+`, `-`, unary `-`, unary `+`, `abs()`
- `*` and `/` by `int | float` scalar (both operand orders for `*`); scalar
  ops round to nearest attosecond.
- `/` interval → `float` ratio (`ZeroDivisionError` on zero divisor).
- `==`, `<`, `<=`, `>`, `>=` (total ordering on signed total), `__hash__`.
- `bool(x)` is `not x.is_zero`.

**Serialization**: `to_dict` and `from_dict` are both implemented on this
class (the Tier-2 ABC declares them abstract and, per `mathTypeTiers.md`, must
stay free of concrete wire mappings — there is nothing to inherit). Both use
the ABC wire shape `{"attoseconds", "seconds", "sign"}` (`sign` as its string
value) — exactly what `foundationTypes` `PrecisionTimeIntervalType.to_dict()`
emits, so payloads round-trip through either carrier (wire-format interop is
the Tier-1↔Tier-3 contract).

## `PrecisionTimestamp`

A point in time = signed attosecond offset from the Unix epoch, plus optional
metadata `timescale: Timescale | None`, `reference_frame: ReferenceFrame | None`,
`uncertainty: int | None` (attoseconds). Immutable, hashable.

**Constructors**
- `PrecisionTimestamp(seconds=0, attoseconds=0, sign=POSITIVE, *, timescale=None, reference_frame=None, uncertainty=None)`
- `from_interval(interval, *, timescale=None, ...)`
- `from_datetime(dt: datetime.datetime, ...)` — pre-epoch supported; naive datetimes are `ValueError` (require tz-aware).
- `now(*, timescale=None, ...)` — classmethod.
- `from_days(days_since_epoch: int, attoseconds_of_day: int = 0, sign=POSITIVE, ...)`
- Class constant `EPOCH`.

**Accessors**: ABC set plus `interval: PrecisionTimeInterval` (offset from
epoch), `days_since_epoch: int`, `seconds_of_day: int`,
`as_datetime: datetime.datetime` (UTC, lossy to microseconds).

**Arithmetic / comparison**
- `timestamp ± interval → timestamp` (metadata carried from the timestamp);
  `interval + timestamp → timestamp`.
- `timestamp - timestamp → PrecisionTimeInterval`.
- `==` includes metadata equality; `<`/`<=`/`>`/`>=` compare offsets only
  (numeric ordering, Swift parity).
- `can_compare(other) -> bool` — False only when **both** sides specify a
  `timescale` and they differ, or both specify a `reference_frame` and they
  differ (a `None` on either side is compatible with anything). Uncertainty
  is NOT part of `can_compare` (Swift parity: `canCompare(to:)`).
- `compare_validated(other) -> int` — returns -1/0/1; raises
  `TimestampComparisonError` (from `math_tools.errors`, with a reason) when
  (a) both specify differing timescales, (b) both specify differing reference
  frames, or (c) both carry `uncertainty` and the absolute offset difference
  is ≤ the sum of the two uncertainties (overlap). This is the Python
  rendering of Swift's `Result<ComparisonResult, ComparisonValidationError>`
  in `PrecisionTimestamp+Comparable.swift`.

**Serialization**: `to_dict` and `from_dict` are both implemented on this
class (camelCase optional keys `referenceFrame`/`timescale`/`uncertainty`
emitted only when present); the wire shape matches `PrecisionTimestampType`
for round-trip parity.

## Compliance requirements (test-checkable)

1. Round-trip: `PrecisionTimeInterval.from_dict(PrecisionTimeIntervalType.from_dict(d).to_dict()).to_dict() == d` for representative payloads (and the timestamp equivalent).
2. `from_string("1", "5")` equals 1.5 s exactly; `from_string("0", "000000000000000001")` is 1 attosecond.
3. Attosecond exactness: `ONE_SECOND - PrecisionTimeInterval.from_attoseconds(1)` has `seconds == 0`, `attoseconds == 10**18 - 1`.
4. Carry normalization: constructing with `attoseconds >= 10**18` carries into seconds.
5. Sign algebra: negating flips `sign`; zero is `NumericSign.ZERO` and `bool` False.
6. Scalar mult/div round to nearest attosecond (pin one case each).
7. `timestamp - timestamp` across the epoch (one pre-1970 operand) is exact.
8. `compare_validated` raises `TimestampComparisonError` on differing timescale (both set), differing frame (both set), and overlapping uncertainty (both set, delta ≤ combined — pin the boundary case delta == combined as raising); returns -1/0/1 otherwise. `can_compare` is True when either side's metadata is `None` and ignores uncertainty.
9. `as_datetime`/`from_datetime` round-trips to microsecond precision, including a pre-epoch instant.
10. mypy strict clean; all classes pass `isinstance(x, <ABC>)`.
