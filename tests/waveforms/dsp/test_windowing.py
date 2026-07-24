"""Unit tests for ``dsp/_windowing.py`` (``WindowingMixin``).

Covers waveformDsp.md §Family contracts (``WindowingMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np
from scipy.signal import get_window as scipy_get_window

from math_tools.waveforms.dsp import _spectral as spectral_module
from math_tools.waveforms.dsp import _windowing as windowing_module
from math_tools.waveforms.dsp._common import DEFAULT_KAISER_BETA
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.dsp._windowing import WindowingMixin
from math_tools.waveforms.support import WaveformWindowType
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


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


class TestWindowCoefficientsMatchScipyDirectly(unittest.TestCase):
    """§Gap 22 (chunk 55): coefficients were verified only for HANN; HAMMING,
    BLACKMAN, BARTLETT, and KAISER were checked only for shape, so a wrong
    ``_WINDOW_NAME_MAP`` entry (``_windowing.py:56``) would still pass. Pin the
    full coefficient array for every member against a direct
    ``scipy.signal.get_window`` call (symmetric convention)."""

    def test_hamming_matches_scipy(self) -> None:
        n = 33
        result = WindowingMixin.generate_window(WaveformWindowType.HAMMING, n)
        expected = scipy_get_window("hamming", n, fftbins=False)
        np.testing.assert_allclose(result, expected)

    def test_blackman_matches_scipy(self) -> None:
        n = 33
        result = WindowingMixin.generate_window(WaveformWindowType.BLACKMAN, n)
        expected = scipy_get_window("blackman", n, fftbins=False)
        np.testing.assert_allclose(result, expected)

    def test_bartlett_matches_scipy(self) -> None:
        n = 33
        result = WindowingMixin.generate_window(WaveformWindowType.BARTLETT, n)
        expected = scipy_get_window("bartlett", n, fftbins=False)
        np.testing.assert_allclose(result, expected)

    def test_kaiser_matches_scipy_with_shared_beta(self) -> None:
        n = 33
        result = WindowingMixin.generate_window(WaveformWindowType.KAISER, n)
        expected = scipy_get_window(("kaiser", DEFAULT_KAISER_BETA), n, fftbins=False)
        np.testing.assert_allclose(result, expected)

    def test_rectangular_matches_scipy(self) -> None:
        n = 33
        result = WindowingMixin.generate_window(WaveformWindowType.RECTANGULAR, n)
        expected = scipy_get_window("boxcar", n, fftbins=False)
        np.testing.assert_allclose(result, expected)


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
        w = Waveform1D([])
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

    def test_hann_processing_gain_matches_analytic_sqrt_3_over_8(self) -> None:
        """§Gap 22 (chunk 55): HANN's known-answer processing gain
        (``sqrt(3/8) ~= 0.6124``) was available but unpinned -- only the loose
        ``RECTANGULAR``-only known-answer test existed."""
        w = _wrap(Waveform1D.constant(1001, value=1.0, dt_seconds=0.001))
        gain = w.window_processing_gain(WaveformWindowType.HANN)
        self.assertAlmostEqual(gain, float(np.sqrt(3.0 / 8.0)), delta=1e-3)

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
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
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.windowed(WaveformWindowType.HANN)


class TestPeriodicConvention(unittest.TestCase):
    """Post-audit D-windowing-(c) / chunk 53: ``periodic=True`` pins scipy's
    default (``fftbins=True``) convention -- the one ``SpectralMixin``
    actually applies -- and ``periodic=False`` (default) keeps the existing
    symmetric convention unchanged."""

    def test_periodic_true_matches_scipy_default(self) -> None:
        n = 64
        coefficients = WindowingMixin.generate_window(WaveformWindowType.HANN, n, periodic=True)
        expected = scipy_get_window("hann", n)
        np.testing.assert_allclose(coefficients, expected)

    def test_periodic_false_matches_scipy_symmetric(self) -> None:
        n = 64
        coefficients = WindowingMixin.generate_window(WaveformWindowType.HANN, n, periodic=False)
        expected = scipy_get_window("hann", n, fftbins=False)
        np.testing.assert_allclose(coefficients, expected)

    def test_default_argument_is_symmetric_unchanged(self) -> None:
        n = 64
        default = WindowingMixin.generate_window(WaveformWindowType.HANN, n)
        symmetric = WindowingMixin.generate_window(WaveformWindowType.HANN, n, periodic=False)
        np.testing.assert_allclose(default, symmetric)


class TestGainHelpersDescribePeriodicConvention(unittest.TestCase):
    """Chunk 53 acceptance: the gain helpers, asked for ``periodic=True``,
    describe the exact window ``power_spectral_density``/``spectrogram``
    apply internally (``dsp/_spectral.py``'s ``_window_array``)."""

    def test_coherent_gain_periodic_matches_spectral_window(self) -> None:
        n = 128
        w = _wrap(Waveform1D.constant(n, value=1.0, dt_seconds=0.01))
        gain = w.window_coherent_gain(WaveformWindowType.HANN, periodic=True)
        spectral_window = spectral_module._window_array(WaveformWindowType.HANN, n)
        self.assertAlmostEqual(gain, float(np.mean(spectral_window)), places=12)

    def test_processing_gain_periodic_matches_spectral_window(self) -> None:
        n = 128
        w = _wrap(Waveform1D.constant(n, value=1.0, dt_seconds=0.01))
        gain = w.window_processing_gain(WaveformWindowType.HANN, periodic=True)
        spectral_window = spectral_module._window_array(WaveformWindowType.HANN, n)
        self.assertAlmostEqual(gain, float(np.sqrt(np.mean(spectral_window**2))), places=12)

    def test_default_periodic_false_is_unchanged_from_before_chunk_53(self) -> None:
        n = 128
        w = _wrap(Waveform1D.constant(n, value=1.0, dt_seconds=0.01))
        default_gain = w.window_coherent_gain(WaveformWindowType.HANN)
        symmetric_gain = w.window_coherent_gain(WaveformWindowType.HANN, periodic=False)
        self.assertEqual(default_gain, symmetric_gain)


class TestSharedKaiserBeta(unittest.TestCase):
    """Chunk 53 acceptance: one shared Kaiser beta constant backs both
    ``_windowing.py`` and ``_spectral.py`` -- not two independent literals."""

    def test_both_modules_reference_the_same_constant(self) -> None:
        self.assertEqual(windowing_module.DEFAULT_KAISER_BETA, DEFAULT_KAISER_BETA)
        self.assertEqual(spectral_module.DEFAULT_KAISER_BETA, DEFAULT_KAISER_BETA)

    def test_kaiser_windows_agree_at_matching_length_and_convention(self) -> None:
        n = 64
        windowing_kaiser = WindowingMixin.generate_window(
            WaveformWindowType.KAISER, n, periodic=True
        )
        spectral_kaiser = spectral_module._window_array(WaveformWindowType.KAISER, n)
        np.testing.assert_allclose(windowing_kaiser, spectral_kaiser)


if __name__ == "__main__":
    unittest.main()
