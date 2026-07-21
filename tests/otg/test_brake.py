"""Unit tests for ``math_tools.otg.brake.BrakeProfile``.

See ``.claude/specs/otg.md`` §Internal fidelity requirement 1 and
``.claude/action-plan/34-otg-block-brake-bound.md``'s TDD steps: a state
exceeding max acceleration produces a non-zero brake duration and
``v_at_t(0) == v0``; a within-limits state produces an empty brake
(``t[0] == 0``).
"""

import unittest

from math_tools.otg.brake import BrakeProfile


class TestBrakeProfileDefaults(unittest.TestCase):
    def test_default_construction(self) -> None:
        brake = BrakeProfile()
        self.assertEqual(brake.duration, 0.0)
        self.assertEqual(brake.t, [0.0, 0.0])
        self.assertEqual(brake.j, [0.0, 0.0])
        self.assertEqual(brake.a, [0.0, 0.0])
        self.assertEqual(brake.v, [0.0, 0.0])
        self.assertEqual(brake.p, [0.0, 0.0])

    def test_equality(self) -> None:
        a = BrakeProfile()
        b = BrakeProfile()
        self.assertEqual(a, b)
        b.t[0] = 1.0
        self.assertNotEqual(a, b)

    def test_equality_rejects_non_brake_profile(self) -> None:
        self.assertNotEqual(BrakeProfile(), object())


class TestVelocityHelpers(unittest.TestCase):
    def test_v_at_t_zero_time_returns_v0(self) -> None:
        brake = BrakeProfile()
        self.assertEqual(brake.v_at_t(3.0, -1.0, 2.0, 0.0), 3.0)

    def test_v_at_t_matches_closed_form(self) -> None:
        brake = BrakeProfile()
        v0, a0, j, t = 1.0, 0.5, -2.0, 1.5
        self.assertAlmostEqual(brake.v_at_t(v0, a0, j, t), v0 + t * (a0 + j * t / 2))

    def test_v_at_a_zero_matches_closed_form(self) -> None:
        brake = BrakeProfile()
        v0, a0, j = 2.0, 3.0, -4.0
        self.assertAlmostEqual(brake.v_at_a_zero(v0, a0, j), v0 + (a0 * a0) / (2 * j))


class TestGetPositionBrakeTrajectory(unittest.TestCase):
    """The chunk's pinned TDD cases for ``get_position_brake_trajectory``."""

    def test_within_limits_state_produces_empty_brake(self) -> None:
        brake = BrakeProfile()
        # v0/a0 comfortably inside [vMin, vMax] / [aMin, aMax]: no braking needed.
        brake.get_position_brake_trajectory(
            v0=0.0, a0=0.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0, j_max=10.0
        )
        self.assertEqual(brake.t[0], 0.0)
        self.assertEqual(brake.duration, 0.0)

    def test_zero_jerk_limit_produces_empty_brake(self) -> None:
        brake = BrakeProfile()
        brake.get_position_brake_trajectory(
            v0=10.0, a0=10.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0, j_max=0.0
        )
        self.assertEqual(brake.t, [0.0, 0.0])
        self.assertEqual(brake.j, [0.0, 0.0])

    def test_acceleration_exceeding_max_produces_nonzero_brake_duration(self) -> None:
        brake = BrakeProfile()
        v0, a0 = 0.0, 5.0  # a0 > aMax=2.0
        brake.get_position_brake_trajectory(
            v0=v0, a0=a0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0, j_max=10.0
        )
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.v_at_t(v0, a0, brake.j[0], 0.0), v0)

    def test_velocity_exceeding_max_with_zero_acceleration_produces_nonzero_brake(self) -> None:
        brake = BrakeProfile()
        v0, a0 = 10.0, 0.0  # v0 > vMax=4.0, within accel bounds.
        brake.get_position_brake_trajectory(
            v0=v0, a0=a0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0, j_max=10.0
        )
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.v_at_t(v0, a0, brake.j[0], 0.0), v0)


class TestFinalize(unittest.TestCase):
    def test_finalize_empty_brake_is_identity(self) -> None:
        brake = BrakeProfile()
        p, v, a = brake.finalize(1.0, 2.0, 3.0)
        self.assertEqual((p, v, a), (1.0, 2.0, 3.0))
        self.assertEqual(brake.duration, 0.0)

    def test_finalize_nonzero_brake_updates_duration_and_state(self) -> None:
        brake = BrakeProfile()
        brake.get_position_brake_trajectory(
            v0=0.0, a0=5.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0, j_max=10.0
        )
        p0, v0, a0 = 0.0, 0.0, 5.0
        p, v, a = brake.finalize(p0, v0, a0)
        self.assertEqual(brake.duration, sum(t for t in brake.t if t > 0.0))
        self.assertEqual(brake.p[0], p0)
        self.assertEqual(brake.v[0], v0)
        self.assertEqual(brake.a[0], a0)
        # After a nonzero brake, acceleration should have moved toward aMax.
        self.assertNotEqual((p, v, a), (p0, v0, a0))

    def test_finalize_second_order_empty_brake_is_identity(self) -> None:
        brake = BrakeProfile()
        p, v, a = brake.finalize_second_order(1.0, 2.0, 3.0)
        self.assertEqual((p, v, a), (1.0, 2.0, 3.0))
        self.assertEqual(brake.duration, 0.0)

    def test_finalize_second_order_nonzero_brake_updates_state(self) -> None:
        brake = BrakeProfile()
        brake.get_second_order_position_brake_trajectory(
            v0=10.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0
        )
        self.assertGreater(brake.t[0], 0.0)
        p0, v0, a0 = 0.0, 10.0, 0.0
        p, v, a = brake.finalize_second_order(p0, v0, a0)
        self.assertEqual(brake.duration, brake.t[0])
        self.assertNotEqual((p, v), (p0, v0))


class TestVelocityInterfaceBrakes(unittest.TestCase):
    def test_get_velocity_brake_trajectory_within_limits_is_empty(self) -> None:
        brake = BrakeProfile()
        brake.get_velocity_brake_trajectory(a0=0.0, a_max=2.0, a_min=-2.0, j_max=10.0)
        self.assertEqual(brake.t, [0.0, 0.0])

    def test_get_velocity_brake_trajectory_exceeding_max_is_nonzero(self) -> None:
        brake = BrakeProfile()
        brake.get_velocity_brake_trajectory(a0=5.0, a_max=2.0, a_min=-2.0, j_max=10.0)
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.j[0], -10.0)

    def test_get_velocity_brake_trajectory_below_min_is_nonzero(self) -> None:
        brake = BrakeProfile()
        brake.get_velocity_brake_trajectory(a0=-5.0, a_max=2.0, a_min=-2.0, j_max=10.0)
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.j[0], 10.0)

    def test_get_velocity_brake_trajectory_zero_jerk_is_empty(self) -> None:
        brake = BrakeProfile()
        brake.get_velocity_brake_trajectory(a0=5.0, a_max=2.0, a_min=-2.0, j_max=0.0)
        self.assertEqual(brake.t, [0.0, 0.0])

    def test_get_second_order_velocity_brake_trajectory_resets(self) -> None:
        brake = BrakeProfile()
        brake.t = [1.0, 2.0]
        brake.j = [3.0, 4.0]
        brake.get_second_order_velocity_brake_trajectory()
        self.assertEqual(brake.t, [0.0, 0.0])
        self.assertEqual(brake.j, [0.0, 0.0])


class TestSecondOrderPositionBrake(unittest.TestCase):
    def test_within_limits_is_empty(self) -> None:
        brake = BrakeProfile()
        brake.get_second_order_position_brake_trajectory(
            v0=0.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0
        )
        self.assertEqual(brake.t[0], 0.0)

    def test_velocity_above_max_brakes_with_a_min(self) -> None:
        brake = BrakeProfile()
        brake.get_second_order_position_brake_trajectory(
            v0=10.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0
        )
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.a[0], -2.0)

    def test_velocity_below_min_brakes_with_a_max(self) -> None:
        brake = BrakeProfile()
        brake.get_second_order_position_brake_trajectory(
            v0=-10.0, v_max=4.0, v_min=-4.0, a_max=2.0, a_min=-2.0
        )
        self.assertGreater(brake.t[0], 0.0)
        self.assertEqual(brake.a[0], 2.0)

    def test_zero_accel_limit_is_empty(self) -> None:
        brake = BrakeProfile()
        brake.get_second_order_position_brake_trajectory(
            v0=10.0, v_max=4.0, v_min=-4.0, a_max=0.0, a_min=-2.0
        )
        self.assertEqual(brake.t[0], 0.0)


if __name__ == "__main__":
    unittest.main()
