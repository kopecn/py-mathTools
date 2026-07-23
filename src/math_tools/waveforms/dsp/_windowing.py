"""``WindowingMixin``: user-facing window-function utilities for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``WindowingMixin``),
§Window convention, §Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Windowing.swift``.

Backing: ``scipy.signal.get_window``, **symmetric** (``fftbins=False``) by
default -- matching the Swift reference's own ``n - 1``-denominator formulas,
where a finite-length window's first and last samples are exactly the
window's edge value and (for an odd length) the true midpoint sample is
exactly the window's peak. scipy's periodic/``fftbins=True`` convention is
built for STFT frame tiling -- ``SpectralMixin``'s own use (``dsp/_spectral.py``),
not this module's default.

**Reconciled seam (chunk 53).** Post-audit finding D-windowing-(c): this
module's default (symmetric) and ``SpectralMixin``'s internal window use
(periodic) are genuinely different conventions, so a caller who used
``window_coherent_gain``/``window_processing_gain`` to correct a
``power_spectral_density``/``spectrogram`` estimate got a subtly wrong scale
factor -- the gain helpers described a different window than the one scipy
actually applied. Per waveformDsp.md's window-convention section, both
conventions stay legitimate and the per-family defaults are unchanged; the
fix is an explicit ``periodic: bool = False`` parameter on
``generate_window`` and both gain helpers so a caller correcting a
periodic-windowed spectral estimate can request the exact matching
convention (``periodic=True`` == ``fftbins=True`` == what ``SpectralMixin``
applies). ``windowed`` keeps the symmetric default only -- applying a window
to a whole waveform (filter design / analysis framing) is this module's own
use case, not a PSD-correction helper.

**Distinct, non-overlapping surface from ``SpectralMixin``'s internal STFT
window use.** ``dsp/_spectral.py`` (chunk 21) already maps
``WaveformWindowType`` to concrete scipy window arrays directly inside that
module, per that chunk's own design constraint that this module's helpers
are for "user-facing window utilities", not a dependency of chunk 21's. The
two modules intentionally duplicate the small enum->scipy-name mapping
rather than share one (waveformDsp.md §Organization / §Compliance 2 forbid a
sibling mixin import here regardless) -- but the Kaiser beta shape parameter
is now a single shared constant (``dsp/_common.DEFAULT_KAISER_BETA``,
chunk 53) imported by both, closing the drift risk of two independent
literals.

``WaveformWindowType.KAISER`` carries no ``beta`` field (the type is a flat
``str`` enum, unlike the Swift reference's ``.kaiser(beta:)`` associated
value) and ``generate_window``'s signature exposes none either -- see
``dsp/_common.py``'s docstring for why chunk 53 kept the flat enum
(exposing beta would force an enum redesign) rather than closing that gap.
YAGNI: expose ``beta`` directly only if a caller ever needs to vary it.

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for ``WaveformWindowType``) -- no sibling
mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class WindowingMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.signal import get_window

from math_tools.waveforms.dsp._common import DEFAULT_KAISER_BETA
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformWindowType

_WINDOW_NAME_MAP: dict[WaveformWindowType, str] = {
    WaveformWindowType.HANN: "hann",
    WaveformWindowType.HAMMING: "hamming",
    WaveformWindowType.BLACKMAN: "blackman",
    WaveformWindowType.BARTLETT: "bartlett",
    WaveformWindowType.RECTANGULAR: "boxcar",
}


def _scipy_window_spec(window: WaveformWindowType) -> str | tuple[str, float]:
    """``WaveformWindowType`` -> a ``scipy.signal.get_window``-compatible spec."""
    if window is WaveformWindowType.KAISER:
        return ("kaiser", DEFAULT_KAISER_BETA)
    return _WINDOW_NAME_MAP[window]


class WindowingMixin:
    """Adds window-function generation and application to a ``WaveformProtocol`` host."""

    @staticmethod
    def generate_window(
        window: WaveformWindowType, length: int, periodic: bool = False
    ) -> npt.NDArray[np.float64]:
        """The ``length``-sample coefficient array for ``window``.

        ``periodic`` selects the convention: ``False`` (default) is the
        symmetric convention (``scipy.signal.get_window(..., fftbins=False)``);
        ``True`` is the periodic convention (``fftbins=True``) that
        ``SpectralMixin.power_spectral_density``/``spectrogram`` actually
        apply internally, for a caller correcting a periodic-windowed
        spectral estimate.

        Raises:
            ValueError: If ``length`` is not a positive integer.
        """
        if length <= 0:
            raise ValueError(f"WindowingMixin.generate_window requires length > 0, got {length}")
        result: npt.NDArray[np.float64] = get_window(
            _scipy_window_spec(window), length, fftbins=periodic
        )
        return result

    def windowed(self: WaveformProtocol, window: WaveformWindowType) -> WaveformProtocol:
        """A copy of ``self`` with ``window``'s coefficients applied elementwise
        (``dt``/``t0`` unchanged). Always the symmetric convention (this
        module's own use case, not a spectral-estimate correction).

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("WindowingMixin.windowed requires at least 1 sample, got 0")
        coefficients = WindowingMixin.generate_window(window, sample_count)
        return self._with_values(self.values * coefficients)

    def window_coherent_gain(
        self: WaveformProtocol, window: WaveformWindowType, periodic: bool = False
    ) -> float:
        """The coherent gain (mean) of ``window``'s coefficients at ``self``'s length.

        ``periodic`` (default ``False``, symmetric) selects the convention;
        pass ``periodic=True`` to describe the exact window
        ``power_spectral_density``/``spectrogram`` apply internally.

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "WindowingMixin.window_coherent_gain requires at least 1 sample, got 0"
            )
        coefficients = WindowingMixin.generate_window(window, sample_count, periodic=periodic)
        return float(np.mean(coefficients))

    def window_processing_gain(
        self: WaveformProtocol, window: WaveformWindowType, periodic: bool = False
    ) -> float:
        """The processing gain (RMS) of ``window``'s coefficients at ``self``'s length.

        ``periodic`` (default ``False``, symmetric) selects the convention;
        pass ``periodic=True`` to describe the exact window
        ``power_spectral_density``/``spectrogram`` apply internally.

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "WindowingMixin.window_processing_gain requires at least 1 sample, got 0"
            )
        coefficients = WindowingMixin.generate_window(window, sample_count, periodic=periodic)
        return float(np.sqrt(np.mean(coefficients**2)))


__all__ = ["WindowingMixin", "DEFAULT_KAISER_BETA"]
