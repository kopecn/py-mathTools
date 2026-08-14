"""Unit tests for the first/second-order position-interface step solvers
(``math_tools.otg.steps.position_first_order``,
``...position_second_order``).

See ``.claude/specs/otg.md`` §Internal fidelity requirements 1, 2 and
``.claude/action-plan/37-otg-position-first-second-steps.md``'s TDD steps:
pin the velocity-limited-only analytic duration for the first-order
(velocity interface) profile, and both the trapezoidal (cruise-phase) and
triangular (no-cruise) analytic regimes for the second-order
(velocity+acceleration interface) profile, in both directions (``Δp < 0``
exercises ``Direction.DOWN``), plus a Step2 (prescribed-duration) case for
each order. All boundary-array/position expectations are computed
independently via ``integrate_jerk`` in each test (never by re-deriving
them from ``Profile``'s own loop), matching
``tests/otg/steps/test_velocity_steps.py``'s established convention.
"""

import math
import unittest

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.block import Block
from math_tools.otg.enums import Direction
from math_tools.otg.profile import Profile
from math_tools.otg.steps.position_first_order import (
    PositionFirstOrderStep1,
    PositionFirstOrderStep2,
)
from math_tools.otg.steps.position_second_order import (
    PositionSecondOrderStep1,
    PositionSecondOrderStep2,
)


class TestPositionFirstOrderStep1Up(unittest.TestCase):
    """Δp > 0: velocity-limited-only profile, ``t = Δp / vMax``,
    ``Direction.UP``.

    p0 = 0, pf = 5.0 => pd = 5.0; vMax = 2.0 => t3 = 2.5.
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = 5.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.step1 = PositionFirstOrderStep1(
            p0=self.p0, pf=self.pf, v_max=self.v_max, v_min=self.v_min
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_duration_and_direction(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        profile = self.block.p_min
        expected_t3 = (self.pf - self.p0) / self.v_max
        for i in (0, 1, 2, 4, 5, 6):
            self.assertEqual(profile.t[i], 0.0, msg=f"t[{i}]")
        self.assertAlmostEqual(profile.t[3], expected_t3, delta=1e-9)
        self.assertAlmostEqual(profile.t_sum[-1], expected_t3, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_t3, delta=1e-9)
        self.assertEqual(profile.direction, Direction.UP)

    def test_pins_position_endpoint(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        p, _, _ = integrate_jerk(profile.t[3], self.p0, self.v_max, 0.0, 0.0)
        self.assertAlmostEqual(profile.p[4], p, delta=1e-9)
        self.assertAlmostEqual(profile.p[-1], self.pf, delta=1e-8)


class TestPositionFirstOrderStep1Down(unittest.TestCase):
    """Δp < 0: velocity-limited-only profile, ``t = |Δp| / vMin``,
    ``Direction.DOWN``.

    p0 = 0, pf = -5.0 => pd = -5.0; vMin = -2.0 => t3 = 2.5.
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = -5.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.step1 = PositionFirstOrderStep1(
            p0=self.p0, pf=self.pf, v_max=self.v_max, v_min=self.v_min
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_duration_and_direction(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        profile = self.block.p_min
        expected_t3 = (self.pf - self.p0) / self.v_min
        for i in (0, 1, 2, 4, 5, 6):
            self.assertEqual(profile.t[i], 0.0, msg=f"t[{i}]")
        self.assertAlmostEqual(profile.t[3], expected_t3, delta=1e-9)
        self.assertAlmostEqual(profile.t_sum[-1], expected_t3, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_t3, delta=1e-9)
        self.assertEqual(profile.direction, Direction.DOWN)

    def test_pins_position_endpoint(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        p, _, _ = integrate_jerk(profile.t[3], self.p0, self.v_min, 0.0, 0.0)
        self.assertAlmostEqual(profile.p[4], p, delta=1e-9)
        self.assertAlmostEqual(profile.p[-1], self.pf, delta=1e-8)


class TestPositionFirstOrderStep2(unittest.TestCase):
    """Step2: a prescribed duration 2x the Step1 time-optimal duration
    must still yield a valid profile that reaches the target position and
    spans exactly the prescribed duration.
    """

    def test_prescribed_duration_reaches_target_position(self) -> None:
        p0, pf, v_max, v_min = 0.0, 5.0, 2.0, -2.0
        t_opt = (pf - p0) / v_max  # 2.5, per TestPositionFirstOrderStep1Up
        tf = 2.0 * t_opt

        profile = Profile()
        profile.set_boundary(p0, 0.0, 0.0, pf, 0.0, 0.0)

        step2 = PositionFirstOrderStep2(tf=tf, p0=p0, pf=pf, v_max=v_max, v_min=v_min)
        success = step2.get_profile(profile)
        self.assertTrue(success)

        self.assertAlmostEqual(profile.t[3], tf, delta=1e-9)
        self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-8)
        self.assertAlmostEqual(profile.p[-1], pf, delta=1e-8)


class TestPositionSecondOrderStep1Trapezoidal(unittest.TestCase):
    """|Δp| >= vMax^2/aMax: the time-optimal profile is trapezoidal
    (ramp to vMax, cruise, ramp to 0), total time
    ``t = Δp/vMax + vMax/aMax``, ``Direction.UP``.

    vMax = aMax = 2.0 => vMax^2/aMax = 2.0; pd = 6.0 >= 2.0.
    Hand-derived (point-to-point, v0 = vf = 0):
        t0 = vMax/aMax = 1.0
        t1 = pd/vMax - vMax/aMax = 3.0 - 1.0 = 2.0
        t2 = vMax/aMax = 1.0
    Total = pd/vMax + vMax/aMax = 3.0 + 1.0 = 4.0.
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = 6.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.a_max = 2.0
        self.a_min = -2.0
        self.step1 = PositionSecondOrderStep1(
            p0=self.p0,
            v0=0.0,
            pf=self.pf,
            vf=0.0,
            v_max=self.v_max,
            v_min=self.v_min,
            a_max=self.a_max,
            a_min=self.a_min,
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_trapezoidal_segment_times_and_direction(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        pd = self.pf - self.p0
        expected_t = [
            self.v_max / self.a_max,
            pd / self.v_max - self.v_max / self.a_max,
            self.v_max / self.a_max,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = pd / self.v_max + self.v_max / self.a_max
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)
        self.assertEqual(profile.direction, Direction.UP)

    def test_pins_boundary_arrays(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_a = [self.a_max, 0.0, self.a_min, 0.0, 0.0, 0.0, 0.0]
        p, v = self.p0, 0.0
        for i in range(7):
            p, v, _ = integrate_jerk(profile.t[i], p, v, expected_a[i], 0.0)
            self.assertAlmostEqual(profile.p[i + 1], p, delta=1e-9, msg=f"p[{i + 1}]")
            self.assertAlmostEqual(profile.v[i + 1], v, delta=1e-9, msg=f"v[{i + 1}]")

        self.assertAlmostEqual(profile.p[-1], self.pf, delta=1e-8)
        self.assertAlmostEqual(profile.v[-1], 0.0, delta=1e-8)


class TestPositionSecondOrderStep1Triangular(unittest.TestCase):
    """|Δp| < vMax^2/aMax: the time-optimal profile is triangular (no
    cruise phase), total time ``t = 2*sqrt(|Δp|/aMax)``, ``Direction.DOWN``.

    vMax = aMax = 2.0 => vMax^2/aMax = 2.0; pd = -1.0, |pd| = 1.0 < 2.0.
    Hand-derived (point-to-point, v0 = vf = 0, Solution 1 of ``timeNone``):
        t0 = t2 = sqrt(|pd|/aMax) = sqrt(0.5)
    Total = 2*sqrt(|pd|/aMax) = 2*sqrt(0.5).
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = -1.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.a_max = 2.0
        self.a_min = -2.0
        self.step1 = PositionSecondOrderStep1(
            p0=self.p0,
            v0=0.0,
            pf=self.pf,
            vf=0.0,
            v_max=self.v_max,
            v_min=self.v_min,
            a_max=self.a_max,
            a_min=self.a_min,
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_triangular_segment_times_and_direction(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        pd = self.pf - self.p0
        t0 = math.sqrt(abs(pd) / self.a_max)
        expected_t = [t0, 0.0, t0, 0.0, 0.0, 0.0, 0.0]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = 2.0 * math.sqrt(abs(pd) / self.a_max)
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)
        self.assertEqual(profile.direction, Direction.DOWN)

    def test_pins_boundary_arrays(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_a = [self.a_min, 0.0, self.a_max, 0.0, 0.0, 0.0, 0.0]
        p, v = self.p0, 0.0
        for i in range(7):
            p, v, _ = integrate_jerk(profile.t[i], p, v, expected_a[i], 0.0)
            self.assertAlmostEqual(profile.p[i + 1], p, delta=1e-9, msg=f"p[{i + 1}]")
            self.assertAlmostEqual(profile.v[i + 1], v, delta=1e-9, msg=f"v[{i + 1}]")

        self.assertAlmostEqual(profile.p[-1], self.pf, delta=1e-8)
        self.assertAlmostEqual(profile.v[-1], 0.0, delta=1e-8)


class TestPositionSecondOrderStep2(unittest.TestCase):
    """Step2: a prescribed duration 2x the Step1 time-optimal (trapezoidal)
    duration must still yield a valid profile that reaches the target
    position and spans exactly the prescribed duration.
    """

    def test_prescribed_duration_reaches_target_position(self) -> None:
        p0, pf = 0.0, 6.0
        v_max, v_min, a_max, a_min = 2.0, -2.0, 2.0, -2.0
        pd = pf - p0
        t_opt = pd / v_max + v_max / a_max  # 4.0, per the trapezoidal Step1 case
        tf = 2.0 * t_opt

        profile = Profile()
        profile.set_boundary(p0, 0.0, 0.0, pf, 0.0, 0.0)

        step2 = PositionSecondOrderStep2(
            tf=tf, p0=p0, v0=0.0, pf=pf, vf=0.0, v_max=v_max, v_min=v_min, a_max=a_max, a_min=a_min
        )
        success = step2.get_profile(profile)
        self.assertTrue(success)

        self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-8)
        self.assertAlmostEqual(profile.p[-1], pf, delta=1e-8)
        self.assertAlmostEqual(profile.v[-1], 0.0, delta=1e-7)


if __name__ == "__main__":
    unittest.main()
