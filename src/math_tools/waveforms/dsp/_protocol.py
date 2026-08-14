"""``WaveformProtocol``: the structural contract every DSP mixin depends on.

See ``.claude/specs/waveformDsp.md`` §Organization. Mixins are stateless and
touch only the public ``Waveform1D`` surface (``values``, ``dt``, ``t0``,
constructors); declaring that surface as a ``Protocol`` (rather than each
mixin inheriting ``Waveform1D`` directly) lets every mixin be independently
mypy-strict-checkable without a circular import back into
``waveforms/waveform1d.py`` (which imports nothing from ``dsp/``).

References only ``PrecisionTimeInterval``/``PrecisionTimestamp`` and numpy
typing -- never a concrete mixin or ``Waveform1D`` itself.

**Mixins type their ``self`` as this Protocol; they do not nominally
inherit it** (i.e. ``def integrate(self: WaveformProtocol, ...)``, not
``class CalcMixin(WaveformProtocol)``). Nominal inheritance was the
original design and is broken at runtime: explicitly subclassing a
``Protocol`` turns its stub property bodies (``...``, so the getter
returns ``None``) into concrete inherited implementations, and when a test
composes ``class _W(SomeMixin, Waveform1D)``, C3 linearization places that
inherited stub ahead of ``Waveform1D``'s real property -- ``self.values``
silently returns ``None`` instead of the sample array. Self-typing avoids
this because the mixin then carries no runtime base beyond ``object``, so
composing it with ``Waveform1D`` never pulls ``WaveformProtocol`` into the
MRO. See ``.claude/specs/waveformDsp.md`` §Organization (fixed in chunk 18,
semver 0.0.3) for the full account.

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

**Added in chunk 25 (semver 0.0.4): ``_with_axis``.** Every mixin through
chunk 24 only ever produces results that share ``self``'s ``dt`` -- so
``_with_values`` (same ``dt``/``t0``, new samples) was a sufficient factory.
``ResamplingMixin`` (``dsp/_resampling.py``) is the first family whose
results have a genuinely different sample spacing (``decimated``/
``interpolated``/``resampled``/``polyphase_resampled`` all compute a new
``dt``), so the structural contract needs a second factory that also takes
the new ``dt``. ``t0`` is deliberately not a parameter -- every
``ResamplingMixin`` method keeps ``t0`` unchanged (waveformDsp.md §Family
contracts (``ResamplingMixin``): "New ``t0`` is unchanged") -- so there is
no caller yet that needs to vary it too; add that only when one does.

**Added in chunk 26 (semver 0.0.5): ``_with_t0``.** ``TimeAlignmentMixin``
(``dsp/_time_alignment.py``) is the first family whose results carry a
genuinely different *start time* than their source: ``aligned`` shifts
``t0`` by a detected (or reference) offset, ``synchronize`` slices every
input down to a shared overlap window starting at a common ``t0``, and
``time_windows``/``time_segments`` each cut out a sub-span starting partway
through ``self``. None of these change ``dt``, so ``_with_axis`` (which
pins ``t0`` to ``self``'s) does not fit; a third, single-purpose factory
completes the same-dt / same-dt-and-t0 / same-t0 triangle
(``_with_values``: same ``dt``, same ``t0``; ``_with_axis``: new ``dt``,
same ``t0``; ``_with_t0``: same ``dt``, new ``t0``) rather than overloading
either existing factory's meaning.
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

    def _with_axis(
        self, values: npt.NDArray[Any], dt: PrecisionTimeInterval
    ) -> WaveformProtocol: ...

    def _with_t0(self, values: npt.NDArray[Any], t0: PrecisionTimestamp) -> WaveformProtocol: ...


__all__ = ["WaveformProtocol"]
