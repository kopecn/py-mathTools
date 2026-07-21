---
chunk: 35-otg-trajectory-and-output
track: E
status: complete
depends_on: [34]
spec: ../specs/otg.md §Public API (Trajectory, OutputParameter)
last_updated: 2026-07-21
semver: 0.0.1
author: Nicholas Bergantz
---

# 35 — `Trajectory` + `OutputParameter`

**Deliverable:** the trajectory container/sampler and the per-cycle output
struct. Faithful ports of `SWIFT_MATH/OTG/Trajectory.swift` and
`OutputParameter.swift`.

## Files

- Create: `src/math_tools/otg/trajectory.py`,
  `src/math_tools/otg/output_parameter.py`
- Edit: `src/math_tools/otg/__init__.py` (export both)
- Create: `tests/otg/test_trajectory.py`, `tests/otg/test_output_parameter.py`

## Design constraints

1. `Trajectory`: `profiles: list[list[Profile]]`, `duration`,
   `cumulative_times`, `independent_min_durations`, `degrees_of_freedom`;
   `at_time(t) -> (positions, velocities, accelerations)` (lists of float;
   clamp to `[0, duration]` per the Swift edge handling — read `atTime`
   first and mirror its section lookup), `position_extrema() ->
   list[Bound]`, internal `get_intermediate_durations`,
   `get_first_time_at_position`.
2. `OutputParameter(dofs, max_number_of_waypoints=0)`: fields per spec
   (`new_position/velocity/acceleration/jerk`, `time`, `new_section`,
   `did_section_change`, `new_calculation`, `calculation_duration` in µs),
   `pass_to_input(input)` (copies new state into the input's current
   state — port the Swift field list exactly), `repr`.
3. Stdlib only; sampling loops over DOFs like the Swift.

## TDD steps

1. Failing tests: build a single-DOF Trajectory from a hand-constructed
   Profile (chunk 33's test fixture): `at_time(0)` == initial state,
   `at_time(duration)` == target state (atol 1e-9), midpoint consistent
   with `integrate_jerk`; out-of-range `t` clamps; `pass_to_input` copies
   every kinematic field (assert against a sentinel-filled InputParameter).
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Endpoint/midpoint sampling tests pass
- [x] `pass_to_input` field coverage pinned (loop over dofs asserting equality)
- [x] `make uv-fullCheck` passes

## Out of scope

Extrema across brake sections beyond the direct port; the driver's time
stepping (41).

## Resolution notes

- **Files landed:** `src/math_tools/otg/trajectory.py` (`Trajectory`),
  `src/math_tools/otg/output_parameter.py` (`OutputParameter`),
  `tests/otg/test_trajectory.py`, `tests/otg/test_output_parameter.py`;
  `src/math_tools/otg/__init__.py` now also exports `Trajectory` and
  `OutputParameter`.
- **`Profile.getPositionExtrema()` / `Profile.getFirstStateAtPosition()`
  (deferred by chunk 33 to "a later chunk (35, trajectory sampling)" per
  its Resolution notes):** ported as module-private functions in
  `trajectory.py` (`_profile_position_extrema`,
  `_profile_first_state_at_position`) rather than as new methods on
  `Profile` itself. This chunk's own file list does not include
  `profile.py`, and both functions only need `Profile`'s already-public
  fields plus the already-public `Profile.check_step_for_position_extremum`
  staticmethod, so no edit to `profile.py` was required. Cubic root
  solving in `_profile_first_state_at_position` delegates to
  `math_tools.functional.roots.solve_cubic` (never reimplemented), per
  otg.md's "OTG chunks MUST NOT reimplement root solving."
- **Constructor overload collapsing:** Swift's two `Trajectory` initializers
  (`init(dofs:)` and `init(dofs:maxNumberOfWaypoints:)`) collapse into one
  Python signature, `Trajectory(dofs, max_number_of_waypoints=0)` --
  `maxNumberOfWaypoints=0` already produces the identical single-section
  shape as the no-waypoints overload in the Swift source, so nothing is
  lost. `OutputParameter(dofs, max_number_of_waypoints=0)` mirrors the same
  collapse for its own two Swift overloads (`init(DOFs:)` /
  `init(dofs:maxNumberOfWaypoints:)`).
- **`at_time` clamping:** implemented by clamping the input `time` to
  `[0, duration]` before section lookup (`max(0.0, min(time, duration))`),
  exactly matching otg.md's own public-API text ("clamped to `[0,
  duration]` ends per Swift") -- not a deviation, just making explicit what
  the spec already specifies. At `time == duration` exactly, the ported
  `stateToIntegrateFrom` branch already yields `t_diff == 0` against the
  final boundary state, so clamping values beyond `duration` down to
  `duration` coincides with (rather than replaces) the literal Swift
  extrapolate-with-constant-acceleration behavior at the boundary itself;
  it only changes behavior strictly beyond the boundary, where the spec
  explicitly calls for clamping anyway.
- **`Bound` import:** `trajectory.py` imports `math_tools.otg.bound.Bound`
  directly (not the `_PositionExtremumSink` Protocol `profile.py` uses).
  Chunk 34's Resolution notes anticipated this: the Protocol was kept in
  `profile.py` specifically "until ... the later `Trajectory`/
  `TargetCalculator` chunks actually need it" -- this is that real
  dependency.
- **Structural-misuse error convention:** `OutputParameter.__init__`
  raises plain `ValueError` for non-positive `dofs` (matching
  `InputParameter.__init__`'s existing precedent), not `OtgError` --
  `OtgError` remains reserved for the `Otg` driver's own structural-misuse
  detection (otg.md §Error semantics, chunk 41), not leaf-type constructor
  validation. `OutputParameter.pass_to_input`'s array-size guard follows
  the same convention.
- **Gate:** `make uv-fullCheck` passes (ruff clean, mypy strict clean over
  95 source files, 1290 tests passed including the 14 new
  `test_trajectory.py` and 9 new `test_output_parameter.py` cases).
  `grep -rn numpy src/math_tools/otg/trajectory.py
  src/math_tools/otg/output_parameter.py` shows no import, preserving
  otg.md's compliance requirement 4. No spec change was needed --
  `otg.md`'s existing text already documents both the clamping behavior
  and the module layout used here.
