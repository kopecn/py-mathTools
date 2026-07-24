"""Unit tests for ``dsp/_zero_crossings.py`` (``ZeroCrossingMixin``).

Covers waveformDsp.md §Family contracts (``ZeroCrossingMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformZeroCrossingDirection
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestZeroCrossingRateOfSine(unittest.TestCase):
    """§Compliance 1: an f-Hz sine over an integer number of periods has
    ``zero_crossing_rate() == 2f`` (within one crossing's worth of tolerance)."""

    def test_rate_matches_2f(self) -> None:
        frequency = 5.0
        periods = 20
        n = 4000
        dt_seconds = (periods / frequency) / n
        w = _wrap(Waveform1D.sine(n, frequency=frequency, amplitude=1.0, dt_seconds=dt_seconds))

        rate = w.zero_crossing_rate()

        duration_seconds = (n - 1) * dt_seconds
        one_crossing_tolerance = 1.0 / duration_seconds
        self.assertAlmostEqual(rate, 2.0 * frequency, delta=one_crossing_tolerance + 1e-6)

    def test_count_matches_2f_times_duration(self) -> None:
        frequency = 5.0
        periods = 20
        n = 4000
        dt_seconds = (periods / frequency) / n
        w = _wrap(Waveform1D.sine(n, frequency=frequency, amplitude=1.0, dt_seconds=dt_seconds))

        count = w.zero_crossing_count()

        expected = 2 * periods
        self.assertLessEqual(abs(count - expected), 1)


class TestPositiveNegativeSumToBoth(unittest.TestCase):
    """§Compliance 1: POSITIVE + NEGATIVE counts sum to BOTH."""

    def test_direction_counts_sum(self) -> None:
        w = _wrap(Waveform1D.sine(2000, frequency=7.0, amplitude=1.0, dt_seconds=0.0005))

        positive = w.zero_crossing_count(direction=WaveformZeroCrossingDirection.POSITIVE)
        negative = w.zero_crossing_count(direction=WaveformZeroCrossingDirection.NEGATIVE)
        both = w.zero_crossing_count(direction=WaveformZeroCrossingDirection.BOTH)

        self.assertEqual(positive + negative, both)
        self.assertGreater(positive, 0)
        self.assertGreater(negative, 0)

    def test_direction_filters_events(self) -> None:
        w = _wrap(Waveform1D.sine(2000, frequency=7.0, amplitude=1.0, dt_seconds=0.0005))

        positive_events = w.zero_crossings(direction=WaveformZeroCrossingDirection.POSITIVE)
        negative_events = w.zero_crossings(direction=WaveformZeroCrossingDirection.NEGATIVE)

        self.assertTrue(
            all(e.direction is WaveformZeroCrossingDirection.POSITIVE for e in positive_events)
        )
        self.assertTrue(
            all(e.direction is WaveformZeroCrossingDirection.NEGATIVE for e in negative_events)
        )


class TestSubSampleInterpolation(unittest.TestCase):
    """§Compliance 1: crossing of a line ``y = t - 0.5`` lands at 0.5 s
    (atol dt/100)."""

    def test_linear_ramp_crossing_interpolated(self) -> None:
        dt_seconds = 0.03
        n = 60
        values = np.arange(n, dtype=np.float64) * dt_seconds - 0.5
        w = Waveform1D(values, dt_seconds=dt_seconds)

        crossings = w.zero_crossings()

        self.assertEqual(len(crossings), 1)
        self.assertAlmostEqual(crossings[0].time_seconds, 0.5, delta=dt_seconds / 100.0)
        self.assertEqual(crossings[0].direction, WaveformZeroCrossingDirection.POSITIVE)

    def test_exact_zero_sample_counts_once(self) -> None:
        # Sample lands exactly on zero at index 5 -- must not be double-counted
        # as both an approach-to-zero and a departure-from-zero crossing.
        values = np.array([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float64)
        w = Waveform1D(values, dt_seconds=1.0)

        crossings = w.zero_crossings()

        self.assertEqual(len(crossings), 1)
        self.assertAlmostEqual(crossings[0].time_seconds, 2.0, delta=1e-9)


class TestEmptyOrTooShortReturnsEmptyList(unittest.TestCase):
    """waveformDsp.md §Numerical conventions: ``zero_crossings`` is a detector
    -- empty/too-short input returns ``[]``, never raises."""

    def test_empty_waveform(self) -> None:
        w = Waveform1D([], dt_seconds=0.1)
        self.assertEqual(w.zero_crossings(), [])
        self.assertEqual(w.zero_crossing_count(), 0)
        self.assertEqual(w.zero_crossing_rate(), 0.0)

    def test_single_sample(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        self.assertEqual(w.zero_crossings(), [])

    def test_no_crossing_all_positive(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        self.assertEqual(w.zero_crossings(), [])
        self.assertEqual(w.zero_crossing_rate(), 0.0)


class TestSegmentsBetweenZeroCrossings(unittest.TestCase):
    """Acceptance criterion: segments' t0s are monotonically increasing and
    lengths sum to ~= n."""

    def test_monotonic_t0_and_length_sum(self) -> None:
        n = 2000
        w = _wrap(Waveform1D.sine(n, frequency=6.0, amplitude=1.0, dt_seconds=0.0005))

        segments = w.segments_between_zero_crossings()

        self.assertGreater(len(segments), 1)
        t0s = [segment.t0 for segment in segments]
        self.assertEqual(t0s, sorted(t0s))
        for earlier, later in zip(t0s, t0s[1:], strict=False):
            self.assertLess(earlier, later)

        total_length = sum(len(segment.values) for segment in segments)
        # Each internal boundary sample is shared by two adjacent segments, so the
        # sum slightly overshoots n by roughly one sample per internal boundary.
        self.assertGreaterEqual(total_length, n)
        self.assertLessEqual(total_length, n + len(segments))

    def test_no_crossings_returns_whole_waveform(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1, t0_seconds=1.0)
        segments = w.segments_between_zero_crossings()
        self.assertEqual(len(segments), 1)
        np.testing.assert_allclose(segments[0].values, w.values)
        self.assertEqual(segments[0].t0, w.t0)

    def test_single_sample_returns_single_segment(self) -> None:
        w = Waveform1D([5.0], dt_seconds=0.1)
        segments = w.segments_between_zero_crossings()
        self.assertEqual(len(segments), 1)
        np.testing.assert_allclose(segments[0].values, [5.0])

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.segments_between_zero_crossings()

    def test_segment_dt_preserved(self) -> None:
        w = _wrap(Waveform1D.sine(500, frequency=4.0, amplitude=1.0, dt_seconds=0.001))
        segments = w.segments_between_zero_crossings()
        for segment in segments:
            self.assertEqual(segment.dt, w.dt)

    def test_inclusive_slicing_pinned_on_hand_computed_case(self) -> None:
        """§Gap 23 (chunk 55): the inclusive ``[start:stop+1]`` slicing
        (``_zero_crossings.py:206``) was never pinned against a hand-computed
        case. ``values = [1, -1, 1, -1, 1]`` (alternating sign, ``dt=1s``) has
        BOTH-direction crossings landing at indices ``[1, 2, 3, 4]`` (each pair
        change is a crossing); with ``split_points = [0, 1, 2, 3, 4, 4]`` (the
        trailing duplicate ``sample_count - 1 == 4`` dropped, since
        ``start >= stop``), the four inclusive segments are
        ``values[0:2], values[1:3], values[2:4], values[3:5]`` -- each interior
        boundary sample shared by exactly two adjacent segments.
        """
        values = [1.0, -1.0, 1.0, -1.0, 1.0]
        w = Waveform1D(values, dt_seconds=1.0, t0_seconds=0.0)

        segments = w.segments_between_zero_crossings()

        self.assertEqual(len(segments), 4)
        expected_slices = [(0, 2), (1, 3), (2, 4), (3, 5)]
        for segment, (start, stop) in zip(segments, expected_slices, strict=True):
            np.testing.assert_allclose(segment.values, values[start:stop])
            self.assertEqual(segment.t0, w.t0 + w.dt * start)


if __name__ == "__main__":
    unittest.main()
