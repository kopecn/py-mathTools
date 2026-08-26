"""``PeakMixin``: peak/valley detection and prominence ranking for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``PeakMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Peak.swift``;
``Waveform1DPeakTests.swift`` (27 tests -- representative cases ported, not
every case; see the module's own ``detectPeaks(threshold:prominence:
minDistance:edgePeaks:)`` argument surface below).

Backing: ``scipy.signal.find_peaks`` / ``scipy.signal.peak_prominences``.
This diverges from the Swift extension's hand-rolled local-maxima scan
(``threshold``/``prominence``/``minDistance``/``edgePeaks`` arguments, a
custom base-level prominence walk) in favor of the better-tested scipy
equivalent -- the spec explicitly allows this ("parity is judged per
capability, not per Swift overload... scipy semantics win"), and the
governing chunk (23-dsp-peaks.md) pins the resulting Python surface as
``detect_peaks(min_height=None, min_distance=None, min_prominence=None)``,
which maps directly onto ``find_peaks(height=, distance=, prominence=)``.

``detect_peaks``/``detect_valleys`` are detectors (waveformDsp.md §Numerical
conventions): they return ``[]`` on no-hit (empty waveform or no qualifying
extrema) rather than raising. ``find_most_prominent_peaks`` is built
directly on top of ``detect_peaks`` and shares that empty-result contract.

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for the ``WaveformPeak``/
``WaveformPeakWithProminence`` descriptor types) -- no sibling mixin imports
(waveformDsp.md §Organization / §Compliance 2).

**Not** ``class PeakMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s module
docstring / waveformDsp.md §Organization for the full account of why mixins
type ``self`` as ``WaveformProtocol`` on each method instead of nominally
subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks, peak_prominences

from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformPeak, WaveformPeakWithProminence


def _detect_peaks_in_array(
    values: npt.NDArray[Any],
    dt_seconds: float,
    min_height: float | None,
    min_distance: int | None,
    min_prominence: float | None,
) -> list[WaveformPeak]:
    """Core ``find_peaks``-backed local-maxima scan shared by peaks and (negated) valleys."""
    if values.shape[0] == 0:
        return []
    indices, _ = find_peaks(
        values, height=min_height, distance=min_distance, prominence=min_prominence
    )
    return [
        WaveformPeak(index=int(i), time_seconds=float(i) * dt_seconds, value=float(values[i]))
        for i in indices
    ]


class PeakMixin:
    """Adds peak/valley detection and prominence ranking to a ``WaveformProtocol`` host."""

    def detect_peaks(
        self: WaveformProtocol,
        min_height: float | None = None,
        min_distance: int | None = None,
        min_prominence: float | None = None,
    ) -> list[WaveformPeak]:
        """Local maxima via ``scipy.signal.find_peaks``.

        ``min_height``/``min_distance``/``min_prominence`` map directly onto
        ``find_peaks``'s ``height``/``distance``/``prominence`` keyword
        arguments. Returns ``[]`` on an empty waveform or when no sample
        qualifies as a peak -- never raises (this is a detector, per
        waveformDsp.md §Numerical conventions).
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        return _detect_peaks_in_array(values, dt_seconds, min_height, min_distance, min_prominence)

    def detect_valleys(
        self: WaveformProtocol,
        min_height: float | None = None,
        min_distance: int | None = None,
        min_prominence: float | None = None,
    ) -> list[WaveformPeak]:
        """Local minima: ``detect_peaks`` run on the negated signal, negated back.

        ``min_height``/``min_distance``/``min_prominence`` are forwarded
        unchanged to the negated-signal peak search (i.e. ``min_height``
        bounds ``-value`` from below, meaning it bounds ``value`` from
        above). Returns ``[]`` on an empty waveform or no qualifying valley.
        """
        values = np.asarray(self.values, dtype=np.float64)
        dt_seconds = float_seconds(self.dt)
        negated_peaks = _detect_peaks_in_array(
            -values, dt_seconds, min_height, min_distance, min_prominence
        )
        return [
            WaveformPeak(index=p.index, time_seconds=p.time_seconds, value=-p.value)
            for p in negated_peaks
        ]

    def find_most_prominent_peaks(
        self: WaveformProtocol,
        count: int,
        min_distance: int | None = None,
    ) -> list[WaveformPeakWithProminence]:
        """The ``count`` peaks with the highest ``scipy.signal.peak_prominences`` value.

        Candidate peaks come from an unfiltered (no height/prominence
        threshold) ``find_peaks`` pass, restricted only by ``min_distance``;
        results are sorted by prominence descending and truncated to
        ``count``. Returns ``[]`` when ``count <= 0``, the waveform is
        empty, or it has no interior peaks.
        """
        if count <= 0:
            return []
        values = np.asarray(self.values, dtype=np.float64)
        if values.shape[0] == 0:
            return []
        dt_seconds = float_seconds(self.dt)
        indices, _ = find_peaks(values, distance=min_distance)
        if indices.size == 0:
            return []
        prominences, _, _ = peak_prominences(values, indices)
        descending_order = np.argsort(-prominences, kind="stable")
        top_order = descending_order[:count]
        result: list[WaveformPeakWithProminence] = []
        for position in top_order:
            index = int(indices[position])
            peak = WaveformPeak(
                index=index, time_seconds=float(index) * dt_seconds, value=float(values[index])
            )
            result.append(
                WaveformPeakWithProminence(peak=peak, prominence=float(prominences[position]))
            )
        return result


__all__ = ["PeakMixin"]
