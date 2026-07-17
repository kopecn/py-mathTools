"""Unit tests for ``dsp/_windowing.py`` (``WindowingMixin``).

Covers waveformDsp.md §Family contracts (``WindowingMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin via a local test subclass
``class _W(WindowingMixin, Waveform1D): pass`` (the pattern every DSP mixin
chunk's tests use).
"""

import unittest

import numpy as np

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.dsp._windowing import WindowingMixin
from math_tools.waveforms.support import WaveformWindowType
from math_tools.waveforms.waveform1d import Waveform1D


class _W(WindowingMixin, Waveform1D):
    pass


def _wrap(base: WaveformProtocol) -> _W:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``_W`` (see ``test_calc.py``)."""
    return _W(base.values, dt=base.dt, t0=base.t0)


class TestGenerateWindowEveryMember(unittest.TestCase):
    """Acceptance criterion: every ``WaveformWindowType`` member generates without error."""

    def test_all_members_generate_correct_length(self) -> None:
        length = 32
        for window in WaveformWindowType:
            coefficients = WindowingMixin.generate_window(window, length)
            self.assertEqual(coefficients.shape, (length,))

    def test_zero_length_raises(self) -> None:
        with self.assertRaises(ValueError):
            WindowingMixin.generate_window(WaveformWindowType.HANN, 0)

    def test_negative_length_raises(self) -> None:
        with self.assertRaises(ValueError):
            WindowingMixin.generate_window(WaveformWindowType.HANN, -5)

    def test_single_sample_is_one(self) -> None:
        for window in WaveformWindowType:
            coefficients = WindowingMixin.generate_window(window, 1)
            np.testing.assert_allclose(coefficients, [1.0])


class TestHannShape(unittest.TestCase):
    """Acceptance criterion: HANN endpoints ~= 0 and midpoint ~= 1."""

    def test_endpoints_near_zero_and_midpoint_near_one(self) -> None:
        length = 101  # odd -> exact midpoint sample
        coefficients = WindowingMixin.generate_window(WaveformWindowType.HANN, length)
        self.assertAlmostEqual(float(coefficients[0]), 0.0, places=9)
        self.assertAlmostEqual(float(coefficients[-1]), 0.0, places=9)
        self.assertAlmostEqual(float(coefficients[length // 2]), 1.0, places=9)


class TestWindowCoherentGain(unittest.TestCase):
    """Acceptance criterion: coherent gain of HANN ~= 0.5 (rtol 1e-2, finite length)."""

    def test_hann_coherent_gain(self) -> None:
        w = _wrap(Waveform1D.constant(1000, value=1.0, dt_seconds=0.1))
        gain = w.window_coherent_gain(WaveformWindowType.HANN)
        self.assertAlmostEqual(gain, 0.5, delta=0.5 * 1e-2)

    def test_rectangular_coherent_gain_is_one(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        gain = w.window_coherent_gain(WaveformWindowType.RECTANGULAR)
        self.assertEqual(gain, 1.0)

    def test_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.window_coherent_gain(WaveformWindowType.HANN)


class TestWindowProcessingGain(unittest.TestCase):
    def test_rectangular_processing_gain_is_one(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        gain = w.window_processing_gain(WaveformWindowType.RECTANGULAR)
        self.assertEqual(gain, 1.0)

    def test_hann_processing_gain_between_zero_and_one(self) -> None:
        w = _wrap(Waveform1D.constant(1000, value=1.0, dt_seconds=0.1))
        gain = w.window_processing_gain(WaveformWindowType.HANN)
        self.assertLess(gain, 1.0)
        self.assertGreater(gain, 0.0)

    def test_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.window_processing_gain(WaveformWindowType.HANN)


class TestWindowed(unittest.TestCase):
    """Acceptance criterion: RECTANGULAR ``windowed`` is identity."""

    def test_rectangular_is_identity(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, amplitude=2.0, dt_seconds=0.001))
        windowed = w.windowed(WaveformWindowType.RECTANGULAR)
        np.testing.assert_allclose(windowed.values, w.values)
        self.assertEqual(windowed.dt, w.dt)
        self.assertEqual(windowed.t0, w.t0)

    def test_hann_tapers_endpoints_to_near_zero(self) -> None:
        w = _wrap(Waveform1D.constant(101, value=1.0, dt_seconds=0.1))
        windowed = w.windowed(WaveformWindowType.HANN)
        self.assertAlmostEqual(float(windowed.values[0]), 0.0, places=9)
        self.assertAlmostEqual(float(windowed.values[-1]), 0.0, places=9)
        self.assertAlmostEqual(float(windowed.values[50]), 1.0, places=9)

    def test_metadata_preserved(self) -> None:
        w = _wrap(Waveform1D.constant(20, value=1.0, dt_seconds=0.25, t0_seconds=5.0))
        windowed = w.windowed(WaveformWindowType.HAMMING)
        self.assertEqual(windowed.dt, w.dt)
        self.assertEqual(windowed.t0, w.t0)

    def test_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.windowed(WaveformWindowType.HANN)


if __name__ == "__main__":
    unittest.main()
