"""``TimeAlignmentMixin``: time-shift alignment, synchronization, and
time-based windowing/segmentation for ``Waveform1D``.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``TimeAlignmentMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-TimeAlignment.swift``.

Backing: correlation-lag search via ``CorrelationMixin.find_max_correlation``
(``aligned``'s ``CORRELATION`` method, ``time_lag``); plain
``PrecisionTimestamp``/``PrecisionTimeInterval`` arithmetic for everything
else (``aligned``'s ``START_TIME`` method, ``synchronize``, ``time_windows``,
``time_segments``) -- per waveformDsp.md's family-contract table.

**Exception to the no-sibling-imports rule ("via CorrelationMixin"), same
shape as the risk chunk 19 flagged for ``support.py``.** This mixin needs
``CorrelationMixin.find_max_correlation`` (``dsp/_correlation.py``) but must
not import that module directly (waveformDsp.md §Organization / §Compliance
2: no sibling mixin imports, enforced by
``tests/test_package_layering.py::test_dsp_mixins_do_not_import_sibling_mixins``).
Instead it types against a small local ``Protocol`` extension
(``_CorrelatingWaveform`` below) declaring only the
``find_max_correlation`` signature it calls; any host that actually
composes both mixins (``Waveform1D`` from the compose chunk onward, and this
module's own test subclass) satisfies it structurally. This mirrors chunk
19's own resolution for importing ``WaveformTimeLag``/``WaveformAlignmentMethod``
from ``waveforms/support.py`` below -- ``support.py`` imports
``waveforms/waveform1d.py``, which (until the chunk-30 compose step) never
imports back into ``dsp/``, so no cycle exists yet; flagged here again per
chunk 26's own instructions, not worked around silently.

``aligned``/``time_lag``/``synchronize`` are not detectors (waveformDsp.md
§Numerical conventions): they raise ``ValueError``/``WaveformCompatibilityError``
(naming the requirement) rather than silently returning an empty/degenerate
result, with one deliberate exception -- ``time_lag`` returns ``None``
(per its own ``WaveformTimeLag | None`` signature) when the strongest
correlation match found carries exactly zero magnitude, since "no
meaningful lag exists" is an expected outcome for that method, not an
error. ``time_windows``/``time_segments`` likewise raise rather than
returning `[]` when the input is too short for even one window/segment.

``synchronize`` intentionally does **not** resample mismatched-rate inputs
the way the Swift reference's ``synchronize(_:to:method:resampleToCommonRate:)``
does -- chunk 26 §Out of scope: "Resampling to a common rate" is
``ResamplingMixin.resampled_to_match``'s job (chunk 25), not this one's. All
inputs to ``synchronize`` must already share the same ``dt``.

Imports only ``dsp/_protocol.py``/``dsp/_common.py`` and
``waveforms/support.py`` (for ``WaveformAlignmentMethod``/``WaveformTimeLag``)
-- no sibling mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class TimeAlignmentMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformAlignmentMethod, WaveformTimeLag


class _CorrelatingWaveform(WaveformProtocol, Protocol):
    """``WaveformProtocol`` extended with the single ``CorrelationMixin`` method
    (``find_max_correlation``) this mixin's ``CORRELATION``-method ``aligned``/
    ``time_lag`` need -- declared locally instead of importing
    ``dsp/_correlation.py`` (see the module docstring)."""

    def find_max_correlation(
        self, other: WaveformProtocol, max_lag: int | None = None
    ) -> WaveformTimeLag: ...


def _end_t0(waveform: WaveformProtocol) -> PrecisionTimestamp:
    """The timestamp of ``waveform``'s last sample (``t0`` when ``sample_count <= 1``)."""
    # int(...): `.shape[0]` on an `npt.NDArray[Any]` (the protocol's `values` type)
    # resolves to `Any` under mypy strict; left uncast, `waveform.dt * (sample_count - 1)`
    # and the `+` below would each become `Any`, tripping "Returning Any from function
    # declared to return PrecisionTimestamp" (no-any-return) at the return statement.
    sample_count = int(waveform.values.shape[0])
    if sample_count <= 1:
        return waveform.t0
    return waveform.t0 + waveform.dt * (sample_count - 1)


def _correlating_time_lag(
    waveform: _CorrelatingWaveform, to: WaveformProtocol, max_lag: int | None
) -> WaveformTimeLag | None:
    """Shared implementation for ``TimeAlignmentMixin.time_lag`` and ``aligned``'s
    ``CORRELATION`` branch -- a module-level helper (not a same-class ``self.time_lag(...)``
    call) so both stay consistent without a mixin calling its own sibling method, matching
    every other DSP mixin's internal-sharing convention (e.g. ``dsp/_resampling.py``'s
    ``_resample_to_frequency``).

    **Deliberately ``t0``-aware, unlike ``CorrelationMixin.find_max_correlation``.**
    ``find_max_correlation`` is a pure value-domain measure: it correlates
    ``waveform.values``/``to.values`` and never looks at either waveform's ``t0``
    (see ``dsp/_correlation.py``'s module docstring). That is exactly right for a
    "how similar are these sample arrays" question, but wrong for a method named
    ``time_lag`` living in a mixin about time-axis reasoning -- two waveforms whose
    ``t0``s already differ can have identical values (raw lag 0) yet clearly occur
    at different real times. This function adds the existing ``t0`` offset (rounded
    to the nearest sample) to the raw value-domain lag, producing the real-world
    sample/second offset between the two waveforms' matching features. That
    combination is also what makes ``aligned``'s ``CORRELATION`` method a true round
    trip: shifting ``t0`` by ``-lag_samples * dt`` always drives a second call to
    this function back to lag 0 (chunk 26's pinned acceptance criterion) -- a purely
    value-domain lag could not guarantee that once the two waveforms' ``t0``s
    already differ, since shifting ``t0`` never touches the values ``find_max_
    correlation`` looks at.

    Returns ``None`` when the strongest value-domain match found carries exactly
    zero correlation magnitude (see ``time_lag``'s docstring).
    """
    raw = waveform.find_max_correlation(to, max_lag=max_lag)
    if raw.correlation == 0.0:
        return None
    dt_seconds = float_seconds(waveform.dt)
    existing_offset_samples = round((waveform.t0 - to.t0).seconds_as_float / dt_seconds)
    combined_samples = existing_offset_samples + raw.lag_samples
    return WaveformTimeLag(
        lag_samples=combined_samples,
        lag_seconds=combined_samples * dt_seconds,
        correlation=raw.correlation,
    )


class TimeAlignmentMixin:
    """Adds time-shift alignment, synchronization, and time windowing/segmentation
    to a ``WaveformProtocol`` host."""

    def aligned(
        self: _CorrelatingWaveform,
        to: WaveformProtocol,
        method: WaveformAlignmentMethod = WaveformAlignmentMethod.CORRELATION,
    ) -> WaveformProtocol:
        """A copy of ``self`` with ``t0`` shifted to align with ``to``; ``values``/``dt``
        unchanged.

        ``WaveformAlignmentMethod.START_TIME`` simply adopts ``to.t0``.
        ``WaveformAlignmentMethod.CORRELATION`` (default) shifts by the
        lag ``time_lag(to)`` detects -- exact integer-sample arithmetic
        (``self.dt * lag_samples``), not a float-seconds round trip -- so
        that a subsequent ``time_lag(to)`` on the result lands back at lag
        0. When ``time_lag`` finds no qualifying peak (returns ``None``),
        ``self`` is returned unshifted.

        Raises:
            WaveformCompatibilityError: If ``method`` is ``CORRELATION`` and
                ``to.dt`` differs from ``self.dt``.
            ValueError: If ``method`` is ``CORRELATION`` and either waveform
                has no samples.
        """
        if method is WaveformAlignmentMethod.START_TIME:
            return self._with_t0(self.values, to.t0)
        if method is WaveformAlignmentMethod.CORRELATION:
            lag = _correlating_time_lag(self, to, max_lag=None)
            if lag is None:
                return self._with_values(self.values)
            offset = self.dt * (-lag.lag_samples)
            return self._with_t0(self.values, self.t0 + offset)
        # pragma: no cover -- WaveformAlignmentMethod is exhaustive above
        raise ValueError(f"TimeAlignmentMixin.aligned: unsupported method {method!r}")

    def time_lag(
        self: _CorrelatingWaveform, to: WaveformProtocol, max_lag: int | None = None
    ) -> WaveformTimeLag | None:
        """The real-world time lag between ``self`` and ``to``'s matching features:
        the existing ``t0`` offset between them plus the value-domain lag
        ``CorrelationMixin.find_max_correlation`` detects between their sample
        arrays (see the module-level ``_correlating_time_lag`` docstring for why
        this is ``t0``-aware, unlike ``find_max_correlation`` itself). ``None`` when
        the strongest match found carries exactly zero correlation magnitude (e.g.
        one of the waveforms carries no correlatable structure) -- an expected
        "nothing to align on" outcome here, not an error.

        Raises:
            WaveformCompatibilityError: If ``to.dt`` differs from ``self.dt``.
            ValueError: If either waveform has no samples, or ``max_lag`` is negative.
        """
        return _correlating_time_lag(self, to, max_lag)

    @classmethod
    def synchronize(cls, waveforms: Sequence[WaveformProtocol]) -> list[WaveformProtocol]:
        """The common overlapping time span of ``waveforms``, sliced from each input.

        Every result shares the same ``dt``, the same ``t0`` (the overlap's
        start), and the same sample count. Unlike the Swift reference, this
        does not resample mismatched-rate inputs first (see the module
        docstring) -- every input must already share the same ``dt``.

        Returns ``[]`` for an empty ``waveforms`` sequence.

        Raises:
            WaveformCompatibilityError: If the waveforms do not all share the same ``dt``.
            ValueError: If any waveform has no samples, or the waveforms share
                no overlapping time span.
        """
        if not waveforms:
            return []

        reference_dt = waveforms[0].dt
        for waveform in waveforms:
            if waveform.dt != reference_dt:
                raise WaveformCompatibilityError(
                    f"TimeAlignmentMixin.synchronize: dt mismatch "
                    f"({reference_dt!r} vs {waveform.dt!r})"
                )
            if waveform.values.shape[0] == 0:
                raise ValueError(
                    "TimeAlignmentMixin.synchronize requires every waveform to have "
                    "at least 1 sample"
                )

        overlap_start = max(waveform.t0 for waveform in waveforms)
        overlap_end = min(_end_t0(waveform) for waveform in waveforms)
        if overlap_end < overlap_start:
            raise ValueError(
                "TimeAlignmentMixin.synchronize: waveforms share no overlapping time span"
            )
        overlap_sample_count = round((overlap_end - overlap_start) / reference_dt) + 1

        synchronized: list[WaveformProtocol] = []
        for waveform in waveforms:
            start_index = round((overlap_start - waveform.t0) / reference_dt)
            segment = waveform.values[start_index : start_index + overlap_sample_count]
            synchronized.append(waveform._with_t0(segment, overlap_start))
        return synchronized

    def time_windows(
        self: WaveformProtocol, window_duration: float, overlap: float = 0.0
    ) -> list[WaveformProtocol]:
        """Overlapping fixed-length windows of ``window_duration`` seconds, stepping by
        ``window_duration * (1 - overlap)``; only full-length windows are kept (a
        trailing remainder shorter than a full window is dropped).

        Raises:
            ValueError: If ``window_duration <= 0``, ``overlap`` is outside
                ``[0.0, 1.0)``, or the waveform has fewer samples than one window
                needs.
        """
        if window_duration <= 0.0:
            raise ValueError(
                f"TimeAlignmentMixin.time_windows: window_duration must be > 0, "
                f"got {window_duration}"
            )
        if not 0.0 <= overlap < 1.0:
            raise ValueError(
                f"TimeAlignmentMixin.time_windows: overlap must be in [0.0, 1.0), "
                f"got {overlap}"
            )
        dt_seconds = float_seconds(self.dt)
        window_samples = max(1, round(window_duration / dt_seconds))
        sample_count = self.values.shape[0]
        if window_samples > sample_count:
            raise ValueError(
                f"TimeAlignmentMixin.time_windows requires at least {window_samples} samples "
                f"for a {window_duration}s window at dt={dt_seconds}s, got {sample_count}"
            )
        step_samples = max(1, round(window_samples * (1.0 - overlap)))

        windows: list[WaveformProtocol] = []
        start = 0
        while start + window_samples <= sample_count:
            segment = self.values[start : start + window_samples]
            windows.append(self._with_t0(segment, self.t0 + self.dt * start))
            start += step_samples
        return windows

    def time_segments(
        self: WaveformProtocol, boundaries: Sequence[float]
    ) -> list[WaveformProtocol]:
        """Non-overlapping segments split at ``boundaries`` (strictly increasing float
        seconds from ``t0``); an empty ``boundaries`` returns ``[self]`` unsplit.

        Raises:
            ValueError: If the waveform has no samples, or ``boundaries`` is not
                strictly increasing and within the waveform's open time span
                (``(0, duration_seconds)``), or two boundaries round to the same
                sample index (a zero-length segment).
        """
        sample_count = self.values.shape[0]
        if sample_count == 0:
            raise ValueError("TimeAlignmentMixin.time_segments requires at least 1 sample")
        dt_seconds = float_seconds(self.dt)
        duration_seconds = (sample_count - 1) * dt_seconds

        boundary_indices: list[int] = []
        previous_seconds = 0.0
        for boundary_seconds in boundaries:
            if not (previous_seconds < boundary_seconds < duration_seconds):
                raise ValueError(
                    f"TimeAlignmentMixin.time_segments: boundaries must be strictly "
                    f"increasing and within (0, {duration_seconds}), got {boundary_seconds}"
                )
            index = round(boundary_seconds / dt_seconds)
            if boundary_indices and index <= boundary_indices[-1]:
                raise ValueError(
                    "TimeAlignmentMixin.time_segments: boundaries round to a "
                    "zero-length segment"
                )
            boundary_indices.append(index)
            previous_seconds = boundary_seconds

        split_points = [0, *boundary_indices, sample_count]
        segments: list[WaveformProtocol] = []
        for start, stop in zip(split_points, split_points[1:], strict=False):
            segment = self.values[start:stop]
            segments.append(self._with_t0(segment, self.t0 + self.dt * start))
        return segments


__all__ = ["TimeAlignmentMixin"]
