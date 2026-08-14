"""Unit tests for ``math_tools.otg.profile.Profile``.

See ``.claude/specs/otg.md`` §Internal fidelity requirement 1 and
``.claude/action-plan/33-otg-profile.md``. Boundary-array expectations are
computed independently via ``integrate_jerk`` in each test (never by
re-deriving them from ``Profile``'s own loop), per the chunk's TDD steps.
"""

import math
import unittest
from dataclasses import dataclass

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.enums import ControlSigns, Direction, ReachedLimits
from math_tools.otg.profile import Profile


@dataclass
class _FakeBound:
    """Minimal stand-in for the not-yet-landed ``Bound`` (chunk 34):
    ``check_position_extremum``/``check_step_for_position_extremum`` only
    need these four mutable float attributes, matching
    ``Profile``'s ``_PositionExtremumSink`` protocol structurally."""

    min: float = math.inf
    max: float = -math.inf
    t_min: float = 0.0
    t_max: float = 0.0


class TestProfileDefaults(unittest.TestCase):
    def test_default_construction_shapes(self) -> None:
        profile = Profile()
        self.assertEqual(profile.t, [0.0] * 7)
        self.assertEqual(profile.t_sum, [0.0] * 7)
        self.assertEqual(profile.j, [0.0] * 7)
        self.assertEqual(profile.a, [0.0] * 8)
        self.assertEqual(profile.v, [0.0] * 8)
        self.assertEqual(profile.p, [0.0] * 8)
        self.assertEqual(profile.brake.duration, 0.0)
        self.assertEqual(profile.accel.duration, 0.0)
        self.assertEqual(profile.pf, 0.0)
        self.assertEqual(profile.vf, 0.0)
        self.assertEqual(profile.af, 0.0)
        self.assertEqual(profile.limits, ReachedLimits.NONE)
        self.assertEqual(profile.direction, Direction.DOWN)
        self.assertEqual(profile.control_signs, ControlSigns.UDDU)

    def test_equality(self) -> None:
        a = Profile()
        b = Profile()
        self.assertEqual(a, b)
        b.t[3] = 1.0
        self.assertNotEqual(a, b)

    def test_equality_rejects_non_profile(self) -> None:
        self.assertNotEqual(Profile(), object())


class TestProfileCheckBoundaryIntegration(unittest.TestCase):
    """The hand-constructed 7-phase constant-jerk (UDDU) S-curve fixture
    shared by the ``check``-family tests below: jf=+/-2.0, every segment
    1.0s, starting and ending at rest."""

    def _expected_pva(self) -> tuple[list[float], list[float], list[float]]:
        jf = 2.0
        t = [1.0] * 7
        j = [jf, 0.0, -jf, 0.0, -jf, 0.0, jf]
        p = [0.0] * 8
        v = [0.0] * 8
        a = [0.0] * 8
        for i in range(7):
            p[i + 1], v[i + 1], a[i + 1] = integrate_jerk(t[i], p[i], v[i], a[i], j[i])
        return p, v, a

    def _valid_profile(self) -> Profile:
        profile = Profile()
        profile.t = [1.0] * 7
        return profile

    def test_boundary_array_integration(self) -> None:
        expected_p, expected_v, expected_a = self._expected_pva()
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = expected_p[-1], expected_v[-1], expected_a[-1]

        accepted = profile.check(
            2.0,
            v_max=4.0,
            v_min=-4.0,
            a_max=2.0,
            a_min=-2.0,
            control_signs=ControlSigns.UDDU,
            limits=ReachedLimits.NONE,
        )

        self.assertTrue(accepted)
        self.assertEqual(profile.p, expected_p)
        self.assertEqual(profile.v, expected_v)
        self.assertEqual(profile.a, expected_a)

    def test_t_sum_is_prefix_sum_of_t(self) -> None:
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = 16.0, 0.0, 0.0
        profile.check(
            2.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0,
            control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
        )
        self.assertEqual(profile.t_sum, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    def test_perturbed_profile_is_rejected(self) -> None:
        expected_p, expected_v, expected_a = self._expected_pva()
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = expected_p[-1], expected_v[-1], expected_a[-1]
        profile.t[3] += 1e-3

        accepted = profile.check(
            2.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0,
            control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
        )

        self.assertFalse(accepted)

    def test_check_with_timing_delegates_without_j_max(self) -> None:
        expected_p, expected_v, expected_a = self._expected_pva()
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = expected_p[-1], expected_v[-1], expected_a[-1]

        self.assertTrue(
            profile.check_with_timing(
                0.0, 2.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0,
                control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
            )
        )

    def test_check_with_timing_rejects_when_jf_exceeds_j_max(self) -> None:
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = 16.0, 0.0, 0.0

        accepted = profile.check_with_timing(
            0.0, 2.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0,
            control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE, j_max=1.5,
        )
        self.assertFalse(accepted)

    def test_check_with_timing_accepts_when_jf_within_j_max(self) -> None:
        expected_p, expected_v, expected_a = self._expected_pva()
        profile = self._valid_profile()
        profile.pf, profile.vf, profile.af = expected_p[-1], expected_v[-1], expected_a[-1]

        accepted = profile.check_with_timing(
            0.0, 2.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0,
            control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE, j_max=3.0,
        )
        self.assertTrue(accepted)


class TestProfileCheckForVelocity(unittest.TestCase):
    def test_accepts_valid_profile(self) -> None:
        jf = 2.0
        t = [1.0] * 7
        j = [jf, 0.0, -jf, 0.0, -jf, 0.0, jf]
        p = [0.0] * 8
        v = [0.0] * 8
        a = [0.0] * 8
        for i in range(7):
            p[i + 1], v[i + 1], a[i + 1] = integrate_jerk(t[i], p[i], v[i], a[i], j[i])

        profile = Profile()
        profile.t = t
        profile.af, profile.vf = a[-1], v[-1]

        accepted = profile.check_for_velocity(
            jf, a_max=2.0, a_min=-2.0, control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE
        )
        self.assertTrue(accepted)
        self.assertEqual(profile.a, a)
        self.assertEqual(profile.v, v)

    def test_with_timing_rejects_when_jf_exceeds_j_max(self) -> None:
        profile = Profile()
        profile.t = [1.0] * 7
        profile.af, profile.vf = 0.0, 0.0

        accepted = profile.check_for_velocity_with_timing(
            0.0, 2.0, a_max=2.0, a_min=-2.0, control_signs=ControlSigns.UDDU,
            limits=ReachedLimits.NONE, j_max=1.0,
        )
        self.assertFalse(accepted)


class TestProfileSecondOrderVelocity(unittest.TestCase):
    def test_accepts_valid_profile(self) -> None:
        t1, a_up, v0 = 2.0, 3.0, 1.0
        p = [0.0] * 8
        v = [v0] * 8
        a = [0.0, a_up, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for i in range(7):
            p[i + 1], v[i + 1], _ = integrate_jerk(t1, p[i], v[i], a[i], 0.0)

        profile = Profile()
        profile.t = [t1] * 7  # check_for_second_order_velocity integrates real per-phase t[i]
        profile.v[0] = v0
        profile.af, profile.vf = 0.0, v[-1]

        accepted = profile.check_for_second_order_velocity(
            a_up, control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE
        )
        self.assertTrue(accepted)
        self.assertEqual(profile.p, p)
        self.assertEqual(profile.v, v)

    def test_with_timing_rejects_out_of_bound_a_up(self) -> None:
        profile = Profile()
        profile.t[1] = 2.0
        profile.v[0] = 1.0
        profile.vf = 100.0  # deliberately unreachable; a-bound should fail first

        accepted = profile.check_for_second_order_velocity_with_timing(
            0.0, 5.0, control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
            a_max=2.0, a_min=-2.0,
        )
        self.assertFalse(accepted)


class TestProfileSecondOrderPosition(unittest.TestCase):
    def test_accepts_valid_profile(self) -> None:
        a_up, a_down = 2.0, -2.0
        t = [1.0] * 7
        a = [a_up, 0.0, a_down, 0.0, a_down, 0.0, a_up, 0.0]
        p = [0.0] * 8
        v = [0.0] * 8
        for i in range(7):
            p[i + 1], v[i + 1], _ = integrate_jerk(t[i], p[i], v[i], a[i], 0.0)

        profile = Profile()
        profile.t = t
        profile.pf, profile.vf = p[-1], v[-1]

        accepted = profile.check_for_second_order(
            a_up, a_down, v_max=2.0, v_min=-2.0,
            control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
        )
        self.assertTrue(accepted)
        self.assertEqual(profile.p, p)
        self.assertEqual(profile.v, v)


class TestProfileFirstOrder(unittest.TestCase):
    def test_accepts_valid_profile(self) -> None:
        v_up = 2.0
        profile = Profile()
        profile.t[3] = 3.0
        profile.pf = 6.0

        accepted = profile.check_for_first_order(
            v_up, control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE
        )
        self.assertTrue(accepted)
        self.assertEqual(profile.p[-1], 6.0)

    def test_with_timing_rejects_out_of_bound_v_up(self) -> None:
        profile = Profile()
        profile.t[3] = 3.0
        profile.pf = 100.0

        accepted = profile.check_for_first_order_with_timing(
            0.0, 5.0, control_signs=ControlSigns.UDDU, limits=ReachedLimits.NONE,
            v_max=2.0, v_min=-2.0,
        )
        self.assertFalse(accepted)


class TestProfileSetBoundary(unittest.TestCase):
    def test_set_boundary_from_profile_copies_state(self) -> None:
        source = Profile()
        source.a[0], source.v[0], source.p[0] = 1.0, 2.0, 3.0
        source.af, source.vf, source.pf = 4.0, 5.0, 6.0

        target = Profile()
        target.set_boundary(source)

        self.assertEqual(target.a[0], 1.0)
        self.assertEqual(target.v[0], 2.0)
        self.assertEqual(target.p[0], 3.0)
        self.assertEqual(target.af, 4.0)
        self.assertEqual(target.vf, 5.0)
        self.assertEqual(target.pf, 6.0)
        self.assertIs(target.brake, source.brake)
        self.assertIs(target.accel, source.accel)

    def test_set_boundary_from_scalars(self) -> None:
        profile = Profile()
        profile.set_boundary(10.0, 20.0, 30.0, 40.0, 50.0, 60.0)

        self.assertEqual(profile.p[0], 10.0)
        self.assertEqual(profile.v[0], 20.0)
        self.assertEqual(profile.a[0], 30.0)
        self.assertEqual(profile.pf, 40.0)
        self.assertEqual(profile.vf, 50.0)
        self.assertEqual(profile.af, 60.0)

    def test_set_boundary_for_velocity(self) -> None:
        profile = Profile()
        profile.set_boundary_for_velocity(1.0, 2.0, 3.0, 4.0, 5.0)

        self.assertEqual(profile.p[0], 1.0)
        self.assertEqual(profile.v[0], 2.0)
        self.assertEqual(profile.a[0], 3.0)
        self.assertEqual(profile.vf, 4.0)
        self.assertEqual(profile.af, 5.0)


class TestProfilePositionExtremumStatics(unittest.TestCase):
    def test_check_position_extremum_updates_max_for_downward_acceleration(self) -> None:
        t_ext, t_sum, t, p, v, a, j = 0.5, 10.0, 1.0, 0.0, 1.0, -1.0, 0.0
        expected_p_ext, _, expected_a_ext = integrate_jerk(t_ext, p, v, a, j)
        self.assertLess(expected_a_ext, 0.0)

        ext = _FakeBound()
        Profile.check_position_extremum(t_ext, t_sum, t, p, v, a, j, ext)

        self.assertEqual(ext.max, expected_p_ext)
        self.assertEqual(ext.t_max, t_sum + t_ext)
        self.assertEqual(ext.min, math.inf)  # untouched

    def test_check_position_extremum_ignores_root_outside_interval(self) -> None:
        ext = _FakeBound()
        # t_ext == t is not strictly inside (0, t): no-op per Swift's `0 < tExt && tExt < t`.
        Profile.check_position_extremum(1.0, 0.0, 1.0, 0.0, 1.0, -1.0, 0.0, ext)
        self.assertEqual(ext, _FakeBound())

    def test_check_step_for_position_extremum_two_real_roots(self) -> None:
        t_sum, t, p, v, a, j = 0.0, 2.0, 5.0, -1.0, 0.0, 2.0

        ext = _FakeBound()
        Profile.check_step_for_position_extremum(t_sum, t, p, v, a, j, ext)

        # The raw sample point p=5.0 sets both min and max first.
        # Root t_ext=1.0 (of the two roots -1.0/1.0) lies in (0, t) and its
        # integrated position (~4.333) undercuts the min set by the sample.
        expected_p_ext, _, expected_a_ext = integrate_jerk(1.0, p, v, a, j)
        self.assertGreater(expected_a_ext, 0.0)

        self.assertEqual(ext.max, 5.0)
        self.assertEqual(ext.t_max, 0.0)
        self.assertEqual(ext.min, expected_p_ext)
        self.assertEqual(ext.t_min, 1.0)

    def test_check_step_for_position_extremum_zero_jerk_only_samples_endpoint(self) -> None:
        ext = _FakeBound()
        Profile.check_step_for_position_extremum(3.0, 1.0, 2.0, 0.5, 0.0, 0.0, ext)
        self.assertEqual(ext.min, 2.0)
        self.assertEqual(ext.max, 2.0)
        self.assertEqual(ext.t_min, 3.0)
        self.assertEqual(ext.t_max, 3.0)


if __name__ == "__main__":
    unittest.main()
