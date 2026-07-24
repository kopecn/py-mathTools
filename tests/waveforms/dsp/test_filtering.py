"""Unit tests for ``dsp/_filtering.py`` (``FilteringMixin``).

Covers waveformDsp.md §Family contracts (``FilteringMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np
import numpy.typing as npt
from scipy.signal import butter, freqz, lfilter, savgol_filter

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformFilterType
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``).

    Needed after any call that returns via ``_with_values`` (a bare ``Waveform1D``,
    which does not carry ``FilteringMixin``'s methods) -- construct a fresh ``Waveform1D``
    directly instead when building test fixtures from raw arrays.
    """
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


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
        mixed = Waveform1D(low.values + high.values, dt_seconds=dt_seconds)

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
        mixed = Waveform1D(low.values + high.values, dt_seconds=dt_seconds)

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
        mixed = Waveform1D(below.values + in_band.values + above.values, dt_seconds=dt_seconds)

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
        mixed = Waveform1D(in_band.values + out_of_band.values, dt_seconds=dt_seconds)

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
        noisy = Waveform1D(np.full(n, 1.0) + rng.normal(scale=0.5, size=n), dt_seconds=0.01)

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
        w = Waveform1D(values, dt_seconds=0.01)
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
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.exponential_filter(alpha=0.5)


class TestSavitzkyGolayFilter(unittest.TestCase):
    """§Compliance 1: savgol on a noiseless cubic reproduces it (atol 1e-8)."""

    def test_cubic_is_reproduced(self) -> None:
        n = 101
        x = np.linspace(-1.0, 1.0, n)
        cubic = 2.0 * x**3 - 3.0 * x**2 + 0.5 * x + 1.0
        w = Waveform1D(cubic, dt_seconds=0.01)

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
        noisy = Waveform1D(np.full(n, 2.0) + rng.normal(scale=0.1, size=n), dt_seconds=0.05)

        smoothed = noisy.whittaker_henderson_filter(lam=1e-9, order=2)

        np.testing.assert_allclose(smoothed.values, noisy.values, rtol=1e-4, atol=1e-4)

    def test_large_lambda_approximates_linear_trend(self) -> None:
        n = 200
        dt_seconds = 0.05
        rng = np.random.default_rng(13)
        ramp = Waveform1D.linear_ramp(n, start_value=0.0, end_value=10.0, dt_seconds=dt_seconds)
        noisy = Waveform1D(ramp.values + rng.normal(scale=0.2, size=n), dt_seconds=dt_seconds)

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
        w = Waveform1D([1.0, 2.0])
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

    def test_band_pass_and_band_stop_and_phases_match_direct_scipy(self) -> None:
        """§Gap 6 (chunk 55): ``phases`` and BAND_PASS/BAND_STOP pinned against a
        direct ``scipy.signal.freqz`` call on the same ``butter``-designed coefficients."""
        w = _wrap(Waveform1D.constant(1000, value=1.0, dt_seconds=1.0 / 2000.0))
        fs = w.sampling_frequency_hz

        for filter_type, btype, kwargs in (
            (WaveformFilterType.BAND_PASS, "bandpass", {"low_hz": 20.0, "high_hz": 100.0}),
            (WaveformFilterType.BAND_STOP, "bandstop", {"low_hz": 20.0, "high_hz": 100.0}),
        ):
            with self.subTest(filter_type=filter_type):
                response = w.frequency_response(filter_type, order=4, num_points=256, **kwargs)
                b, a = butter(4, [20.0, 100.0], btype=btype, fs=fs)
                expected_freq, expected_response = freqz(b, a, worN=256, fs=fs)
                np.testing.assert_allclose(response.frequencies, expected_freq)
                np.testing.assert_allclose(response.magnitudes, np.abs(expected_response))
                np.testing.assert_allclose(response.phases, np.angle(expected_response))


class TestCausalFilterUsesLfilterNotFiltfilt(unittest.TestCase):
    """§Gap 1 (chunk 55): ``causal=True`` selects a single-pass ``scipy.signal.lfilter``
    (matched exactly, coefficient-for-coefficient), and differs from the zero-phase
    ``filtfilt`` default -- pinning waveformDsp.md §Numerical conventions' ``causal=``
    flag, previously never exercised by any test in the suite."""

    def test_low_pass_causal_matches_direct_lfilter(self) -> None:
        n = 1000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=200.0, dt_seconds=1.0 / fs))

        causal = w.low_pass_filter(cutoff_hz=50.0, order=4, causal=True)

        b, a = butter(4, 50.0, btype="low", fs=fs)
        expected = lfilter(b, a, w.values)
        np.testing.assert_allclose(causal.values, expected, rtol=0.0, atol=1e-12)

    def test_causal_differs_from_zero_phase_default(self) -> None:
        n = 1000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=200.0, dt_seconds=1.0 / fs))

        causal = w.low_pass_filter(cutoff_hz=50.0, order=4, causal=True)
        zero_phase = w.low_pass_filter(cutoff_hz=50.0, order=4, causal=False)

        self.assertFalse(np.allclose(causal.values, zero_phase.values))

    def test_high_pass_causal_matches_direct_lfilter(self) -> None:
        n = 1000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=5.0, dt_seconds=1.0 / fs))

        causal = w.high_pass_filter(cutoff_hz=50.0, order=4, causal=True)

        b, a = butter(4, 50.0, btype="high", fs=fs)
        expected = lfilter(b, a, w.values)
        np.testing.assert_allclose(causal.values, expected, rtol=0.0, atol=1e-12)

    def test_band_pass_causal_matches_direct_lfilter(self) -> None:
        n = 1000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, dt_seconds=1.0 / fs))

        causal = w.band_pass_filter(low_hz=20.0, high_hz=100.0, order=4, causal=True)

        b, a = butter(4, [20.0, 100.0], btype="bandpass", fs=fs)
        expected = lfilter(b, a, w.values)
        np.testing.assert_allclose(causal.values, expected, rtol=0.0, atol=1e-12)

    def test_filtered_dispatch_honors_causal(self) -> None:
        n = 1000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=200.0, dt_seconds=1.0 / fs))

        via_dispatch = w.filtered(WaveformFilterType.LOW_PASS, cutoff_hz=50.0, causal=True)
        via_dedicated = w.low_pass_filter(cutoff_hz=50.0, causal=True)
        np.testing.assert_allclose(via_dispatch.values, via_dedicated.values, rtol=0.0, atol=1e-12)


class TestValidateOrderRaisesForEveryButterworthMethod(unittest.TestCase):
    """§Gap 4 (chunk 55): ``order < 1`` (the raise-don't-clamp policy's load-bearing
    path, ``_filtering.py:63``) was never triggered for any Butterworth method."""

    def test_low_pass_order_zero_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=10.0, order=0)

    def test_high_pass_order_zero_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.high_pass_filter(cutoff_hz=10.0, order=0)

    def test_band_pass_order_zero_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.band_pass_filter(low_hz=5.0, high_hz=10.0, order=0)

    def test_filtered_order_zero_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.filtered(WaveformFilterType.LOW_PASS, cutoff_hz=10.0, order=0)

    def test_frequency_response_order_zero_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.frequency_response(WaveformFilterType.LOW_PASS, cutoff_hz=10.0, order=0)

    def test_negative_order_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=10.0, order=-1)


class TestValidateCutoffLowerBoundRaises(unittest.TestCase):
    """§Gap 5 (chunk 55): ``cutoff_hz <= 0`` (``_filtering.py:68``) was untested --
    only the upper (Nyquist) bound was exercised before this chunk."""

    def test_low_pass_zero_cutoff_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=0.0)

    def test_low_pass_negative_cutoff_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.low_pass_filter(cutoff_hz=-10.0)

    def test_high_pass_zero_cutoff_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.high_pass_filter(cutoff_hz=0.0)

    def test_band_pass_zero_low_raises(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.band_pass_filter(low_hz=0.0, high_hz=10.0)


class TestExponentialFilterClosedForm(unittest.TestCase):
    """§Gap 7 (chunk 55): pin the closed-form recursion ``y[i] = alpha*x[i] +
    (1-alpha)*y[i-1]`` at a specific interior ``i`` -- the existing suite only
    checked ``alpha=1.0`` (identity) and ``values[20] < 1.0`` (a bound a swapped
    ``alpha``/``1-alpha`` would also satisfy)."""

    def test_recursion_matches_hand_computed_value_at_i5(self) -> None:
        values = [1.0, 4.0, 2.0, 9.0, 5.0, 7.0, 3.0]
        alpha = 0.3
        w = Waveform1D(values, dt_seconds=0.1)

        filtered = w.exponential_filter(alpha=alpha)

        expected = values[0]
        for x in values[1:6]:
            expected = alpha * x + (1.0 - alpha) * expected
        self.assertAlmostEqual(float(filtered.values[5]), expected, places=12)

    def test_swapped_alpha_would_not_match(self) -> None:
        """Sanity check that the closed-form pin above actually distinguishes a
        swapped alpha/(1-alpha) -- guards against a vacuously-passing assertion."""
        values = [1.0, 4.0, 2.0, 9.0, 5.0, 7.0, 3.0]
        alpha = 0.3
        w = Waveform1D(values, dt_seconds=0.1)

        filtered = w.exponential_filter(alpha=alpha)

        wrong_expected = values[0]
        for x in values[1:6]:
            wrong_expected = (1.0 - alpha) * x + alpha * wrong_expected
        self.assertNotAlmostEqual(float(filtered.values[5]), wrong_expected, places=6)


class TestSavitzkyGolayDerivativeUnits(unittest.TestCase):
    """§Gap 2 (chunk 55): ``deriv > 0`` is the only place ``delta=dt_seconds`` is
    applied (``_filtering.py:356``) -- a wrong ``delta`` silently returns
    per-sample rather than per-second derivatives, and no existing test set
    ``deriv > 0``."""

    def test_matches_direct_scipy_call_with_delta(self) -> None:
        """Pins that the mixin forwards exactly ``delta=dt_seconds`` to scipy --
        a direct-scipy-reference comparison (design constraint 1)."""
        n = 500
        dt_seconds = 1.0 / 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=dt_seconds))

        result = w.savitzky_golay_filter(window_length=11, polyorder=3, deriv=1)

        expected = savgol_filter(
            np.asarray(w.values), 11, 3, deriv=1, delta=dt_seconds
        )
        np.testing.assert_allclose(result.values, expected, rtol=0.0, atol=1e-12)

    def test_interior_matches_analytic_derivative_in_per_second_units(self) -> None:
        """A wrong ``delta`` (e.g. the unscaled per-sample default of 1.0) would
        return values off by a factor of ``dt_seconds`` (~2e-4 here) -- this
        analytic comparison to ``2*pi*f*A*cos(2*pi*f*t)`` fails loudly in that case."""
        n = 1000
        fs = 2000.0
        dt_seconds = 1.0 / fs
        frequency = 50.0
        amplitude = 1.0
        w = _wrap(
            Waveform1D.sine(n, frequency=frequency, amplitude=amplitude, dt_seconds=dt_seconds)
        )

        result = w.savitzky_golay_filter(window_length=11, polyorder=3, deriv=1)

        t = np.arange(n, dtype=np.float64) * dt_seconds
        analytic = 2.0 * np.pi * frequency * amplitude * np.cos(2.0 * np.pi * frequency * t)
        interior = slice(20, -20)
        np.testing.assert_allclose(
            result.values[interior], analytic[interior], rtol=2e-2, atol=1.0
        )


if __name__ == "__main__":
    unittest.main()
