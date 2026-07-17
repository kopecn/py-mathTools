"""``ResamplingMixin``: sample-rate conversion for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``ResamplingMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Resampling.swift``.

Backing: ``scipy.signal.decimate`` (``decimated``, built-in anti-aliasing
filter), ``scipy.signal.resample`` / ``np.interp`` / ``scipy.interpolate.
CubicSpline`` (``interpolated``, selected by the ``WaveformInterpolationMethod``
kernel argument), ``scipy.signal.resample`` (``resampled``/
``resampled_to_match``, FFT-based), ``scipy.signal.resample_poly``
(``polyphase_resampled``) -- per waveformDsp.md's family-contract table.

**dt bookkeeping (the chunk's own "tricky bit").** Every mixin through
chunk 24 only ever produces results sharing ``self``'s ``dt`` (built via
``_with_values``, see ``dsp/_protocol.py``'s and ``dsp/_phase.py``'s
docstrings). ``ResamplingMixin`` is the first family whose results have a
genuinely different sample spacing, so this chunk adds ``_with_axis`` to
``WaveformProtocol``/``Waveform1D`` (``dsp/_protocol.py``, ``waveforms/
waveform1d.py``; a forced contract change, waveformDsp.md bumped to
semver 0.0.4) -- the dt-changing sibling of ``_with_values``. ``t0`` is
never changed by any method here (waveformDsp.md: "New ``t0`` is
unchanged").

Integer-factor paths (``decimated``, ``interpolated``) compute the new
``dt`` exactly via ``PrecisionTimeInterval`` arithmetic (``dt * factor`` /
``dt / factor``, both exact or rounded to the nearest attosecond -- see
``precision_time_interval.py``). ``polyphase_resampled(up, down)``
generalizes this to a rational factor (``dt * down / up``).
``resampled(target_frequency_hz)`` cannot use exact rational arithmetic in
general (the achieved sample count is an integer, so the achieved rate is
only ever an approximation of the requested one); its ``dt`` is derived
from the *achieved* rate: ``new_dt = dt * sample_count / new_sample_count``
(the same relationship ``scipy.signal.resample`` itself assumes between
input/output length and sampling interval).

``factor < 1`` or a non-int ``factor`` (``decimated``, ``interpolated``,
and ``up``/``down`` of ``polyphase_resampled``) raises ``ValueError``
(waveformDsp.md §Numerical conventions -- none of these are in the
``detect_*``/``zero_crossings`` detector family that gets the empty-result
exemption).

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for the ``WaveformInterpolationMethod`` enum
argument) -- no sibling mixin imports (waveformDsp.md §Organization /
§Compliance 2).

**Not** ``class ResamplingMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.interpolate import CubicSpline
from scipy.signal import decimate as scipy_decimate
from scipy.signal import resample as scipy_resample
from scipy.signal import resample_poly as scipy_resample_poly

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInterpolationMethod


def _validate_positive_int_factor(factor: int, op_name: str, param_name: str = "factor") -> None:
    """Raise ``ValueError`` unless ``factor`` is a (non-``bool``) ``int`` ``>= 1``."""
    if isinstance(factor, bool) or not isinstance(factor, int):
        raise ValueError(
            f"ResamplingMixin.{op_name}: {param_name} must be an int, got {factor!r}"
        )
    if factor < 1:
        raise ValueError(
            f"ResamplingMixin.{op_name}: {param_name} must be >= 1, got {factor}"
        )


def _require_min_samples(sample_count: int, minimum: int, op_name: str) -> None:
    if sample_count < minimum:
        raise ValueError(
            f"ResamplingMixin.{op_name} requires at least {minimum} samples, got {sample_count}"
        )


def _interpolate(
    values: npt.NDArray[Any], factor: int, method: WaveformInterpolationMethod
) -> npt.NDArray[np.float64]:
    """Insert ``factor - 1`` samples between every consecutive pair of ``values``
    (endpoints preserved), per ``method``'s interpolation kernel.

    New length is always ``(len(values) - 1) * factor + 1``.
    """
    float_values = np.asarray(values, dtype=np.float64)
    sample_count = float_values.shape[0]
    new_length = (sample_count - 1) * factor + 1

    if method is WaveformInterpolationMethod.FOURIER:
        result = scipy_resample(float_values, new_length)
        return np.asarray(result, dtype=np.float64)

    source_positions = np.arange(sample_count, dtype=np.float64)
    target_positions = np.linspace(0.0, sample_count - 1, new_length)

    if method is WaveformInterpolationMethod.LINEAR:
        return np.asarray(
            np.interp(target_positions, source_positions, float_values), dtype=np.float64
        )
    if method is WaveformInterpolationMethod.CUBIC:
        spline = CubicSpline(source_positions, float_values)
        return np.asarray(spline(target_positions), dtype=np.float64)
    if method is WaveformInterpolationMethod.NEAREST:
        nearest_indices = np.round(target_positions).astype(np.intp)
        return float_values[nearest_indices]
    # pragma: no cover -- WaveformInterpolationMethod is exhaustive above
    raise ValueError(f"ResamplingMixin.interpolated: unsupported method {method!r}")


def _resample_to_frequency(
    self: WaveformProtocol, target_frequency_hz: float, op_name: str
) -> WaveformProtocol:
    """Shared implementation for ``resampled``/``resampled_to_match``: FFT-resample
    to the sample count implied by ``target_frequency_hz``, deriving the result's
    ``dt`` from the achieved (rounded) sample count -- see the module docstring.
    """
    values = self.values
    sample_count = values.shape[0]
    _require_min_samples(sample_count, 2, op_name)

    original_frequency_hz = self.sampling_frequency_hz
    new_length = max(1, round(sample_count * target_frequency_hz / original_frequency_hz))
    if new_length < 2:
        raise ValueError(
            f"ResamplingMixin.{op_name}: target_frequency_hz={target_frequency_hz} yields "
            f"fewer than 2 samples from {sample_count} samples at {original_frequency_hz} Hz"
        )

    resampled_values = np.asarray(scipy_resample(values, new_length), dtype=np.float64)
    achieved_dt_seconds = float_seconds(self.dt) * sample_count / new_length
    new_dt = PrecisionTimeInterval.from_seconds(achieved_dt_seconds)
    return self._with_axis(resampled_values, new_dt)


class ResamplingMixin:
    """Adds sample-rate conversion (``decimated``/``interpolated``/``resampled``/
    ``resampled_to_match``/``polyphase_resampled``) to a ``WaveformProtocol`` host."""

    def decimated(self: WaveformProtocol, factor: int) -> WaveformProtocol:
        """Reduce the sampling rate by the integer ``factor`` (``scipy.signal.decimate``,
        which applies its own anti-aliasing filter). ``dt`` becomes ``dt * factor``
        exactly; ``t0`` is unchanged.

        Raises:
            ValueError: If ``factor`` is not an int, or ``factor < 1``.
            ValueError: If the waveform has fewer than 2 samples.
        """
        _validate_positive_int_factor(factor, "decimated")
        values = self.values
        if factor == 1:
            return self._with_values(values.copy())
        _require_min_samples(values.shape[0], 2, "decimated")

        # ftype="fir": scipy.signal.decimate's default IIR (Chebyshev I) anti-alias
        # filter has ~0.05 dB passband ripple, doubled by zero-phase filtfilt to
        # ~1.1% amplitude error even deep in the passband -- enough to blow the
        # interpolated().decimated() round-trip's rtol (waveformDsp.md §Compliance
        # 1). The FIR variant (linear-phase, near-flat passband) round-trips to
        # ~1e-6 on the same signal and also tolerates much shorter inputs (its
        # padding requirement scales with taps, not a fixed minimum of 27+).
        decimated_values = np.asarray(
            scipy_decimate(values, factor, ftype="fir"), dtype=np.float64
        )
        new_dt = self.dt * factor
        return self._with_axis(decimated_values, new_dt)

    def interpolated(
        self: WaveformProtocol,
        factor: int,
        method: WaveformInterpolationMethod = WaveformInterpolationMethod.LINEAR,
    ) -> WaveformProtocol:
        """Increase the sampling rate by the integer ``factor``, inserting
        ``factor - 1`` new samples between every consecutive pair (per ``method``'s
        kernel: LINEAR/CUBIC/NEAREST fit the original samples directly; FOURIER
        uses ``scipy.signal.resample``). ``dt`` becomes ``dt / factor`` (rounded
        to the nearest attosecond); ``t0`` is unchanged.

        Raises:
            ValueError: If ``factor`` is not an int, or ``factor < 1``.
            ValueError: If the waveform has fewer than 2 samples.
        """
        _validate_positive_int_factor(factor, "interpolated")
        values = self.values
        if factor == 1:
            return self._with_values(values.copy())
        _require_min_samples(values.shape[0], 2, "interpolated")

        interpolated_values = _interpolate(values, factor, method)
        new_dt = self.dt / factor
        return self._with_axis(interpolated_values, new_dt)

    def resampled(self: WaveformProtocol, target_frequency_hz: float) -> WaveformProtocol:
        """FFT-resample (``scipy.signal.resample``) to ``target_frequency_hz``.

        The achieved sample count is ``round(sample_count * target_frequency_hz /
        sampling_frequency_hz)``; ``dt`` is derived from that achieved count
        rather than blindly set to ``1 / target_frequency_hz`` (waveformDsp.md:
        "``resampled(hz)`` derives dt from the achieved rate"). ``t0`` is
        unchanged.

        Raises:
            ValueError: If ``target_frequency_hz <= 0``.
            ValueError: If the waveform has fewer than 2 samples, or the
                achieved sample count would be fewer than 2.
        """
        if not target_frequency_hz > 0.0:
            raise ValueError(
                f"ResamplingMixin.resampled: target_frequency_hz must be > 0, "
                f"got {target_frequency_hz}"
            )
        return _resample_to_frequency(self, target_frequency_hz, "resampled")

    def resampled_to_match(self: WaveformProtocol, other: WaveformProtocol) -> WaveformProtocol:
        """``resampled`` to ``other.sampling_frequency_hz`` -- resample ``self`` onto
        (approximately) ``other``'s rate and length.

        Raises:
            ValueError: If the waveform has fewer than 2 samples, or the
                achieved sample count would be fewer than 2.
        """
        return _resample_to_frequency(self, other.sampling_frequency_hz, "resampled_to_match")

    def polyphase_resampled(self: WaveformProtocol, up: int, down: int) -> WaveformProtocol:
        """Efficient polyphase resampling by the rational factor ``up / down``
        (``scipy.signal.resample_poly``, which applies its own anti-aliasing
        filter). ``dt`` becomes ``dt * down / up`` (rounded to the nearest
        attosecond); ``t0`` is unchanged.

        Raises:
            ValueError: If ``up``/``down`` are not ints, or either is ``< 1``.
            ValueError: If the waveform has fewer than 2 samples.
        """
        _validate_positive_int_factor(up, "polyphase_resampled", "up")
        _validate_positive_int_factor(down, "polyphase_resampled", "down")
        values = self.values
        _require_min_samples(values.shape[0], 2, "polyphase_resampled")

        resampled_values = np.asarray(
            scipy_resample_poly(values, up, down), dtype=np.float64
        )
        new_dt = (self.dt * down) / up
        return self._with_axis(resampled_values, new_dt)


__all__ = ["ResamplingMixin"]
