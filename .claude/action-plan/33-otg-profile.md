---
chunk: 33-otg-profile
track: E
status: pending
depends_on: [31]
spec: ../specs/otg.md §Internal fidelity 1, 4, 5
last_updated: 2026-07-11
semver: 0.0.1
author: Nicholas Bergantz
---

# 33 — `Profile`

**Deliverable:** the per-DOF kinematic profile record — the hot data
structure every step solver fills. Faithful port of
`SWIFT_MATH/OTG/Profile.swift` (~715 lines; translate mechanically,
preserve method and branch structure).

## Files

- Create: `src/math_tools/otg/profile.py`
- Create: `tests/otg/test_profile.py`

## Design constraints

1. Fixed-length `list[float]` arrays `t[7]`, `t_sum[7]`, `j[7]`, `a[8]`,
   `v[8]`, `p[8]` — never resized. Targets `pf/vf/af`; `limits:
   ReachedLimits`, `direction: Direction`, `control_signs: ControlSigns`;
   `brake`/`accel` BrakeProfile fields are typed as the placeholder until
   chunk 34 lands — declare them `brake: "BrakeProfile"` with a deferred
   import if 34 is not yet merged, or coordinate to land 34's dataclass
   stub here (note which).
2. Kinematic stepping uses `math_tools.functional.roots.integrate_jerk` —
   never a fresh implementation.
3. Port the full `check*` family (`check`, `check_for_velocity`,
   `check_for_second_order`, `check_for_first_order`, `set_boundary`,
   `*_with_timing` variants, `check_position_extremum`,
   `check_step_for_position_extremum`) with the Swift epsilon constants
   (`EPS16` etc. from `functional.roots`).
4. Stdlib `math` only.

## TDD steps

1. Failing tests: a hand-constructed 7-phase profile (constant jerk ±j)
   integrates to the expected `p/v/a` boundary arrays (compute the expected
   values with `integrate_jerk` in the test, independent of Profile's own
   loop ordering); `check` accepts a known-valid profile and rejects a
   perturbed one (`t[3] += 1e-3`); `t_sum` is the prefix sum of `t`.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [ ] Boundary-array integration test passes; perturbation rejected
- [ ] `grep -n "integrate_jerk" src/math_tools/otg/profile.py` ≥ 1;
      no local jerk-integration reimplementation
- [ ] `make uv-fullCheck` passes

## Out of scope

Brake trajectory computation (34); step solvers; trajectory sampling.
