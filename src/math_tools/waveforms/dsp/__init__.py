"""DSP mixin substrate for ``Waveform1D`` (protocol + shared helpers).

See ``.claude/specs/waveformDsp.md``. This package holds the per-family
mixin modules (chunks 18-30) plus the shared ``WaveformProtocol`` typing
contract (``_protocol.py``) and cross-mixin helpers (``_common.py``). As of
chunk 30, all twelve mixins below are composed onto
``waveforms.waveform1d.Waveform1D`` (see that module's docstring); this
package still exposes each mixin individually for direct
mypy-strict-checkable/testable use.
"""

from math_tools.waveforms.dsp._calc import CalcMixin
from math_tools.waveforms.dsp._correlation import CorrelationMixin
from math_tools.waveforms.dsp._envelope import EnvelopeMixin
from math_tools.waveforms.dsp._filtering import FilteringMixin
from math_tools.waveforms.dsp._peaks import PeakMixin
from math_tools.waveforms.dsp._phase import PhaseMixin
from math_tools.waveforms.dsp._resampling import ResamplingMixin
from math_tools.waveforms.dsp._spectral import SpectralMixin
from math_tools.waveforms.dsp._time_alignment import TimeAlignmentMixin
from math_tools.waveforms.dsp._triggers import TriggerMixin
from math_tools.waveforms.dsp._windowing import WindowingMixin
from math_tools.waveforms.dsp._zero_crossings import ZeroCrossingMixin

__all__ = [
    "CalcMixin",
    "CorrelationMixin",
    "EnvelopeMixin",
    "FilteringMixin",
    "PeakMixin",
    "PhaseMixin",
    "ResamplingMixin",
    "SpectralMixin",
    "TimeAlignmentMixin",
    "TriggerMixin",
    "WindowingMixin",
    "ZeroCrossingMixin",
]
