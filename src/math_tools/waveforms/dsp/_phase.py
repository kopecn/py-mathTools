"""``PhaseMixin``: instantaneous phase/frequency and phase-synchrony analysis.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``PhaseMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-PhaseAnalysis.swift``.

Backing: ``scipy.signal.hilbert`` (analytic-signal phase), ``np.unwrap``,
per waveformDsp.md's family-contract table. This diverges from the Swift
extension's hand-rolled "quadrature filter" approximation of the Hilbert
transform (a fixed-window finite-difference stand-in, see
``Waveform1D-PhaseAnalysis.swift``'s private ``quadratureComponent``) in
favor of the better-tested ``scipy.signal.hilbert`` -- the spec explicitly
allows this ("parity is judged per capability, not per Swift overload...
scipy semantics win").

``instantaneous_phase``/``unwrap_phase``/``instantaneous_frequency`` raise
``ValueError`` (naming the requirement) on an empty/too-short input waveform
(waveformDsp.md §Numerical conventions -- none of these are in the
``detect_*``/``zero_crossings`` detector family that gets the empty-result
exemption). ``phase_difference``/``phase_coherence``/
``phase_synchronization_index`` are binary: they raise
``WaveformCompatibilityError`` when ``other.dt`` differs from ``self.dt`` or
the two waveforms have a different sample count (``errors.py``'s
``WaveformCompatibilityError`` docstring: "dt/shape mismatch").

``group_delay`` is a ``staticmethod``: like the Swift reference's
``groupDelay(frequencies:phases:)``, it operates purely on caller-supplied
frequency/phase arrays (e.g. from ``SpectralMixin.fft``'s
``WaveformSpectrum``) and never touches ``self.values``/``self.dt`` -- it
does not need ``self: WaveformProtocol`` typing at all.

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for ``WaveformInstantaneousFrequency``) -- no
sibling mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class PhaseMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import hilbert

from math_tools.errors import WaveformCompatibilityError
from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInstantaneousFrequency


def _analytic_phase(values: npt.NDArray[Any]) -> npt.NDArray[np.float64]:
    """Wrapped instantaneous phase (``[-pi, pi]``) of ``values`` via the analytic signal."""
    analytic = hilbert(np.asarray(values, dtype=np.float64))
    result: npt.NDArray[np.float64] = np.angle(analytic)
    return result


def _wrap_to_pi(radians: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Wrap ``radians`` into ``(-pi, pi]`` (via the unit complex exponential)."""
    result: npt.NDArray[np.float64] = np.angle(np.exp(1j * radians))
    return result


def _plv(phase_difference_radians: npt.NDArray[np.float64]) -> float:
    """Phase-locking value: magnitude of the mean unit vector at ``phase_difference_radians``."""
    return float(np.abs(np.mean(np.exp(1j * phase_difference_radians))))


def _require_compatible(waveform: WaveformProtocol, other: WaveformProtocol, op_name: str) -> None:
    """Raise ``WaveformCompatibilityError`` unless ``other`` shares ``waveform``'s ``dt``
    and sample count (errors.py's ``WaveformCompatibilityError``: "dt/shape mismatch")."""
    if waveform.dt != other.dt:
        raise WaveformCompatibilityError(
            f"PhaseMixin.{op_name}: dt mismatch ({waveform.dt!r} vs {other.dt!r})"
        )
    self_count = waveform.values.shape[0]
    other_count = other.values.shape[0]
    if self_count != other_count:
        raise WaveformCompatibilityError(
            f"PhaseMixin.{op_name}: sample-count mismatch ({self_count} vs {other_count})"
        )


class PhaseMixin:
    """Adds instantaneous phase/frequency and phase-synchrony methods to a
    ``WaveformProtocol`` host."""

    def instantaneous_phase(self: WaveformProtocol, unwrapped: bool = True) -> WaveformProtocol:
        """Instantaneous phase via the analytic-signal angle (``scipy.signal.hilbert``).

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("PhaseMixin.instantaneous_phase requires at least 1 sample, got 0")
        phase = _analytic_phase(self.values)
        if unwrapped:
            phase = np.unwrap(phase)
        return self._with_values(phase)

    def unwrap_phase(self: WaveformProtocol, threshold: float = np.pi) -> WaveformProtocol:
        """``np.unwrap`` applied to ``self.values`` as already-computed phase data.

        ``threshold`` is ``np.unwrap``'s ``discont`` (a jump larger than this
        many radians between consecutive samples is treated as a wraparound
        and corrected); it defaults to pi, matching ``np.unwrap``'s own
        default.

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("PhaseMixin.unwrap_phase requires at least 1 sample, got 0")
        unwrapped = np.unwrap(np.asarray(self.values, dtype=np.float64), discont=threshold)
        return self._with_values(unwrapped)

    def instantaneous_frequency(self: WaveformProtocol) -> WaveformInstantaneousFrequency:
        """Instantaneous frequency (Hz): the unwrapped analytic-signal phase's time
        gradient, scaled by ``1 / (2 * pi)`` (``np.gradient``, scaled by ``dt`` seconds).

        Raises:
            ValueError: If the waveform has fewer than 2 samples (``np.gradient``'s
                minimum for a first-order estimate).
        """
        sample_count = self.values.shape[0]
        if sample_count < 2:
            raise ValueError(
                f"PhaseMixin.instantaneous_frequency requires at least 2 samples, "
                f"got {sample_count}"
            )
        dt_seconds = float_seconds(self.dt)
        phase = np.unwrap(_analytic_phase(self.values))
        frequencies_hz = np.gradient(phase, dt_seconds) / (2.0 * np.pi)
        times_seconds = np.arange(sample_count, dtype=np.float64) * dt_seconds
        return WaveformInstantaneousFrequency(
            frequencies_hz=frequencies_hz, times_seconds=times_seconds
        )

    def phase_difference(self: WaveformProtocol, other: WaveformProtocol) -> WaveformProtocol:
        """Wrapped phase difference (``self``'s analytic phase minus ``other``'s),
        wrapped into ``(-pi, pi]``.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``,
                or the sample counts differ.
            ValueError: If either waveform has no samples.
        """
        _require_compatible(self, other, "phase_difference")
        if self.values.shape[0] == 0:
            raise ValueError("PhaseMixin.phase_difference requires at least 1 sample, got 0")
        phase_self = _analytic_phase(self.values)
        phase_other = _analytic_phase(other.values)
        return self._with_values(_wrap_to_pi(phase_self - phase_other))

    def phase_coherence(
        self: WaveformProtocol, other: WaveformProtocol, window: int | None = None
    ) -> WaveformProtocol:
        """Windowed phase-locking value between ``self`` and ``other`` (non-overlapping
        windows of ``window`` samples; one coherence value per window).

        ``window`` defaults to ``min(256, max(1, sample_count // 4))`` (mirrors the
        Swift reference's default). The result's ``dt``/``t0`` are inherited unchanged
        from ``self`` (the ``WaveformProtocol`` surface has no other way to construct
        a result -- see ``_with_values``'s docstring; ``CorrelationMixin.auto_correlation``
        establishes the same precedent of a differently-spaced result reusing the
        source's ``dt`` as inherited metadata).

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``,
                or the sample counts differ.
            ValueError: If the waveform has fewer than 2 samples, or ``window``
                is not in ``[1, sample_count]``.
        """
        _require_compatible(self, other, "phase_coherence")
        sample_count = self.values.shape[0]
        if sample_count < 2:
            raise ValueError(
                f"PhaseMixin.phase_coherence requires at least 2 samples, got {sample_count}"
            )
        resolved_window = window if window is not None else min(256, max(1, sample_count // 4))
        if not (1 <= resolved_window <= sample_count):
            raise ValueError(
                f"PhaseMixin.phase_coherence: window must be in [1, {sample_count}], "
                f"got {resolved_window}"
            )

        phase_diff = _analytic_phase(self.values) - _analytic_phase(other.values)
        coherence_values = [
            _plv(phase_diff[start : start + resolved_window])
            for start in range(0, sample_count - resolved_window + 1, resolved_window)
        ]
        return self._with_values(np.asarray(coherence_values, dtype=np.float64))

    def phase_synchronization_index(self: WaveformProtocol, other: WaveformProtocol) -> float:
        """Phase-locking value (PLV) between ``self`` and ``other`` over the full
        signal, in ``[0, 1]`` (``1.0`` = perfectly phase-locked, ``0.0`` = uniformly
        random relative phase).

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``,
                or the sample counts differ.
            ValueError: If either waveform has no samples.
        """
        _require_compatible(self, other, "phase_synchronization_index")
        if self.values.shape[0] == 0:
            raise ValueError(
                "PhaseMixin.phase_synchronization_index requires at least 1 sample, got 0"
            )
        phase_diff = _analytic_phase(self.values) - _analytic_phase(other.values)
        return _plv(phase_diff)

    @staticmethod
    def group_delay(
        frequencies: npt.NDArray[Any], phases: npt.NDArray[Any]
    ) -> npt.NDArray[np.float64]:
        """Group delay (seconds): the negative derivative of unwrapped ``phases``
        (radians) with respect to ``frequencies`` (Hz), divided by ``2 * pi``.

        A ``staticmethod`` -- see the module docstring for why it does not take
        ``self``.

        Raises:
            ValueError: If ``frequencies``/``phases`` have mismatched shape, or
                fewer than 2 samples.
        """
        freq = np.asarray(frequencies, dtype=np.float64)
        phase = np.asarray(phases, dtype=np.float64)
        if freq.shape != phase.shape:
            raise ValueError(
                f"PhaseMixin.group_delay: frequencies/phases shape mismatch "
                f"({freq.shape} vs {phase.shape})"
            )
        if freq.shape[0] < 2:
            raise ValueError(
                f"PhaseMixin.group_delay requires at least 2 samples, got {freq.shape[0]}"
            )
        unwrapped = np.unwrap(phase)
        result: npt.NDArray[np.float64] = -np.gradient(unwrapped, freq) / (2.0 * np.pi)
        return result


__all__ = ["PhaseMixin"]
