"""Unit tests for the velocity-interface step solvers
(``math_tools.otg.steps.velocity_second_order``,
``...velocity_third_order``).

See ``.claude/specs/otg.md`` §Internal fidelity requirements 1, 2 and
``.claude/action-plan/36-otg-velocity-steps.md``'s TDD steps: pin both the
trapezoidal-acceleration and triangular analytic regimes for the
third-order (jerk-limited) interface, the ``t = Δv / a`` regime for the
second-order (no jerk limit) interface, and a Step2 (prescribed-duration)
case for each order. All boundary-array expectations are computed
independently via ``integrate_jerk`` in each test (never by re-deriving
them from ``Profile``'s own loop), matching ``tests/otg/test_profile.py``'s
convention.
"""

import math
import unittest

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.block import Block
from math_tools.otg.profile import Profile
from math_tools.otg.steps.velocity_second_order import (
    VelocitySecondOrderStep1,
    VelocitySecondOrderStep2,
)
from math_tools.otg.steps.velocity_third_order import (
    VelocityThirdOrderStep1,
    VelocityThirdOrderStep2,
)


class TestVelocityThirdOrderStep1Trapezoidal(unittest.TestCase):
    """Δv >= a²/j: the time-optimal profile is trapezoidal-acceleration
    (ramp to +a, hold, ramp to 0), total time ``t = Δv/a + a/j``.

    a = 2.0, j = 1.0 => a²/j = 4.0; Δv = 6.0 >= 4.0.
    Hand-derived segment times (ACC0 reached limits, UDDU):
        t0 = a/j = 2.0
        t1 = Δv/a - a/j = 3.0 - 2.0 = 1.0
        t2 = a/j = 2.0
    Total = Δv/a + a/j = 3.0 + 2.0 = 5.0.
    """

    def setUp(self) -> None:
        self.a = 2.0
        self.j = 1.0
        self.dv = 6.0
        self.step1 = VelocityThirdOrderStep1(
            v0=0.0, a0=0.0, vf=self.dv, af=0.0, a_max=self.a, a_min=-self.a, j_max=self.j
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary_for_velocity(
            p0_new=0.0, v0_new=0.0, a0_new=0.0, vf_new=self.dv, af_new=0.0
        )
        self.block = Block()

    def test_pins_trapezoidal_segment_times_and_total_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        expected_t = [
            self.a / self.j,
            self.dv / self.a - self.a / self.j,
            self.a / self.j,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = self.dv / self.a + self.a / self.j
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)

    def test_pins_boundary_arrays(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_j = [self.j, 0.0, -self.j, 0.0, 0.0, 0.0, 0.0]
        p, v, a = 0.0, 0.0, 0.0
        for i in range(7):
            p, v, a = integrate_jerk(profile.t[i], p, v, a, expected_j[i])
            self.assertAlmostEqual(profile.p[i + 1], p, delta=1e-9, msg=f"p[{i + 1}]")
            self.assertAlmostEqual(profile.v[i + 1], v, delta=1e-9, msg=f"v[{i + 1}]")
            self.assertAlmostEqual(profile.a[i + 1], a, delta=1e-9, msg=f"a[{i + 1}]")

        self.assertAlmostEqual(profile.v[-1], self.dv, delta=1e-8)
        self.assertAlmostEqual(profile.a[-1], 0.0, delta=1e-10)


class TestVelocityThirdOrderStep1Triangular(unittest.TestCase):
    """Δv < a²/j: the time-optimal profile is triangular (no constant-accel
    plateau), total time ``t = 2 * sqrt(Δv/j)``.

    a = 2.0, j = 1.0 => a²/j = 4.0; Δv = 3.0 < 4.0.
    Hand-derived (Solution 2 of ``timeNone``): t0 = t2 = sqrt(Δv/j),
    t1 = 0. Peak accel reached = sqrt(j*Δv) = sqrt(3) < a = 2.0, so the
    acceleration limit is never actually touched (NONE reached-limits).
    """

    def setUp(self) -> None:
        self.a = 2.0
        self.j = 1.0
        self.dv = 3.0
        self.step1 = VelocityThirdOrderStep1(
            v0=0.0, a0=0.0, vf=self.dv, af=0.0, a_max=self.a, a_min=-self.a, j_max=self.j
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary_for_velocity(
            p0_new=0.0, v0_new=0.0, a0_new=0.0, vf_new=self.dv, af_new=0.0
        )
        self.block = Block()

    def test_pins_triangular_segment_times_and_total_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        t0 = math.sqrt(self.dv / self.j)
        expected_t = [t0, 0.0, t0, 0.0, 0.0, 0.0, 0.0]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = 2.0 * math.sqrt(self.dv / self.j)
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)

    def test_pins_boundary_arrays(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_j = [self.j, 0.0, -self.j, 0.0, 0.0, 0.0, 0.0]
        p, v, a = 0.0, 0.0, 0.0
        for i in range(7):
            p, v, a = integrate_jerk(profile.t[i], p, v, a, expected_j[i])
            self.assertAlmostEqual(profile.p[i + 1], p, delta=1e-9, msg=f"p[{i + 1}]")
            self.assertAlmostEqual(profile.v[i + 1], v, delta=1e-9, msg=f"v[{i + 1}]")
            self.assertAlmostEqual(profile.a[i + 1], a, delta=1e-9, msg=f"a[{i + 1}]")

        self.assertAlmostEqual(profile.v[-1], self.dv, delta=1e-8)
        self.assertAlmostEqual(profile.a[-1], 0.0, delta=1e-10)


class TestVelocitySecondOrderStep1(unittest.TestCase):
    """No jerk limit: the time-optimal profile is a single constant-accel
    ramp, total time ``t = Δv / a``.

    Δv = 4.0, aMax = 2.0 => t1 = Δv / aMax = 2.0.
    """

    def setUp(self) -> None:
        self.a = 2.0
        self.dv = 4.0
        self.step1 = VelocitySecondOrderStep1(v0=0.0, vf=self.dv, a_max=self.a, a_min=-self.a)
        self.input_profile = Profile()
        self.input_profile.set_boundary_for_velocity(
            p0_new=0.0, v0_new=0.0, a0_new=0.0, vf_new=self.dv, af_new=0.0
        )
        self.block = Block()

    def test_pins_ramp_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        profile = self.block.p_min
        expected_t1 = self.dv / self.a
        self.assertEqual(profile.t[0], 0.0)
        self.assertAlmostEqual(profile.t[1], expected_t1, delta=1e-9)
        for i in range(2, 7):
            self.assertEqual(profile.t[i], 0.0, msg=f"t[{i}]")

        self.assertAlmostEqual(profile.t_sum[-1], expected_t1, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_t1, delta=1e-9)

    def test_pins_boundary_arrays(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_a = [0.0, self.a, 0.0, 0.0, 0.0, 0.0, 0.0]
        p, v = 0.0, 0.0
        for i in range(7):
            p, v, _ = integrate_jerk(profile.t[i], p, v, expected_a[i], 0.0)
            self.assertAlmostEqual(profile.p[i + 1], p, delta=1e-9, msg=f"p[{i + 1}]")
            self.assertAlmostEqual(profile.v[i + 1], v, delta=1e-9, msg=f"v[{i + 1}]")

        self.assertAlmostEqual(profile.v[-1], self.dv, delta=1e-8)


class TestVelocityThirdOrderStep2(unittest.TestCase):
    """Step2: a prescribed duration 1.5x the Step1 time-optimal duration
    for the same trapezoidal-regime target must still yield a valid
    profile that hits the target velocity/acceleration, and must span
    exactly the prescribed duration.
    """

    def test_prescribed_duration_hits_target_velocity(self) -> None:
        a, j, dv = 2.0, 1.0, 6.0
        t_opt = dv / a + a / j  # 5.0, per TestVelocityThirdOrderStep1Trapezoidal
        tf = 1.5 * t_opt

        profile = Profile()
        profile.set_boundary_for_velocity(p0_new=0.0, v0_new=0.0, a0_new=0.0, vf_new=dv, af_new=0.0)

        step2 = VelocityThirdOrderStep2(
            tf=tf, v0=0.0, a0=0.0, vf=dv, af=0.0, a_max=a, a_min=-a, j_max=j
        )
        success = step2.get_profile(profile)
        self.assertTrue(success)

        self.assertAlmostEqual(profile.v[-1], dv, delta=1e-8)
        self.assertAlmostEqual(profile.a[-1], 0.0, delta=1e-10)
        self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-8)
        self.assertAlmostEqual(profile.pf, profile.p[7], delta=0.0)


class TestVelocitySecondOrderStep2(unittest.TestCase):
    """Step2: a prescribed duration 1.5x the Step1 time-optimal duration
    must still yield a valid profile that hits the target velocity and
    spans exactly the prescribed duration.
    """

    def test_prescribed_duration_hits_target_velocity(self) -> None:
        a, dv = 2.0, 4.0
        t_opt = dv / a  # 2.0, per TestVelocitySecondOrderStep1
        tf = 1.5 * t_opt

        profile = Profile()
        profile.set_boundary_for_velocity(p0_new=0.0, v0_new=0.0, a0_new=0.0, vf_new=dv, af_new=0.0)

        step2 = VelocitySecondOrderStep2(tf=tf, v0=0.0, vf=dv, a_max=a, a_min=-a)
        success = step2.get_profile(profile)
        self.assertTrue(success)

        self.assertAlmostEqual(profile.v[-1], dv, delta=1e-8)
        self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-8)


if __name__ == "__main__":
    unittest.main()
