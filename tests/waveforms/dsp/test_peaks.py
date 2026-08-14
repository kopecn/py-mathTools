"""Unit tests for ``dsp/_peaks.py`` (``PeakMixin``).

Covers waveformDsp.md §Family contracts (``PeakMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import math
import unittest

import numpy as np
from scipy.signal import find_peaks, peak_prominences

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestDetectPeaksOnSineHasExactCount(unittest.TestCase):
    """§Compliance 1: ``sine(n, f, fs)`` yields exactly ``floor(n*f/fs)`` peaks.

    ``n=1000``, ``frequency=10``, ``fs=1000`` (``dt_seconds=0.001``) is
    unambiguous: 10 whole periods (100 samples each) fit exactly in 1000
    samples, so every peak (one per period, at the quarter-period sample)
    falls strictly in the interior -- no boundary-peak ambiguity.
    """

    def test_exact_peak_count(self) -> None:
        n = 1000
        frequency = 10.0
        fs = 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=frequency, dt_seconds=1.0 / fs))

        peaks = w.detect_peaks()

        expected_count = math.floor(n * frequency / fs)
        self.assertEqual(expected_count, 10)
        self.assertEqual(len(peaks), expected_count)

    def test_peak_indices_and_time_seconds(self) -> None:
        n = 1000
        frequency = 10.0
        fs = 1000.0
        dt_seconds = 1.0 / fs
        w = _wrap(Waveform1D.sine(n, frequency=frequency, dt_seconds=dt_seconds))

        peaks = w.detect_peaks()

        expected_indices = [25 + 100 * m for m in range(10)]
        self.assertEqual([p.index for p in peaks], expected_indices)
        for peak in peaks:
            self.assertAlmostEqual(peak.time_seconds, peak.index * dt_seconds, places=12)
            self.assertAlmostEqual(peak.value, 1.0, places=6)


class TestDetectValleysMirrorPeaksUnderNegation(unittest.TestCase):
    """§TDD step 1: valleys mirror peaks under negation."""

    def test_matches_negated_detect_peaks(self) -> None:
        values = [1.0, 3.0, 0.5, 4.0, -2.0, 5.0, -3.0, 2.0, 6.0, 0.0]
        w = Waveform1D(values, dt_seconds=0.1)
        negated_w = Waveform1D([-v for v in values], dt_seconds=0.1)

        valleys = w.detect_valleys()
        negated_peaks = negated_w.detect_peaks()

        self.assertTrue(len(valleys) > 0)
        self.assertEqual(len(valleys), len(negated_peaks))
        for valley, negated_peak in zip(valleys, negated_peaks, strict=True):
            self.assertEqual(valley.index, negated_peak.index)
            self.assertAlmostEqual(valley.time_seconds, negated_peak.time_seconds, places=12)
            self.assertAlmostEqual(valley.value, -negated_peak.value, places=12)

    def test_sine_valley_count_matches_peak_count(self) -> None:
        n = 1000
        frequency = 10.0
        fs = 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=frequency, dt_seconds=1.0 / fs))

        self.assertEqual(len(w.detect_valleys()), len(w.detect_peaks()))

    def test_min_height_bounds_value_from_above(self) -> None:
        values = [5.0, 1.0, 4.0, -3.0, 4.0, 0.5, 5.0]
        w = Waveform1D(values, dt_seconds=0.1)

        valleys = w.detect_valleys(min_height=2.0)

        self.assertEqual(len(valleys), 1)
        self.assertEqual(valleys[0].index, 3)
        self.assertAlmostEqual(valleys[0].value, -3.0, places=12)


class TestFindMostProminentPeaksOrdering(unittest.TestCase):
    """§TDD step 1: prominence ordering on a two-tone signal returns the big ones first."""

    def _two_tone_waveform(self) -> Waveform1D:
        values = [0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0]
        return Waveform1D(values, dt_seconds=0.1)

    def test_big_peak_returned_before_small_peak(self) -> None:
        w = self._two_tone_waveform()

        top_peaks = w.find_most_prominent_peaks(count=2)

        self.assertEqual(len(top_peaks), 2)
        self.assertEqual(top_peaks[0].peak.index, 3)
        self.assertAlmostEqual(top_peaks[0].peak.value, 10.0, places=12)
        self.assertEqual(top_peaks[1].peak.index, 7)
        self.assertAlmostEqual(top_peaks[1].peak.value, 3.0, places=12)
        self.assertGreater(top_peaks[0].prominence, top_peaks[1].prominence)

    def test_count_one_returns_only_the_biggest(self) -> None:
        w = self._two_tone_waveform()

        top_peaks = w.find_most_prominent_peaks(count=1)

        self.assertEqual(len(top_peaks), 1)
        self.assertEqual(top_peaks[0].peak.index, 3)

    def test_count_larger_than_available_peaks_truncates_gracefully(self) -> None:
        w = self._two_tone_waveform()

        top_peaks = w.find_most_prominent_peaks(count=10)

        self.assertEqual(len(top_peaks), 2)

    def test_non_positive_count_returns_empty(self) -> None:
        w = self._two_tone_waveform()

        self.assertEqual(w.find_most_prominent_peaks(count=0), [])
        self.assertEqual(w.find_most_prominent_peaks(count=-1), [])

    def test_prominence_values_match_direct_scipy_peak_prominences(self) -> None:
        """§Gap 18 (chunk 55): ``WaveformPeakWithProminence.prominence``
        (``_peaks.py:144``) only had its ordering asserted, never the numeric
        value -- pin it against a direct ``scipy.signal.peak_prominences`` call."""
        w = self._two_tone_waveform()
        values = np.array([0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0])

        top_peaks = w.find_most_prominent_peaks(count=2)

        indices, _ = find_peaks(values)
        expected_prominences, _, _ = peak_prominences(values, indices)
        expected_by_index = dict(zip(indices.tolist(), expected_prominences.tolist(), strict=True))
        for peak_with_prominence in top_peaks:
            self.assertAlmostEqual(
                peak_with_prominence.prominence,
                expected_by_index[peak_with_prominence.peak.index],
                places=9,
            )

    def test_min_distance_suppresses_close_secondary_peak(self) -> None:
        """§Gap 18 (chunk 55): ``min_distance`` (``_peaks.py:131``) was never passed
        to ``find_most_prominent_peaks`` by any test."""
        values = [0.0, 5.0, 0.0, 6.0, 0.0, 4.0, 0.0]
        w = Waveform1D(values, dt_seconds=0.1)

        unfiltered = w.find_most_prominent_peaks(count=3)
        filtered = w.find_most_prominent_peaks(count=3, min_distance=5)

        self.assertEqual(len(unfiltered), 3)
        self.assertLess(len(filtered), len(unfiltered))
        self.assertIn(3, [p.peak.index for p in filtered])


class TestFlatSignalHasNoPeaksOrValleys(unittest.TestCase):
    """§TDD step 1: flat signal -> []."""

    def test_detect_peaks_empty(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=5.0, dt_seconds=0.1))
        self.assertEqual(w.detect_peaks(), [])

    def test_detect_valleys_empty(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=5.0, dt_seconds=0.1))
        self.assertEqual(w.detect_valleys(), [])

    def test_find_most_prominent_peaks_empty(self) -> None:
        w = _wrap(Waveform1D.constant(10, value=5.0, dt_seconds=0.1))
        self.assertEqual(w.find_most_prominent_peaks(count=5), [])


class TestEmptyWaveformNeverRaises(unittest.TestCase):
    """waveformDsp.md §Numerical conventions: detectors return [] on no-hit, never raise."""

    def test_detect_peaks_on_empty_waveform(self) -> None:
        w = Waveform1D([])
        self.assertEqual(w.detect_peaks(), [])

    def test_detect_valleys_on_empty_waveform(self) -> None:
        w = Waveform1D([])
        self.assertEqual(w.detect_valleys(), [])

    def test_find_most_prominent_peaks_on_empty_waveform(self) -> None:
        w = Waveform1D([])
        self.assertEqual(w.find_most_prominent_peaks(count=3), [])


class TestDetectPeaksFilters(unittest.TestCase):
    def test_min_height_filters_low_peaks(self) -> None:
        values = [0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0]
        w = Waveform1D(values, dt_seconds=0.1)

        peaks = w.detect_peaks(min_height=5.0)

        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0].index, 3)

    def test_min_prominence_filters_low_prominence_peaks(self) -> None:
        values = [0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0]
        w = Waveform1D(values, dt_seconds=0.1)

        peaks = w.detect_peaks(min_prominence=5.0)

        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0].index, 3)

    def test_min_distance_suppresses_close_secondary_peaks(self) -> None:
        values = [0.0, 5.0, 0.0, 6.0, 0.0, 4.0, 0.0]
        w = Waveform1D(values, dt_seconds=0.1)

        unfiltered = w.detect_peaks()
        filtered = w.detect_peaks(min_distance=5)

        self.assertEqual(len(unfiltered), 3)
        self.assertLess(len(filtered), len(unfiltered))
        self.assertIn(3, [p.index for p in filtered])


if __name__ == "__main__":
    unittest.main()
