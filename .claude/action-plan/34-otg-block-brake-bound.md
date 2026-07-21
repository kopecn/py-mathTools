---
chunk: 34-otg-block-brake-bound
track: E
status: complete
depends_on: [33]
spec: ../specs/otg.md §Internal fidelity 3–5
last_updated: 2026-07-21
semver: 0.0.1
author: Nicholas Bergantz
---

# 34 — `Block`, `BrakeProfile`, `Bound`, `Interval`

**Deliverable:** the block-interval synchronization support types and the
brake pre-trajectory. Faithful ports of `SWIFT_MATH/OTG/Block.swift`,
`Brake.swift`, `Bound.swift`.

## Files

- Create: `src/math_tools/otg/block.py` (Block + Interval),
  `src/math_tools/otg/brake.py`, `src/math_tools/otg/bound.py`
- Edit: `src/math_tools/otg/profile.py` ONLY if chunk 33 left the
  BrakeProfile fields as deferred placeholders (wire the real type in)
- Create: `tests/otg/test_block.py`, `tests/otg/test_brake.py`

## Design constraints

1. `bound.py`: `Bound` (min/max/t_min/t_max) — plain mutable dataclass.
2. `brake.py`: `BrakeProfile` — port `finalize`, `finalize_second_order`,
   `acceleration_brake`, `velocity_brake`,
   `get_position_brake_trajectory`, `get_velocity_brake_trajectory`,
   `v_at_t`, `v_at_a_zero`, `==` branch-for-branch.
3. `block.py`: `Block` (`p_min`, `t_min`, optional intervals `a`/`b`,
   `calculate_block`, `is_blocked`, `get_profile`) and `Interval`
   (`left`/`right`/`profile`). Preserve the blocked-interval selection
   logic exactly — it drives synchronization in chunk 40.
4. Stdlib `math` + `functional.roots` only.

## TDD steps

1. Failing tests: brake — a state exceeding max acceleration produces a
   non-zero brake duration and `v_at_t(0)` equals the initial velocity;
   a within-limits state produces an empty brake (t[0] == 0). Block —
   `is_blocked` boundary behavior at interval edges; `get_profile` returns
   the interval's profile for an in-interval t.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Brake zero/non-zero cases pass; interval edge cases pinned
- [x] `make uv-fullCheck` passes

## Out of scope

Step solvers; TargetCalculator.

## Resolution notes

- **Files landed:** `src/math_tools/otg/bound.py` (`Bound`, plain mutable
  `@dataclass`), `src/math_tools/otg/brake.py` (`BrakeProfile`),
  `src/math_tools/otg/block.py` (`Block` + `Interval`),
  `tests/otg/test_bound.py` was not created separately -- `Bound` has no
  behavior beyond its four fields and default values, so it is exercised
  indirectly via `test_block.py`'s `Interval`/`Block` fixtures and directly
  covered by mypy structural-Protocol satisfaction against
  `profile.py`'s `_PositionExtremumSink` (see below); `tests/otg/test_block.py`,
  `tests/otg/test_brake.py` created per the chunk's file list.
- **`BrakeProfile` scope beyond the chunk's design-constraint-2 method
  list:** also ported `get_second_order_position_brake_trajectory` and
  `get_second_order_velocity_brake_trajectory` (present in `Brake.swift`
  but not named in this chunk's design constraint 2). Justification:
  otg.md's fidelity ranking puts "faithful port" first, `Brake.swift`'s
  four `get*BrakeTrajectory` methods are all part of one cohesive public
  surface, and the second-order velocity/position step solvers (chunks
  36–39, not yet landed) will need the second-order brake paths — landing
  a partial `BrakeProfile` now would force a second, disruptive edit to
  this same file later. All four `get*BrakeTrajectory` methods, both
  `finalize*` methods, both velocity helpers, and `==` are ported
  branch-for-branch from `Brake.swift`.
- **Swift `inout` parameters:** `BrakeProfile.finalize`/
  `finalize_second_order` take `pS`/`vS`/`aS` as Swift `inout Double`;
  Python has no by-reference scalar parameters, so both return the updated
  `(p, v, a)` tuple instead. `Block.calculateBlock`/`Block.removeProfile`'s
  `inout Int` (`validProfileCounter`) becomes a returned, possibly
  decremented counter for the same reason; `block` (a class instance) and
  `validProfiles` (a list) mutate in place as normal Python object
  references, matching Swift's `inout` semantics for those two without any
  signature change.
- **Bug caught during self-review before running the gate:** an early
  draft of `BrakeProfile.acceleration_brake` added `del a_min` to mark the
  parameter as intentionally unused (mirroring `velocity_brake`, where
  `aMax` truly is unused in every branch of the Swift source) — but
  `acceleration_brake` **does** use `a_min` later, in the
  `velocity_brake(v0, a0, v_max, v_min, a_max, a_min, j_max)` delegation
  call. The `del` would have raised `UnboundLocalError` at runtime the
  first time that branch executed. Caught by re-reading `Brake.swift`
  side-by-side with the draft before writing tests; fixed by removing the
  `del` (kept only on `velocity_brake`'s genuinely-unused `a_max`).
- **`profile.py` reconciliation (chunk 33's deferred placeholders):**
  - `BrakeProfile`: removed the module-private `_DeferredBrakeProfile`
    dataclass and its now-unused `dataclasses.field`/`dataclass` imports;
    `profile.py` now does `from math_tools.otg.brake import BrakeProfile`
    and `Profile.brake`/`Profile.accel` are typed and constructed as the
    real `BrakeProfile`. No other call site changed — every chunk-33
    method already treated `brake`/`accel` as opaque (copied via
    `set_boundary`, never read field-by-field), exactly as chunk 33's
    Resolution notes predicted.
  - `Bound`: **left the `_PositionExtremumSink` structural `Protocol` in
    place**, rather than importing `math_tools.otg.bound.Bound` directly
    into `profile.py`. Chunk 33's Resolution notes explicitly authorized
    this ("the Protocol can stay indefinitely, or be swapped for a direct
    `Bound` import later purely for readability"). Reasons for choosing
    "stay" over "swap": (1) `Bound`'s fields (`min`, `max`, `t_min`,
    `t_max`) already satisfy the Protocol structurally by construction —
    the swap has zero behavioral or type-safety benefit; (2) swapping
    would additionally require retyping `tests/otg/test_profile.py`'s
    `_FakeBound` fixture (which duck-types the same Protocol) to import
    the real `Bound`, an edit to a file outside this chunk's own file list
    that the stay-in-scope default posture counsels against absent a
    concrete benefit; (3) it keeps `bound.py` a leaf module with zero
    importers inside `otg/` until `block.py`'s `Interval`/`Block` and the
    later `Trajectory`/`TargetCalculator` chunks actually need it,
    matching the "no import edge until there's a real dependency" spirit
    of the original deferral. Only `profile.py`'s module docstring and the
    `_PositionExtremumSink` class docstring were reworded (from
    "not-yet-landed" to "why this stays a Protocol") — no code/behavior
    change.
- **Gate:** `make uv-fullCheck` passes (ruff clean, mypy strict clean over
  91 source files, 1267 tests passed including the 21 new `test_block.py`
  and 23 new `test_brake.py` cases). `grep -rn numpy src/math_tools/otg/`
  shows no import (only doc-comment mentions), preserving otg.md's
  compliance requirement 4.
