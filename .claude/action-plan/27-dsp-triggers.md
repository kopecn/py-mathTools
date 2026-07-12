---
chunk: 27-dsp-triggers
track: D
status: pending
depends_on: [14]
spec: ../specs/waveformDsp.md §Family contracts (TriggerMixin), §Compliance 1–2
last_updated: 2026-07-11
semver: 0.0.1
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

- [ ] Square-wave edge counts exact; pattern indices exact
- [ ] `make uv-fullCheck` passes

## Out of scope

Zero crossings (29 — level 0 lives there); peak detection (23).
