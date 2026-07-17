"""``WindowingMixin``: user-facing window-function utilities for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``WindowingMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Windowing.swift``.

Backing: ``scipy.signal.get_window`` called **symmetric** (``fftbins=False``)
-- matching the Swift reference's own ``n - 1``-denominator formulas, where a
finite-length window's first and last samples are exactly the window's edge
value and (for an odd length) the true midpoint sample is exactly the
window's peak. scipy's periodic/``fftbins=True`` variant is built for STFT
frame tiling -- ``SpectralMixin``'s own use, not this one's.

**Distinct, non-overlapping surface from ``SpectralMixin``'s internal STFT
window use.** ``dsp/_spectral.py`` (chunk 21) already maps
``WaveformWindowType`` to concrete scipy window arrays directly inside that
module, per that chunk's own design constraint that this module's helpers
are for "user-facing window utilities", not a dependency of chunk 21's. The
two modules intentionally duplicate a small enum->scipy-name mapping rather
than share one (waveformDsp.md §Organization / §Compliance 2 forbid a
sibling mixin import here regardless).

``WaveformWindowType.KAISER`` carries no ``beta`` field (the type is a flat
``str`` enum, unlike the Swift reference's ``.kaiser(beta:)`` associated
value) and ``generate_window``'s signature exposes none either (matching the
family-contract table's literal ``generate_window(window, length) ->
npt.NDArray``) -- so this module fixes one general-purpose default beta (the
same value ``dsp/_spectral.py`` independently chose, for the same reason:
comparable sidelobe suppression to a Blackman window) rather than adding a
parameter no other window type needs. YAGNI: expose ``beta`` directly only
if a caller ever needs to vary it.

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

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformWindowType

# See module docstring: independently chosen, matching dsp/_spectral.py's own
# fixed default for the same reason -- no shared import between the two modules.
_DEFAULT_KAISER_BETA = 14.0

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
        return ("kaiser", _DEFAULT_KAISER_BETA)
    return _WINDOW_NAME_MAP[window]


class WindowingMixin:
    """Adds window-function generation and application to a ``WaveformProtocol`` host."""

    @staticmethod
    def generate_window(window: WaveformWindowType, length: int) -> npt.NDArray[np.float64]:
        """The ``length``-sample coefficient array for ``window`` (symmetric,
        ``scipy.signal.get_window(..., fftbins=False)``).

        Raises:
            ValueError: If ``length`` is not a positive integer.
        """
        if length <= 0:
            raise ValueError(f"WindowingMixin.generate_window requires length > 0, got {length}")
        result: npt.NDArray[np.float64] = get_window(
            _scipy_window_spec(window), length, fftbins=False
        )
        return result

    def windowed(self: WaveformProtocol, window: WaveformWindowType) -> WaveformProtocol:
        """A copy of ``self`` with ``window``'s coefficients applied elementwise
        (``dt``/``t0`` unchanged).

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("WindowingMixin.windowed requires at least 1 sample, got 0")
        coefficients = WindowingMixin.generate_window(window, sample_count)
        return self._with_values(self.values * coefficients)

    def window_coherent_gain(self: WaveformProtocol, window: WaveformWindowType) -> float:
        """The coherent gain (mean) of ``window``'s coefficients at ``self``'s length.

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "WindowingMixin.window_coherent_gain requires at least 1 sample, got 0"
            )
        coefficients = WindowingMixin.generate_window(window, sample_count)
        return float(np.mean(coefficients))

    def window_processing_gain(self: WaveformProtocol, window: WaveformWindowType) -> float:
        """The processing gain (RMS) of ``window``'s coefficients at ``self``'s length.

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError(
                "WindowingMixin.window_processing_gain requires at least 1 sample, got 0"
            )
        coefficients = WindowingMixin.generate_window(window, sample_count)
        return float(np.sqrt(np.mean(coefficients**2)))


__all__ = ["WindowingMixin"]
