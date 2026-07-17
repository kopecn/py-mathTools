"""``CalcMixin``: numerical integration and differentiation for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``CalcMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-Calc.swift``.

Both methods scale by ``dt`` in seconds (not raw sample spacing), and both
raise ``ValueError`` (naming the required minimum length) rather than
silently returning an empty result when the waveform is too short --
per waveformDsp.md §Numerical conventions, that empty-result path is
reserved for the ``detect_*``/``zero_crossings`` detector family, which
this is not.

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
(no sibling mixin imports -- waveformDsp.md §Organization / §Compliance 2).

**Not** ``class CalcMixin(WaveformProtocol)``: nominally inheriting the
``Protocol`` turns its stub property bodies into concrete implementations
that shadow ``Waveform1D``'s real ones once a test composes
``class _W(CalcMixin, Waveform1D)`` (C3 puts the inherited stub ahead of
``Waveform1D`` in the MRO, so ``self.values`` silently returns ``None`` --
see waveformDsp.md §Organization for the full account). ``CalcMixin`` is a
plain class instead, typing ``self`` as ``WaveformProtocol`` on each method
(mypy's "mixin classes" idiom) -- structurally checkable, no runtime base.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import cumulative_trapezoid

from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol


class CalcMixin:
    """Adds ``integrate``/``derivative`` to a ``WaveformProtocol``-satisfying host."""

    def integrate(self: WaveformProtocol, initial_value: float = 0.0) -> WaveformProtocol:
        """Cumulative trapezoidal integral, scaled by ``dt`` seconds.

        The first sample of the result equals ``initial_value``; each
        subsequent sample adds the trapezoidal area accumulated since the
        start (``scipy.integrate.cumulative_trapezoid``).

        Raises:
            ValueError: If the waveform has no samples.
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("CalcMixin.integrate requires at least 1 sample, got 0")
        dt_seconds = float_seconds(self.dt)
        cumulative = cumulative_trapezoid(self.values, dx=dt_seconds, initial=0.0)
        return self._with_values(cumulative + initial_value)

    def derivative(self: WaveformProtocol) -> WaveformProtocol:
        """Numerical derivative over the time axis (``np.gradient``, scaled by ``dt`` seconds).

        Raises:
            ValueError: If the waveform has fewer than 2 samples (``np.gradient``'s
                minimum for a first-order estimate).
        """
        sample_count = self.values.shape[0]
        if sample_count < 2:
            raise ValueError(
                f"CalcMixin.derivative requires at least 2 samples, got {sample_count}"
            )
        dt_seconds = float_seconds(self.dt)
        gradient = np.gradient(self.values, dt_seconds)
        return self._with_values(gradient)


__all__ = ["CalcMixin"]
