"""Unit tests for ``dsp/_correlation.py`` (``CorrelationMixin``).

Covers waveformDsp.md §Family contracts (``CorrelationMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.errors import WaveformCompatibilityError
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestAutoCorrelationOfWhiteNoiseIsApproximatelyADeltaFunction(unittest.TestCase):
    """§Compliance 1: autocorrelation of white noise ~= delta (lag-0 dominates)."""

    def test_lag_zero_is_one_and_dominates(self) -> None:
        n = 2000
        w = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=42, dt_seconds=0.001))

        auto_corr = w.auto_correlation(normalized=True)

        self.assertAlmostEqual(float(auto_corr.values[0]), 1.0, places=9)
        # Off-zero lags should be small relative to the lag-0 peak for white noise.
        self.assertTrue(np.all(np.abs(auto_corr.values[1:]) < 0.2))

    def test_result_length_matches_default_max_lag(self) -> None:
        n = 40
        w = _wrap(Waveform1D.white_noise(n, seed=1, dt_seconds=0.01))
        auto_corr = w.auto_correlation()
        self.assertEqual(len(auto_corr.values), n // 2 + 1)

    def test_custom_max_lag(self) -> None:
        n = 40
        w = _wrap(Waveform1D.white_noise(n, seed=1, dt_seconds=0.01))
        auto_corr = w.auto_correlation(max_lag=5)
        self.assertEqual(len(auto_corr.values), 6)

    def test_max_lag_clamped_to_sample_count_minus_one(self) -> None:
        n = 5
        w = _wrap(Waveform1D.white_noise(n, seed=1, dt_seconds=0.01))
        auto_corr = w.auto_correlation(max_lag=100)
        self.assertEqual(len(auto_corr.values), n)

    def test_negative_max_lag_raises(self) -> None:
        w = _wrap(Waveform1D.white_noise(10, seed=1, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.auto_correlation(max_lag=-1)


class TestAutoCorrelationEdgeCases(unittest.TestCase):
    """Zero-variance (constant) signals and empty input."""

    def test_nonzero_constant_signal_is_one_at_every_lag(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=5.0, dt_seconds=0.1))
        auto_corr = w.auto_correlation(normalized=True)
        np.testing.assert_allclose(auto_corr.values, np.ones(len(auto_corr.values)))

    def test_all_zero_signal_is_zero_at_every_lag(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=0.0, dt_seconds=0.1))
        auto_corr = w.auto_correlation(normalized=True)
        np.testing.assert_allclose(auto_corr.values, np.zeros(len(auto_corr.values)))

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.auto_correlation()

    def test_unnormalized_lag_zero_equals_signal_energy(self) -> None:
        values = [1.0, 2.0, 3.0, 2.0, 1.0]
        w = Waveform1D(values, dt_seconds=0.1)
        auto_corr = w.auto_correlation(normalized=False)
        expected_energy = sum(v * v for v in values)
        self.assertAlmostEqual(float(auto_corr.values[0]), expected_energy, places=9)


class TestCrossCorrelationDtMismatchRaises(unittest.TestCase):
    """Design constraint: dt mismatch -> ``WaveformCompatibilityError``."""

    def test_cross_correlation_dt_mismatch(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.cross_correlation(w2)

    def test_find_max_correlation_dt_mismatch(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.find_max_correlation(w2)


class TestCrossCorrelationBasics(unittest.TestCase):
    def test_full_mode_output_length(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 1.0, 1.0], dt_seconds=0.1)
        cross = w1.cross_correlation(w2)
        self.assertEqual(len(cross.values), 5)  # 3 + 3 - 1

    def test_identical_signals_peak_at_zero_lag_and_near_one(self) -> None:
        values = [1.0, 2.0, 3.0, 2.0, 1.0]
        w1 = Waveform1D(values, dt_seconds=0.1)
        w2 = Waveform1D(values, dt_seconds=0.1)
        cross = w1.cross_correlation(w2, normalized=True)
        center_index = len(cross.values) // 2
        self.assertEqual(int(np.argmax(cross.values)), center_index)
        self.assertAlmostEqual(float(cross.values[center_index]), 1.0, places=9)

    def test_normalized_bounds(self) -> None:
        w1 = Waveform1D([1.0, 3.0, 2.0, 4.0, 1.0], dt_seconds=0.1)
        w2 = Waveform1D([2.0, 1.0, 3.0, 1.0, 2.0], dt_seconds=0.1)
        cross = w1.cross_correlation(w2, normalized=True)
        self.assertTrue(np.all(cross.values >= -1.0 - 1e-9))
        self.assertTrue(np.all(cross.values <= 1.0 + 1e-9))

    def test_max_lag_trims_output(self) -> None:
        w1 = Waveform1D(list(range(20)), dt_seconds=0.1)
        w2 = Waveform1D(list(range(20)), dt_seconds=0.1)
        cross = w1.cross_correlation(w2, max_lag=3)
        self.assertEqual(len(cross.values), 7)  # lags -3..3

    def test_negative_max_lag_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.cross_correlation(w2, max_lag=-1)

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.cross_correlation(w2)


class TestFindMaxCorrelationKnownShiftRecoversExactLag(unittest.TestCase):
    """Acceptance criterion: known-shift lag recovery exact for k in {0, 3, 17}.

    ``other`` is built as ``np.roll(self.values, k)`` -- i.e.
    ``other[i] == self[i - k]`` (``other`` trails ``self`` by ``k``
    samples). Per this module's documented lag sign convention (scipy's
    native one), that yields ``lag_samples == -k``.
    """

    def _check_known_shift(self, k: int) -> None:
        n = 2000
        base = Waveform1D.white_noise(n, amplitude=1.0, seed=42, dt_seconds=0.001)
        w1 = _wrap(base)
        shifted_values = np.roll(base.values, k)
        w2 = Waveform1D(shifted_values, dt=base.dt, t0=base.t0)

        result = w1.find_max_correlation(w2)

        self.assertEqual(result.lag_samples, -k)
        self.assertAlmostEqual(result.lag_seconds, -k * 0.001, places=9)
        self.assertGreater(result.correlation, 0.95)

    def test_zero_shift(self) -> None:
        self._check_known_shift(0)

    def test_three_sample_shift(self) -> None:
        self._check_known_shift(3)

    def test_seventeen_sample_shift(self) -> None:
        self._check_known_shift(17)


class TestFindMaxCorrelationBasics(unittest.TestCase):
    def test_identical_signals_zero_lag_high_correlation(self) -> None:
        values = [1.0, 3.0, 2.0, 4.0, 1.0]
        w1 = Waveform1D(values, dt_seconds=0.1)
        w2 = Waveform1D(values, dt_seconds=0.1)
        result = w1.find_max_correlation(w2)
        self.assertEqual(result.lag_samples, 0)
        self.assertEqual(result.lag_seconds, 0.0)
        self.assertGreater(result.correlation, 0.9)

    def test_max_lag_restricts_search(self) -> None:
        n = 2000
        base = Waveform1D.white_noise(n, amplitude=1.0, seed=7, dt_seconds=0.001)
        w1 = _wrap(base)
        shifted_values = np.roll(base.values, 17)
        w2 = Waveform1D(shifted_values, dt=base.dt, t0=base.t0)

        restricted = w1.find_max_correlation(w2, max_lag=5)

        self.assertLessEqual(abs(restricted.lag_samples), 5)

    def test_negative_max_lag_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.find_max_correlation(w2, max_lag=-1)

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.find_max_correlation(w2)


if __name__ == "__main__":
    unittest.main()
