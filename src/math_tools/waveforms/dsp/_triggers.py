"""``TriggerMixin``: edge/level/window/pattern trigger detection and event
marking for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``TriggerMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-TriggerDetection.swift``.

Backing: numpy comparisons + sign-change indexing, per waveformDsp.md's
family-contract table -- not the Swift extension's hand-rolled state
machine, which the extension's own comments admit is "simplified" (e.g.
``evaluateEdgeTrigger``'s ``.both`` case literally returns ``true``
unconditionally, "would need state tracking"). This module implements the
chunk's own design constraint directly instead: edge/level triggers are
genuine sign changes of ``values - level`` (``RISING``: crosses from
``<= 0`` to ``> 0``; ``FALLING``: the reverse; ``BOTH``: either), window
triggers are enter/exit transitions of the ``[low, high]`` band, and
pattern triggers are a sliding-window elementwise-tolerance match
(``max(abs(segment - pattern)) <= tolerance``) -- deterministic and exact,
unlike the Swift extension's normalized-correlation ``threshold`` (the spec
explicitly allows this: "parity is judged per capability, not per Swift
overload... scipy semantics win" applies equally to the better-tested/
better-specified numpy equivalent here).

All four ``detect_*`` methods are detectors (waveformDsp.md §Numerical
conventions): they return ``[]`` on no-hit (empty/too-short waveform, an
out-of-range band, a pattern longer than the waveform, ...) rather than
raising -- there is deliberately no separate "invalid input" guard clause
for these, since every out-of-range input degrades naturally to zero
qualifying samples. ``detect_triggers`` (the generic ``WaveformTrigger``-
driven dispatcher) is the one exception: it raises ``ValueError`` when the
fields its ``trigger.kind`` requires are missing (``level`` for ``EDGE``/
``LEVEL``, ``lower``/``upper`` for ``WINDOW``, ``pattern``/``tolerance`` for
``PATTERN``) -- a malformed ``WaveformTrigger`` is a programmer error, not
"no samples matched".

``detect_level_triggers`` shares ``detect_edge_triggers``'s sign-change
machinery (same private ``_sign_change_events`` helper, parametrized by the
``WaveformTriggerType`` tag stamped onto the resulting events) rather than
introducing a separate "level" concept -- the spec's ``WaveformTriggerType``
distinguishes ``EDGE``/``LEVEL`` as a provenance tag, not a different
detection algorithm, and the Swift reference's own ``evaluateLevelTrigger``
is likewise just a threshold comparison. It defaults to ``RISING`` (crossing
up into "at/above `level`") where ``detect_edge_triggers`` defaults to
``BOTH``, matching the "a level trigger fires once you're at/above this
level" reading distinct from "an edge trigger fires on either transition".

``detect_triggers``'s dispatch for ``EDGE``/``LEVEL``/``WINDOW`` needs a
direction/enter-exit selector that ``WaveformTrigger`` did not carry before
this chunk; see ``waveforms/support.py``'s module docstring ("Forced
contract change (chunk 27)") for the two optional fields
(``edge``/``window_kind``) added to carry it, defaulting to ``BOTH``/
``RISING``/``ENTER`` respectively when the caller leaves them unset (i.e.
``detect_triggers`` and the direct methods agree on defaults).

**``detect_triggers`` calls the same private module-level helpers the direct
``detect_*`` methods call, never ``self.detect_edge_triggers(...)`` etc.**
Every method here types ``self`` as ``WaveformProtocol`` (see below), which
only declares the *host*'s surface (``values``/``dt``/``t0``/factories) --
not this mixin's own sibling methods, so a same-class ``self.detect_edge_
triggers(...)`` call would not type-check under mypy strict (no such
attribute on ``WaveformProtocol``). This mirrors ``dsp/_time_alignment.py``'s
``_correlating_time_lag`` and ``dsp/_resampling.py``'s
``_resample_to_frequency``: shared logic between two public methods of the
same mixin lives in a private module-level function that both call, not one
public method calling another via ``self``.

``with_event_markers`` is the first mixin method that embeds ``self``
itself into a returned descriptor; see ``waveforms/support.py``'s module
docstring for why ``WaveformWithEvents.waveform`` is typed
``WaveformProtocol`` rather than concrete ``Waveform1D`` as a result.

Imports only ``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py`` and
``waveforms/support.py`` -- no sibling mixin imports (waveformDsp.md
§Organization / §Compliance 2).

**Not** ``class TriggerMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import (
    WaveformEdgeType,
    WaveformEventMarker,
    WaveformTrigger,
    WaveformTriggerEvent,
    WaveformTriggerType,
    WaveformWindowTriggerType,
    WaveformWithEvents,
)


def _events_from_indices(
    indices: npt.NDArray[Any],
    values: npt.NDArray[Any],
    dt: PrecisionTimeInterval,
    dt_seconds: float,
    kind: WaveformTriggerType,
    minimum_interval: PrecisionTimeInterval | None,
) -> list[WaveformTriggerEvent]:
    """Build ``WaveformTriggerEvent``s from candidate sample ``indices``, dropping any
    that fall within ``minimum_interval`` of the previously emitted event (dedup, per
    the Swift reference's ``lastTriggerIndex``/``minInterval`` bookkeeping)."""
    events: list[WaveformTriggerEvent] = []
    last_index: int | None = None
    for raw_index in indices:
        index = int(raw_index)
        if minimum_interval is not None and last_index is not None:
            elapsed = dt * (index - last_index)
            if elapsed < minimum_interval:
                continue
        events.append(
            WaveformTriggerEvent(
                index=index,
                time_seconds=index * dt_seconds,
                value=float(values[index]),
                kind=kind,
            )
        )
        last_index = index
    return events


def _sign_change_events(
    values: npt.NDArray[Any],
    dt: PrecisionTimeInterval,
    dt_seconds: float,
    level: float,
    edge: WaveformEdgeType,
    kind: WaveformTriggerType,
    minimum_interval: PrecisionTimeInterval | None,
) -> list[WaveformTriggerEvent]:
    """Sample indices where ``values - level`` changes sign, filtered by ``edge``
    direction -- the shared implementation behind ``detect_edge_triggers`` and
    ``detect_level_triggers`` (see module docstring)."""
    if values.shape[0] < 2:
        return []
    shifted = values - level
    previous = shifted[:-1]
    current = shifted[1:]
    rising = (previous <= 0.0) & (current > 0.0)
    falling = (previous >= 0.0) & (current < 0.0)
    if edge is WaveformEdgeType.RISING:
        mask = rising
    elif edge is WaveformEdgeType.FALLING:
        mask = falling
    else:
        mask = rising | falling
    # +1: the mask is computed over the (n-1)-length pair array `previous`/`current`,
    # so a `True` at position i marks the crossing landing on original index i+1.
    candidate_indices = np.flatnonzero(mask) + 1
    return _events_from_indices(candidate_indices, values, dt, dt_seconds, kind, minimum_interval)


def _window_trigger_events(
    values: npt.NDArray[Any],
    dt: PrecisionTimeInterval,
    dt_seconds: float,
    low: float,
    high: float,
    kind: WaveformWindowTriggerType,
    minimum_interval: PrecisionTimeInterval | None,
) -> list[WaveformTriggerEvent]:
    """Sample indices where membership in the inclusive ``[low, high]`` band
    transitions -- ``ENTER``: outside -> inside, ``EXIT``: inside -> outside. The
    shared implementation behind ``detect_window_triggers`` (see module docstring)."""
    if values.shape[0] < 2:
        return []
    inside = (values >= low) & (values <= high)
    previous_inside = inside[:-1]
    current_inside = inside[1:]
    if kind is WaveformWindowTriggerType.ENTER:
        mask = (~previous_inside) & current_inside
    else:
        mask = previous_inside & (~current_inside)
    candidate_indices = np.flatnonzero(mask) + 1
    return _events_from_indices(
        candidate_indices, values, dt, dt_seconds, WaveformTriggerType.WINDOW, minimum_interval
    )


def _pattern_trigger_events(
    values: npt.NDArray[Any],
    dt: PrecisionTimeInterval,
    dt_seconds: float,
    pattern: Sequence[float],
    tolerance: float,
    minimum_interval: PrecisionTimeInterval | None,
) -> list[WaveformTriggerEvent]:
    """Start indices of sliding windows matching ``pattern`` within ``tolerance``
    (``max(abs(segment - pattern)) <= tolerance``). The shared implementation behind
    ``detect_pattern_triggers`` (see module docstring)."""
    pattern_arr = np.asarray(pattern, dtype=np.float64)
    pattern_length = pattern_arr.shape[0]
    if pattern_length == 0 or pattern_length > values.shape[0]:
        return []
    windows = np.lib.stride_tricks.sliding_window_view(values, pattern_length)
    max_abs_diff = np.max(np.abs(windows - pattern_arr), axis=1)
    candidate_indices = np.flatnonzero(max_abs_diff <= tolerance)
    return _events_from_indices(
        candidate_indices, values, dt, dt_seconds, WaveformTriggerType.PATTERN, minimum_interval
    )


class TriggerMixin:
    """Adds edge/level/window/pattern trigger detection and event marking to a
    ``WaveformProtocol`` host."""

    def detect_edge_triggers(
        self: WaveformProtocol,
        level: float,
        edge: WaveformEdgeType = WaveformEdgeType.BOTH,
        minimum_interval: PrecisionTimeInterval | None = None,
    ) -> list[WaveformTriggerEvent]:
        """Sign-change crossings of ``values - level``: ``RISING`` fires where the
        previous sample was ``<= level`` and the current sample is ``> level``,
        ``FALLING`` the reverse, ``BOTH`` (default) either. Event ``index``/
        ``time_seconds`` mark the sample landing on the crossing.

        Returns ``[]`` for a waveform with fewer than 2 samples or no qualifying
        crossing -- never raises (detector, per waveformDsp.md §Numerical
        conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _sign_change_events(
            values, self.dt, dt_seconds, level, edge, WaveformTriggerType.EDGE, minimum_interval
        )

    def detect_level_triggers(
        self: WaveformProtocol,
        level: float,
        edge: WaveformEdgeType = WaveformEdgeType.RISING,
        minimum_interval: PrecisionTimeInterval | None = None,
    ) -> list[WaveformTriggerEvent]:
        """Sign-change crossings of ``values - level``, same mechanics as
        ``detect_edge_triggers`` (default ``RISING``: fires on crossing up to
        at/above ``level``) but stamped with ``WaveformTriggerType.LEVEL``.

        Returns ``[]`` for a waveform with fewer than 2 samples or no qualifying
        crossing -- never raises (detector, per waveformDsp.md §Numerical
        conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _sign_change_events(
            values, self.dt, dt_seconds, level, edge, WaveformTriggerType.LEVEL, minimum_interval
        )

    def detect_window_triggers(
        self: WaveformProtocol,
        low: float,
        high: float,
        kind: WaveformWindowTriggerType,
        minimum_interval: PrecisionTimeInterval | None = None,
    ) -> list[WaveformTriggerEvent]:
        """Enter/exit transitions of the inclusive ``[low, high]`` band: ``ENTER``
        fires where the previous sample was outside the band and the current
        sample is inside it, ``EXIT`` the reverse.

        Returns ``[]`` for a waveform with fewer than 2 samples, ``low > high``,
        or no qualifying transition -- never raises (detector, per
        waveformDsp.md §Numerical conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _window_trigger_events(
            values, self.dt, dt_seconds, low, high, kind, minimum_interval
        )

    def detect_pattern_triggers(
        self: WaveformProtocol,
        pattern: Sequence[float],
        tolerance: float,
        minimum_interval: PrecisionTimeInterval | None = None,
    ) -> list[WaveformTriggerEvent]:
        """Sliding-window elementwise match: a window starting at sample ``i``
        qualifies when ``max(abs(values[i:i+len(pattern)] - pattern)) <= tolerance``.
        Event ``index``/``time_seconds`` mark the start of the matching window.

        Returns ``[]`` when ``pattern`` is empty, longer than the waveform, or no
        window qualifies -- never raises (detector, per waveformDsp.md §Numerical
        conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _pattern_trigger_events(
            values, self.dt, dt_seconds, pattern, tolerance, minimum_interval
        )

    def detect_triggers(
        self: WaveformProtocol, trigger: WaveformTrigger
    ) -> list[WaveformTriggerEvent]:
        """Dispatch on ``trigger.kind`` to the matching sign-change/window/pattern
        computation above, reading its arguments from ``trigger``'s fields
        (``level``, ``lower``/``upper``, ``pattern``/``tolerance``,
        ``minimum_interval``, and the ``edge``/``window_kind`` direction
        selectors -- see module docstring).

        Raises:
            ValueError: If ``trigger.kind`` is missing the field(s) its detection
                requires, or is not a recognized ``WaveformTriggerType`` member.
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)

        if trigger.kind is WaveformTriggerType.EDGE:
            if trigger.level is None:
                raise ValueError("TriggerMixin.detect_triggers: EDGE trigger requires 'level'")
            edge = trigger.edge if trigger.edge is not None else WaveformEdgeType.BOTH
            return _sign_change_events(
                values,
                self.dt,
                dt_seconds,
                trigger.level,
                edge,
                WaveformTriggerType.EDGE,
                trigger.minimum_interval,
            )
        if trigger.kind is WaveformTriggerType.LEVEL:
            if trigger.level is None:
                raise ValueError("TriggerMixin.detect_triggers: LEVEL trigger requires 'level'")
            edge = trigger.edge if trigger.edge is not None else WaveformEdgeType.RISING
            return _sign_change_events(
                values,
                self.dt,
                dt_seconds,
                trigger.level,
                edge,
                WaveformTriggerType.LEVEL,
                trigger.minimum_interval,
            )
        if trigger.kind is WaveformTriggerType.WINDOW:
            if trigger.lower is None or trigger.upper is None:
                raise ValueError(
                    "TriggerMixin.detect_triggers: WINDOW trigger requires 'lower' and 'upper'"
                )
            window_kind = (
                trigger.window_kind
                if trigger.window_kind is not None
                else WaveformWindowTriggerType.ENTER
            )
            return _window_trigger_events(
                values,
                self.dt,
                dt_seconds,
                trigger.lower,
                trigger.upper,
                window_kind,
                trigger.minimum_interval,
            )
        if trigger.kind is WaveformTriggerType.PATTERN:
            if trigger.pattern is None or trigger.tolerance is None:
                raise ValueError(
                    "TriggerMixin.detect_triggers: PATTERN trigger requires 'pattern' "
                    "and 'tolerance'"
                )
            return _pattern_trigger_events(
                values,
                self.dt,
                dt_seconds,
                trigger.pattern,
                trigger.tolerance,
                trigger.minimum_interval,
            )
        # pragma: no cover -- WaveformTriggerType is exhaustive above
        raise ValueError(f"TriggerMixin.detect_triggers: unsupported kind {trigger.kind!r}")

    def with_event_markers(
        self: WaveformProtocol, events: Sequence[WaveformTriggerEvent]
    ) -> WaveformWithEvents:
        """Pair ``self`` with a marker per ``events`` entry (``label`` is the
        event's ``kind`` value, e.g. ``"edge"``).

        ``events`` is typically the result of one of this mixin's ``detect_*``
        methods, but any ``WaveformTriggerEvent`` sequence works. An empty
        ``events`` yields ``WaveformWithEvents`` with no markers (not an error).
        """
        markers = tuple(
            WaveformEventMarker(index=event.index, label=event.kind.value) for event in events
        )
        return WaveformWithEvents(waveform=self, events=markers)


__all__ = ["TriggerMixin"]
