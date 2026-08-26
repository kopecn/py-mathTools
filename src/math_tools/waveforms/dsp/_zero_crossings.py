"""``ZeroCrossingMixin``: sign-change detection with sub-sample linear
interpolation, rate, and crossing-delimited segmentation for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``ZeroCrossingMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-ZeroX.swift``.

Backing: numpy sign-change indexing (the same ``previous``/``current`` mask
technique ``dsp/_triggers.py``'s ``_sign_change_events`` uses for
``level=0``) plus a sub-sample linear-interpolation refinement step for
``time_seconds`` -- per waveformDsp.md's family-contract table
("numpy sign-change indexing, sub-sample linear interp"). This diverges from
the Swift reference's ``threshold``-parametrized "is this sample close
enough to zero to ignore" scheme: the Python surface has no ``threshold``
argument (not listed in the governing chunk's Design constraints), so a
crossing is a strict sign change of ``values`` against exactly ``0.0``.
"Exact zeros count once" (the chunk's own design constraint) falls out of
using the same *non-strict-on-the-departed-side* comparison
``_triggers.py`` uses (``previous <= 0 & current > 0`` for a rising
crossing, the mirror for falling): a sample sitting exactly on zero is the
"``<= 0``"/"``>= 0``" side of both its neighboring pairs, so it can only
ever complete one crossing, never start a second one.

``WaveformZeroCrossing.direction`` (``waveforms/support.py``) reuses
``WaveformZeroCrossingDirection`` itself (``POSITIVE``/``NEGATIVE``/``BOTH``)
rather than the Swift reference's separate ``WaveformZeroCrossingType``
(``rising``/``falling``) -- a single enum with a ``BOTH`` query filter and a
POSITIVE-or-NEGATIVE-per-event tag, matching this repo's existing convention
of query/result enums doing double duty (e.g. ``WaveformEdgeType`` on
``dsp/_triggers.py``, though that one keeps ``BOTH`` as a query-only value
too -- no completed crossing event is ever literally "both").

``zero_crossings`` is the family's one detector (waveformDsp.md §Numerical
conventions: "detectors (``detect_*``, ``zero_crossings``) ... return empty
lists on no-hit") -- empty/too-short input yields ``[]``, never raises.
``zero_crossing_count``/``zero_crossing_rate`` are built directly on top of
it and inherit that empty-result contract (0 / 0.0 respectively; ``rate``
additionally guards a non-positive duration, mirroring the Swift
reference's ``guard totalDuration > 0 else { return 0.0 }``).
``zero_crossing_count``/``zero_crossing_rate`` both grew an optional
``direction`` parameter (default ``BOTH``) beyond the governing chunk's
literal ``zero_crossing_rate() -> float`` signature, for parity with the
Swift reference's ``zeroCrossingRate(direction:)`` overload and with this
mixin's own ``zero_crossings(direction=...)`` -- a backward-compatible
superset (every call site the chunk names, ``zero_crossing_rate()``, still
works unchanged), not a contract narrowing, so no spec bump is needed.

``segments_between_zero_crossings`` mirrors the Swift reference's
*inclusive*-range segmentation (``values[startIdx...endIdx]``) rather than
``dsp/_time_alignment.py``'s exclusive, non-overlapping
``time_segments``/``time_windows`` split: each interior zero-crossing
sample is deliberately shared by the two segments it borders, so the
segments' length sum slightly *overshoots* the source sample count (one
extra sample per interior boundary) -- exactly the "lengths sum to ~= n"
(not "``== n``") the governing chunk's own TDD step names. Always includes
the leading/trailing partial segments (no ``includePartial`` flag, unlike
the Swift reference -- not in the governing chunk's Design constraints);
an empty waveform raises ``ValueError`` (there is nothing to segment, not a
detector no-hit), while a single-sample or crossing-free waveform each
degrade to the one segment that already covers all the data.

Imports only ``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py`` and
``waveforms/support.py`` -- no sibling mixin imports (waveformDsp.md
§Organization / §Compliance 2).

**Not** ``class ZeroCrossingMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformZeroCrossing, WaveformZeroCrossingDirection


def _zero_crossing_events(
    values: npt.NDArray[Any],
    dt_seconds: float,
    direction: WaveformZeroCrossingDirection,
) -> list[WaveformZeroCrossing]:
    """Sample-pair sign changes of ``values`` against ``0.0``, filtered by
    ``direction`` and refined to a sub-sample ``time_seconds`` via linear
    interpolation between the two samples that bracket each crossing. The
    shared implementation behind every public method on this mixin (see
    module docstring)."""
    if values.shape[0] < 2:
        return []
    previous = values[:-1]
    current = values[1:]
    rising = (previous <= 0.0) & (current > 0.0)
    falling = (previous >= 0.0) & (current < 0.0)
    if direction is WaveformZeroCrossingDirection.POSITIVE:
        mask = rising
    elif direction is WaveformZeroCrossingDirection.NEGATIVE:
        mask = falling
    else:
        mask = rising | falling

    events: list[WaveformZeroCrossing] = []
    for pair_index in np.flatnonzero(mask):
        i = int(pair_index)
        prev_value = float(values[i])
        curr_value = float(values[i + 1])
        fraction = min(1.0, max(0.0, -prev_value / (curr_value - prev_value)))
        interpolated_position = i + fraction
        crossing_direction = (
            WaveformZeroCrossingDirection.POSITIVE
            if rising[i]
            else WaveformZeroCrossingDirection.NEGATIVE
        )
        events.append(
            WaveformZeroCrossing(
                index=i + 1,
                time_seconds=interpolated_position * dt_seconds,
                direction=crossing_direction,
            )
        )
    return events


class ZeroCrossingMixin:
    """Adds zero-crossing detection, rate, and crossing-delimited
    segmentation to a ``WaveformProtocol`` host."""

    def zero_crossings(
        self: WaveformProtocol,
        direction: WaveformZeroCrossingDirection = WaveformZeroCrossingDirection.BOTH,
    ) -> list[WaveformZeroCrossing]:
        """Sign-change crossings of ``values`` against ``0.0``, sub-sample
        interpolated: ``time_seconds`` is the linearly-interpolated crossing
        location between the two bracketing samples, not simply
        ``index * dt``. ``index`` marks the sample landing just after the
        crossing (matching ``dsp/_triggers.py``'s sign-change convention).

        Returns ``[]`` for a waveform with fewer than 2 samples or no
        qualifying crossing -- never raises (detector, per waveformDsp.md
        §Numerical conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _zero_crossing_events(values, dt_seconds, direction)

    def zero_crossing_count(
        self: WaveformProtocol,
        direction: WaveformZeroCrossingDirection = WaveformZeroCrossingDirection.BOTH,
    ) -> int:
        """``len(self.zero_crossings(direction))`` (see module docstring for
        why ``direction`` is accepted directly rather than only via
        ``zero_crossings``)."""
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return len(_zero_crossing_events(values, dt_seconds, direction))

    def zero_crossing_rate(
        self: WaveformProtocol,
        direction: WaveformZeroCrossingDirection = WaveformZeroCrossingDirection.BOTH,
    ) -> float:
        """Crossings per second: ``zero_crossing_count(direction) /
        duration_seconds``. Returns ``0.0`` when the waveform spans zero
        duration (0 or 1 samples) -- never raises or divides by zero."""
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        sample_count = values.shape[0]
        duration_seconds = (sample_count - 1) * dt_seconds if sample_count > 0 else 0.0
        if duration_seconds <= 0.0:
            return 0.0
        count = len(_zero_crossing_events(values, dt_seconds, direction))
        return count / duration_seconds

    def segments_between_zero_crossings(self: WaveformProtocol) -> list[WaveformProtocol]:
        """``self`` split at every (``BOTH``-direction) zero crossing into
        inclusive segments; each segment's ``t0`` is shifted to its start
        sample (see module docstring for why segment lengths sum to
        approximately, not exactly, the source sample count).

        A waveform with no crossings yields a single segment covering all of
        ``self``; a single-sample waveform likewise yields one one-sample
        segment. Segments are always ordered by strictly increasing ``t0``.

        Raises:
            ValueError: If the waveform has no samples.
        """
        values = np.asarray(self.values, dtype=np.float64)
        sample_count = values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "ZeroCrossingMixin.segments_between_zero_crossings requires at least 1 sample"
            )
        dt_seconds = float_seconds(self.dt)
        crossings = _zero_crossing_events(values, dt_seconds, WaveformZeroCrossingDirection.BOTH)
        boundary_indices = [crossing.index for crossing in crossings]
        split_points = [0, *boundary_indices, sample_count - 1]

        segments: list[WaveformProtocol] = []
        for start, stop in zip(split_points, split_points[1:], strict=False):
            if start >= stop:
                continue
            segment = self.values[start : stop + 1]
            segments.append(self._with_t0(segment, self.t0 + self.dt * start))
        if not segments:
            segments.append(self._with_t0(self.values, self.t0))
        return segments


__all__ = ["ZeroCrossingMixin"]
