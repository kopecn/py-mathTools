"""Tests for the DSP mixin composition onto ``Waveform1D`` (waveformDsp.md
§Organization "Composition phasing", §Compliance 4).

This is the chunk-30 "compose" chunk's own test: it pins that all twelve
DSP mixins are composed onto the concrete ``Waveform1D`` class exactly once,
that the composed class remains concrete (no abstract methods left
unimplemented), that bare construction still succeeds, and that a method
from each mixin family is actually reachable and returns a correct,
non-``None`` result on a live instance -- the same kind of runtime check
that caught chunk 18's C3-linearization bug (mypy alone would not have).
"""

import unittest

import numpy as np

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
from math_tools.waveforms.waveform1d import Waveform1D

_EXPECTED_MIXINS = (
    CalcMixin,
    CorrelationMixin,
    EnvelopeMixin,
    SpectralMixin,
    FilteringMixin,
    PeakMixin,
    PhaseMixin,
    ResamplingMixin,
    TimeAlignmentMixin,
    TriggerMixin,
    WindowingMixin,
    ZeroCrossingMixin,
)


class TestMroComposesEveryMixinExactlyOnce(unittest.TestCase):
    def test_every_mixin_appears_exactly_once(self) -> None:
        mro = Waveform1D.__mro__
        for mixin in _EXPECTED_MIXINS:
            self.assertEqual(
                mro.count(mixin),
                1,
                f"{mixin.__name__} should appear exactly once in Waveform1D.__mro__, "
                f"found {mro.count(mixin)}",
            )


class TestComposedClassRemainsConcrete(unittest.TestCase):
    def test_no_abstract_methods_remain(self) -> None:
        self.assertEqual(Waveform1D.__abstractmethods__, frozenset())

    def test_bare_construction_succeeds(self) -> None:
        w = Waveform1D([1.0, 2.0])
        self.assertEqual(list(w.values), [1.0, 2.0])


class TestEveryDspFamilyIsCallableDirectlyOnWaveform1D(unittest.TestCase):
    """One smoke call per mixin family on a short sine, proving the method is
    reachable through the composed MRO and returns a correct, non-``None``
    result -- not just that mypy resolves the attribute."""

    def setUp(self) -> None:
        self.n = 200
        self.fs = 200.0
        self.w = Waveform1D.sine(
            self.n, frequency=10.0, amplitude=1.0, dt_seconds=1.0 / self.fs
        )

    def test_calc_derivative(self) -> None:
        result = self.w.derivative()
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n)

    def test_correlation_auto_correlation(self) -> None:
        result = self.w.auto_correlation()
        self.assertIsNotNone(result)
        self.assertGreater(len(result.values), 0)

    def test_envelope_amplitude_envelope(self) -> None:
        result = self.w.amplitude_envelope()
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n)

    def test_spectral_fft(self) -> None:
        spectrum = self.w.fft()
        self.assertIsNotNone(spectrum)
        peak_index = int(np.argmax(spectrum.magnitudes))
        self.assertAlmostEqual(spectrum.frequencies[peak_index], 10.0, delta=self.fs / self.n)

    def test_filtering_low_pass_filter(self) -> None:
        result = self.w.low_pass_filter(cutoff_hz=50.0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n)

    def test_peaks_detect_peaks(self) -> None:
        peaks = self.w.detect_peaks()
        self.assertIsNotNone(peaks)
        self.assertGreater(len(peaks), 0)

    def test_phase_instantaneous_phase(self) -> None:
        result = self.w.instantaneous_phase()
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n)

    def test_resampling_decimated(self) -> None:
        result = self.w.decimated(2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n // 2)

    def test_time_alignment_time_windows(self) -> None:
        windows = self.w.time_windows(window_duration=0.5)
        self.assertIsNotNone(windows)
        self.assertGreater(len(windows), 0)

    def test_trigger_detect_edge_triggers(self) -> None:
        from math_tools.waveforms.support import WaveformEdgeType

        events = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        self.assertIsNotNone(events)
        self.assertGreater(len(events), 0)

    def test_windowing_windowed(self) -> None:
        from math_tools.waveforms.support import WaveformWindowType

        result = self.w.windowed(WaveformWindowType.HANN)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.values), self.n)

    def test_zero_crossing_zero_crossings(self) -> None:
        crossings = self.w.zero_crossings()
        self.assertIsNotNone(crossings)
        self.assertGreater(len(crossings), 0)


if __name__ == "__main__":
    unittest.main()
