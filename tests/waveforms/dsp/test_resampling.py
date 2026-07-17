"""Unit tests for ``dsp/_resampling.py`` (``ResamplingMixin``).

Covers waveformDsp.md §Family contracts (``ResamplingMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInterpolationMethod
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestDecimatedFactorValidation(unittest.TestCase):
    def test_factor_zero_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.decimated(0)

    def test_negative_factor_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.decimated(-2)

    def test_non_int_factor_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.decimated(1.5)  # type: ignore[arg-type]


class TestDecimatedDtIsExact(unittest.TestCase):
    """§Design constraints: integer-factor ``dt`` bookkeeping is attosecond-exact."""

    def test_decimated_by_four_dt_exact(self) -> None:
        n = 2000
        w = _wrap(Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=1.0 / 1000.0))
        decimated = w.decimated(4)
        self.assertEqual(decimated.dt, w.dt * 4)

    def test_decimated_by_one_is_identity_dt(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0, 5.0], dt_seconds=0.25)
        decimated = w.decimated(1)
        self.assertEqual(decimated.dt, w.dt)
        np.testing.assert_allclose(decimated.values, w.values)

    def test_decimated_preserves_t0(self) -> None:
        n = 2000
        w = _wrap(
            Waveform1D.sine(
                n, frequency=5.0, amplitude=1.0, dt_seconds=1.0 / 1000.0, t0_seconds=3.0
            )
        )
        decimated = w.decimated(4)
        self.assertEqual(decimated.t0, w.t0)


class TestInterpolatedFactorValidation(unittest.TestCase):
    def test_factor_zero_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.interpolated(0)

    def test_negative_factor_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.interpolated(-3)

    def test_non_int_factor_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.interpolated(2.5)  # type: ignore[arg-type]


class TestInterpolatedDtIsExact(unittest.TestCase):
    def test_interpolated_by_two_dt_exact(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.5)
        interpolated = w.interpolated(2)
        self.assertEqual(interpolated.dt, w.dt / 2)

    def test_interpolated_by_one_is_identity_dt(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        interpolated = w.interpolated(1)
        self.assertEqual(interpolated.dt, w.dt)
        np.testing.assert_allclose(interpolated.values, w.values)

    def test_interpolated_preserves_t0(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.5, t0_seconds=1.0)
        interpolated = w.interpolated(2)
        self.assertEqual(interpolated.t0, w.t0)

    def test_interpolated_endpoint_preserving_length(self) -> None:
        n = 10
        w = Waveform1D(list(range(n)), dt_seconds=1.0)
        interpolated = w.interpolated(3)
        self.assertEqual(len(interpolated.values), (n - 1) * 3 + 1)


class TestInterpolatedDecimatedRoundTrip(unittest.TestCase):
    """§Compliance 1 (TDD step 1): ``interpolated(2).decimated(2)`` round-trips a
    smooth signal interior (rtol 1e-3)."""

    def test_sine_round_trip(self) -> None:
        n = 2000
        original = _wrap(Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=1.0 / 1000.0))

        round_tripped = _wrap(original.interpolated(2)).decimated(2)

        self.assertEqual(len(round_tripped.values), n)
        interior = slice(20, -20)
        np.testing.assert_allclose(
            round_tripped.values[interior], original.values[interior], rtol=1e-3, atol=1e-3
        )

    def test_cubic_method_round_trip(self) -> None:
        n = 2000
        original = _wrap(Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=1.0 / 1000.0))

        round_tripped = _wrap(
            original.interpolated(2, method=WaveformInterpolationMethod.CUBIC)
        ).decimated(2)

        interior = slice(20, -20)
        np.testing.assert_allclose(
            round_tripped.values[interior], original.values[interior], rtol=1e-3, atol=1e-3
        )


class TestResampledValidation(unittest.TestCase):
    def test_zero_target_frequency_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.resampled(0.0)

    def test_negative_target_frequency_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.resampled(-10.0)


class TestResampledDerivesDtFromAchievedRate(unittest.TestCase):
    def test_doubling_rate_halves_dt(self) -> None:
        n = 1000
        w = _wrap(Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=1.0 / 100.0))
        target_hz = 2.0 * w.sampling_frequency_hz

        resampled = w.resampled(target_hz)

        self.assertAlmostEqual(
            resampled.dt.seconds_as_float, w.dt.seconds_as_float / 2.0, places=9
        )
        self.assertEqual(len(resampled.values), 2 * n)
        self.assertEqual(resampled.t0, w.t0)


class TestResampledToMatch(unittest.TestCase):
    """§Compliance 1 (TDD step 1): ``resampled_to_match`` yields matching ``dt``
    and length within ±1."""

    def test_matches_other_rate_and_length(self) -> None:
        duration_seconds = 2.0
        n1 = 1000
        n2 = 500
        w1 = _wrap(
            Waveform1D.sine(n1, frequency=5.0, amplitude=1.0, dt_seconds=duration_seconds / n1)
        )
        other = _wrap(
            Waveform1D.sine(n2, frequency=5.0, amplitude=1.0, dt_seconds=duration_seconds / n2)
        )

        matched = w1.resampled_to_match(other)

        self.assertAlmostEqual(
            matched.dt.seconds_as_float, other.dt.seconds_as_float, places=6
        )
        self.assertLessEqual(abs(len(matched.values) - len(other.values)), 1)


class TestPolyphaseResampled(unittest.TestCase):
    """§Compliance 1 (TDD step 1): polyphase 3:2 length check."""

    def test_three_two_length(self) -> None:
        n = 100
        w = _wrap(Waveform1D.sine(n, frequency=5.0, amplitude=1.0, dt_seconds=0.01))
        result = w.polyphase_resampled(up=3, down=2)
        expected_length = -(-(n * 3) // 2)  # ceil(n * up / down)
        self.assertEqual(len(result.values), expected_length)

    def test_dt_is_exact(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dt_seconds=0.5)
        result = w.polyphase_resampled(up=3, down=2)
        self.assertEqual(result.dt, (w.dt * 2) / 3)

    def test_invalid_up_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.polyphase_resampled(up=0, down=2)

    def test_invalid_down_raises(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.polyphase_resampled(up=2, down=0)


class TestMinimumLengthRaises(unittest.TestCase):
    def test_decimated_on_single_sample_raises(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.decimated(2)

    def test_interpolated_on_single_sample_raises(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.interpolated(2)

    def test_resampled_on_single_sample_raises(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.resampled(20.0)

    def test_polyphase_resampled_on_single_sample_raises(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.polyphase_resampled(up=3, down=2)


class TestMetadataPreserved(unittest.TestCase):
    """dt/t0 are ``PrecisionTimeInterval``/``PrecisionTimestamp`` typed, and ``t0``
    is always unchanged by resampling (waveformDsp.md's stated design constraint)."""

    def test_resampled_t0_unchanged(self) -> None:
        w = _wrap(
            Waveform1D.sine(500, frequency=5.0, dt_seconds=1.0 / 500.0, t0_seconds=10.0)
        )
        resampled = w.resampled(250.0)
        self.assertEqual(resampled.t0, w.t0)

    def test_polyphase_t0_unchanged(self) -> None:
        w = _wrap(
            Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01, t0_seconds=2.0)
        )
        result = w.polyphase_resampled(up=3, down=2)
        self.assertEqual(result.t0, w.t0)

    def test_dt_is_precision_time_interval(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.1)
        decimated = w.decimated(2)
        self.assertIsInstance(decimated.dt, PrecisionTimeInterval)


if __name__ == "__main__":
    unittest.main()
