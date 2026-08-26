---
version: 1.0
type: specification
name: otg
purpose: Behavioral contract for the online trajectory generation (OTG / Ruckig-port) subsystem
spec: OTG
scope: project
status: accepted
applies_to: src/math_tools/otg/, tests/otg/
last_updated: 2026-07-22
semver: 0.0.5
author: Nicholas Bergantz
---

# Online Trajectory Generation (OTG)

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). A
> **faithful port** of the Swift OTG subsystem
> (`spmMathTools/FoundationMathTypes/OTG/`, itself a Ruckig port): time
> optimal, jerk-limited, multi-DOF trajectory generation. Fidelity ranking:
> (1) identical results on the truth-table oracles, (2) identical public
> semantics, (3) code structure mirroring the Swift files so the two ports
> stay diffable. Numeric kernel: `functional/roots.py`
> ([polynomials.md](polynomials.md)) — the OTG chunks MUST NOT reimplement
> root solving.

## Module layout (mirrors the Swift files 1:1)

```
math_tools/otg/
  __init__.py            # public re-exports: Otg, InputParameter, OutputParameter,
                         # Trajectory, Profile, Result, ControlInterface,
                         # Synchronization, DurationDiscretization, OtgError
  otg.py                 # Otg driver class            (spmOTG.swift)
  input_parameter.py     # InputParameter + validate   (InputParameter.swift + codable ext)
  output_parameter.py    # OutputParameter             (OutputParameter.swift)
  trajectory.py          # Trajectory                  (Trajectory.swift)
  profile.py             # Profile + ControlSigns/Direction/ReachedLimits (Profile.swift)
  block.py               # Block, Interval             (Block.swift)
  bound.py               # Bound                       (Bound.swift)
  brake.py               # BrakeProfile                (Brake.swift)
  calculator_target.py   # TargetCalculator            (CalculatorTarget.swift)
  enums.py               # Result, ControlInterface, Synchronization, DurationDiscretization
  errors.py              # OtgError (Swift RuckigError/OTGErrors)
  steps/
    position_first_order.py    # PositionFirstOrderStep1/Step2
    position_second_order.py   # PositionSecondOrderStep1/Step2
    position_third_order_step1.py  # PositionThirdOrderStep1 (~850 Swift lines)
    position_third_order_step2.py  # PositionThirdOrderStep2 (~1900 Swift lines)
    velocity_second_order.py   # VelocitySecondOrderStep1/Step2
    velocity_third_order.py    # VelocityThirdOrderStep1/Step2
```

**Chunking hints (sized for one-session execution):**
`position_third_order_step1.py` and `position_third_order_step2.py` are
separate modules AND separate chunks (combined they are ~2,750 Swift lines —
never one chunk; split further along Swift function boundaries if needed,
preserving diffability). `profile.py` (~715 Swift lines),
`calculator_target.py` (~780), and the `Otg` driver each get their own
chunk.

Only the `__init__.py` re-exports are public; `steps/`, `block/bound/brake`,
and `calculator_target` are private (`_`-free filenames but excluded from
`__all__`; they mirror Swift `internal`).

## Public API

**Enums** (`enums.py`):
- `Result(IntEnum)`: `WORKING = 0`, `FINISHED = 1`, `ERROR = -1`,
  `ERROR_INVALID_INPUT = -100`, `ERROR_TRAJECTORY_DURATION = -101`,
  `ERROR_POSITIONAL_LIMITS = -102`, `ERROR_ZERO_LIMITS = -104`,
  `ERROR_EXECUTION_TIME_CALCULATION = -110`,
  `ERROR_SYNCHRONIZATION_CALCULATION = -111` — values are wire-stable
  (Ruckig parity).
- `ControlInterface`: `POSITION`, `VELOCITY`.
- `Synchronization`: `TIME`, `TIME_IF_NECESSARY`, `PHASE`, `NONE`.
- `DurationDiscretization`: `CONTINUOUS`, `DISCRETE`.

**`InputParameter(dofs: int)`** — mutable per-cycle input; field-for-field
port of the Swift struct (current/target position/velocity/acceleration,
max/min velocity/acceleration, max jerk, optional position limits,
`enabled: list[bool]`, per-DOF control interface/synchronization overrides,
`intermediate_positions`, per-section limits/durations, `minimum_duration`,
`interrupt_calculation_duration`). `validate(check_current_state_within_limits=False,
check_target_state_within_limits=True) -> bool`. `==` field equality.
`to_dict`/`from_dict` (camelCase keys per the Swift Codable extension).

**`OutputParameter(dofs: int, max_number_of_waypoints: int = 0)`** —
`trajectory: Trajectory`, `new_position/new_velocity/new_acceleration/
new_jerk: list[float]`, `time: float`, `new_section: int`,
`did_section_change: bool`, `new_calculation: bool`,
`calculation_duration: float` (µs, Swift parity),
`pass_to_input(input: InputParameter) -> None`.

**`Trajectory`** — `duration: float`, `degrees_of_freedom: int`,
`at_time(t: float) -> tuple[list[float], list[float], list[float]]`
(position, velocity, acceleration; clamped to `[0, duration]` ends per
Swift), `position_extrema() -> list[Bound]`, `independent_min_durations:
list[float]`, profile access for tests.

**`Otg(control_cycle: float, dofs: int, max_number_of_waypoints: int = 0)`**
— the driver:
- `update(input: InputParameter, output: OutputParameter) -> Result` — one
  control cycle: validates (→ `ERROR_INVALID_INPUT`), recalculates when the
  input changed, steps `output.time` forward by `control_cycle`, samples the
  trajectory into `output.new_*`, returns `WORKING`/`FINISHED`/error code.
- `calculate(input: InputParameter, output: OutputParameter) -> Result` —
  full-trajectory calculation without time stepping.
- `reset() -> None`.

**Error semantics** (umbrella exception carve-out): per-cycle failures are
`Result` codes, never exceptions. `OtgError` is raised only for structural
misuse (mismatched DOF counts between constructor and parameters,
non-positive `control_cycle`) — conditions that make every future cycle
invalid.

## Internal fidelity requirements

1. `Profile` is the hot per-DOF state record: arrays `t[7]`, `t_sum[7]`,
   `j[7]`, `a[8]`, `v[8]`, `p[8]` as `list[float]` (fixed length, never
   resized), plus `brake`/`accel: BrakeProfile`, targets `pf/vf/af`,
   `limits: ReachedLimits`, `direction: Direction`,
   `control_signs: ControlSigns`, and the `check*` method family with the
   same names snake_cased. The kinematic stepping uses
   `functional.roots.integrate_jerk`.
2. Step-solver classes port one Swift class each, same names snake_cased
   (`PositionThirdOrderStep1.get_profile_...` etc.), same branch structure.
   Translate mechanically; do not restructure the case analysis (it encodes
   the Ruckig paper's profile taxonomy).
3. `TargetCalculator.synchronize` reproduces the Swift block-interval
   synchronization (including `Block`/`Interval` blocked-interval logic and
   the discrete-duration path).
4. Float64 throughout; comparisons use the Swift port's exact epsilon
   constants (`EPS16`, `POLYNOMIAL_*` from `functional/roots.py` — never
   fresh literals). Swift `Double` division silently yields `inf`/`nan` on
   a zero denominator (IEEE 754); Python's `/` raises `ZeroDivisionError`
   instead. Where a step solver's own algebra can produce a legitimate
   zero denominator at a degenerate root (e.g.
   `steps/position_third_order_step1.py`'s `_time_all_none_acc0_acc1`, a
   `t == 0` quartic root when the polynomial's constant term is zero), the
   division is routed through an IEEE-754-semantics helper
   (`_ieee754_div`) instead of the bare `/` operator, reproducing Swift's
   silent nan/inf propagation (which `Profile.check`'s precision
   comparisons then naturally reject) rather than crashing. This is NOT a
   blanket rule to wrap every division in the OTG port — only sites where
   a real Swift Double division-by-zero has been shown (by a failing
   test) to be reachable. The same total-vs-partial-function divergence
   applies to `sqrt`: Swift `Double`'s `sqrt` of a negative argument is
   `nan` (never traps), Python's `math.sqrt` raises `ValueError`. A
   negative-discriminant `sqrt` is the *generic* way a Step2 time-
   synchronization solver's algebra signals "no real solution at this
   prescribed duration" — reachable from ordinary usage (any
   below-time-optimal duration), not a rare degenerate root — so
   `steps/position_third_order_step2.py` routes every `sqrt` call through
   an `_ieee754_sqrt` helper file-wide, unlike `_ieee754_div`'s
   deliberately per-site scoping (see that file's module docstring and
   `_ieee754_sqrt`'s docstring for the reachability trace that motivated
   the broader scope, and `39-otg-position-third-step2.md`'s Resolution
   notes). Future step-solver chunks should default to `_ieee754_div`'s
   narrower, failing-test-driven scoping and only widen it the way this
   file did if a similar cascade is demonstrated.
5. Pure Python + stdlib `math` in the per-cycle path (no numpy — scalar
   loops over DOFs, matching Swift; performance is explicitly a non-goal
   until measured).

## Oracle and test strategy

Two oracle tiers — the JSON corpus records **inputs only** (no durations, no
kinematics, no Result codes), so it can classify but not pin numbers; the
numeric golden lives in a hardcoded Swift test array.

1. **Classification corpus:** copy `successful_trajectories.json`
   (~1,680 cases) and `failed_trajectories.json` (~100 cases) from
   `spmMathTools/spm/Tests/spmMathToolsTests/OTGTests/truthTables/` into
   `tests/otg/data/` unmodified. `test_otg_truth_table.py` asserts:
   successful cases → `calculate` returns a non-error `Result`
   (`Result >= 0`); failed cases → an error `Result` (`Result < 0` — the
   JSON's free-text error strings are NOT mapped to specific codes).
2. **Numeric oracle:** port the 31-case hardcoded truth table from
   `OTGTruthTableTests.swift` (each case: input state/limits +
   `expectedDuration` + `expectedTimeIntervals`, the 7 profile segment
   times) into `tests/otg/data/otg_numeric_truth.json`, transcribed
   verbatim from the Swift literals. Assertions per case: trajectory
   duration rtol 1e-6; `Profile.t` segment times against
   `expectedTimeIntervals` atol 1e-6 (this pins branch selection, not just
   the coincidentally-summable duration; capped at 1e-6 rather than 1e-8
   because the Swift literals themselves are recorded to only 6 decimal
   places — a tighter atol cannot be satisfied by any correct port).
3. **Ported suites:** the Swift `OTGComprehensiveTests`, `OTGContinuityTests`
   (position/velocity/acceleration continuity across cycle boundaries and
   section changes), and `OTGFailureFixTests` regression cases are ported
   test-for-test.
4. **Invariant tests:** for randomized (seeded) valid inputs — output never
   exceeds max velocity/acceleration/jerk beyond 1e-9; `at_time(duration)`
   hits the target state within 1e-8; `FINISHED` is reached within
   `duration/control_cycle + 2` update calls.

## Compliance requirements (test-checkable)

1. Classification corpus passes 100% of cases; numeric 31-case oracle passes
   (duration rtol 1e-6, segment times atol 1e-6).
2. Continuity suite passes (no kinematic discontinuities at cycle/section
   boundaries).
3. `Result` enum integer values grep-match the table above.
4. `math_tools/otg/` imports numpy nowhere (grep-pinned); imports the root
   kernel only from `math_tools.functional.roots`.
5. Public surface = the `__init__.py` re-export list, nothing else
   (`__all__` pinned by test).
6. mypy strict clean.
