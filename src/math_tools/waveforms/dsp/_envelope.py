"""``EnvelopeMixin``: amplitude envelope / instantaneous amplitude for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``EnvelopeMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Envelope.swift``.

Backing: ``scipy.signal.hilbert`` (analytic-signal amplitude),
``scipy.signal.find_peaks`` + ``np.interp`` (peak/valley envelope
interpolation), per waveformDsp.md's family-contract table. This diverges
from the Swift extension's hand-rolled approximations (a fixed-window
"quadrature filter" standing in for the Hilbert transform, and a
local-window ``allSatisfy`` extrema search) in favor of the better-tested
scipy/numpy equivalents -- the spec explicitly allows this ("parity is
judged per capability, not per Swift overload... scipy semantics win").

``amplitude_envelope``/``upper_lower_envelopes``/``instantaneous_amplitude``
all raise ``ValueError`` (naming the requirement) on an empty input
waveform (waveformDsp.md §Numerical conventions -- these are not in the
``detect_*``/``zero_crossings`` detector family that gets the
empty-result exemption).

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py`` and
``waveforms/support.py`` (for the ``WaveformInstantaneousMethod`` enum
argument) -- no sibling mixin imports (waveformDsp.md §Organization /
§Compliance 2; ``support.py`` is outside ``dsp/`` and is the same import
``_correlation.py`` (chunk 19) already makes for ``WaveformTimeLag``).

**Not** ``class EnvelopeMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks, hilbert

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInstantaneousMethod


def _hilbert_amplitude(values: npt.NDArray[Any]) -> npt.NDArray[np.float64]:
    """Analytic-signal magnitude of ``values`` (``scipy.signal.hilbert``-backed)."""
    analytic = hilbert(np.asarray(values, dtype=np.float64))
    result: npt.NDArray[np.float64] = np.abs(analytic)
    return result


def _with_boundary_indices(
    indices: npt.NDArray[Any], sample_count: int
) -> npt.NDArray[np.intp]:
    """``indices`` plus the first/last sample index, sorted ascending with duplicates removed.

    Guarantees an envelope interpolation always has at least the two
    boundary samples as anchors, even when a signal has no interior local
    extrema (e.g. a monotonic ramp).
    """
    combined = np.concatenate(([0], indices, [sample_count - 1]))
    unique_sorted: npt.NDArray[np.intp] = np.unique(combined).astype(np.intp)
    return unique_sorted


def _peak_envelope(values: npt.NDArray[Any]) -> npt.NDArray[np.float64]:
    """Envelope through the peaks of ``abs(values)`` (``find_peaks`` + ``np.interp``)."""
    abs_values = np.abs(np.asarray(values, dtype=np.float64))
    sample_count = abs_values.shape[0]
    peak_indices, _ = find_peaks(abs_values)
    anchor_indices = _with_boundary_indices(peak_indices, sample_count)
    sample_positions = np.arange(sample_count, dtype=np.float64)
    result: npt.NDArray[np.float64] = np.interp(
        sample_positions, anchor_indices, abs_values[anchor_indices]
    )
    return result


def _windowed_rms(values: npt.NDArray[Any], window_size: int) -> npt.NDArray[np.float64]:
    """Centered moving-window RMS of ``values`` (edge-padded so the result matches length)."""
    values_f64 = np.asarray(values, dtype=np.float64)
    sample_count = values_f64.shape[0]
    half_window = window_size // 2
    padded = np.pad(values_f64 * values_f64, (half_window, half_window), mode="edge")
    kernel = np.ones(window_size, dtype=np.float64) / window_size
    convolved = np.convolve(padded, kernel, mode="valid")
    result: npt.NDArray[np.float64] = np.sqrt(convolved[:sample_count])
    return result


class EnvelopeMixin:
    """Adds amplitude-envelope / instantaneous-amplitude methods to a ``WaveformProtocol`` host."""

    def amplitude_envelope(self: WaveformProtocol) -> WaveformProtocol:
        """Instantaneous amplitude via the analytic-signal magnitude (``scipy.signal.hilbert``).

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("EnvelopeMixin.amplitude_envelope requires at least 1 sample, got 0")
        return self._with_values(_hilbert_amplitude(self.values))

    def upper_lower_envelopes(self: WaveformProtocol) -> tuple[WaveformProtocol, WaveformProtocol]:
        """Upper/lower envelopes via local-maxima/-minima interpolation.

        Local maxima/minima are found with ``scipy.signal.find_peaks`` (on
        ``values`` for the upper envelope, on ``-values`` for the lower);
        the envelope between them is linear (``np.interp``). The first and
        last samples are always included as anchor points -- even when they
        are not local extrema -- so a signal with no interior extrema (e.g.
        a monotonic ramp) still yields an envelope spanning the full
        waveform instead of a degenerate one.

        Raises:
            ValueError: If the waveform has no samples.
        """
        values = np.asarray(self.values, dtype=np.float64)
        sample_count = values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "EnvelopeMixin.upper_lower_envelopes requires at least 1 sample, got 0"
            )
        peak_indices, _ = find_peaks(values)
        valley_indices, _ = find_peaks(-values)
        upper_anchors = _with_boundary_indices(peak_indices, sample_count)
        lower_anchors = _with_boundary_indices(valley_indices, sample_count)
        sample_positions = np.arange(sample_count, dtype=np.float64)
        upper = np.interp(sample_positions, upper_anchors, values[upper_anchors])
        lower = np.interp(sample_positions, lower_anchors, values[lower_anchors])
        return self._with_values(upper), self._with_values(lower)

    def instantaneous_amplitude(
        self: WaveformProtocol,
        method: WaveformInstantaneousMethod = WaveformInstantaneousMethod.HILBERT,
        window_size: int = 5,
    ) -> WaveformProtocol:
        """Instantaneous amplitude estimate, per ``method``.

        - ``HILBERT``: analytic-signal magnitude (same as ``amplitude_envelope``).
        - ``RMS``: centered moving-window RMS (``window_size`` samples, edge-padded).
        - ``PEAK``: envelope through the peaks of ``abs(values)`` (``find_peaks`` +
          ``np.interp``, same construction as ``upper_lower_envelopes``' upper side
          applied to the rectified signal).

        Raises:
            ValueError: If the waveform has no samples, or (``RMS``) ``window_size < 1``.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "EnvelopeMixin.instantaneous_amplitude requires at least 1 sample, got 0"
            )
        if method is WaveformInstantaneousMethod.HILBERT:
            return self._with_values(_hilbert_amplitude(self.values))
        if method is WaveformInstantaneousMethod.RMS:
            if window_size < 1:
                raise ValueError(
                    "EnvelopeMixin.instantaneous_amplitude: window_size must be >= 1, "
                    f"got {window_size}"
                )
            return self._with_values(_windowed_rms(self.values, window_size))
        if method is WaveformInstantaneousMethod.PEAK:
            return self._with_values(_peak_envelope(self.values))
        raise ValueError(f"EnvelopeMixin.instantaneous_amplitude: unsupported method {method!r}")


__all__ = ["EnvelopeMixin"]
