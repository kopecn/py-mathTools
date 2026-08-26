"""``FilteringMixin``: digital filtering (Butterworth, moving-average, EMA,
Savitzky-Golay, Whittaker-Henderson) plus filter frequency response.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``FilteringMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Filtering.swift``.

Backing: ``scipy.signal.butter`` (+ ``filtfilt``/``lfilter``) for the
Butterworth families, ``scipy.signal.savgol_filter`` for Savitzky-Golay,
``scipy.signal.freqz`` for the frequency-response sampler, and a sparse
difference-matrix solve (``scipy.sparse`` + ``scipy.sparse.linalg.spsolve``)
for Whittaker-Henderson, per waveformDsp.md's family-contract table and the
chunk's own "one clever bit" recipe.

**Zero-phase by default.** The Butterworth designs (``low_pass_filter``,
``high_pass_filter``, ``band_pass_filter``, and ``filtered``'s BAND_STOP
branch) filter via ``scipy.signal.filtfilt`` (zero-phase, doubles the
effective attenuation in dB relative to a single pass) unless the caller
passes ``causal=True``, in which case a single causal ``scipy.signal.lfilter``
pass is used instead -- per waveformDsp.md §Numerical conventions.

**Nyquist validation.** Every cutoff/band edge is validated against the
waveform's Nyquist frequency (``sampling_frequency_hz / 2``) and raises
``ValueError`` naming the requirement -- the chunk's own acceptance
criterion -- rather than silently clamping (the Swift reference clamps;
this Python port does not, consistent with waveformDsp.md §Numerical
conventions' "raise `ValueError`... never a silent empty/clamped result"
policy already followed by every other mixin chunk).

**Deviation from the Swift reference's silent-no-op guards.** The Swift
methods return ``self`` unchanged on invalid parameters (e.g. an
out-of-range ``windowSize``); this port raises ``ValueError`` instead,
consistent with every other DSP mixin chunk (waveformDsp.md §Numerical
conventions) and with scipy's own behavior for the methods that wrap it
directly (``savgol_filter``, ``filtfilt``) -- "parity is judged per
capability, not per Swift overload" (waveformDsp.md's opening note).

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for the enum/descriptor types) -- no sibling
mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class FilteringMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import sparse
from scipy.signal import butter, filtfilt, freqz, lfilter, savgol_filter
from scipy.sparse.linalg import spsolve

from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformFilterType, WaveformSpectrum


def _validate_order(order: int, op_name: str) -> None:
    if order < 1:
        raise ValueError(f"FilteringMixin.{op_name}: order must be >= 1, got {order}")


def _validate_cutoff(cutoff_hz: float, nyquist_hz: float, op_name: str) -> None:
    if not (0.0 < cutoff_hz < nyquist_hz):
        raise ValueError(
            f"FilteringMixin.{op_name}: cutoff_hz must be in (0, {nyquist_hz}) Hz "
            f"(Nyquist), got {cutoff_hz}"
        )


def _validate_band(low_hz: float, high_hz: float, nyquist_hz: float, op_name: str) -> None:
    if not (0.0 < low_hz < high_hz < nyquist_hz):
        raise ValueError(
            f"FilteringMixin.{op_name}: require 0 < low_hz < high_hz < {nyquist_hz} Hz "
            f"(Nyquist), got low_hz={low_hz}, high_hz={high_hz}"
        )


def _butter_coefficients(
    filter_type: WaveformFilterType,
    order: int,
    fs: float,
    cutoff_hz: float | None,
    low_hz: float | None,
    high_hz: float | None,
    op_name: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Design Butterworth coefficients ``(b, a)`` for ``filter_type`` (Nyquist-validated).

    Shared by every Butterworth-backed method (``low_pass_filter``,
    ``high_pass_filter``, ``band_pass_filter``, ``filtered``,
    ``frequency_response``) so they stay exactly consistent about validation
    and design parameters.
    """
    _validate_order(order, op_name)
    nyquist_hz = fs / 2.0

    if filter_type is WaveformFilterType.LOW_PASS:
        if cutoff_hz is None:
            raise ValueError(f"FilteringMixin.{op_name}: cutoff_hz is required for LOW_PASS")
        _validate_cutoff(cutoff_hz, nyquist_hz, op_name)
        b, a = butter(order, cutoff_hz, btype="low", fs=fs)
    elif filter_type is WaveformFilterType.HIGH_PASS:
        if cutoff_hz is None:
            raise ValueError(f"FilteringMixin.{op_name}: cutoff_hz is required for HIGH_PASS")
        _validate_cutoff(cutoff_hz, nyquist_hz, op_name)
        b, a = butter(order, cutoff_hz, btype="high", fs=fs)
    elif filter_type in (WaveformFilterType.BAND_PASS, WaveformFilterType.BAND_STOP):
        if low_hz is None or high_hz is None:
            raise ValueError(
                f"FilteringMixin.{op_name}: low_hz and high_hz are required for "
                f"{filter_type.value.upper()}"
            )
        _validate_band(low_hz, high_hz, nyquist_hz, op_name)
        btype = "bandpass" if filter_type is WaveformFilterType.BAND_PASS else "bandstop"
        b, a = butter(order, [low_hz, high_hz], btype=btype, fs=fs)
    else:  # pragma: no cover - WaveformFilterType is exhaustive above
        raise ValueError(f"FilteringMixin.{op_name}: unsupported filter_type {filter_type!r}")

    return np.asarray(b, dtype=np.float64), np.asarray(a, dtype=np.float64)


def _apply_iir(
    values: npt.NDArray[Any],
    b: npt.NDArray[np.float64],
    a: npt.NDArray[np.float64],
    causal: bool,
) -> npt.NDArray[np.float64]:
    """Apply ``(b, a)`` to ``values``: zero-phase (``filtfilt``) unless ``causal``."""
    float_values = np.asarray(values, dtype=np.float64)
    result = lfilter(b, a, float_values) if causal else filtfilt(b, a, float_values)
    return np.asarray(result, dtype=np.float64)


def _moving_average(
    values: npt.NDArray[Any], window_size: int, op_name: str
) -> npt.NDArray[np.float64]:
    """Centered moving average; the window shrinks (rather than zero-pads) near the
    edges, so it averages over exactly the samples available at each point."""
    if window_size < 1:
        raise ValueError(f"FilteringMixin.{op_name}: window_size must be >= 1, got {window_size}")
    float_values = np.asarray(values, dtype=np.float64)
    n = float_values.shape[0]
    half_window = window_size // 2
    cumulative = np.concatenate(([0.0], np.cumsum(float_values)))
    index = np.arange(n)
    starts = np.clip(index - half_window, 0, n)
    ends = np.clip(index + half_window + 1, 0, n)
    sums = cumulative[ends] - cumulative[starts]
    counts = (ends - starts).astype(np.float64)
    result: npt.NDArray[np.float64] = np.divide(
        sums, counts, out=np.zeros_like(sums), where=counts > 0.0
    )
    return result


def _exponential_smooth(
    values: npt.NDArray[Any], alpha: float, op_name: str
) -> npt.NDArray[np.float64]:
    """Exponential moving average: ``y[0] = x[0]``, ``y[i] = alpha*x[i] + (1-alpha)*y[i-1]``."""
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"FilteringMixin.{op_name}: alpha must be in (0, 1], got {alpha}")
    float_values = np.asarray(values, dtype=np.float64)
    n = float_values.shape[0]
    if n == 0:
        raise ValueError(f"FilteringMixin.{op_name} requires at least 1 sample, got 0")
    smoothed = np.empty(n, dtype=np.float64)
    smoothed[0] = float_values[0]
    one_minus_alpha = 1.0 - alpha
    for i in range(1, n):
        smoothed[i] = alpha * float_values[i] + one_minus_alpha * smoothed[i - 1]
    return smoothed


def _whittaker_henderson_smooth(
    values: npt.NDArray[Any], lam: float, order: int, op_name: str
) -> npt.NDArray[np.float64]:
    """Whittaker-Henderson smoother: solve ``(I + lam * D^T D) z = v`` for the
    order-th difference matrix ``D`` -- the chunk's own recipe, verbatim."""
    if order < 1:
        raise ValueError(f"FilteringMixin.{op_name}: order must be >= 1, got {order}")
    if lam < 0.0:
        raise ValueError(f"FilteringMixin.{op_name}: lam must be >= 0, got {lam}")
    float_values = np.asarray(values, dtype=np.float64)
    n = float_values.shape[0]
    if n <= order:
        raise ValueError(
            f"FilteringMixin.{op_name} requires more than order ({order}) samples, got {n}"
        )

    d = sparse.eye(n, format="csc")
    for _ in range(order):
        d = d[1:] - d[:-1]
    system = (sparse.eye(n, format="csc") + lam * (d.T @ d)).tocsc()
    smoothed = spsolve(system, float_values)
    return np.asarray(smoothed, dtype=np.float64)


class FilteringMixin:
    """Adds digital-filtering methods to a ``WaveformProtocol``-satisfying host."""

    def low_pass_filter(
        self: WaveformProtocol, cutoff_hz: float, order: int = 4, causal: bool = False
    ) -> WaveformProtocol:
        """Zero-phase (unless ``causal``) Butterworth low-pass filter.

        Raises:
            ValueError: If ``order < 1`` or ``cutoff_hz`` is outside
                ``(0, nyquist)``.
        """
        b, a = _butter_coefficients(
            WaveformFilterType.LOW_PASS,
            order,
            self.sampling_frequency_hz,
            cutoff_hz,
            None,
            None,
            "low_pass_filter",
        )
        return self._with_values(_apply_iir(self.values, b, a, causal))

    def high_pass_filter(
        self: WaveformProtocol, cutoff_hz: float, order: int = 4, causal: bool = False
    ) -> WaveformProtocol:
        """Zero-phase (unless ``causal``) Butterworth high-pass filter.

        Raises:
            ValueError: If ``order < 1`` or ``cutoff_hz`` is outside
                ``(0, nyquist)``.
        """
        b, a = _butter_coefficients(
            WaveformFilterType.HIGH_PASS,
            order,
            self.sampling_frequency_hz,
            cutoff_hz,
            None,
            None,
            "high_pass_filter",
        )
        return self._with_values(_apply_iir(self.values, b, a, causal))

    def band_pass_filter(
        self: WaveformProtocol,
        low_hz: float,
        high_hz: float,
        order: int = 4,
        causal: bool = False,
    ) -> WaveformProtocol:
        """Zero-phase (unless ``causal``) Butterworth band-pass filter.

        Raises:
            ValueError: If ``order < 1`` or ``0 < low_hz < high_hz < nyquist``
                does not hold.
        """
        b, a = _butter_coefficients(
            WaveformFilterType.BAND_PASS,
            order,
            self.sampling_frequency_hz,
            None,
            low_hz,
            high_hz,
            "band_pass_filter",
        )
        return self._with_values(_apply_iir(self.values, b, a, causal))

    def filtered(
        self: WaveformProtocol,
        filter_type: WaveformFilterType,
        cutoff_hz: float | None = None,
        low_hz: float | None = None,
        high_hz: float | None = None,
        order: int = 4,
        causal: bool = False,
    ) -> WaveformProtocol:
        """Generic Butterworth dispatch over ``WaveformFilterType`` (adds BAND_STOP,
        unreachable from the three dedicated methods above).

        Raises:
            ValueError: If the arguments ``filter_type`` requires are missing,
                ``order < 1``, or a cutoff/band edge violates Nyquist.
        """
        b, a = _butter_coefficients(
            filter_type,
            order,
            self.sampling_frequency_hz,
            cutoff_hz,
            low_hz,
            high_hz,
            "filtered",
        )
        return self._with_values(_apply_iir(self.values, b, a, causal))

    def moving_average_filter(self: WaveformProtocol, window_size: int) -> WaveformProtocol:
        """Centered moving average (``window_size`` samples; shrinks near the edges
        rather than zero-padding).

        Raises:
            ValueError: If ``window_size < 1``.
        """
        return self._with_values(
            _moving_average(self.values, window_size, "moving_average_filter")
        )

    def exponential_filter(self: WaveformProtocol, alpha: float) -> WaveformProtocol:
        """Exponential moving average (first sample unchanged).

        Raises:
            ValueError: If ``alpha`` is outside ``(0, 1]``, or the waveform is
                empty.
        """
        return self._with_values(_exponential_smooth(self.values, alpha, "exponential_filter"))

    def savitzky_golay_filter(
        self: WaveformProtocol, window_length: int, polyorder: int, deriv: int = 0
    ) -> WaveformProtocol:
        """Savitzky-Golay smoothing/derivative filter (``scipy.signal.savgol_filter``).

        ``deriv > 0`` results are scaled by ``1/dt**deriv`` (via ``delta=dt``)
        to carry proper derivative units.

        Raises:
            ValueError: If ``window_length`` is not odd and ``>= 3``, if
                ``polyorder`` is not in ``[0, window_length)``, if ``deriv``
                is not in ``[0, polyorder]``, or if the waveform has fewer
                samples than ``window_length``.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if window_length < 3 or window_length % 2 == 0:
            raise ValueError(
                "FilteringMixin.savitzky_golay_filter: window_length must be odd and "
                f">= 3, got {window_length}"
            )
        if not (0 <= polyorder < window_length):
            raise ValueError(
                "FilteringMixin.savitzky_golay_filter: polyorder must be in "
                f"[0, {window_length}), got {polyorder}"
            )
        if not (0 <= deriv <= polyorder):
            raise ValueError(
                "FilteringMixin.savitzky_golay_filter: deriv must be in "
                f"[0, {polyorder}], got {deriv}"
            )
        if n < window_length:
            raise ValueError(
                "FilteringMixin.savitzky_golay_filter requires at least "
                f"{window_length} samples, got {n}"
            )
        dt_seconds = float_seconds(self.dt)
        result = savgol_filter(
            values, window_length, polyorder, deriv=deriv, delta=dt_seconds if deriv > 0 else 1.0
        )
        return self._with_values(np.asarray(result, dtype=np.float64))

    def whittaker_henderson_filter(
        self: WaveformProtocol, lam: float, order: int = 2
    ) -> WaveformProtocol:
        """Whittaker-Henderson smoother: trades fidelity to the data against
        smoothness of the ``order``-th difference, weighted by ``lam``.

        ``lam -> 0`` approximates the identity; large ``lam`` approximates the
        least-squares polynomial trend of degree ``order - 1``.

        Raises:
            ValueError: If ``order < 1``, ``lam < 0``, or the waveform has
                ``order`` or fewer samples.
        """
        return self._with_values(
            _whittaker_henderson_smooth(self.values, lam, order, "whittaker_henderson_filter")
        )

    def frequency_response(
        self: WaveformProtocol,
        filter_type: WaveformFilterType,
        order: int = 4,
        cutoff_hz: float | None = None,
        low_hz: float | None = None,
        high_hz: float | None = None,
        num_points: int = 512,
    ) -> WaveformSpectrum:
        """The designed Butterworth filter's frequency response (``scipy.signal.freqz``),
        sampled at ``num_points`` points from 0 Hz to Nyquist.

        Raises:
            ValueError: Same conditions as the matching Butterworth design
                method (see ``filtered``).
        """
        b, a = _butter_coefficients(
            filter_type,
            order,
            self.sampling_frequency_hz,
            cutoff_hz,
            low_hz,
            high_hz,
            "frequency_response",
        )
        frequencies, response = freqz(b, a, worN=num_points, fs=self.sampling_frequency_hz)
        return WaveformSpectrum(
            frequencies=np.asarray(frequencies, dtype=np.float64),
            magnitudes=np.abs(response).astype(np.float64),
            phases=np.angle(response).astype(np.float64),
        )


__all__ = ["FilteringMixin"]
