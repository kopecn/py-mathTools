"""Unit tests for ``dsp/_spectral.py`` (``SpectralMixin``).

Covers waveformDsp.md §Family contracts (``SpectralMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin via a local test subclass
``class _W(SpectralMixin, Waveform1D): pass`` (the pattern every DSP mixin
chunk's tests use, per chunk 18).
"""

import unittest

import numpy as np

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.dsp._spectral import SpectralMixin, _mel_filterbank
from math_tools.waveforms.waveform1d import Waveform1D


class _W(SpectralMixin, Waveform1D):
    pass


def _wrap(base: WaveformProtocol) -> _W:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``_W`` (see ``test_calc.py``)."""
    return _W(base.values, dt=base.dt, t0=base.t0)


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
        w = _W([1.0])
        with self.assertRaises(ValueError):
            w.fft()

    def test_empty_waveform_raises(self) -> None:
        w = _W([])
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
        w = _W([1.0])
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
        w = _W([1.0])
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
        w = _W([1.0])
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
        w = _W([1.0])
        with self.assertRaises(ValueError):
            w.spectral_features()

    def test_invalid_rolloff_fraction_raises(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.spectral_features(rolloff_fraction=0.0)
        with self.assertRaises(ValueError):
            w.spectral_features(rolloff_fraction=1.5)


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


if __name__ == "__main__":
    unittest.main()
