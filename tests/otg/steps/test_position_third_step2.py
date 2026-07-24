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

**Chunk 56 coverage note (post-audit finding E-10).** No new cases were
added to this file for E-10 -- the multi-DOF corpus test
(``test_calculator_target.py::TestMultiDofCorpusReachesStep2``) exercises
these branches indirectly through 450 real synchronized multi-DOF cases,
which is a more representative sample than hand-authored boundary
conditions here. Statement coverage measured via ``sys.settrace`` over the
full OTG test suite, before -> after chunk 56's additions (design
constraint 1, "measure, don't assume"): ``check_root_udud`` 82% -> 98%,
``_time_acc0_vel`` 39% -> 99% (effectively complete -- the one "uncovered"
line is the ``def`` line itself, a measurement artifact), ``_time_acc1_vel``
41% -> 99% (same artifact), ``_time_acc0_acc1`` 98% -> 98% (unchanged; one
substantive branch, an alternate ``check_with_timing`` outcome at
``position_third_order_step2.py:1267``, remains unreached -- recorded, not
chased further). ``_time_none_smooth`` (0%, dead in Swift too) is out of
this chunk's scope per its own "Out of scope" section.
"""

import unittest

from math_tools.otg.block import Block
from math_tools.otg.enums import ControlSigns
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


class TestPositionThirdOrderStep2UdudT0246Discriminant(unittest.TestCase):
    """Regression pin for chunk 44 (action-plan
    ``44-otg-step2-udud-discriminant.md``, post-audit finding E-1).

    ``_time_none``'s "UDUD T 0246" branch had ``j_max * self.tf_p3 *
    self.tf`` (``j*tf**4``) at three sites where the Swift source
    (``PositionThirdOrderStep2.swift:1279,1286,1289``) computes ``jMax *
    tfP2 * tf`` (``j*tf**3``). Both the buggy and the Swift-faithful form
    produce a profile that satisfies ``Profile.check_with_timing`` for this
    boundary condition -- they just pick *different* profiles -- so no
    existing oracle (including the 31-case numeric truth table, which is
    1-DOF and never reaches Step2) can distinguish them.

    This boundary condition was found by exhaustive random search
    (``a0 != 0`` so the two earlier guard blocks in ``_time_none`` are
    skipped and "UDUD T 0246" is the first branch tried) for an input where
    the buggy and Swift-faithful forms of the discriminant select different
    control-sign profiles. The expected segment times below were derived by
    evaluating the Swift-faithful (``j*tf**3``) form of the three sites
    in-memory (a patched copy of the module, `tf_p3` -> `tf_p2` at the
    three UDUD-T0246 discriminant sites) against this same boundary
    condition -- i.e. these are the Swift-faithful oracle values, not the
    values the pre-fix Python produced.
    """

    def test_udud_t0246_branch_matches_swift_faithful_j_tf3_discriminant(self) -> None:
        p0, v0, a0 = 0.0, -0.5237, 2.7015
        pf, vf, af = -1.7271, -1.9901, 1.6448
        v_max, v_min, a_max, a_min, j_max = 10.0, -10.0, 10.0, -10.0, 1.0
        tf = 11.2581

        step2 = PositionThirdOrderStep2(
            tf, p0, v0, a0, pf, vf, af, v_max, v_min, a_max, a_min, j_max
        )
        profile = Profile()
        profile.set_boundary(p0, v0, a0, pf, vf, af)
        self.assertTrue(step2.get_profile(profile), f"expected a feasible profile at tf={tf}")

        # Swift-faithful (j*tf**3) UDUD T0246 branch: control signs UDUD,
        # t[1] = t[3] = t[5] = 0.
        self.assertEqual(profile.control_signs, ControlSigns.UDUD)
        expected_t = [
            0.1810029002957043,
            0.0,
            5.82749192002557,
            0.0,
            4.919697099704295,
            0.0,
            0.3299080799744306,
        ]
        for i, (actual, expected) in enumerate(zip(profile.t, expected_t, strict=True)):
            self.assertAlmostEqual(actual, expected, delta=1e-9, msg=f"t[{i}]")

        self.assertAlmostEqual(profile.t_sum[-1], tf, delta=1e-9, msg="t_sum")
        self.assertAlmostEqual(profile.p[-1], pf, delta=1e-8, msg="pf")
        self.assertAlmostEqual(profile.v[-1], vf, delta=1e-8, msg="vf")
        self.assertAlmostEqual(profile.a[-1], af, delta=1e-8, msg="af")


if __name__ == "__main__":
    unittest.main()
