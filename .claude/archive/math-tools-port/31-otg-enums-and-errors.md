---
chunk: 31-otg-enums-and-errors
track: E
status: complete
depends_on: [10]
spec: ../specs/otg.md §Public API (enums), §Error semantics; §Compliance 3, 4
last_updated: 2026-07-21
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

- [x] Nine `Result` values pinned literally; the −103 gap pinned
- [x] No numpy import anywhere under `src/math_tools/otg/`
- [x] `make uv-fullCheck` passes

## Out of scope

Every other OTG module.

## Resolution notes

- Transcribed all seven enums from `SWIFT_MATH/OTG/enums/*.swift` (`Result`,
  `ControlInterface`, `Synchronization`, `DurationDiscretization`,
  `ControlSigns`, `Direction`, `ReachedLimits`). `Result` is `enum.IntEnum`
  (wire-stable ints); the rest are `str, enum.Enum` per the existing
  repo convention (`waveforms/support.py`) — public string enums keep the
  Swift raw string values verbatim (`"Position"`, `"TimeIfNecessary"`, …) for
  `to_dict`/`from_dict` wire parity; internal enums (`ControlSigns`,
  `Direction`, `ReachedLimits`) live in `enums.py` but are excluded from
  `__all__`, matching Swift's `internal` visibility.
- `otg/__init__.py` re-exports only the four public enums + `OtgError` this
  chunk introduces; the flat `math_tools` root `__init__.py` is left
  untouched (still empty — curating it is chunk 43's job per
  mathToolsArchitecture.md §Public surface).
- `tests/test_package_layering.py::test_otg_does_not_import_numpy` was
  already written (guarded to skip until `math_tools/otg` exists) by an
  earlier chunk; it now runs for real against this package and passes with
  no changes needed to that test file.
- No spec changes were required; `otg.md` §Public API's enum table matched
  the Swift source exactly, including the `-103` gap.
- `tests/otg/test_enums.py` also pins the three public string enums and the
  three internal enums (beyond the chunk's minimum TDD step) since the
  chunk's own "Design constraints" section requires transcribing all seven
  from the Swift source — leaving them untested would leave the fidelity
  requirement unverified.
