"""Unit tests for the third-order (jerk-limited) position-interface Step 2
solver (``math_tools.otg.steps.position_third_order_step2``).

See ``.claude/specs/otg.md`` §Internal fidelity requirements 2, 4, 5 and
``.claude/action-plan/39-otg-position-third-step2.md``'s TDD steps: reuse
chunk 38 (``PositionThirdOrderStep1``)'s three analytic cases to compute
each one's time-optimal duration, then ask Step2 to hit the SAME boundary
conditions at 1.25x/1.5x/3x that duration (a prescribed, non-optimal
duration -- Step2's whole purpose is multi-DOF time synchronization: "give
me a profile that takes exactly this long"). Every scaled case must (a)
report success, (b) land on the target ``pf``/``vf``/``af`` state, and (c)
sum its segment times to exactly the prescribed ``tf``. A duration below
the time-optimal minimum must be infeasible (no ``t >= 0`` decomposition
exists) and so must fail.
"""

import unittest

from math_tools.otg.block import Block
from math_tools.otg.profile import Profile
from math_tools.otg.steps.position_third_order_step1 import PositionThirdOrderStep1
from math_tools.otg.steps.position_third_order_step2 import PositionThirdOrderStep2


def _optimal_duration(
    p0: float,
    v0: float,
    a0: float,
    pf: float,
    vf: float,
    af: float,
    v_max: float,
    v_min: float,
    a_max: float,
    a_min: float,
    j_max: float,
) -> float:
    """Time-optimal duration for a boundary condition, via chunk 38's Step 1
    solver (the ground truth this chunk's Step 2 cases are scaled from)."""
    step1 = PositionThirdOrderStep1(
        p0=p0,
        v0=v0,
        a0=a0,
        pf=pf,
        vf=vf,
        af=af,
        v_max=v_max,
        v_min=v_min,
        a_max=a_max,
        a_min=a_min,
        j_max=j_max,
    )
    input_profile = Profile()
    input_profile.set_boundary(p0, v0, a0, pf, vf, af)
    block = Block()
    success = step1.get_profile(input_profile, block)
    assert success, "chunk 38 Step1 case must itself be feasible"
    return block.t_min


class _Step2ScaledDurationMixin:
    """Shared assertions for a boundary condition run through Step2 at
    several prescribed-duration scale factors of its Step1-optimal
    duration."""

    p0: float
    v0: float
    a0: float
    pf: float
    vf: float
    af: float
    v_max: float
    v_min: float
    a_max: float
    a_min: float
    j_max: float

    def _t_opt(self) -> float:
        return _optimal_duration(
            self.p0,
            self.v0,
            self.a0,
            self.pf,
            self.vf,
            self.af,
            self.v_max,
            self.v_min,
            self.a_max,
            self.a_min,
            self.j_max,
        )

    def _run(self, tf: float) -> Profile:
        step2 = PositionThirdOrderStep2(
            tf,
            self.p0,
            self.v0,
            self.a0,
            self.pf,
            self.vf,
            self.af,
            self.v_max,
            self.v_min,
            self.a_max,
            self.a_min,
            self.j_max,
        )
        profile = Profile()
        profile.set_boundary(self.p0, self.v0, self.a0, self.pf, self.vf, self.af)
        success = step2.get_profile(profile)
        assert isinstance(self, unittest.TestCase)
        self.assertTrue(success, f"expected a feasible profile at tf={tf}")
        return profile

    def test_scaled_durations_reach_target_at_exact_duration(self) -> None:
        assert isinstance(self, unittest.TestCase)
        t_opt = self._t_opt()
        for scale in (1.25, 1.5, 3.0):
            tf = scale * t_opt
            with self.subTest(scale=scale):
                profile = self._run(tf)
                self.assertAlmostEqual(profile.p[-1], self.pf, delta=1e-8, msg="pf")
                self.assertAlmostEqual(profile.v[-1], self.vf, delta=1e-8, msg="vf")
                self.assertAlmostEqual(profile.a[-1], self.af, delta=1e-8, msg="af")
                self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-9, msg="t_sum")


class TestPositionThirdOrderStep2LongMove(_Step2ScaledDurationMixin, unittest.TestCase):
    """Rest-to-rest long move (chunk 38's ACC0_ACC1_VEL case): t_opt = 8."""

    def setUp(self) -> None:
        self.p0 = 0.0
        self.v0 = 0.0
        self.a0 = 0.0
        self.pf = 10.0
        self.vf = 0.0
        self.af = 0.0
        self.v_max = 2.0
        self.v_min = -2.0
        self.a_max = 1.0
        self.a_min = -1.0
        self.j_max = 1.0

    def test_below_optimal_duration_is_infeasible(self) -> None:
        t_opt = self._t_opt()
        step2 = PositionThirdOrderStep2(
            0.9 * t_opt,
            self.p0,
            self.v0,
            self.a0,
            self.pf,
            self.vf,
            self.af,
            self.v_max,
            self.v_min,
            self.a_max,
            self.a_min,
            self.j_max,
        )
        profile = Profile()
        profile.set_boundary(self.p0, self.v0, self.a0, self.pf, self.vf, self.af)
        self.assertFalse(step2.get_profile(profile))


class TestPositionThirdOrderStep2ShortMove(_Step2ScaledDurationMixin, unittest.TestCase):
    """Rest-to-rest short, jerk-dominated move (chunk 38's NONE case)."""

    def setUp(self) -> None:
        self.p0 = 0.0
        self.v0 = 0.0
        self.a0 = 0.0
        self.pf = 1.0
        self.vf = 0.0
        self.af = 0.0
        self.v_max = 100.0
        self.v_min = -100.0
        self.a_max = 100.0
        self.a_min = -100.0
        self.j_max = 1.0


class TestPositionThirdOrderStep2MovingStart(_Step2ScaledDurationMixin, unittest.TestCase):
    """Moving-start case (chunk 38's a0 = af != 0 NONE case): t_opt = 4."""

    def setUp(self) -> None:
        self.p0 = 0.0
        self.v0 = 0.0
        self.a0 = 0.5
        self.pf = 1.5
        self.vf = 0.0
        self.af = 0.5
        self.v_max = 10.0
        self.v_min = -10.0
        self.a_max = 10.0
        self.a_min = -10.0
        self.j_max = 1.0


if __name__ == "__main__":
    unittest.main()
