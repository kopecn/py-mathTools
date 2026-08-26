---
chunk: 40-otg-calculator-target
track: E
status: complete
depends_on: [32, 35, 36, 37, 38, 39]
spec: ../specs/otg.md §Internal fidelity 3
last_updated: 2026-07-21
semver: 0.0.1
author: Nicholas Bergantz
---

# 40 — `TargetCalculator`

**Deliverable:** `calculator_target.py` — faithful port of
`SWIFT_MATH/OTG/CalculatorTarget.swift` (~780 lines): per-DOF Step1/Step2
dispatch plus cross-DOF synchronization (Block/Interval logic, the
discrete-duration path, phase sync).

## Files

- Create: `src/math_tools/otg/calculator_target.py`
- Create: `tests/otg/test_calculator_target.py`

## Design constraints

1. Port `calculate(...)` and `synchronize(...)` branch-for-branch: per-DOF
   control-interface dispatch to the step solver classes (36–39), Block
   construction, blocked-interval resolution, `Synchronization` mode
   handling (TIME / TIME_IF_NECESSARY / PHASE / NONE), minimum-duration and
   discrete-duration paths.
2. Error paths return the spec'd `Result` codes
   (`ERROR_EXECUTION_TIME_CALCULATION`, `ERROR_SYNCHRONIZATION_CALCULATION`)
   — no exceptions.
3. Fills a `Trajectory` (chunk 35); consumes `InputParameter` (32).

## TDD steps

1. Failing tests: (a) 1-DOF position case reproduces chunk 38's analytic
   duration through the full calculate path; (b) 3-DOF TIME sync — all DOFs
   report identical trajectory duration equal to the slowest DOF's optimal
   (compose from chunk 38's cases with different distances); (c) NONE sync —
   per-DOF durations equal their independent optima; (d) an `enabled=False`
   DOF stays at its current state; (e) an unsolvable synchronization input
   returns `ERROR_SYNCHRONIZATION_CALCULATION` rather than raising.
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] TIME/NONE sync duration semantics pinned; disabled-DOF pinned
- [x] No `raise` in the calculate path (grep for `raise` → only in
      structural-misuse guards, if any)
- [x] `make uv-fullCheck` passes

## Out of scope

The `Otg` driver loop (41); waypoints beyond what the Swift implements.

## Resolution notes

- **Deliverable**: `src/math_tools/otg/calculator_target.py` (`TargetCalculator`,
  private per otg.md's module layout — `__all__ = []`) plus
  `tests/otg/test_calculator_target.py` (6 tests covering TDD cases a-e; (e)
  is covered by two tests, see below). Ported `calculate()`, `synchronize()`
  (as `_synchronize`, since Swift's `private func`), and
  `isInputCollinear()` (as `_is_input_collinear`) branch-for-branch from
  `CalculatorTarget.swift`.
- **Alias-mutation hazard, identified and fixed at 8 sites**: unlike chunks
  36-39 (where the hazard is *within* a single `get_profile()` call),
  `TargetCalculator` holds `self._blocks` as *instance* state that persists
  across `calculate()` calls, so every Swift `trajectory.profiles[0][dof] =
  blocks[dof].pMin` (or `.a!.profile!` / `.b!.profile!`) — a value copy in
  Swift, a live alias in Python otherwise — was routed through
  `copy.deepcopy()`: `_synchronize`'s own save point (3 branches), the "None
  Synchronization" loop, the `duration == 0.0` copy-all-profiles branch, the
  1-DOF shortcut, and the "Time Synchronization" loop's 3 early-exit
  branches. Also caught one array-level (not whole-`Profile`) case: Swift's
  `p.t = pLimiting.t` (phase sync) copies a Swift array *value*; ported as
  `p.t = list(p_limiting.t)`, not a bare `p.t = p_limiting.t` (which would
  alias the two profiles' timing arrays). Full reasoning, including why the
  *other* `trajectory.profiles[0][dof] = p` write-backs need no copy
  (`p` already *is* that list slot's object — Python alias mutation, not a
  fresh Swift struct copy), is in the module docstring.
- **Verified analytically that `TargetCalculator._synchronize`'s search is
  provably complete for any Block state a real Step1 call produces** (a
  DOF's own `t_min`, and any `Interval.right`, is never self-blocking at its
  own boundary — `Block.is_blocked`/`Interval.is_blocked` both use strict
  `<`/open intervals). This made TDD case (e) ("an unsolvable
  synchronization input") impractical to reach through a *naturally*
  Step1-derived `InputParameter` without an adversarial multi-DOF interval
  coincidence, so it's covered by two targeted tests instead: one calls
  `_synchronize` directly with a hand-built `Block` pair proven by
  construction to block every finite candidate (an `Interval(1.0, math.inf)`
  combined with a second DOF's `t_min` floor that blocks the first DOF's
  only escape point at `t=1.0`); the other forces `_synchronize` to return
  `False` via `unittest.mock.patch.object` and confirms `calculate()`
  propagates it to `Result.ERROR_SYNCHRONIZATION_CALCULATION` without
  raising. Documented in the test file's own docstring.
- **Dropped 4 Swift `print("[DEBUG] ...")` statements** (in `synchronize()`'s
  failure path and `calculate()`'s two error branches) — unconditional
  developer tracing, not part of the algorithm, same category as chunk 39's
  dropped `debugTimeVel` print block. Every branch/decision they straddled
  is preserved exactly.
- **No new `_ieee754_div`/`_ieee754_sqrt` sites**: `_is_input_collinear`'s
  divisions (`pd[dof] / scale`, etc.) all divide by `scale_vector[scale_dof]`,
  which is only selected after `abs(...) > _EPS` was already checked —
  provably nonzero, so plain `/` is correct per otg.md §Internal fidelity
  requirement 4 (`_ieee754_div` is for a *failing test*-demonstrated
  zero-denominator, not a blanket wrap). One division
  (`controlLimiting * currentScale / scaleLimiting`) has no such proof and
  is flagged in the module docstring for a future chunk to revisit if a
  test ever reaches it; none of this chunk's own tests do (no `Synchronization.PHASE`
  case was required by the chunk's TDD steps, so this path is implemented
  per the design constraints but not itself under test here).
- **Fidelity oddity ported verbatim**: the trivial "already at target, zero
  motion" branch sets `p.a`/`p.v`/`p.p` to length-7 lists (`[value] * 7`),
  matching Swift's `Array(repeating: ..., count: 7)` exactly even though
  `Profile`'s normal invariant is 8-element `a`/`v`/`p` arrays — verified
  harmless (every element is identical, and `Trajectory.at_time` always
  indexes via `[-1]`, never a hardcoded `[7]`, so the shorter list is never
  a break) but preserved rather than "corrected" to 8, per the port's
  mechanical-translation mandate.
- **Known, accepted, untested Python/Swift divergence documented, not
  fixed**: an early error `return` (`ERROR_ZERO_LIMITS`,
  `ERROR_EXECUTION_TIME_CALCULATION`) can leave `trajectory.profiles[0][dof]`
  partially mutated in Python (reference-type alias), where Swift's local
  struct copy would leave it untouched. Nothing in otg.md's oracle/
  classification/numeric test strategy inspects trajectory state after an
  error `Result`, so this is unobservable through the documented contract;
  not patched with defensive copying (would violate the alias-mutation
  fix's "not blanket everywhere" scoping). Recorded in the module docstring.
- Gate: `make uv-fullCheck` — ruff clean, mypy strict clean (109 source
  files), 1324/1324 tests pass (full suite ran in ~12s locally, well under
  the 60-70s ceiling the chunk brief warned about).
