---
chunk: 31-otg-enums-and-errors
track: E
status: pending
depends_on: [10]
spec: ../specs/otg.md §Public API (enums), §Error semantics; §Compliance 3, 4
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 31 — OTG enums + errors

**Deliverable:** the OTG package skeleton with wire-stable enums.

## Files

- Create: `src/math_tools/otg/__init__.py` (exports grow per chunk; start
  with the enums + `OtgError`), `src/math_tools/otg/py.typed`,
  `src/math_tools/otg/enums.py`, `src/math_tools/otg/errors.py`
- Create: `tests/otg/__init__.py`, `tests/otg/test_enums.py`

## Design constraints

1. `enums.py` per spec: `Result(IntEnum)` with the exact nine values
   (including the intentional gap at −103 — transcribe from the spec table,
   verify against `SWIFT_MATH/OTG/enums/Result.swift`); `ControlInterface`,
   `Synchronization`, `DurationDiscretization` (string enums);
   internal `ControlSigns` (UDDU/UDUD), `Direction` (UP/DOWN),
   `ReachedLimits` (8 members per the Swift enum) — internal ones may live
   in `enums.py` but are excluded from `__all__`.
2. `errors.py`: `OtgError(MathToolsError)` — raised only for structural
   misuse per spec §Error semantics.
3. Pure stdlib module (the layering test's no-numpy-in-otg rule starts
   applying here).

## TDD steps

1. Failing tests: every `Result` member's integer value grep-matches the
   spec table (write the values as literals in the test); `Result(-103)`
   raises `ValueError` (the gap is real); `OtgError` is a `MathToolsError`.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Nine `Result` values pinned literally; the −103 gap pinned
- [ ] No numpy import anywhere under `src/math_tools/otg/`
- [ ] `make uv-fullCheck` passes

## Out of scope

Every other OTG module.
