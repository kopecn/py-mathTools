"""``CorrelationMixin``: auto/cross-correlation and lag search for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``CorrelationMixin``),
§Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Correlation.swift``; test ideas:
``Waveform1DCorrelationTests.swift`` (39 tests -- representative cases ported).

Backing: ``scipy.signal.correlate``/``correlation_lags`` (linear, full-mode
correlation), per waveformDsp.md's family-contract table. This diverges from
the Swift extension in two ways the spec explicitly allows ("parity is
judged per capability, not per Swift overload"):

- ``cross_correlation``/``find_max_correlation`` only ever compute scipy's
  ``mode="full"``; the Swift ``WaveformCorrelationMode`` (``valid``/``same``)
  overloads are not ported (YAGNI -- add with a caller that needs them).
- **Lag sign convention.** ``scipy.signal.correlation_lags`` defines a lag
  such that ``other`` shifted *right* by ``lag`` samples (conceptually
  ``other[n - lag]``) aligns with ``self[n]`` at the correlation peak --
  i.e. ``lag`` is (roughly) "``self``'s feature index minus ``other``'s
  feature index". Swift's hand-rolled ``findMaxCorrelation`` computes the
  opposite sign (``actualLag = maxIndex - (other.count - 1)``, "``other``'s
  index minus ``self``'s"). This module keeps scipy's native sign rather
  than negating it, since scipy is the backing implementation the spec
  names: a waveform ``other`` that trails ``self`` by ``k`` samples (i.e.
  ``other[i] == self[i - k]``) yields ``lag_samples == -k``, not ``+k``.

Both ``auto_correlation`` and ``cross_correlation`` raise ``ValueError`` on
an empty input waveform (waveformDsp.md §Numerical conventions -- these are
not in the ``detect_*``/``zero_crossings`` detector family that gets the
empty-result exemption). ``cross_correlation``/``find_max_correlation`` raise
``WaveformCompatibilityError`` when ``other.dt`` differs from ``self.dt``
(the family contract's stated requirement).

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for the ``WaveformTimeLag`` return type) --
no sibling mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class CorrelationMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import correlate, correlation_lags

from math_tools.errors import WaveformCompatibilityError
from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformTimeLag


def _demeaned(values: npt.NDArray[Any], normalized: bool) -> npt.NDArray[np.float64]:
    """``values`` (as ``float64``) minus its mean when ``normalized``, else unchanged."""
    values_f64 = np.asarray(values, dtype=np.float64)
    return values_f64 - values_f64.mean() if normalized else values_f64


def _unit_normalized(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """``values`` scaled to unit energy (``sqrt(sum(values ** 2))``); unscaled if that is 0."""
    norm = float(np.sqrt(np.sum(values * values)))
    return values / norm if norm > 0.0 else values


def _cross_correlation_and_lags(
    self_values: npt.NDArray[Any], other_values: npt.NDArray[Any], normalized: bool
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int_]]:
    """Full-mode cross-correlation of ``self_values``/``other_values`` and its matching lags.

    Shared by ``cross_correlation`` and ``find_max_correlation`` so both stay
    exactly consistent about lag indexing.
    """
    x = _demeaned(self_values, normalized)
    y = _demeaned(other_values, normalized)
    if normalized:
        x = _unit_normalized(x)
        y = _unit_normalized(y)
    correlation: npt.NDArray[np.float64] = correlate(x, y, mode="full")
    lags: npt.NDArray[np.int_] = correlation_lags(x.shape[0], y.shape[0], mode="full")
    return correlation, lags


def _require_compatible_dt(
    waveform: WaveformProtocol, other: WaveformProtocol, op_name: str
) -> None:
    """Raise ``WaveformCompatibilityError`` unless ``other`` shares ``waveform``'s ``dt``."""
    if waveform.dt != other.dt:
        raise WaveformCompatibilityError(
            f"CorrelationMixin.{op_name}: dt mismatch ({waveform.dt!r} vs {other.dt!r})"
        )


def _require_nonempty(waveform: WaveformProtocol, other: WaveformProtocol, op_name: str) -> None:
    """Raise ``ValueError`` unless both ``waveform`` and ``other`` have at least 1 sample."""
    self_count = waveform.values.shape[0]
    other_count = other.values.shape[0]
    if self_count == 0 or other_count == 0:
        raise ValueError(
            f"CorrelationMixin.{op_name} requires both waveforms to have at least 1 sample, "
            f"got {self_count} and {other_count}"
        )


class CorrelationMixin:
    """Adds auto/cross-correlation and max-correlation lag search to a ``WaveformProtocol`` host."""

    def auto_correlation(
        self: WaveformProtocol, max_lag: int | None = None, normalized: bool = True
    ) -> WaveformProtocol:
        """One-sided auto-correlation (lags ``0..max_lag``), ``scipy.signal.correlate``-backed.

        ``max_lag`` defaults to ``sample_count // 2`` and is clamped to
        ``sample_count - 1``. When ``normalized``, lag 0 is ``1.0`` for any
        signal with nonzero variance; a zero-variance (constant) signal
        normalizes to ``1.0`` at every lag if the constant is nonzero, else
        ``0.0`` at every lag (matches the Swift reference's zero-variance
        special case).

        Raises:
            ValueError: If the waveform has no samples, or ``max_lag`` is negative.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("CorrelationMixin.auto_correlation requires at least 1 sample, got 0")
        resolved_max_lag = sample_count // 2 if max_lag is None else max_lag
        if resolved_max_lag < 0:
            raise ValueError(
                f"CorrelationMixin.auto_correlation: max_lag must be >= 0, got {resolved_max_lag}"
            )
        clamped_max_lag = min(resolved_max_lag, sample_count - 1)

        signal = _demeaned(self.values, normalized)
        full: npt.NDArray[np.float64] = correlate(signal, signal, mode="full")
        lags: npt.NDArray[np.int_] = correlation_lags(sample_count, sample_count, mode="full")
        one_sided = full[lags >= 0][: clamped_max_lag + 1]

        if normalized:
            zero_lag_energy = float(one_sided[0])
            if zero_lag_energy > 0.0:
                one_sided = one_sided / zero_lag_energy
            else:
                # Zero-variance (constant) signal: a nonzero constant is fully
                # self-similar at every lag (1.0); an all-zero signal carries no
                # correlatable structure (0.0) -- mirrors the Swift reference.
                fill = 1.0 if float(self.values[0]) != 0.0 else 0.0
                one_sided = np.full_like(one_sided, fill, dtype=np.float64)

        return self._with_values(one_sided)

    def cross_correlation(
        self: WaveformProtocol,
        other: WaveformProtocol,
        max_lag: int | None = None,
        normalized: bool = True,
    ) -> WaveformProtocol:
        """Full-mode cross-correlation against ``other`` (``scipy.signal.correlate``-backed).

        When ``max_lag`` is given, the result is trimmed to
        ``abs(lag) <= max_lag`` (see the module docstring for this module's
        lag sign convention, which is scipy's native one -- opposite of the
        Swift reference).

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
            ValueError: If either waveform has no samples, or ``max_lag`` is negative.
        """
        _require_compatible_dt(self, other, "cross_correlation")
        _require_nonempty(self, other, "cross_correlation")
        if max_lag is not None and max_lag < 0:
            raise ValueError(
                f"CorrelationMixin.cross_correlation: max_lag must be >= 0, got {max_lag}"
            )

        correlation, lags = _cross_correlation_and_lags(self.values, other.values, normalized)
        if max_lag is not None:
            correlation = correlation[np.abs(lags) <= max_lag]

        return self._with_values(correlation)

    def find_max_correlation(
        self: WaveformProtocol, other: WaveformProtocol, max_lag: int | None = None
    ) -> WaveformTimeLag:
        """The lag (samples/seconds) and correlation value of the strongest match with ``other``.

        Always normalizes internally (a "strongest match" search is
        meaningless on raw, unnormalized energy). See the module docstring
        for the lag sign convention.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
            ValueError: If either waveform has no samples, or ``max_lag`` is negative.
        """
        _require_compatible_dt(self, other, "find_max_correlation")
        _require_nonempty(self, other, "find_max_correlation")
        if max_lag is not None and max_lag < 0:
            raise ValueError(
                f"CorrelationMixin.find_max_correlation: max_lag must be >= 0, got {max_lag}"
            )

        correlation, lags = _cross_correlation_and_lags(self.values, other.values, normalized=True)
        if max_lag is not None:
            within_range = np.abs(lags) <= max_lag
            correlation = correlation[within_range]
            lags = lags[within_range]

        best_index = int(np.argmax(correlation))
        lag_samples = int(lags[best_index])
        lag_seconds = lag_samples * float_seconds(self.dt)
        return WaveformTimeLag(
            lag_samples=lag_samples,
            lag_seconds=lag_seconds,
            correlation=float(correlation[best_index]),
        )


__all__ = ["CorrelationMixin"]
