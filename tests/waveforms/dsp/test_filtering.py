"""Unit tests for ``dsp/_filtering.py`` (``FilteringMixin``).

Covers waveformDsp.md §Family contracts (``FilteringMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin via a local test subclass
``class _W(FilteringMixin, Waveform1D): pass`` (the pattern every DSP mixin
chunk's tests use, per chunk 18).
"""

import unittest

import numpy as np
import numpy.typing as npt

from math_tools.waveforms.dsp._filtering import FilteringMixin
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformFilterType
from math_tools.waveforms.waveform1d import Waveform1D


class _W(FilteringMixin, Waveform1D):
    pass


def _wrap(base: WaveformProtocol) -> _W:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``_W`` (see ``test_calc.py``).

    Needed after any call that returns via ``_with_values`` (a bare ``Waveform1D``,
    which does not carry ``FilteringMixin``'s methods) -- construct a fresh ``_W``
    directly instead when building test fixtures from raw arrays.
    """
    return _W(base.values, dt=base.dt, t0=base.t0)


def _rfft_magnitude_at(
    values: npt.NDArray[np.float64], dt_seconds: float, target_hz: float
) -> float:
    """Chunk-local rfft magnitude nearest ``target_hz`` (no dependency on ``SpectralMixin``)."""
    n = values.shape[0]
    spectrum = np.fft.rfft(values)
    frequencies = np.fft.rfftfreq(n, d=dt_seconds)
    index = int(np.argmin(np.abs(frequencies - target_hz)))
    return float(np.abs(spectrum[index]))


class TestLowPassFilterAttenuatesHighFrequency(unittest.TestCase):
    """§Compliance 1: 5 Hz + 200 Hz mix (fs=2kHz) -> low_pass_filter(50) attenuates the
    200 Hz component by >= 40 dB while the 5 Hz amplitude survives (rtol 5e-2)."""

    def test_attenuation_and_passband_survival(self) -> None:
        n = 4000
        fs = 2000.0
        dt_seconds = 1.0 / fs
        low = Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=dt_seconds)
        high = Waveform1D.sine(n, frequency=200.0, amplitude=1.0, dt_seconds=dt_seconds)
        mixed = _W(low.values + high.values, dt_seconds=dt_seconds)

        filtered = mixed.low_pass_filter(cutoff_hz=50.0, order=4)

        original_5 = _rfft_magnitude_at(mixed.values, dt_seconds, 5.0)
        filtered_5 = _rfft_magnitude_at(filtered.values, dt_seconds, 5.0)
        self.assertAlmostEqual(filtered_5 / original_5, 1.0, delta=5e-2)

        original_200 = _rfft_magnitude_at(mixed.values, dt_seconds, 200.0)
        filtered_200 = _rfft_magnitude_at(filtered.values, dt_seconds, 200.0)
        attenuation_db = 20.0 * np.log10(original_200 / filtered_200)
        self.assertGreaterEqual(attenuation_db, 40.0)


class TestHighPassFilterAttenuatesLowFrequency(unittest.TestCase):
    """§Compliance 1: high-pass mirror of the low-pass test."""

    def test_attenuation_and_passband_survival(self) -> None:
        n = 4000
        fs = 2000.0
        dt_seconds = 1.0 / fs
        low = Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=dt_seconds)
        high = Waveform1D.sine(n, frequency=200.0, amplitude=1.0, dt_seconds=dt_seconds)
        mixed = _W(low.values + high.values, dt_seconds=dt_seconds)

        filtered = mixed.high_pass_filter(cutoff_hz=50.0, order=4)

        original_200 = _rfft_magnitude_at(mixed.values, dt_seconds, 200.0)
        filtered_200 = _rfft_magnitude_at(filtered.values, dt_seconds, 200.0)
        self.assertAlmostEqual(filtered_200 / original_200, 1.0, delta=5e-2)

        original_5 = _rfft_magnitude_at(mixed.values, dt_seconds, 5.0)
        filtered_5 = _rfft_magnitude_at(filtered.values, dt_seconds, 5.0)
        attenuation_db = 20.0 * np.log10(original_5 / filtered_5)
        self.assertGreaterEqual(attenuation_db, 40.0)


class TestBandPassFilterKeepsOnlyInBandTone(unittest.TestCase):
    """§Compliance 1: band-pass keeps only the in-band tone."""

    def test_only_in_band_tone_survives(self) -> None:
        n = 4000
        fs = 2000.0
        dt_seconds = 1.0 / fs
        below = Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=dt_seconds)
        in_band = Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=dt_seconds)
        above = Waveform1D.sine(n, frequency=200.0, amplitude=1.0, dt_seconds=dt_seconds)
        mixed = _W(below.values + in_band.values + above.values, dt_seconds=dt_seconds)

        filtered = mixed.band_pass_filter(low_hz=20.0, high_hz=100.0, order=4)

        original_in_band = _rfft_magnitude_at(mixed.values, dt_seconds, 50.0)
        filtered_in_band = _rfft_magnitude_at(filtered.values, dt_seconds, 50.0)
        self.assertAlmostEqual(filtered_in_band / original_in_band, 1.0, delta=5e-2)

        for out_of_band_hz in (5.0, 200.0):
            original = _rfft_magnitude_at(mixed.values, dt_seconds, out_of_band_hz)
            filtered_mag = _rfft_magnitude_at(filtered.values, dt_seconds, out_of_band_hz)
            attenuation_db = 20.0 * np.log10(original / filtered_mag)
            self.assertGreaterEqual(attenuation_db, 40.0)


class TestFilteredDispatcher(unittest.TestCase):
    """``filtered`` dispatches to the same Butterworth design as the named methods."""

    def test_low_pass_matches_dedicated_method(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=200.0, dt_seconds=1.0 / 2000.0))
        via_dispatch = w.filtered(WaveformFilterType.LOW_PASS, cutoff_hz=50.0, order=4)
        via_dedicated = w.low_pass_filter(cutoff_hz=50.0, order=4)
        np.testing.assert_allclose(via_dispatch.values, via_dedicated.values, rtol=0.0, atol=1e-12)

    def test_band_stop_is_reachable_only_via_dispatch(self) -> None:
        n = 4000
        fs = 2000.0
        dt_seconds = 1.0 / fs
        in_band = Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=dt_seconds)
        out_of_band = Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=dt_seconds)
        mixed = _W(in_band.values + out_of_band.values, dt_seconds=dt_seconds)

        filtered = mixed.filtered(WaveformFilterType.BAND_STOP, low_hz=20.0, high_hz=100.0, order=4)

        original_in_band = _rfft_magnitude_at(mixed.values, dt_seconds, 50.0)
        filtered_in_band = _rfft_magnitude_at(filtered.values, dt_seconds, 50.0)
        attenuation_db = 20.0 * np.log10(original_in_band / filtered_in_band)
        self.assertGreaterEqual(attenuation_db, 40.0)

        original_out = _rfft_magnitude_at(mixed.values, dt_seconds, 5.0)
        filtered_out = _rfft_magnitude_at(filtered.values, dt_seconds, 5.0)
        self.assertAlmostEqual(filtered_out / original_out, 1.0, delta=5e-2)

    def test_missing_cutoff_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.001))
        with self.assertRaises(ValueError):
            w.filtered(WaveformFilterType.LOW_PASS)

    def test_missing_band_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.001))
        with self.assertRaises(ValueError):
            w.filtered(WaveformFilterType.BAND_PASS, low_hz=10.0)


class TestNyquistViolationRaises(unittest.TestCase):
    """waveformDsp.md's Butterworth designs validate cutoffs against Nyquist."""

    def test_low_pass_cutoff_at_nyquist_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.01))
        nyquist = w.sampling_frequency_hz / 2.0
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=nyquist)

    def test_low_pass_cutoff_above_nyquist_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.01))
        nyquist = w.sampling_frequency_hz / 2.0
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=nyquist * 2.0)

    def test_high_pass_cutoff_above_nyquist_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.01))
        nyquist = w.sampling_frequency_hz / 2.0
        with self.assertRaises(ValueError):
            w.high_pass_filter(cutoff_hz=nyquist * 1.5)

    def test_band_pass_high_above_nyquist_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.01))
        nyquist = w.sampling_frequency_hz / 2.0
        with self.assertRaises(ValueError):
            w.band_pass_filter(low_hz=1.0, high_hz=nyquist * 1.5)

    def test_band_pass_low_above_high_raises(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.band_pass_filter(low_hz=100.0, high_hz=50.0)


class TestMovingAverageFilter(unittest.TestCase):
    """§Compliance 1: moving average of a constant is identity."""

    def test_constant_is_identity(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=3.0, dt_seconds=0.1))
        filtered = w.moving_average_filter(window_size=5)
        np.testing.assert_allclose(filtered.values, w.values, rtol=0.0, atol=1e-12)

    def test_smooths_a_noisy_signal_at_interior_points(self) -> None:
        rng = np.random.default_rng(3)
        n = 500
        noisy = _W(np.full(n, 1.0) + rng.normal(scale=0.5, size=n), dt_seconds=0.01)

        filtered = noisy.moving_average_filter(window_size=25)

        interior = slice(50, -50)
        self.assertLess(
            float(np.std(filtered.values[interior])), float(np.std(noisy.values[interior]))
        )

    def test_invalid_window_size_raises(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.moving_average_filter(window_size=0)


class TestExponentialFilter(unittest.TestCase):
    """Exponential (EMA) smoothing: alpha=1 is identity; smaller alpha smooths."""

    def test_alpha_one_is_identity(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=3.0, dt_seconds=0.01))
        filtered = w.exponential_filter(alpha=1.0)
        np.testing.assert_allclose(filtered.values, w.values, rtol=0.0, atol=1e-12)

    def test_first_sample_unchanged(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=3.0, dt_seconds=0.01))
        filtered = w.exponential_filter(alpha=0.2)
        self.assertEqual(filtered.values[0], w.values[0])

    def test_smooths_a_step(self) -> None:
        values = np.concatenate([np.zeros(20), np.ones(20)])
        w = _W(values, dt_seconds=0.01)
        filtered = w.exponential_filter(alpha=0.3)
        # The step response should not jump immediately to 1.0 the sample after the step.
        self.assertLess(float(filtered.values[20]), 1.0)

    def test_invalid_alpha_raises(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.exponential_filter(alpha=0.0)
        with self.assertRaises(ValueError):
            w.exponential_filter(alpha=1.5)

    def test_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.exponential_filter(alpha=0.5)


class TestSavitzkyGolayFilter(unittest.TestCase):
    """§Compliance 1: savgol on a noiseless cubic reproduces it (atol 1e-8)."""

    def test_cubic_is_reproduced(self) -> None:
        n = 101
        x = np.linspace(-1.0, 1.0, n)
        cubic = 2.0 * x**3 - 3.0 * x**2 + 0.5 * x + 1.0
        w = _W(cubic, dt_seconds=0.01)

        filtered = w.savitzky_golay_filter(window_length=11, polyorder=3, deriv=0)

        np.testing.assert_allclose(filtered.values, cubic, rtol=0.0, atol=1e-8)

    def test_invalid_window_length_raises(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.savitzky_golay_filter(window_length=4, polyorder=2)  # even window

    def test_polyorder_too_large_raises(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.savitzky_golay_filter(window_length=5, polyorder=5)

    def test_deriv_exceeds_polyorder_raises(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.savitzky_golay_filter(window_length=5, polyorder=2, deriv=3)


class TestWhittakerHendersonFilter(unittest.TestCase):
    """§Compliance 1: lam -> 0 approximates identity; large lam approximates a linear trend."""

    def test_small_lambda_approximates_identity(self) -> None:
        rng = np.random.default_rng(11)
        n = 200
        noisy = _W(np.full(n, 2.0) + rng.normal(scale=0.1, size=n), dt_seconds=0.05)

        smoothed = noisy.whittaker_henderson_filter(lam=1e-9, order=2)

        np.testing.assert_allclose(smoothed.values, noisy.values, rtol=1e-4, atol=1e-4)

    def test_large_lambda_approximates_linear_trend(self) -> None:
        n = 200
        dt_seconds = 0.05
        rng = np.random.default_rng(13)
        ramp = Waveform1D.linear_ramp(n, start_value=0.0, end_value=10.0, dt_seconds=dt_seconds)
        noisy = _W(ramp.values + rng.normal(scale=0.2, size=n), dt_seconds=dt_seconds)

        smoothed = noisy.whittaker_henderson_filter(lam=1e8, order=2)

        # A degree-1 polynomial least-squares fit to the noisy ramp is the reference
        # "linear trend"; the heavily-smoothed result should track it closely away
        # from the very ends.
        coeffs = np.polyfit(np.arange(n), noisy.values, 1)
        trend = np.polyval(coeffs, np.arange(n))
        interior = slice(10, -10)
        np.testing.assert_allclose(
            smoothed.values[interior], trend[interior], rtol=0.0, atol=0.2
        )

    def test_invalid_order_raises(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        with self.assertRaises(ValueError):
            w.whittaker_henderson_filter(lam=1.0, order=0)

    def test_too_few_samples_raises(self) -> None:
        w = _W([1.0, 2.0])
        with self.assertRaises(ValueError):
            w.whittaker_henderson_filter(lam=1.0, order=2)


class TestFrequencyResponse(unittest.TestCase):
    """``frequency_response`` returns a ``WaveformSpectrum`` sampling the filter's
    magnitude/phase response over frequency."""

    def test_low_pass_passes_dc_and_attenuates_high_frequency(self) -> None:
        w = _wrap(Waveform1D.constant(1000, value=1.0, dt_seconds=1.0 / 2000.0))
        response = w.frequency_response(
            WaveformFilterType.LOW_PASS, cutoff_hz=50.0, order=4, num_points=512
        )

        self.assertAlmostEqual(float(response.magnitudes[0]), 1.0, delta=1e-2)
        near_nyquist_index = -1
        self.assertLess(float(response.magnitudes[near_nyquist_index]), 0.01)

    def test_result_lengths_match_num_points(self) -> None:
        w = _wrap(Waveform1D.constant(1000, value=1.0, dt_seconds=1.0 / 2000.0))
        response = w.frequency_response(
            WaveformFilterType.HIGH_PASS, cutoff_hz=50.0, order=4, num_points=128
        )
        self.assertEqual(len(response.frequencies), 128)
        self.assertEqual(len(response.magnitudes), 128)
        self.assertEqual(len(response.phases), 128)


if __name__ == "__main__":
    unittest.main()
