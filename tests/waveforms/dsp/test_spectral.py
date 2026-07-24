"""Unit tests for ``dsp/_spectral.py`` (``SpectralMixin``).

Covers waveformDsp.md §Family contracts (``SpectralMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np
from scipy.signal import get_window, welch
from scipy.signal import spectrogram as scipy_spectrogram

from math_tools.waveforms.dsp import _spectral as spectral_module
from math_tools.waveforms.dsp._common import DEFAULT_KAISER_BETA
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.dsp._spectral import _mel_filterbank
from math_tools.waveforms.dsp._windowing import WindowingMixin
from math_tools.waveforms.support import WaveformPSDScaling, WaveformWindowType
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestFftPeakBin(unittest.TestCase):
    """§Compliance 1: fft of a pure 10 Hz sine (fs=1kHz, n=1000) peaks at the 10 Hz bin."""

    def test_peak_at_10hz(self) -> None:
        n = 1000
        fs = 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=10.0, amplitude=1.0, dt_seconds=1.0 / fs))

        spectrum = w.fft()

        peak_index = int(np.argmax(spectrum.magnitudes))
        self.assertAlmostEqual(float(spectrum.frequencies[peak_index]), 10.0, places=6)

    def test_frequency_axis_length_matches_rfft_convention(self) -> None:
        n = 256
        w = _wrap(Waveform1D.sine(n, frequency=5.0, dt_seconds=0.01))
        spectrum = w.fft()
        self.assertEqual(len(spectrum.frequencies), n // 2 + 1)
        self.assertEqual(len(spectrum.magnitudes), n // 2 + 1)
        self.assertEqual(len(spectrum.phases), n // 2 + 1)

    def test_minimum_length_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.fft()

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.fft()


class TestFftParsevalSanity(unittest.TestCase):
    """§Compliance 1: Parseval's theorem holds for the returned one-sided magnitudes."""

    def test_parseval_relation_holds(self) -> None:
        n = 512  # even, so the one-sided reconstruction weighting below is exact
        w = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=7, dt_seconds=0.01))

        spectrum = w.fft()
        # One-sided reconstruction: sum(x^2) == (1/N) * (|X[0]|^2 + |X[N/2]|^2
        # + 2 * sum(|X[1..N/2-1]|^2)) for even N.
        mag_sq = spectrum.magnitudes**2
        reconstructed = (mag_sq[0] + mag_sq[-1] + 2.0 * np.sum(mag_sq[1:-1])) / n

        time_domain_energy = float(np.sum(w.values**2))
        self.assertAlmostEqual(reconstructed / time_domain_energy, 1.0, delta=1e-6)


class TestPowerSpectralDensityOfWhiteNoiseIsFlat(unittest.TestCase):
    """§Compliance 1: PSD of white noise is flat within a loose band."""

    def test_psd_is_approximately_flat(self) -> None:
        n = 20_000
        w = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=11, dt_seconds=1.0 / 2000.0))

        spectrum = w.power_spectral_density(nperseg=512)

        # Exclude DC; white-noise PSD should vary loosely around its mean once
        # enough segments have been averaged (Welch's method).
        interior = spectrum.magnitudes[1:]
        mean_power = float(np.mean(interior))
        relative_deviation = float(np.std(interior)) / mean_power
        self.assertLess(relative_deviation, 0.5)

    def test_result_length_matches_frequency_axis(self) -> None:
        w = _wrap(Waveform1D.white_noise(1000, amplitude=1.0, seed=3, dt_seconds=0.01))
        spectrum = w.power_spectral_density(nperseg=128)
        self.assertEqual(len(spectrum.magnitudes), len(spectrum.frequencies))
        self.assertTrue(np.all(spectrum.phases == 0.0))

    def test_minimum_length_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.power_spectral_density()

    def test_nperseg_exceeding_sample_count_raises(self) -> None:
        w = _wrap(Waveform1D.sine(50, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.power_spectral_density(nperseg=100)


class TestSpectrogramOfChirpIsMonotone(unittest.TestCase):
    """§Compliance 1: spectrogram of a chirp has a monotonically increasing
    argmax-frequency per time frame."""

    def test_peak_frequency_increases_with_time(self) -> None:
        n = 4000
        fs = 4000.0
        w = _wrap(
            Waveform1D.chirp(
                n, start_frequency=50.0, end_frequency=500.0, amplitude=1.0, dt_seconds=1.0 / fs
            )
        )

        spec = w.spectrogram(nperseg=256, overlap=0.75)

        peak_freqs = spec.frequencies[np.argmax(spec.magnitudes, axis=1)]
        # Trim the first/last couple of frames (window-edge artifacts) and allow a
        # small negative tolerance (one frequency bin) for quantization noise.
        interior = peak_freqs[2:-2]
        freq_resolution = float(spec.frequencies[1] - spec.frequencies[0])
        diffs = np.diff(interior)
        self.assertTrue(np.all(diffs >= -freq_resolution))
        self.assertGreater(interior[-1], interior[0])

    def test_result_shape(self) -> None:
        w = _wrap(Waveform1D.sine(2000, frequency=10.0, dt_seconds=0.001))
        spec = w.spectrogram(nperseg=256, overlap=0.5)
        self.assertEqual(spec.magnitudes.shape, (len(spec.times), len(spec.frequencies)))

    def test_minimum_length_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.spectrogram()

    def test_invalid_overlap_raises(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.spectrogram(overlap=1.0)
        with self.assertRaises(ValueError):
            w.spectrogram(overlap=-0.1)

    def test_nperseg_exceeding_sample_count_raises(self) -> None:
        w = _wrap(Waveform1D.sine(50, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.spectrogram(nperseg=100)


class TestMelFilterbankRowsSumToOne(unittest.TestCase):
    """§Compliance 1: mel filterbank rows sum ~= 1 where fully inside the band."""

    def test_rows_sum_to_approximately_one(self) -> None:
        frequency_bins = np.linspace(0.0, 500.0, 257)
        filterbank, mel_centers = _mel_filterbank(
            frequency_bins_hz=frequency_bins,
            n_mels=20,
            min_frequency_hz=0.0,
            max_frequency_hz=500.0,
        )
        row_sums = np.sum(filterbank, axis=1)
        np.testing.assert_allclose(row_sums, np.ones(20), rtol=1e-6, atol=1e-9)
        self.assertEqual(len(mel_centers), 20)


class TestMelSpectrogram(unittest.TestCase):
    """§Compliance 1: mel_spectrogram round-trips sanely through the FFT/mel pipeline."""

    def test_result_shape(self) -> None:
        w = _wrap(Waveform1D.sine(2000, frequency=50.0, dt_seconds=1.0 / 2000.0))
        mel_spec = w.mel_spectrogram(n_mels=10, nperseg=256, overlap=0.5)
        self.assertEqual(mel_spec.magnitudes.shape, (len(mel_spec.times), 10))
        self.assertEqual(len(mel_spec.mel_frequencies), 10)

    def test_magnitudes_are_nonnegative(self) -> None:
        w = _wrap(Waveform1D.white_noise(1000, amplitude=1.0, seed=5, dt_seconds=0.01))
        mel_spec = w.mel_spectrogram(n_mels=8, nperseg=128)
        self.assertTrue(np.all(mel_spec.magnitudes >= -1e-9))

    def test_n_mels_less_than_one_raises(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.mel_spectrogram(n_mels=0)

    def test_minimum_length_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.mel_spectrogram()

    def test_inverted_frequency_band_raises(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.mel_spectrogram(min_frequency_hz=100.0, max_frequency_hz=10.0)


class TestSpectralFeaturesOfSine(unittest.TestCase):
    """§Compliance 1: spectral centroid of the 10 Hz sine ~= 10 Hz (rtol 5e-2)."""

    def test_centroid_matches_sine_frequency(self) -> None:
        n = 1000
        fs = 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=10.0, amplitude=1.0, dt_seconds=1.0 / fs))

        features = w.spectral_features()

        self.assertAlmostEqual(features.centroid, 10.0, delta=10.0 * 5e-2)

    def test_spread_is_nonnegative(self) -> None:
        w = _wrap(Waveform1D.white_noise(1000, amplitude=1.0, seed=9, dt_seconds=0.01))
        features = w.spectral_features()
        self.assertGreaterEqual(features.spread, 0.0)

    def test_rolloff_within_nyquist_range(self) -> None:
        w = _wrap(Waveform1D.sine(1000, frequency=10.0, dt_seconds=0.001))
        features = w.spectral_features()
        self.assertGreaterEqual(features.rolloff, 0.0)
        self.assertLessEqual(features.rolloff, w.nyquist_frequency_hz)

    def test_flatness_in_unit_range(self) -> None:
        w = _wrap(Waveform1D.white_noise(1000, amplitude=1.0, seed=13, dt_seconds=0.01))
        features = w.spectral_features()
        self.assertGreaterEqual(features.flatness, 0.0)
        self.assertLessEqual(features.flatness, 1.0 + 1e-9)

    def test_minimum_length_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.spectral_features()

    def test_invalid_rolloff_fraction_raises(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.spectral_features(rolloff_fraction=0.0)
        with self.assertRaises(ValueError):
            w.spectral_features(rolloff_fraction=1.5)


class TestPsdScalingParameter(unittest.TestCase):
    """§Gap 8 (chunk 55): ``scaling: WaveformPSDScaling`` (``_spectral.py:232``) was
    never passed by any test -- pin both members against a direct
    ``scipy.signal.welch`` call and confirm they diverge materially."""

    def test_density_matches_direct_scipy_call(self) -> None:
        n = 4000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=1.0 / fs))
        window_array = spectral_module._window_array(WaveformWindowType.HANN, 512)

        result = w.power_spectral_density(nperseg=512, scaling=WaveformPSDScaling.DENSITY)

        _, expected = welch(
            np.asarray(w.values), fs=fs, window=window_array, nperseg=512, scaling="density"
        )
        np.testing.assert_allclose(result.magnitudes, expected)

    def test_spectrum_matches_direct_scipy_call(self) -> None:
        n = 4000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=1.0 / fs))
        window_array = spectral_module._window_array(WaveformWindowType.HANN, 512)

        result = w.power_spectral_density(nperseg=512, scaling=WaveformPSDScaling.SPECTRUM)

        _, expected = welch(
            np.asarray(w.values), fs=fs, window=window_array, nperseg=512, scaling="spectrum"
        )
        np.testing.assert_allclose(result.magnitudes, expected)

    def test_density_and_spectrum_diverge_materially(self) -> None:
        n = 4000
        fs = 2000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, amplitude=1.0, dt_seconds=1.0 / fs))

        density = w.power_spectral_density(nperseg=512, scaling=WaveformPSDScaling.DENSITY)
        spectrum = w.power_spectral_density(nperseg=512, scaling=WaveformPSDScaling.SPECTRUM)

        peak_ratio = float(np.max(spectrum.magnitudes) / np.max(density.magnitudes))
        # Observed ratio for this nperseg/fs combination is ~5.9x -- assert it is
        # far from 1.0 so a `scaling` parameter that silently no-ops would fail.
        self.assertGreater(peak_ratio, 2.0)


class TestSpectralWindowVariedToKaiser(unittest.TestCase):
    """§Gap 9 (chunk 55): ``window: WaveformWindowType`` (``_spectral.py:231,268,292``)
    was never varied from ``HANN`` in any test -- the KAISER branch of
    ``_window_array``/``_scipy_window_spec`` (``get_window`` with an explicit beta
    tuple) was unreached."""

    def test_power_spectral_density_kaiser_matches_direct_scipy(self) -> None:
        n = 2000
        fs = 1000.0
        w = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=5, dt_seconds=1.0 / fs))
        kaiser_array = get_window(("kaiser", DEFAULT_KAISER_BETA), 256)

        result = w.power_spectral_density(window=WaveformWindowType.KAISER, nperseg=256)

        _, expected = welch(np.asarray(w.values), fs=fs, window=kaiser_array, nperseg=256)
        np.testing.assert_allclose(result.magnitudes, expected)

    def test_spectrogram_kaiser_matches_direct_scipy(self) -> None:
        n = 2000
        fs = 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=50.0, dt_seconds=1.0 / fs))
        kaiser_array = get_window(("kaiser", DEFAULT_KAISER_BETA), 256)

        result = w.spectrogram(window=WaveformWindowType.KAISER, nperseg=256, overlap=0.5)

        expected_f, expected_t, expected_sxx = scipy_spectrogram(
            np.asarray(w.values),
            fs=fs,
            window=kaiser_array,
            nperseg=256,
            noverlap=128,
            mode="magnitude",
        )
        np.testing.assert_allclose(result.frequencies, expected_f)
        np.testing.assert_allclose(result.times, expected_t)
        np.testing.assert_allclose(result.magnitudes, expected_sxx.T)


class TestMelSpectrogramConcentratesEnergyInTonalBand(unittest.TestCase):
    """§Gap 10 (chunk 55): mel magnitudes for a pure tone should concentrate in the
    mel band nearest the tone's frequency, not merely be non-negative of the right
    shape (the existing coverage before this chunk)."""

    def test_1khz_tone_dominates_its_nearest_mel_band(self) -> None:
        n = 8000
        fs = 8000.0
        w = _wrap(Waveform1D.sine(n, frequency=1000.0, amplitude=1.0, dt_seconds=1.0 / fs))

        mel_spec = w.mel_spectrogram(n_mels=40, nperseg=512, overlap=0.5)

        mean_per_mel_band = np.mean(mel_spec.magnitudes, axis=0)
        peak_band_index = int(np.argmax(mean_per_mel_band))
        peak_band_frequency = float(mel_spec.mel_frequencies[peak_band_index])

        self.assertAlmostEqual(peak_band_frequency, 1000.0, delta=100.0)
        energy_fraction_at_peak = float(
            mean_per_mel_band[peak_band_index] / np.sum(mean_per_mel_band)
        )
        self.assertGreater(energy_fraction_at_peak, 0.5)


class TestSpectralFeaturesKnownAnswerTwoTone(unittest.TestCase):
    """§Gap 11 (chunk 55): a two-tone signal with exact-bin-resolved frequencies
    (no spectral leakage) gives hand-derivable centroid/spread/rolloff/flatness --
    closing the range-check-only coverage that a swapped mean or a power-vs-
    magnitude weighting would previously have passed.

    ``n=1000``, ``fs=1000`` gives 1 Hz bin resolution; ``f1=10 Hz`` (bin 10,
    amplitude 1.0 -> magnitude ~500) and ``f2=100 Hz`` (bin 100, amplitude 3.0
    -> magnitude ~1500) are each an exact integer number of periods, so (up to
    floating-point noise ~1e-10 relative) all spectral energy is concentrated
    in exactly those two bins.
    """

    def setUp(self) -> None:
        n = 1000
        fs = 1000.0
        dt_seconds = 1.0 / fs
        tone_low = Waveform1D.sine(n, frequency=10.0, amplitude=1.0, dt_seconds=dt_seconds)
        tone_high = Waveform1D.sine(n, frequency=100.0, amplitude=3.0, dt_seconds=dt_seconds)
        self.w = Waveform1D(tone_low.values + tone_high.values, dt_seconds=dt_seconds)
        # Magnitude-weighted-mean-frequency closed form for two dominant bins
        # (m1 ~= 500 at 10 Hz, m2 ~= 1500 at 100 Hz):
        self.expected_centroid = (10.0 * 500.0 + 100.0 * 1500.0) / 2000.0
        self.expected_spread = float(
            np.sqrt(
                (500.0 * (10.0 - self.expected_centroid) ** 2
                 + 1500.0 * (100.0 - self.expected_centroid) ** 2)
                / 2000.0
            )
        )

    def test_centroid_matches_hand_derived_weighted_mean(self) -> None:
        features = self.w.spectral_features()
        self.assertAlmostEqual(features.centroid, self.expected_centroid, places=6)

    def test_spread_matches_hand_derived_weighted_std(self) -> None:
        features = self.w.spectral_features()
        self.assertAlmostEqual(features.spread, self.expected_spread, places=6)

    def test_rolloff_lands_at_the_second_tone_bin(self) -> None:
        # Cumulative magnitude reaches 25% of total at bin 10 (500/2000), then
        # stays flat until it jumps to 100% at bin 100 (2000/2000) -- so the
        # default 95%-rolloff must land exactly on the 100 Hz bin.
        features = self.w.spectral_features()
        self.assertAlmostEqual(features.rolloff, 100.0, places=6)

    def test_flatness_matches_independent_geomean_over_arithmean(self) -> None:
        """Flatness has no scipy reference; derive it independently from the raw
        FFT magnitude array (following the method's own documented definition)
        rather than by calling any private helper of the implementation."""
        values = np.asarray(self.w.values, dtype=np.float64)
        magnitudes = np.abs(np.fft.rfft(values))
        nonzero = magnitudes[magnitudes > 0.0]
        expected_flatness = float(np.exp(np.mean(np.log(nonzero))) / np.mean(magnitudes))

        features = self.w.spectral_features()

        self.assertAlmostEqual(features.flatness, expected_flatness, places=9)
        # Sanity: this two-tone signal is strongly tonal, so flatness should be
        # near zero -- catches a geomean/arithmean swap (which would report ~1
        # or a value >> the ~1e-13 observed here).
        self.assertLess(features.flatness, 1e-6)


class TestDescriptorsRoundTripFromMethods(unittest.TestCase):
    """Acceptance: all four descriptor types round out of the methods without
    eq/hash errors (waveformDsp.md §Compliance 3)."""

    def test_fft_result_eq_does_not_raise(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        a, b = w.fft(), w.fft()
        self.assertFalse(a == b)  # eq=False -> identity comparison, never raises
        self.assertEqual(a, a)

    def test_spectrogram_result_eq_does_not_raise(self) -> None:
        w = _wrap(Waveform1D.sine(500, frequency=5.0, dt_seconds=0.01))
        a, b = w.spectrogram(nperseg=64), w.spectrogram(nperseg=64)
        self.assertFalse(a == b)
        self.assertEqual(a, a)

    def test_mel_spectrogram_result_eq_does_not_raise(self) -> None:
        w = _wrap(Waveform1D.sine(500, frequency=5.0, dt_seconds=0.01))
        a, b = w.mel_spectrogram(n_mels=4, nperseg=64), w.mel_spectrogram(n_mels=4, nperseg=64)
        self.assertFalse(a == b)
        self.assertEqual(a, a)

    def test_spectral_features_result_eq_does_not_raise(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        a, b = w.spectral_features(), w.spectral_features()
        # Scalar-only dataclass: default eq compares field values.
        self.assertEqual(a, b)


class TestSharedKaiserBetaConstant(unittest.TestCase):
    """Chunk 53 acceptance: ``_spectral.py`` sources its Kaiser beta from the
    shared ``dsp/_common.py`` constant -- not an independent literal -- and
    its own internal window array is unaffected by the reconciliation
    (design constraint 4: no default-behavior change)."""

    def test_spectral_module_constant_matches_common(self) -> None:
        self.assertEqual(spectral_module.DEFAULT_KAISER_BETA, DEFAULT_KAISER_BETA)

    def test_internal_kaiser_window_matches_windowing_periodic_convention(self) -> None:
        n = 64
        spectral_kaiser = spectral_module._window_array(WaveformWindowType.KAISER, n)
        windowing_kaiser = WindowingMixin.generate_window(
            WaveformWindowType.KAISER, n, periodic=True
        )
        np.testing.assert_allclose(spectral_kaiser, windowing_kaiser)

    def test_power_spectral_density_default_unchanged(self) -> None:
        """Regression pin: default PSD output is bit-identical pre/post chunk 53
        (additive parameters only, per design constraint 4)."""
        n = 2000
        w = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=17, dt_seconds=0.01))
        spectrum = w.power_spectral_density(nperseg=256)
        window_array = spectral_module._window_array(WaveformWindowType.HANN, 256)
        # HANN default is periodic (scipy's own default) -- confirms this
        # module's internal convention is untouched by the new `periodic`
        # parameter, which lives only on WindowingMixin.
        self.assertAlmostEqual(
            float(np.mean(window_array)),
            float(
                np.mean(
                    WindowingMixin.generate_window(WaveformWindowType.HANN, 256, periodic=True)
                )
            ),
            places=12,
        )
        self.assertEqual(len(spectrum.magnitudes), len(spectrum.frequencies))


if __name__ == "__main__":
    unittest.main()
