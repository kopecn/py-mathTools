"""``WaveformProtocol``: the structural contract every DSP mixin depends on.

See ``.claude/specs/waveformDsp.md`` §Organization. Mixins are stateless and
touch only the public ``Waveform1D`` surface (``values``, ``dt``, ``t0``,
constructors); declaring that surface as a ``Protocol`` (rather than each
mixin inheriting ``Waveform1D`` directly) lets every mixin be independently
mypy-strict-checkable without a circular import back into
``waveforms/waveform1d.py`` (which imports nothing from ``dsp/``).

References only ``PrecisionTimeInterval``/``PrecisionTimestamp`` and numpy
typing -- never a concrete mixin or ``Waveform1D`` itself.

Deviation from the chunk doc's literal code block: ``_with_values`` returns
``WaveformProtocol`` (self-type), not the quoted forward reference
``"Waveform1D"`` shown there -- importing ``Waveform1D`` here (even under
``TYPE_CHECKING``) is exactly what the hard constraint above forbids, and an
unimported bare ``"Waveform1D"`` annotation is a mypy-strict "Name is not
defined" error under ``from __future__ import annotations``. Returning the
protocol itself is structurally equivalent for every caller (a mixin only
ever needs the result to satisfy ``WaveformProtocol`` again) and
``Waveform1D._with_values -> Waveform1D`` remains a valid (covariant)
implementation of this method.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy.typing as npt

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp


@runtime_checkable
class WaveformProtocol(Protocol):
    """Structural surface a DSP mixin needs from its host ``Waveform1D``."""

    @property
    def values(self) -> npt.NDArray[Any]: ...

    @property
    def dt(self) -> PrecisionTimeInterval: ...

    @property
    def t0(self) -> PrecisionTimestamp: ...

    @property
    def sampling_frequency_hz(self) -> float: ...

    def _with_values(self, values: npt.NDArray[Any]) -> WaveformProtocol: ...


__all__ = ["WaveformProtocol"]
