"""Unit tests for ``math_tools.otg.trajectory.Trajectory``.

See ``.claude/specs/otg.md`` §Public API (Trajectory) and
``.claude/action-plan/35-otg-trajectory-and-output.md``'s TDD steps: a
single-DOF ``Trajectory`` built from chunk 33's hand-constructed 7-phase
``Profile`` fixture. Endpoint/midpoint expectations are computed
independently via ``integrate_jerk`` in each test, never re-derived from
``Trajectory``'s own sampling loop.
"""

import unittest

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile
from math_tools.otg.trajectory import Trajectory


def _seven_phase_profile() -> Profile:
    """chunk 33's shared fixture: jf=+/-2.0, every segment 1.0s, UDDU
    control signs, starting and ending at rest (rest-to-rest S-curve)."""
    profile = Profile()
    profile.t = [1.0] * 7
    jf = 2.0
    expected_j = [jf, 0.0, -jf, 0.0, -jf, 0.0, jf]
    p = [0.0] * 8
    v = [0.0] * 8
    a = [0.0] * 8
    for i in range(7):
        p[i + 1], v[i + 1], a[i + 1] = integrate_jerk(1.0, p[i], v[i], a[i], expected_j[i])
    profile.pf, profile.vf, profile.af = p[-1], v[-1], a[-1]

    accepted = profile.check(
        jf,
        v_max=4.0,
        v_min=-4.0,
        a_max=2.0,
        a_min=-2.0,
        control_signs=ControlSigns.UDDU,
        limits=ReachedLimits.NONE,
    )
    assert accepted, "fixture profile must be accepted by check()"
    return profile


def _single_dof_trajectory(profile: Profile) -> Trajectory:
    trajectory = Trajectory(dofs=1)
    trajectory.profiles = [[profile]]
    trajectory.duration = profile.t_sum[-1] + profile.brake.duration
    trajectory.cumulative_times = [trajectory.duration]
    return trajectory


class TestAtTimeEndpointsAndMidpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _seven_phase_profile()
        self.trajectory = _single_dof_trajectory(self.profile)

    def test_at_time_zero_returns_initial_state(self) -> None:
        p, v, a = self.trajectory.at_time(0.0)
        self.assertEqual(p, [self.profile.p[0]])
        self.assertEqual(v, [self.profile.v[0]])
        self.assertEqual(a, [self.profile.a[0]])

    def test_at_time_duration_returns_target_state(self) -> None:
        p, v, a = self.trajectory.at_time(self.trajectory.duration)
        self.assertAlmostEqual(p[0], self.profile.pf, delta=1e-9)
        self.assertAlmostEqual(v[0], self.profile.vf, delta=1e-9)
        self.assertAlmostEqual(a[0], self.profile.af, delta=1e-9)

    def test_at_time_midpoint_within_first_segment(self) -> None:
        # t=0.5 falls within segment 0 (t_sum == [1, 2, 3, 4, 5, 6, 7]).
        expected_p, expected_v, expected_a = integrate_jerk(
            0.5, self.profile.p[0], self.profile.v[0], self.profile.a[0], self.profile.j[0]
        )
        p, v, a = self.trajectory.at_time(0.5)
        self.assertAlmostEqual(p[0], expected_p, places=12)
        self.assertAlmostEqual(v[0], expected_v, places=12)
        self.assertAlmostEqual(a[0], expected_a, places=12)

    def test_at_time_midpoint_crosses_segment_boundary(self) -> None:
        # t=3.5 falls within segment 3 (local offset 0.5 past t_sum[2] == 3.0).
        expected_p, expected_v, expected_a = integrate_jerk(
            0.5, self.profile.p[3], self.profile.v[3], self.profile.a[3], self.profile.j[3]
        )
        p, v, a = self.trajectory.at_time(3.5)
        self.assertAlmostEqual(p[0], expected_p, places=12)
        self.assertAlmostEqual(v[0], expected_v, places=12)
        self.assertAlmostEqual(a[0], expected_a, places=12)

    def test_at_time_negative_clamps_to_start(self) -> None:
        self.assertEqual(self.trajectory.at_time(-5.0), self.trajectory.at_time(0.0))

    def test_at_time_beyond_duration_clamps_to_end(self) -> None:
        beyond = self.trajectory.duration + 100.0
        self.assertEqual(
            self.trajectory.at_time(beyond), self.trajectory.at_time(self.trajectory.duration)
        )


class TestPositionExtrema(unittest.TestCase):
    def test_single_section_monotonic_profile(self) -> None:
        # Rest-to-rest forward S-curve: velocity never goes negative, so
        # position is monotonically non-decreasing -- min is the start
        # position, max is the final (target) position.
        profile = _seven_phase_profile()
        trajectory = _single_dof_trajectory(profile)

        extrema = trajectory.position_extrema()

        self.assertEqual(len(extrema), 1)
        self.assertAlmostEqual(extrema[0].min, profile.p[0], places=9)
        self.assertAlmostEqual(extrema[0].max, profile.pf, places=9)

    def test_merges_across_multiple_sections(self) -> None:
        profile_a = _seven_phase_profile()
        profile_b = _seven_phase_profile()
        # Shift the second section's boundary values up, so its max exceeds
        # the first section's (and its min no longer beats the first's).
        for i in range(8):
            profile_b.p[i] += 10.0
        profile_b.pf += 10.0

        trajectory = Trajectory(dofs=1, max_number_of_waypoints=1)
        trajectory.profiles = [[profile_a], [profile_b]]
        trajectory.cumulative_times = [
            profile_a.t_sum[-1],
            profile_a.t_sum[-1] + profile_b.t_sum[-1],
        ]
        trajectory.duration = trajectory.cumulative_times[-1]

        extrema = trajectory.position_extrema()

        self.assertEqual(len(extrema), 1)
        self.assertAlmostEqual(extrema[0].max, profile_b.pf, places=9)
        self.assertAlmostEqual(extrema[0].min, profile_a.p[0], places=9)


class TestGetFirstTimeAtPosition(unittest.TestCase):
    def test_finds_time_within_first_segment(self) -> None:
        profile = _seven_phase_profile()
        trajectory = _single_dof_trajectory(profile)

        # profile.p[1] is reached exactly at t == profile.t[0] == 1.0.
        found_time = trajectory._get_first_time_at_position(0, profile.p[1])

        self.assertIsNotNone(found_time)
        assert found_time is not None
        self.assertAlmostEqual(found_time, 1.0, places=6)

    def test_out_of_range_dof_returns_none(self) -> None:
        trajectory = _single_dof_trajectory(_seven_phase_profile())
        self.assertIsNone(trajectory._get_first_time_at_position(5, 0.0))

    def test_unreached_position_returns_none(self) -> None:
        trajectory = _single_dof_trajectory(_seven_phase_profile())
        self.assertIsNone(trajectory._get_first_time_at_position(0, 1e9))


class TestGetIntermediateDurations(unittest.TestCase):
    def test_returns_cumulative_times(self) -> None:
        trajectory = _single_dof_trajectory(_seven_phase_profile())
        self.assertEqual(trajectory._get_intermediate_durations(), trajectory.cumulative_times)


class TestConstruction(unittest.TestCase):
    def test_single_section_default(self) -> None:
        trajectory = Trajectory(dofs=2)
        self.assertEqual(trajectory.degrees_of_freedom, 2)
        self.assertEqual(len(trajectory.profiles), 1)
        self.assertEqual(len(trajectory.profiles[0]), 2)
        self.assertEqual(trajectory.cumulative_times, [0.0])
        self.assertEqual(trajectory.duration, 0.0)
        self.assertEqual(trajectory.independent_min_durations, [0.0, 0.0])

    def test_max_number_of_waypoints_sizes_sections(self) -> None:
        trajectory = Trajectory(dofs=1, max_number_of_waypoints=3)
        self.assertEqual(len(trajectory.profiles), 4)
        self.assertEqual(trajectory.cumulative_times, [0.0, 0.0, 0.0, 0.0])
