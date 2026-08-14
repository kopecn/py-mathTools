"""Unit tests for the third-order (jerk-limited) position-interface Step 1
solver (``math_tools.otg.steps.position_third_order_step1``).

See ``.claude/specs/otg.md`` §Internal fidelity requirements 1, 2 and
``.claude/action-plan/38-otg-position-third-step1.md``'s TDD steps: pin the
segment times and total duration for three hand-derivable cases -- (a) a
rest-to-rest long move that saturates velocity and acceleration limits
(ACC0_ACC1_VEL), (b) a rest-to-rest short move that is jerk-dominated and
never reaches either limit (NONE), and (c) a moving-start case (``a0 != 0``,
still ``NONE``). All three are cross-checked by re-integrating the returned
segment times independently via ``integrate_jerk`` and asserting the
integration lands on the target ``p``/``v``/``a`` state, matching
``tests/otg/steps/test_velocity_steps.py``'s established convention.
"""

import unittest

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.block import Block
from math_tools.otg.enums import ReachedLimits
from math_tools.otg.profile import Profile
from math_tools.otg.steps.position_third_order_step1 import PositionThirdOrderStep1


class TestPositionThirdOrderStep1LongMove(unittest.TestCase):
    """Rest-to-rest long move: velocity and acceleration limits are both
    saturated (ACC0_ACC1_VEL), a symmetric jerk-limited S-curve.

    v_max = 2, a_max = 1, j_max = 1 => t_j = a_max/j_max = 1 (jerk ramp
    time), the acceleration phase reaches a_max with a genuine 1s dwell
    (T_acc = v_max/a_max + a_max/j_max = 2 + 1 = 3, dwell = T_acc - 2*t_j =
    1). Choosing pd = 10 gives the well-known time-optimal duration
    identity ``t = pd/v_max + v_max/a_max + a_max/j_max = 5 + 2 + 1 = 8``
    (see otg.md's numeric-oracle convention), decomposed by symmetry into
    seven segments: jerk-up-accel, const-accel, jerk-down-accel (reaching
    v_max), cruise, jerk-down-decel, const-decel, jerk-up-decel (reaching
    rest) = [1, 1, 1, 2, 1, 1, 1].
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = 10.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.a_max = 1.0
        self.a_min = -1.0
        self.j_max = 1.0
        self.step1 = PositionThirdOrderStep1(
            p0=self.p0,
            v0=0.0,
            a0=0.0,
            pf=self.pf,
            vf=0.0,
            af=0.0,
            v_max=self.v_max,
            v_min=self.v_min,
            a_max=self.a_max,
            a_min=self.a_min,
            j_max=self.j_max,
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_segment_times_and_total_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        expected_t = [1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = self.pf / self.v_max + self.v_max / self.a_max + self.a_max / self.j_max
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)
        self.assertEqual(profile.limits, ReachedLimits.ACC0_ACC1_VEL)

    def test_reintegration_reaches_target_state(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_j = [self.j_max, 0.0, -self.j_max, 0.0, -self.j_max, 0.0, self.j_max]
        p, v, a = self.p0, 0.0, 0.0
        for i in range(7):
            p, v, a = integrate_jerk(profile.t[i], p, v, a, expected_j[i])
        self.assertAlmostEqual(p, self.pf, delta=1e-8)
        self.assertAlmostEqual(v, 0.0, delta=1e-8)
        self.assertAlmostEqual(a, 0.0, delta=1e-9)


class TestPositionThirdOrderStep1ShortMove(unittest.TestCase):
    """Rest-to-rest short move: jerk-dominated, neither v_max nor a_max is
    reached (NONE). The time-optimal three-segment jerk profile (+j, -j,
    +j; the middle -j segment runs through the accel zero-crossing so it
    covers twice the duration of the two ramps) has a closed form when
    v0 = a0 = vf = af = 0::

        t2 = (4 * pd / j_max) ** (1/3)
        t0 = t6 = t2 / 2

    derived from ``polynomNone`` collapsing to ``x*(x**3 - 4*pd/j) = 0``
    when all boundary velocities/accelerations are zero.
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.pf = 1.0
        self.v_max = 100.0
        self.v_min = -100.0
        self.a_max = 100.0
        self.a_min = -100.0
        self.j_max = 1.0
        self.step1 = PositionThirdOrderStep1(
            p0=self.p0,
            v0=0.0,
            a0=0.0,
            pf=self.pf,
            vf=0.0,
            af=0.0,
            v_max=self.v_max,
            v_min=self.v_min,
            a_max=self.a_max,
            a_min=self.a_min,
            j_max=self.j_max,
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, 0.0, self.pf, 0.0, 0.0)
        self.block = Block()

    def test_pins_segment_times_and_total_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        t2 = (4.0 * (self.pf - self.p0) / self.j_max) ** (1.0 / 3.0)
        expected_t = [t2 / 2, 0.0, t2, 0.0, 0.0, 0.0, t2 / 2]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = 2 * t2
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)
        self.assertEqual(profile.limits, ReachedLimits.NONE)

    def test_reintegration_reaches_target_state(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_j = [self.j_max, 0.0, -self.j_max, 0.0, 0.0, 0.0, self.j_max]
        p, v, a = self.p0, 0.0, 0.0
        for i in range(7):
            p, v, a = integrate_jerk(profile.t[i], p, v, a, expected_j[i])
        self.assertAlmostEqual(p, self.pf, delta=1e-8)
        self.assertAlmostEqual(v, 0.0, delta=1e-8)
        self.assertAlmostEqual(a, 0.0, delta=1e-9)


class TestPositionThirdOrderStep1MovingStart(unittest.TestCase):
    """Moving-start case: a0 = af = 0.5 != 0 (v0 = vf = 0), neither v_max
    nor a_max reached (NONE). With a0 = af = A the ``h2_none`` term
    collapses (``(a0^2 - af^2)/(2j) + (vf - v0) = 0``), reducing the
    quartic to the cubic ``t2^3 - (4*A^2/j^2)*t2 - 4*pd/j = 0``. Choosing
    t2 = 2, j = 1, A = 0.5 pins pd = 1.5 (``8 - 1*2 - 4*pd = 0``).
    Hand-derived segments (``h0 = h2_none/(2*j*t2) = 0`` since
    ``h2_none = 0``): t0 = t2/2 - A/j = 0.5, t2 (index 2) = 2.0,
    t6 = t2/2 + A/j = 1.5 -- verified by direct kinematic re-integration
    below.
    """

    def setUp(self) -> None:
        self.p0 = 0.0
        self.a0 = 0.5
        self.af = 0.5
        self.pf = 1.5
        self.v_max = 10.0
        self.v_min = -10.0
        self.a_max = 10.0
        self.a_min = -10.0
        self.j_max = 1.0
        self.step1 = PositionThirdOrderStep1(
            p0=self.p0,
            v0=0.0,
            a0=self.a0,
            pf=self.pf,
            vf=0.0,
            af=self.af,
            v_max=self.v_max,
            v_min=self.v_min,
            a_max=self.a_max,
            a_min=self.a_min,
            j_max=self.j_max,
        )
        self.input_profile = Profile()
        self.input_profile.set_boundary(self.p0, 0.0, self.a0, self.pf, 0.0, self.af)
        self.block = Block()

    def test_pins_segment_times_and_total_duration(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)

        expected_t = [0.5, 0.0, 2.0, 0.0, 0.0, 0.0, 1.5]
        profile = self.block.p_min
        for i, expected in enumerate(expected_t):
            self.assertAlmostEqual(profile.t[i], expected, delta=1e-9, msg=f"t[{i}]")

        expected_total = 4.0
        self.assertAlmostEqual(profile.t_sum[-1], expected_total, delta=1e-9)
        self.assertAlmostEqual(self.block.t_min, expected_total, delta=1e-9)
        self.assertEqual(profile.limits, ReachedLimits.NONE)

    def test_reintegration_reaches_target_state(self) -> None:
        success = self.step1.get_profile(self.input_profile, self.block)
        self.assertTrue(success)
        profile = self.block.p_min

        expected_j = [self.j_max, 0.0, -self.j_max, 0.0, 0.0, 0.0, self.j_max]
        p, v, a = self.p0, 0.0, self.a0
        for i in range(7):
            p, v, a = integrate_jerk(profile.t[i], p, v, a, expected_j[i])
        self.assertAlmostEqual(p, self.pf, delta=1e-8)
        self.assertAlmostEqual(v, 0.0, delta=1e-8)
        self.assertAlmostEqual(a, self.af, delta=1e-9)


class TestPositionThirdOrderStep1NegativeRadicandGuard(unittest.TestCase):
    """Regression for post-audit finding E-3 (action-plan chunk 46).

    ``_time_all_single_step`` (the zero-limits special case, entered from
    ``get_profile`` when ``j_max == 0``) computes
    ``q = sqrt(2 * a0 * pd + v0**2)`` with no guard. With ``a0 == af``
    (required to enter this branch) and a radicand that goes negative --
    e.g. ``a0 = af = -1``, ``v0 = 0``, ``pd = 1`` gives
    ``2*(-1)*1 + 0 = -2`` -- Swift's ``Double.sqrt`` silently yields
    ``nan`` and the candidate is rejected (``t[3] = nan`` fails the
    ``>= 0.0`` guard immediately after). The un-guarded ``math.sqrt`` this
    file used instead raised ``ValueError: math domain error``. Reproduced
    directly at the ``PositionThirdOrderStep1.get_profile`` public entry --
    not via fuzzing the full ``Otg.calculate`` stack, per the audit finding.
    """

    def test_negative_radicand_does_not_raise(self) -> None:
        step1 = PositionThirdOrderStep1(
            p0=0.0,
            v0=0.0,
            a0=-1.0,
            pf=1.0,
            vf=0.0,
            af=-1.0,
            v_max=10.0,
            v_min=-10.0,
            a_max=10.0,
            a_min=-10.0,
            j_max=0.0,
        )
        input_profile = Profile()
        input_profile.set_boundary(0.0, 0.0, -1.0, 1.0, 0.0, -1.0)
        block = Block()

        # Must not raise ValueError ("math domain error"); the branch is
        # rejected (returns False), matching Swift's nan-propagation
        # behavior rather than crashing.
        success = step1.get_profile(input_profile, block)
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
