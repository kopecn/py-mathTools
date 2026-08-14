"""Unit tests for ``dsp/_phase.py`` (``PhaseMixin``).

Covers waveformDsp.md §Family contracts (``PhaseMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.errors import WaveformCompatibilityError
from math_tools.waveforms.dsp._phase import PhaseMixin
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInstantaneousFrequency
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestInstantaneousPhaseOfChirpIsMonotoneIncreasingWhenUnwrapped(unittest.TestCase):
    """§Compliance 1: unwrapped phase of a chirp is monotone increasing."""

    def test_chirp_unwrapped_phase_is_monotone(self) -> None:
        n = 2000
        w = _wrap(
            Waveform1D.chirp(n, start_frequency=5.0, end_frequency=50.0, dt_seconds=1.0 / 1000.0)
        )
        phase = w.instantaneous_phase(unwrapped=True)

        interior = phase.values[10:-10]
        self.assertTrue(np.all(np.diff(interior) > 0.0))

    def test_wrapped_phase_stays_within_pi(self) -> None:
        n = 2000
        w = _wrap(
            Waveform1D.chirp(n, start_frequency=5.0, end_frequency=50.0, dt_seconds=1.0 / 1000.0)
        )
        phase = w.instantaneous_phase(unwrapped=False)

        self.assertTrue(np.all(phase.values >= -np.pi - 1e-9))
        self.assertTrue(np.all(phase.values <= np.pi + 1e-9))

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.instantaneous_phase()


class TestUnwrapPhase(unittest.TestCase):
    """``unwrap_phase`` treats ``self.values`` as already-computed phase data."""

    def test_recovers_a_linear_ramp_from_wrapped_phase(self) -> None:
        n = 500
        true_phase = np.linspace(0.0, 40.0 * np.pi, n)
        wrapped = np.angle(np.exp(1j * true_phase))
        w = Waveform1D(wrapped, dt_seconds=0.01)

        unwrapped = w.unwrap_phase()

        # Unwrapping recovers the true phase up to a constant 2*pi*k offset
        # (np.unwrap anchors on the first sample, which is already wrapped).
        offset = unwrapped.values[0] - true_phase[0]
        np.testing.assert_allclose(unwrapped.values, true_phase + offset, atol=1e-6)

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.unwrap_phase()

    def test_threshold_changes_whether_a_borderline_step_is_corrected(self) -> None:
        """§Gap 19 (chunk 55): ``threshold`` (``_phase.py:107``) was never varied
        from the default. A constant per-sample step of 3.3 rad sits strictly
        between ``pi`` (~3.14159, the default) and 3.4: the default threshold
        registers it as a discontinuity and unwraps it, while ``threshold=3.4``
        treats the same data as already continuous and leaves it untouched."""
        n = 5
        raw_phase = np.arange(n, dtype=np.float64) * 3.3
        w = Waveform1D(raw_phase, dt_seconds=0.01)

        unchanged = w.unwrap_phase(threshold=3.4)
        np.testing.assert_allclose(unchanged.values, raw_phase)

        corrected = w.unwrap_phase()  # default threshold=pi
        expected = np.unwrap(raw_phase, discont=np.pi)
        np.testing.assert_allclose(corrected.values, expected)
        self.assertFalse(np.allclose(corrected.values, raw_phase))

    def test_matches_direct_numpy_unwrap_at_a_non_default_threshold(self) -> None:
        n = 5
        raw_phase = np.arange(n, dtype=np.float64) * 3.3
        w = Waveform1D(raw_phase, dt_seconds=0.01)

        result = w.unwrap_phase(threshold=3.29)

        expected = np.unwrap(raw_phase, discont=3.29)
        np.testing.assert_allclose(result.values, expected)


class TestInstantaneousFrequencyOfPureSineApproximatesFrequency(unittest.TestCase):
    """§Compliance 1: instantaneous frequency of a pure f-Hz sine ~= f on the
    interior (rtol 1e-2)."""

    def test_ten_hz_sine(self) -> None:
        n = 5000
        frequency = 10.0
        dt_seconds = 1.0 / 1000.0
        w = _wrap(Waveform1D.sine(n, frequency=frequency, amplitude=1.0, dt_seconds=dt_seconds))

        result = w.instantaneous_frequency()

        self.assertIsInstance(result, WaveformInstantaneousFrequency)
        interior = result.frequencies_hz[20:-20]
        np.testing.assert_allclose(interior, frequency, rtol=1e-2)

    def test_times_seconds_matches_time_axis(self) -> None:
        n = 100
        dt_seconds = 0.01
        w = _wrap(Waveform1D.sine(n, frequency=5.0, dt_seconds=dt_seconds))
        result = w.instantaneous_frequency()
        expected_times = np.arange(n, dtype=np.float64) * dt_seconds
        np.testing.assert_allclose(result.times_seconds, expected_times)

    def test_single_sample_raises(self) -> None:
        w = Waveform1D([1.0])
        with self.assertRaises(ValueError):
            w.instantaneous_frequency()

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.instantaneous_frequency()


class TestPhaseDifferenceOfSinVsCosApproximatesHalfPi(unittest.TestCase):
    """§Compliance 1: ``phase_difference`` of ``sin`` vs ``cos`` ~= pi/2 interior."""

    def test_magnitude_is_approximately_half_pi(self) -> None:
        n = 2000
        dt_seconds = 1.0 / 1000.0
        sine = _wrap(Waveform1D.sine(n, frequency=10.0, dt_seconds=dt_seconds))
        cosine = _wrap(Waveform1D.cosine(n, frequency=10.0, dt_seconds=dt_seconds))

        diff = sine.phase_difference(cosine)

        interior = diff.values[20:-20]
        np.testing.assert_allclose(np.abs(interior), np.pi / 2.0, atol=0.05)

    def test_dt_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.phase_difference(w2)

    def test_sample_count_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        with self.assertRaises(WaveformCompatibilityError):
            w1.phase_difference(w2)

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.phase_difference(w2)


class TestPhaseSynchronizationIndex(unittest.TestCase):
    """§Compliance 1: PLV of a signal with itself == 1.0; with independent
    seeded-noise signal < 0.3."""

    def test_signal_with_itself_is_one(self) -> None:
        n = 1000
        w = _wrap(Waveform1D.sine(n, frequency=7.0, dt_seconds=0.001))
        plv = w.phase_synchronization_index(w)
        self.assertAlmostEqual(plv, 1.0, places=9)

    def test_independent_noise_signals_are_weakly_synchronized(self) -> None:
        n = 4000
        w1 = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=1, dt_seconds=0.001))
        w2 = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=2, dt_seconds=0.001))
        plv = w1.phase_synchronization_index(w2)
        self.assertLess(plv, 0.3)

    def test_dt_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.phase_synchronization_index(w2)

    def test_empty_waveform_raises(self) -> None:
        w1 = Waveform1D([], dt_seconds=0.1)
        w2 = Waveform1D([], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w1.phase_synchronization_index(w2)


class TestPhaseCoherence(unittest.TestCase):
    def test_signal_with_itself_is_approximately_one_in_every_window(self) -> None:
        n = 2000
        w = _wrap(Waveform1D.sine(n, frequency=7.0, dt_seconds=0.001))
        coherence = w.phase_coherence(w, window=200)
        np.testing.assert_allclose(coherence.values, 1.0, atol=1e-9)

    def test_independent_noise_signals_have_low_coherence(self) -> None:
        n = 4000
        w1 = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=3, dt_seconds=0.001))
        w2 = _wrap(Waveform1D.white_noise(n, amplitude=1.0, seed=4, dt_seconds=0.001))
        coherence = w1.phase_coherence(w2, window=200)
        self.assertTrue(np.all(coherence.values < 0.6))

    def test_output_length_matches_number_of_windows(self) -> None:
        w = Waveform1D(np.zeros(1000), dt_seconds=0.001)
        coherence = w.phase_coherence(w, window=100)
        self.assertEqual(len(coherence.values), 10)

    def test_window_out_of_range_raises(self) -> None:
        w = Waveform1D(np.zeros(10), dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.phase_coherence(w, window=0)
        with self.assertRaises(ValueError):
            w.phase_coherence(w, window=11)

    def test_dt_mismatch_raises(self) -> None:
        w1 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        w2 = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.2)
        with self.assertRaises(WaveformCompatibilityError):
            w1.phase_coherence(w2)

    def test_single_sample_raises(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        with self.assertRaises(ValueError):
            w.phase_coherence(w)

    def test_default_window_matches_sample_count_over_four_when_small(self) -> None:
        """§Gap 19 (chunk 55): the default ``window`` expression (``_phase.py:187``,
        ``min(256, max(1, sample_count // 4))``) was never exercised -- pin the
        unclamped branch (``sample_count // 4 < 256``) by comparing against an
        explicit matching ``window``."""
        w = Waveform1D(np.zeros(40), dt_seconds=0.001)
        default_result = w.phase_coherence(w)
        explicit_result = w.phase_coherence(w, window=40 // 4)
        self.assertEqual(len(default_result.values), len(explicit_result.values))

    def test_default_window_clamps_to_256_when_sample_count_over_four_exceeds_it(self) -> None:
        """Pins the ``min(256, ...)`` clamp branch (``sample_count // 4 > 256``)."""
        w = Waveform1D(np.zeros(2000), dt_seconds=0.001)
        default_result = w.phase_coherence(w)
        explicit_result = w.phase_coherence(w, window=256)
        self.assertEqual(len(default_result.values), len(explicit_result.values))


class TestGroupDelay(unittest.TestCase):
    """A linear phase-vs-frequency response has a constant group delay."""

    def test_linear_phase_gives_constant_group_delay(self) -> None:
        frequencies = np.linspace(1.0, 100.0, 200)
        delay_seconds = 0.005
        phases = -2.0 * np.pi * frequencies * delay_seconds

        result = PhaseMixin.group_delay(frequencies, phases)

        np.testing.assert_allclose(result, delay_seconds, atol=1e-9)

    def test_callable_on_an_instance_too(self) -> None:
        w = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        frequencies = np.array([1.0, 2.0, 3.0])
        phases = np.array([0.0, -0.1, -0.2])
        result = w.group_delay(frequencies, phases)
        self.assertEqual(result.shape, (3,))

    def test_shape_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            PhaseMixin.group_delay(np.array([1.0, 2.0, 3.0]), np.array([0.0, 0.1]))

    def test_too_short_raises(self) -> None:
        with self.assertRaises(ValueError):
            PhaseMixin.group_delay(np.array([1.0]), np.array([0.0]))


class TestMetadataPreserved(unittest.TestCase):
    """Unary results share ``dt``/``t0`` with the source."""

    def test_instantaneous_phase_preserves_dt_and_t0(self) -> None:
        w = _wrap(Waveform1D.sine(50, frequency=5.0, dt_seconds=0.02, t0_seconds=3.0))
        phase = w.instantaneous_phase()
        self.assertEqual(phase.dt, w.dt)
        self.assertEqual(phase.t0, w.t0)


if __name__ == "__main__":
    unittest.main()
