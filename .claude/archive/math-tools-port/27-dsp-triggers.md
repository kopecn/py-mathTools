---
chunk: 27-dsp-triggers
track: D
status: complete
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (TriggerMixin), §Compliance 1–2
last_updated: 2026-07-17
semver: 0.0.2
author: Nicholas Bergantz
---

# 27 — `TriggerMixin`

**Deliverable:** `dsp/_triggers.py` + tests. Swift reference:
`SWIFT_MATH/Waveform1D/Extensions/Waveform1D+TriggerDetection.swift`.

## Files

Create `src/math_tools/waveforms/dsp/_triggers.py`,
`tests/waveforms/dsp/test_triggers.py`. Test-subclass pattern per chunk 18.

## Design constraints

- Methods per spec table: `detect_edge_triggers(level, edge:
  WaveformEdgeType)` (sign-change of `values - level`, RISING/FALLING/BOTH),
  `detect_level_triggers(level, ...)`, `detect_window_triggers(low, high,
  kind: WaveformWindowTriggerType)` (ENTER/EXIT of the band),
  `detect_pattern_triggers(pattern, tolerance)` (sliding-window match),
  generic `detect_triggers(trigger: WaveformTrigger)` dispatching on
  `trigger.kind`, `with_event_markers(events) -> WaveformWithEvents`.
- All detectors return `list[WaveformTriggerEvent]`, empty on no-hit;
  events carry index, `time_seconds`, value, kind.

## TDD steps

1. Failing tests: square wave — rising-edge count == cycle count, falling
   likewise, BOTH is their sum; window ENTER/EXIT pair up on a sine
   crossing a band; pattern trigger finds an embedded motif at the planted
   indices; no-hit → [].
2. Implement. 3. `make uv-fullCheck` green.

## Acceptance criteria

- [x] Square-wave edge counts exact; pattern indices exact
- [x] `make uv-fullCheck` passes

## Out of scope

Zero crossings (29 — level 0 lives there); peak detection (23).

## Resolution notes

- **Design constraints followed as written** (the chunk file already used the
  post-chunk-18 self-typed-``WaveformProtocol`` idiom, not nominal Protocol
  inheritance, so no rewrite was needed there).
- **`detect_level_triggers`** shares `detect_edge_triggers`'s sign-change
  machinery (same private `_sign_change_events` helper), distinguished only
  by the `WaveformTriggerType` tag stamped on the resulting events and its
  default direction (`RISING` vs. `EDGE`'s `BOTH`) — the spec's `EDGE`/
  `LEVEL` split reads as a provenance/intent tag, not two different
  detection algorithms (the Swift reference's own `evaluateLevelTrigger` is
  likewise a plain threshold comparison).
- **Forced contract change, `waveforms/support.py` (semver 0.0.5 → 0.0.6),
  touched even though it is outside this chunk's literal "Files" list** —
  same escape hatch chunks 25/26 used for `dsp/_protocol.py`'s factories:
  1. `WaveformTrigger` gained two optional fields, `edge: WaveformEdgeType
     | None` and `window_kind: WaveformWindowTriggerType | None`, both
     defaulting to `None`. Without them, the generic `detect_triggers`
     dispatcher had no way to read the direction/enter-exit selector a
     `WaveformTrigger` should carry for `EDGE`/`LEVEL`/`WINDOW` kinds — the
     direct `detect_edge_triggers`/`detect_level_triggers`/
     `detect_window_triggers` methods take it as an explicit argument, but
     nothing on the dataclass could express it before this change.
     Backward-compatible: every existing `WaveformTrigger(...)` call site
     (including `tests/waveforms/test_support.py`) omits both new fields and
     is unaffected; dispatch falls back to `BOTH`/`RISING`/`ENTER`
     respectively when unset.
  2. `WaveformWithEvents.waveform` is now typed `WaveformProtocol`
     (`dsp/_protocol.py`), not the concrete `Waveform1D` it held through
     chunk 26. `with_event_markers` is the first mixin method that has to
     embed `self` itself into a returned descriptor; every earlier
     descriptor only ever held *derived* values. Since mixins type `self` as
     `WaveformProtocol` and must never import `Waveform1D` — not even under
     `TYPE_CHECKING`, per `dsp/_protocol.py`'s own docstring — a field typed
     concrete `Waveform1D` was unsatisfiable from `_triggers.py` without
     breaking that rule. Retyping the field to the already-`Waveform1D`-
     satisfying structural protocol resolves this and, as a side effect,
     removes `support.py`'s only import of `waveforms/waveform1d.py` —
     closing off what would otherwise become a real circular import once
     the chunk-30 compose step makes `waveform1d.py` import every mixin
     (mixins already import `support.py`; `support.py` importing
     `waveform1d.py` back would have completed the cycle). Not exercised by
     this chunk's own tests, but `tests/waveforms/test_support.py`'s
     existing `WaveformWithEvents` construction/mutation/slots assertions
     continue to pass unchanged (a `Waveform1D` instance still satisfies the
     field at runtime).
  3. `.claude/specs/waveformDsp.md` §Support descriptor types updated to
     describe both changes; spec semver bumped 0.0.5 → 0.0.6.
- **`detect_triggers` never calls `self.detect_edge_triggers(...)` etc.**
  Each `detect_*` method's shared sign-change/window/pattern logic lives in
  a private module-level function (`_sign_change_events`,
  `_window_trigger_events`, `_pattern_trigger_events`) that both the direct
  method and `detect_triggers`'s dispatch call directly — a same-class
  `self.<sibling method>(...)` call would not type-check under mypy strict
  (`self: WaveformProtocol` does not declare this mixin's own methods),
  mirroring `dsp/_time_alignment.py`'s `_correlating_time_lag` /
  `dsp/_resampling.py`'s `_resample_to_frequency` precedent. Caught by
  running `make uv-typecheck` during implementation, not by inspection.
- **Pattern matching uses elementwise tolerance** (`max(abs(segment -
  pattern)) <= tolerance`), not the Swift reference's normalized-correlation
  `threshold` — deterministic and exact for the "finds the planted motif at
  the planted indices" acceptance criterion, and the spec's "scipy/better-
  tested semantics win" allowance applies equally to a better-specified
  numpy equivalent.
- `make uv-fullCheck` verified clean: ruff (`All checks passed!`), mypy
  strict (`Success: no issues found in 72 source files`), pytest (1087
  passed, including 32 new tests in `tests/waveforms/dsp/test_triggers.py`).
