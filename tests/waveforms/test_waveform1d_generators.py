"""Dedicated compliance tests for the ``Waveform1D`` signal generators.

Covers waveformCore.md §Waveform1D Constructors (generators) and §Compliance
4. The generators themselves were implemented as part of chunk 11 (the
umbrella spec groups them under "Constructors"); chunk 11's own test suite
(``test_waveform1d_core.py::TestGenerators``) already exercises every
generator's shape. This file supplies the specific named compliance-4
checks the chunk plan calls for (sine vs. ``np.sin``, seeded white-noise
reproducibility/divergence, impulse summation, chirp instantaneous-frequency
endpoints) plus the no-time-args / no-frequency-arg construction pinned by
this chunk's own acceptance criteria, rather than duplicating chunk 11's
broader shape coverage.
"""

from __future__ import annotations

import unittest

import numpy as np

from math_tools.waveforms import Waveform1D

_ALL_GENERATOR_NAMES = [
    "sine",
    "cosine",
    "square",
    "triangle",
    "sawtooth",
    "chirp",
    "exponential_decay",
    "exponential_growth",
    "polynomial",
    "linear_ramp",
    "logarithm",
    "logarithm10",
    "square_root",
    "heaviside",
    "relu",
    "sigmoid",
    "white_noise",
    "constant",
    "impulse",
    "damped_sinusoid",
    "counter",
    "digital_square",
]


class TestAllGeneratorsExist(unittest.TestCase):
    def test_all_21_plus_generators_are_classmethods(self) -> None:
        for name in _ALL_GENERATOR_NAMES:
            self.assertTrue(hasattr(Waveform1D, name), f"missing generator: {name}")
            self.assertTrue(callable(getattr(Waveform1D, name)))
        self.assertGreaterEqual(len(_ALL_GENERATOR_NAMES), 21)


class TestSineNoTimeArgs(unittest.TestCase):
    def test_sine_n_only_constructs_with_dt_one_second(self) -> None:
        """waveformCore.md §Time axis / this chunk's acceptance criteria pin
        ``Waveform1D.sine(n=1000)`` as legal with no other arguments."""
        w = Waveform1D.sine(n=1000)
        self.assertEqual(len(w), 1000)
        self.assertEqual(w.dt.seconds_as_float, 1.0)


class TestComplianceFourSine(unittest.TestCase):
    def test_sine_matches_np_sin_on_time_axis(self) -> None:
        w = Waveform1D.sine(n=200, frequency=3.0, amplitude=2.0, dt_seconds=0.005)
        t = w.time_axis()
        expected = 2.0 * np.sin(2.0 * np.pi * 3.0 * t)
        np.testing.assert_allclose(w.values, expected, atol=1e-12)


class TestComplianceFourWhiteNoise(unittest.TestCase):
    def test_seeded_white_noise_is_reproducible(self) -> None:
        a = Waveform1D.white_noise(n=50, seed=7)
        b = Waveform1D.white_noise(n=50, seed=7)
        np.testing.assert_array_equal(a.values, b.values)

    def test_white_noise_k_plus_one_seed_differs(self) -> None:
        a = Waveform1D.white_noise(n=50, seed=7)
        b = Waveform1D.white_noise(n=50, seed=8)
        self.assertFalse(np.array_equal(a.values, b.values))


class TestComplianceFourImpulse(unittest.TestCase):
    def test_impulse_sums_to_one_sample_of_amplitude(self) -> None:
        w = Waveform1D.impulse(n=20, amplitude=4.5, impulse_index=3)
        self.assertAlmostEqual(float(np.sum(w.values)), 4.5)
        nonzero = np.flatnonzero(w.values)
        self.assertEqual(len(nonzero), 1)
        self.assertEqual(nonzero[0], 3)


class TestComplianceFourCounter(unittest.TestCase):
    def test_counter_is_arange_based(self) -> None:
        w = Waveform1D.counter(n=6, start_value=10, increment=3)
        np.testing.assert_array_equal(w.values, 10 + 3 * np.arange(6))


class TestComplianceFourChirp(unittest.TestCase):
    def test_chirp_instantaneous_frequency_endpoints(self) -> None:
        """Coarse check via zero-crossing counts in the first vs. last quarter:
        a chirp sweeping low-to-high frequency should cross zero far more
        often in its last quarter than its first."""
        n = 4000
        w = Waveform1D.chirp(n=n, start_frequency=1.0, end_frequency=50.0, dt_seconds=0.001)
        values = w.values
        quarter = n // 4

        def zero_crossings(segment: np.typing.NDArray[np.float64]) -> int:
            return int(np.sum(np.diff(np.sign(segment)) != 0))

        first_quarter_crossings = zero_crossings(values[:quarter])
        last_quarter_crossings = zero_crossings(values[-quarter:])
        self.assertGreater(last_quarter_crossings, first_quarter_crossings)


class TestGeneratorSpanConvention(unittest.TestCase):
    """waveformCore.md's generator span convention: for an ``n``-sample
    waveform, the span is ``(n-1)*dt`` (endpoint-inclusive), not ``n*dt``.
    Pins chunk 51 / post-audit finding C-15."""

    def test_heaviside_default_step_time_is_midpoint_of_sample_span(self) -> None:
        """``n=5``, ``dt=1s`` -> true span ``[0, 4]``, midpoint ``t=2`` lands
        exactly on sample index 2. The buggy ``n*dt/2 = 2.5`` convention
        would instead step at index 3: ``[0, 0, 0, 1, 1]``."""
        w = Waveform1D.heaviside(n=5, dt_seconds=1.0)
        np.testing.assert_array_equal(w.values, [0.0, 0.0, 1.0, 1.0, 1.0])

    def test_sigmoid_default_center_is_midpoint_of_sample_span(self) -> None:
        """Same ``n=5`` span; a logistic sigmoid centered exactly on a sample
        evaluates to ``0.5`` there. The buggy ``n*dt/2 = 2.5`` convention
        would put the center between samples 2 and 3, so sample 2 would not
        be ``0.5``."""
        w = Waveform1D.sigmoid(n=5, dt_seconds=1.0)
        self.assertAlmostEqual(w.values[2], 0.5, places=12)

    def test_chirp_final_sample_instantaneous_frequency_equals_end_frequency(self) -> None:
        """Recover the chirp's realized sweep rate from its own zero
        crossings (interpolated crossing times fit against the quadratic
        phase model ``k/2 = start*t + 0.5*sr*t**2``, with the crossing
        order used as a linear proxy for ``k`` -- valid since the swept
        frequency stays positive and monotonic throughout, so no crossing is
        missed or duplicated) and check the resulting final-sample
        instantaneous frequency against ``end_frequency``. This is a real
        measurement of the generated samples, not a re-derivation of the
        generator's own formula: under the pre-fix ``n*dt`` span convention
        the realized sweep rate is measurably slower, so the recovered final
        frequency undershoots ``end_frequency`` by ``(end-start)/n``.
        """
        n = 201
        dt_seconds = 0.001
        start_frequency = 5.0
        end_frequency = 50.0
        w = Waveform1D.chirp(
            n=n,
            start_frequency=start_frequency,
            end_frequency=end_frequency,
            dt_seconds=dt_seconds,
        )
        t = w.time_axis()
        values = w.values

        signs = np.sign(values)
        crossing_indices = np.flatnonzero(np.diff(signs) != 0)
        t0s = t[crossing_indices]
        t1s = t[crossing_indices + 1]
        v0s = values[crossing_indices]
        v1s = values[crossing_indices + 1]
        crossing_times = t0s + (0.0 - v0s) * (t1s - t0s) / (v1s - v0s)
        self.assertGreater(
            len(crossing_times), 4, "need several zero crossings to fit the sweep rate"
        )

        order = np.arange(len(crossing_times), dtype=np.float64)
        y = order / 2.0 - start_frequency * crossing_times
        x = crossing_times * crossing_times
        slope, _intercept = np.polyfit(x, y, 1)
        measured_sweep_rate = 2.0 * slope

        measured_final_frequency = start_frequency + measured_sweep_rate * t[-1]
        self.assertAlmostEqual(measured_final_frequency, end_frequency, delta=0.05)

    def test_generators_with_n_equals_one_do_not_raise(self) -> None:
        """``n=1`` is a zero-length span; none of the three affected
        generators should divide by zero or otherwise raise."""
        heaviside = Waveform1D.heaviside(n=1, dt_seconds=1.0)
        sigmoid = Waveform1D.sigmoid(n=1, dt_seconds=1.0)
        chirp = Waveform1D.chirp(n=1, start_frequency=1.0, end_frequency=10.0, dt_seconds=1.0)

        self.assertEqual(len(heaviside), 1)
        self.assertEqual(len(sigmoid), 1)
        self.assertEqual(len(chirp), 1)
        self.assertAlmostEqual(sigmoid.values[0], 0.5, places=12)


if __name__ == "__main__":
    unittest.main()
