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


if __name__ == "__main__":
    unittest.main()
