"""Unit tests for ``dsp/_envelope.py`` (``EnvelopeMixin``).

Covers waveformDsp.md §Family contracts (``EnvelopeMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import WaveformInstantaneousMethod
from math_tools.waveforms.waveform1d import Waveform1D


def _wrap(base: WaveformProtocol) -> Waveform1D:
    """Rewrap a ``WaveformProtocol``-satisfying result as ``Waveform1D`` (see ``test_calc.py``)."""
    return Waveform1D(base.values, dt=base.dt, t0=base.t0)


class TestAmplitudeEnvelopeOfSineIsApproximatelyConstant(unittest.TestCase):
    """§Compliance 1: envelope of ``A*sin`` is ~= A on the interior (rtol 5e-2)."""

    def test_interior_matches_amplitude(self) -> None:
        n = 2000
        amplitude = 3.0
        w = _wrap(
            Waveform1D.sine(n, frequency=20.0, amplitude=amplitude, dt_seconds=1.0 / 2000.0)
        )

        envelope = w.amplitude_envelope()

        interior = slice(50, -50)
        np.testing.assert_allclose(
            envelope.values[interior],
            np.full(n, amplitude)[interior],
            rtol=5e-2,
        )

    def test_result_length_matches_input(self) -> None:
        w = _wrap(Waveform1D.sine(500, frequency=10.0, dt_seconds=1.0 / 500.0))
        envelope = w.amplitude_envelope()
        self.assertEqual(len(envelope.values), 500)

    def test_metadata_preserved(self) -> None:
        w = _wrap(
            Waveform1D.sine(100, frequency=5.0, dt_seconds=0.01, t0_seconds=2.0)
        )
        envelope = w.amplitude_envelope()
        self.assertEqual(envelope.dt, w.dt)
        self.assertEqual(envelope.t0, w.t0)


class TestAmplitudeEnvelopeOfDampedSinusoidTracksDecay(unittest.TestCase):
    """§Compliance 1: envelope of a damped sinusoid tracks ``A*exp(-t/tau)`` (interior)."""

    def test_interior_tracks_exponential_decay(self) -> None:
        n = 4000
        dt_seconds = 1.0 / 4000.0
        amplitude = 2.0
        time_constant = 1.5
        w = _wrap(
            Waveform1D.damped_sinusoid(
                n,
                frequency=30.0,
                damping_constant=time_constant,
                amplitude=amplitude,
                dt_seconds=dt_seconds,
            )
        )

        envelope = w.amplitude_envelope()

        t = np.arange(n, dtype=np.float64) * dt_seconds
        expected = amplitude * np.exp(-t / time_constant)
        interior = slice(100, -100)
        np.testing.assert_allclose(
            envelope.values[interior], expected[interior], rtol=0.1
        )


class TestAmplitudeEnvelopeMinimumLengthRaises(unittest.TestCase):
    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.amplitude_envelope()


class TestUpperLowerEnvelopes(unittest.TestCase):
    """§Compliance 1: upper >= lower everywhere."""

    def test_upper_at_least_lower_for_sine(self) -> None:
        w = _wrap(Waveform1D.sine(500, frequency=10.0, amplitude=2.0, dt_seconds=1.0 / 500.0))
        upper, lower = w.upper_lower_envelopes()
        self.assertTrue(np.all(upper.values >= lower.values - 1e-9))

    def test_upper_at_least_lower_for_white_noise(self) -> None:
        w = _wrap(Waveform1D.white_noise(500, amplitude=1.0, seed=3, dt_seconds=0.01))
        upper, lower = w.upper_lower_envelopes()
        self.assertTrue(np.all(upper.values >= lower.values - 1e-9))

    def test_result_lengths_match_input(self) -> None:
        w = _wrap(Waveform1D.sine(300, frequency=5.0, dt_seconds=0.01))
        upper, lower = w.upper_lower_envelopes()
        self.assertEqual(len(upper.values), 300)
        self.assertEqual(len(lower.values), 300)

    def test_metadata_preserved(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=5.0, dt_seconds=0.02, t0_seconds=1.0))
        upper, lower = w.upper_lower_envelopes()
        self.assertEqual(upper.dt, w.dt)
        self.assertEqual(upper.t0, w.t0)
        self.assertEqual(lower.dt, w.dt)
        self.assertEqual(lower.t0, w.t0)

    def test_boundary_samples_are_anchored(self) -> None:
        # A monotonic ramp has no interior local extrema, so the envelope must
        # fall back to interpolating between the two boundary samples.
        w = _wrap(Waveform1D.linear_ramp(50, start_value=0.0, end_value=10.0, dt_seconds=0.1))
        upper, lower = w.upper_lower_envelopes()
        self.assertAlmostEqual(float(upper.values[0]), 0.0, places=9)
        self.assertAlmostEqual(float(upper.values[-1]), 10.0, places=9)
        self.assertAlmostEqual(float(lower.values[0]), 0.0, places=9)
        self.assertAlmostEqual(float(lower.values[-1]), 10.0, places=9)

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.upper_lower_envelopes()


class TestInstantaneousAmplitudeMethods(unittest.TestCase):
    """§Compliance 1: each ``WaveformInstantaneousMethod`` returns the right length."""

    def test_hilbert_length(self) -> None:
        w = _wrap(Waveform1D.sine(400, frequency=10.0, dt_seconds=0.01))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.HILBERT)
        self.assertEqual(len(result.values), 400)

    def test_rms_length(self) -> None:
        w = _wrap(Waveform1D.sine(400, frequency=10.0, dt_seconds=0.01))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.RMS)
        self.assertEqual(len(result.values), 400)

    def test_peak_length(self) -> None:
        w = _wrap(Waveform1D.sine(400, frequency=10.0, dt_seconds=0.01))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.PEAK)
        self.assertEqual(len(result.values), 400)

    def test_hilbert_matches_amplitude_envelope(self) -> None:
        w = _wrap(Waveform1D.sine(400, frequency=10.0, dt_seconds=0.01))
        via_dispatch = w.instantaneous_amplitude(WaveformInstantaneousMethod.HILBERT)
        via_direct = w.amplitude_envelope()
        np.testing.assert_allclose(via_dispatch.values, via_direct.values)

    def test_rms_is_nonnegative(self) -> None:
        w = _wrap(Waveform1D.white_noise(300, amplitude=1.0, seed=1, dt_seconds=0.01))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.RMS)
        self.assertTrue(np.all(result.values >= 0.0))

    def test_rms_window_size_less_than_one_raises(self) -> None:
        w = _wrap(Waveform1D.sine(50, frequency=5.0, dt_seconds=0.01))
        with self.assertRaises(ValueError):
            w.instantaneous_amplitude(WaveformInstantaneousMethod.RMS, window_size=0)

    def test_peak_is_nonnegative(self) -> None:
        w = _wrap(Waveform1D.sine(400, frequency=10.0, dt_seconds=0.01))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.PEAK)
        self.assertTrue(np.all(result.values >= -1e-9))

    def test_empty_waveform_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.instantaneous_amplitude()

    def test_default_method_is_hilbert(self) -> None:
        w = _wrap(Waveform1D.sine(200, frequency=10.0, dt_seconds=0.01))
        default_result = w.instantaneous_amplitude()
        hilbert_result = w.instantaneous_amplitude(WaveformInstantaneousMethod.HILBERT)
        np.testing.assert_allclose(default_result.values, hilbert_result.values)

    def test_metadata_preserved(self) -> None:
        w = _wrap(Waveform1D.sine(100, frequency=5.0, dt_seconds=0.02, t0_seconds=1.0))
        result = w.instantaneous_amplitude(WaveformInstantaneousMethod.RMS)
        self.assertEqual(result.dt, w.dt)
        self.assertEqual(result.t0, w.t0)


if __name__ == "__main__":
    unittest.main()
