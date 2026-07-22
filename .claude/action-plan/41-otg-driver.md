---
chunk: 41-otg-driver
track: E
status: complete
depends_on: [40]
spec: ../specs/otg.md §Public API (Otg), §Error semantics, §Compliance 5
last_updated: 2026-07-22
semver: 0.0.1
author: Nicholas Bergantz
---

# 41 — `Otg` driver

**Deliverable:** the per-cycle driver class and the finished public surface.
Faithful port of `SWIFT_MATH/OTG/spmOTG.swift`.

## Files

- Create: `src/math_tools/otg/otg.py`
- Edit: `src/math_tools/otg/__init__.py` (final `__all__` per spec §Module
  layout)
- Create: `tests/otg/test_otg_driver.py`

## Design constraints

1. `Otg(control_cycle, dofs, max_number_of_waypoints=0)`; `OtgError` for
   structural misuse only (non-positive control_cycle, DOF mismatch between
   constructor and parameters); `update(input, output) -> Result` (validate
   → recalc-on-change → step `output.time` → sample → WORKING/FINISHED),
   `calculate(input, output) -> Result`, `reset()`. Port the input-change
   detection and `interrupt_calculation_duration` handling as the Swift
   does.
2. `calculation_duration` measured with `time.perf_counter_ns()` → µs
   (Swift used DispatchTime).

## TDD steps

1. Failing tests: a 1-DOF rest-to-rest move driven via repeated `update`
   reaches `FINISHED` in ≤ `duration/control_cycle + 2` calls (spec
   invariant); `output.new_position` at each cycle matches
   `trajectory.at_time(output.time)`; invalid input → `ERROR_INVALID_INPUT`
   (no exception); DOF mismatch raises `OtgError`; `pass_to_input` +
   `update` chaining is stable (`new_calculation` False when input
   unchanged).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] FINISHED-within-bound and no-exception error paths pass
- [x] `math_tools/otg/__init__.py` `__all__` == the spec's export list
      (pinned by test — spec compliance 5)
- [x] `make uv-fullCheck` passes

## Out of scope

Oracle suites (42); performance tuning.

## Resolution notes

- **Deliverable**: `src/math_tools/otg/otg.py` (`Otg`, the finished driver)
  plus `tests/otg/test_otg_driver.py` (17 tests across 6 `TestCase`
  classes). `__init__.py` now exports `Otg` and `Profile` (the latter was
  already public in `profile.py`'s own `__all__` since chunk 33 but not yet
  wired into the package `__init__`), bringing `__all__` to the spec's full
  10-name §Module layout list, pinned by `TestPublicSurface`.
- **Constructor deviates from Swift by design, per the chunk brief**:
  Swift's `OTG.init(deltaTime: Double = -1.0)` only rejects a non-positive
  delta lazily inside `validateInput`, and only when
  `durationDiscretization != .Continuous`. This port requires
  `control_cycle > 0` unconditionally at construction (`OtgError`
  otherwise), per design constraint 1's "non-positive control_cycle" ->
  structural misuse. Consequence: Swift's `deltaTime <= 0.0` branch inside
  `validateInput` is dead code under this port's stricter contract and was
  not ported (documented in `otg.py`'s module docstring).
- **DOF-mismatch guard added (not in Swift)**: Swift's fixed-size arrays
  make a DOF mismatch a compile-time non-issue in normal use, so
  `OTG.swift` never checks for one. This port's `InputParameter`/
  `OutputParameter` are plain Python lists with no static size, so
  `Otg._check_degrees_of_freedom` raises `OtgError` explicitly (checked at
  the top of both `calculate()` and `update()`, since `update()` can skip
  its own call to `calculate()` when the input hasn't changed).
- **Alias-mutation hazard (otg.md's cross-chunk pattern)**: Swift's
  `currentInput: InputParameter` is a struct field, so `currentInput =
  input` is a value copy; this port's `InputParameter` is a reference type
  (chunk 32), so the equivalent line uses `copy.deepcopy`. Verified by
  construction that a bare `self._current_input = input_parameter` would
  have aliased the caller's object and made the next cycle's
  `input_parameter != self._current_input` compare always `False`
  (identity), permanently breaking recalculation-on-change — documented in
  the module docstring rather than left implicit.
- **Confirmed the standard drive loop requires the caller to call
  `output.pass_to_input(input)` themselves each cycle** (mirroring Swift's
  documented Ruckig usage pattern): `Otg.update`'s internal
  `output.pass_to_input(self._current_input)` only keeps the driver's own
  cached copy in sync, not the caller's `input` object. A first draft of
  the `TestReset` test omitted this call between cycles and failed
  (`new_calculation` stayed `True` every cycle, since the caller's
  unmodified `input` kept diverging from the driver's internally-advancing
  cache) — fixed by adding `output.pass_to_input(inp)` between `update()`
  calls, which is the correct, intended usage pattern, not a workaround.
- **`filterIntermediatePositions` and the `interrupt_calculation_duration`
  field are intentionally not ported**: both are dead in the Swift source
  itself (`filterIntermediatePositions` is defined on `OTG` but never
  called by `calculate`/`update`; `interruptCalculationDuration` is read
  only by the Codable wire format, never by `OTG.swift` or
  `CalculatorTarget.swift`) — porting either would add untested surface
  outside otg.md §Public API (Otg) and this chunk's scope. Documented in
  the module docstring per the chunk instruction to "port
  `interrupt_calculation_duration` handling as the Swift does" (i.e.,
  not at all, since the Swift driver never reads it).
- **`Trajectory._state_to_integrate_from` reused directly**, per that
  method's own docstring ("available for the driver, chunk 41, to reuse")
  — the public `Trajectory.at_time` clamps its `time` argument to
  `[0, duration]` for its own standalone convenience-method contract, but
  `Otg.update` needs the section index and per-DOF jerk value alongside
  position/velocity/acceleration (`OutputParameter.new_section`/
  `new_jerk`), which `at_time`'s public signature doesn't expose; the
  private method returns exactly the `(section, [(t, p, v, a, j), ...])`
  tuple the driver needs and already handles the `time >= duration`
  constant-acceleration hold internally, matching Swift's unclamped
  `stateToIntegrateFrom(time: output.time, ...)` call inside `update`.
- **Test convergence tuned for speed, not fidelity**: chunk 40's shared
  rest-to-rest limits (`v_max=2, a_max=1, j_max=1`) were kept, but the
  target distance was reduced to `2.0` (`duration ≈ 4.0s`) with
  `control_cycle=0.1`, converging in ~40 `update()` calls instead of
  thousands — the FINISHED-within-bound invariant
  (`duration/control_cycle + 2`) is dimensionless and holds at any scale
  the numeric-stepping loop can just as well exercise at a much smaller
  iteration count.
- **`calculate()`'s public signature is `(input, output)`, not
  `(input, trajectory)`** like Swift's `OTG.calculate` — matching otg.md
  §Public API's unification (`calculate(input, output) -> Result`) already
  established by the chunk brief; internally it forwards
  `output.trajectory` to `TargetCalculator.calculate`.
- Gate: `make uv-fullCheck` — ruff clean, mypy strict clean (111 source
  files), 1335/1335 tests pass (full suite ran in ~1.6s locally).
