"""Unit tests for ``dsp/_time_alignment.py`` (``TimeAlignmentMixin``).

Covers waveformDsp.md §Family contracts (``TimeAlignmentMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``,
which composes both ``TimeAlignmentMixin`` and ``CorrelationMixin`` (the
``aligned``/``time_lag`` ``CORRELATION`` path calls
``CorrelationMixin.find_max_correlation`` through a structural ``Protocol``)
from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.errors import WaveformCompatibilityError
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformAlignmentMethod
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestAlignedCorrelationRecoversKnownShift(unittest.TestCase):
    """Acceptance criterion: ``aligned`` recovers a k-sample shift (result lag 0
    afterward). ``other`` is built as ``np.roll(base.values, k)`` at the *same*
    ``t0`` as ``self`` (matching ``test_correlation.py``'s known-shift convention),
    so ``self.aligned(to=other)`` must shift ``t0`` forward by exactly ``k * dt``
    for a subsequent ``time_lag`` against ``other`` to land back at 0.
    """

    def _check_known_shift(self, k: int) -> None:
        n = 2000
        base = Waveform1D.white_noise(n, amplitude=1.0, seed=42, dt_seconds=0.001)
        w1 = _wrap(base)
        shifted_values = np.roll(base.values, k)
        w2 = Waveform1D(shifted_values, dt=base.dt, t0=base.t0)

        aligned = w1.aligned(w2)

        self.assertEqual(aligned.t0, w1.t0 + w1.dt * k)
        np.testing.assert_allclose(aligned.values, w1.values)
        self.assertEqual(aligned.dt, w1.dt)

        lag_after = _wrap(aligned).time_lag(w2)
        self.assertIsNotNone(lag_after)
        assert lag_after is not None  # mypy narrowing for the assertions below
        self.assertEqual(lag_after.lag_samples, 0)
        self.assertEqual(lag_after.lag_seconds, 0.0)
        self.assertGreater(lag_after.correlation, 0.95)

    def test_zero_shift(self) -> None:
        self._check_known_shift(0)

    def test_three_sample_shift(self) -> None:
        self._check_known_shift(3)

    def test_seventeen_sample_shift(self) -> None:
        self._check_known_shift(17)


class TestAlignedStartTime(unittest.TestCase):
    def test_adopts_reference_t0_unchanged_values_and_dt(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1, t0_seconds=0.0)
        w2 = Waveform1D([5.0, 6.0, 7.0, 8.0], dt_seconds=0.1, t0_seconds=2.5)

        aligned = w1.aligned(w2, method=WaveformAlignmentMethod.START_TIME)

        self.assertEqual(aligned.t0, w2.t0)
        self.assertEqual(aligned.dt, w1.dt)
        np.testing.assert_allclose(aligned.values, w1.values)

    def test_no_qualifying_correlation_peak_returns_self_unshifted(self) -> None:
        w1 = Waveform1D([0.0] * 10, dt_seconds=0.1)
        w2 = Waveform1D(list(range(10)), dt_seconds=0.1)

        aligned = w1.aligned(w2)  # default CORRELATION method

        self.assertEqual(aligned.t0, w1.t0)
        np.testing.assert_allclose(aligned.values, w1.values)


class TestTimeLagNoneWhenNoCorrelatablePeak(unittest.TestCase):
    """``time_lag`` returns ``None`` when the strongest match carries zero
    correlation magnitude (an all-zero waveform correlates to exactly 0 against
    anything, per ``CorrelationMixin``'s zero-variance handling)."""

    def test_all_zero_waveform_yields_none(self) -> None:
        w1 = Waveform1D([0.0] * 10, dt_seconds=0.1)
        w2 = Waveform1D(list(range(10)), dt_seconds=0.1)
        self.assertIsNone(w1.time_lag(w2))


class TestTimeLagAccountsForExistingT0Offset(unittest.TestCase):
    """``time_lag`` is ``t0``-aware: identical values at different ``t0``s still
    report a nonzero real-world lag (unlike ``CorrelationMixin.find_max_correlation``,
    which is purely value-domain and would report 0 here)."""

    def test_identical_values_different_t0_reports_the_t0_offset(self) -> None:
        values = [1.0, 3.0, 2.0, 4.0, 1.0, 5.0, 2.0]
        w1 = Waveform1D(values, dt_seconds=0.1, t0_seconds=0.5)
        w2 = Waveform1D(values, dt_seconds=0.1, t0_seconds=0.2)

        lag = w1.time_lag(w2)

        self.assertIsNotNone(lag)
        assert lag is not None
        self.assertEqual(lag.lag_samples, 3)
        self.assertAlmostEqual(lag.lag_seconds, 0.3, places=9)


class TestTimeLagPropagatesCorrelationMixinValidation(unittest.TestCase):
    def test_dt_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.time_lag(w2)

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.time_lag(w2)


class TestSynchronizeCommonOverlap(unittest.TestCase):
    """Acceptance criterion: ``synchronize`` of two offset waveforms returns
    equal-length overlaps with matching ``t0``."""

    def test_two_offset_waveforms_return_matching_overlap(self) -> None:
        w1 = Waveform1D(np.arange(50, dtype=np.float64), dt_seconds=0.1, t0_seconds=0.0)
        w2 = Waveform1D(np.arange(100.0, 150.0), dt_seconds=0.1, t0_seconds=1.0)

        synced = Waveform1D.synchronize([w1, w2])

        self.assertEqual(len(synced), 2)
        self.assertEqual(len(synced[0].values), 40)
        self.assertEqual(len(synced[1].values), 40)
        self.assertEqual(synced[0].t0, synced[1].t0)
        self.assertEqual(synced[0].t0, w2.t0)
        np.testing.assert_allclose(synced[0].values, np.arange(10, 50, dtype=np.float64))
        np.testing.assert_allclose(synced[1].values, np.arange(100.0, 140.0))

    def test_empty_sequence_returns_empty_list(self) -> None:
        self.assertEqual(Waveform1D.synchronize([]), [])

    def test_dt_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            Waveform1D.synchronize([w1, w2])

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            Waveform1D.synchronize([w1, w2])

    def test_no_overlap_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1, t0_seconds=0.0)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1, t0_seconds=10.0)
        with self.assertRaises(ValueError):
            Waveform1D.synchronize([w1, w2])


class TestTimeWindowsCountFormula(unittest.TestCase):
    """Acceptance criterion: ``time_windows(1.0, overlap=0.5)`` count formula pinned."""

    def test_pinned_window_count(self) -> None:
        w = Waveform1D(np.arange(100, dtype=np.float64), dt_seconds=0.1)

        windows = w.time_windows(1.0, overlap=0.5)

        self.assertEqual(len(windows), 19)
        for window in windows:
            self.assertEqual(len(window.values), 10)
            self.assertEqual(window.dt, w.dt)

    def test_window_start_times_step_by_overlap(self) -> None:
        w = Waveform1D(np.arange(100, dtype=np.float64), dt_seconds=0.1)
        windows = w.time_windows(1.0, overlap=0.5)

        self.assertEqual(windows[0].t0, w.t0)
        self.assertEqual(windows[1].t0, w.t0 + w.dt * 5)
        np.testing.assert_allclose(windows[0].values, np.arange(0, 10, dtype=np.float64))
        np.testing.assert_allclose(windows[1].values, np.arange(5, 15, dtype=np.float64))

    def test_no_overlap_default(self) -> None:
        w = Waveform1D(np.arange(30, dtype=np.float64), dt_seconds=0.1)
        windows = w.time_windows(1.0)
        self.assertEqual(len(windows), 3)

    def test_non_positive_duration_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.time_windows(0.0)

    def test_overlap_out_of_range_raises(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.time_windows(0.5, overlap=1.0)

    def test_too_short_for_one_window_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.time_windows(1.0)


class TestTimeSegmentsBoundariesRespected(unittest.TestCase):
    """Acceptance criterion: segment boundaries respected."""

    def test_boundaries_split_into_three_segments(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=1.0, t0_seconds=0.0)

        segments = w.time_segments([3.0, 6.0])

        self.assertEqual(len(segments), 3)
        np.testing.assert_allclose(segments[0].values, [0.0, 1.0, 2.0])
        np.testing.assert_allclose(segments[1].values, [3.0, 4.0, 5.0])
        np.testing.assert_allclose(segments[2].values, [6.0, 7.0, 8.0, 9.0])
        self.assertEqual(segments[0].t0, w.t0)
        self.assertEqual(segments[1].t0, w.t0 + w.dt * 3)
        self.assertEqual(segments[2].t0, w.t0 + w.dt * 6)

    def test_empty_boundaries_returns_whole_waveform_unsplit(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=1.0)
        segments = w.time_segments([])
        self.assertEqual(len(segments), 1)
        np.testing.assert_allclose(segments[0].values, w.values)
        self.assertEqual(segments[0].t0, w.t0)

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.time_segments([1.0])

    def test_boundary_out_of_range_raises(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.time_segments([9.0])

    def test_non_increasing_boundaries_raise(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.time_segments([5.0, 3.0])

    def test_boundaries_rounding_to_same_index_raise(self) -> None:
        w = Waveform1D(np.arange(10, dtype=np.float64), dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.time_segments([3.0, 3.01])


if __name__ == "__main__":
    unittest.main()
