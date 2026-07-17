"""Unit tests for ``dsp/_calc.py`` (``CalcMixin``: ``integrate``/``derivative``).

Covers waveformDsp.md §Family contracts (``CalcMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin via a local test subclass
``class _W(CalcMixin, Waveform1D): pass`` (the pattern every DSP mixin
chunk's tests use).
"""

import unittest

import numpy as np

from math_tools.waveforms.dsp._calc import CalcMixin
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.waveform1d import Waveform1D


class _W(CalcMixin, Waveform1D):
    pass


def _wrap(base: WaveformProtocol) -> _W:
    """Rewrap a ``WaveformProtocol``-satisfying result (a bare ``Waveform1D``, whether
    from a generator classmethod's static ``-> Waveform1D`` return type -- even when
    called as ``_W.sine(...)`` -- or from ``CalcMixin``'s own ``-> WaveformProtocol``
    results) as ``_W`` so ``CalcMixin`` methods are statically visible under mypy
    strict."""
    return _W(base.values, dt=base.dt, t0=base.t0)


class TestDerivativeOfLinearRampIsConstant(unittest.TestCase):
    """§Compliance 1: derivative of a linear ramp is constant (atol 1e-9)."""

    def test_constant_slope(self) -> None:
        n = 500
        dt_seconds = 1.0 / 500.0
        w = _wrap(Waveform1D.linear_ramp(n, start_value=0.0, end_value=1.0, dt_seconds=dt_seconds))
        derived = w.derivative()

        expected_slope = 1.0 / ((n - 1) * dt_seconds)
        np.testing.assert_allclose(
            derived.values, np.full(n, expected_slope), rtol=0.0, atol=1e-9
        )

    def test_negative_slope(self) -> None:
        n = 200
        dt_seconds = 0.01
        w = _wrap(
            Waveform1D.linear_ramp(n, start_value=5.0, end_value=-5.0, dt_seconds=dt_seconds)
        )
        derived = w.derivative()

        expected_slope = -10.0 / ((n - 1) * dt_seconds)
        np.testing.assert_allclose(
            derived.values, np.full(n, expected_slope), rtol=0.0, atol=1e-9
        )


class TestIntegrateOfConstantIsARamp(unittest.TestCase):
    """§Compliance 1: integrate of a constant is a ramp."""

    def test_exact_linear_ramp(self) -> None:
        n = 300
        dt_seconds = 0.02
        level = 3.0
        w = _wrap(Waveform1D.constant(n, value=level, dt_seconds=dt_seconds))
        integrated = w.integrate()

        expected = level * dt_seconds * np.arange(n, dtype=np.float64)
        np.testing.assert_allclose(integrated.values, expected, rtol=0.0, atol=1e-9)

    def test_initial_value_offsets_the_ramp(self) -> None:
        n = 100
        dt_seconds = 0.05
        level = 2.0
        initial_value = 10.0
        w = _wrap(Waveform1D.constant(n, value=level, dt_seconds=dt_seconds))
        integrated = w.integrate(initial_value=initial_value)

        expected = initial_value + level * dt_seconds * np.arange(n, dtype=np.float64)
        np.testing.assert_allclose(integrated.values, expected, rtol=0.0, atol=1e-9)
        self.assertEqual(integrated.values[0], initial_value)

    def test_default_initial_value_is_zero(self) -> None:
        w = _wrap(Waveform1D.constant(50, value=1.0, dt_seconds=0.1))
        integrated = w.integrate()
        self.assertEqual(integrated.values[0], 0.0)


class TestIntegrateThenDerivativeRecoversInterior(unittest.TestCase):
    """§Compliance 1: ``integrate().derivative()`` recovers a smooth signal
    (interior points, rtol 1e-6)."""

    def test_sine_wave(self) -> None:
        n = 10_000
        dt_seconds = 1.0 / n
        original = _wrap(Waveform1D.sine(n, frequency=2.0, amplitude=1.0, dt_seconds=dt_seconds))

        integrated = original.integrate()
        # `integrate()` builds its result via `_with_values`, which (per
        # `Waveform1D._with_values`) always yields a bare `Waveform1D` --
        # rewrap in `_W` to exercise `CalcMixin.derivative` again.
        recovered = _wrap(integrated).derivative()

        interior = slice(10, -10)
        np.testing.assert_allclose(
            recovered.values[interior], original.values[interior], rtol=1e-6, atol=1e-9
        )


class TestMetadataPreserved(unittest.TestCase):
    """``integrate``/``derivative`` results share ``dt``/``t0`` with the source."""

    def test_integrate_preserves_dt_and_t0(self) -> None:
        w = _wrap(Waveform1D.constant(20, value=1.0, dt_seconds=0.25, t0_seconds=5.0))
        integrated = w.integrate()
        self.assertEqual(integrated.dt, w.dt)
        self.assertEqual(integrated.t0, w.t0)

    def test_derivative_preserves_dt_and_t0(self) -> None:
        w = _wrap(
            Waveform1D.linear_ramp(
                20, start_value=0.0, end_value=1.0, dt_seconds=0.25, t0_seconds=5.0
            )
        )
        derived = w.derivative()
        self.assertEqual(derived.dt, w.dt)
        self.assertEqual(derived.t0, w.t0)


class TestMinimumLengthRaises(unittest.TestCase):
    """waveformDsp.md §Numerical conventions: too-short input raises ``ValueError``
    naming the requirement (this is not a detector method)."""

    def test_integrate_on_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.integrate()

    def test_derivative_on_empty_waveform_raises(self) -> None:
        w = _W([])
        with self.assertRaises(ValueError):
            w.derivative()

    def test_derivative_on_single_sample_raises(self) -> None:
        w = _W([1.0])
        with self.assertRaises(ValueError):
            w.derivative()

    def test_integrate_on_single_sample_succeeds(self) -> None:
        # integrate only needs >= 1 sample (unlike derivative's >= 2).
        w = _W([7.0])
        integrated = w.integrate(initial_value=2.0)
        self.assertEqual(list(integrated.values), [2.0])


if __name__ == "__main__":
    unittest.main()
