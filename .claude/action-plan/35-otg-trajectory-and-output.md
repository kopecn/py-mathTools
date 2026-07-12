---
chunk: 35-otg-trajectory-and-output
track: E
status: pending
depends_on: [34]
spec: ../specs/otg.md §Public API (Trajectory, OutputParameter)
last_updated: 2026-07-11
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

- [ ] Endpoint/midpoint sampling tests pass
- [ ] `pass_to_input` field coverage pinned (loop over dofs asserting equality)
- [ ] `make uv-fullCheck` passes

## Out of scope

Extrema across brake sections beyond the direct port; the driver's time
stepping (41).
