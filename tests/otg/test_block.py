"""Unit tests for ``math_tools.otg.block.Block``/``Interval``.

See ``.claude/specs/otg.md`` §Internal fidelity requirement 3 and
``.claude/action-plan/34-otg-block-brake-bound.md``'s TDD steps:
``is_blocked`` boundary behavior at interval edges; ``get_profile`` returns
the interval's profile for an in-interval ``t``.
"""

import unittest

from math_tools.otg.block import Block, Interval
from math_tools.otg.enums import Direction
from math_tools.otg.profile import Profile


def _profile(duration: float, direction: Direction = Direction.UP) -> Profile:
    """A minimal ``Profile`` whose total duration (``t_sum[-1] +
    brake.duration + accel.duration``) is exactly ``duration`` (brake/accel
    left at their zero defaults)."""
    profile = Profile()
    profile.t_sum[-1] = duration
    profile.direction = direction
    return profile


class TestInterval(unittest.TestCase):
    def test_is_blocked_strictly_inside_open_interval(self) -> None:
        interval = Interval(2.0, 5.0)
        self.assertFalse(interval.is_blocked(2.0))
        self.assertTrue(interval.is_blocked(2.0001))
        self.assertTrue(interval.is_blocked(4.9999))
        self.assertFalse(interval.is_blocked(5.0))
        self.assertFalse(interval.is_blocked(1.999))
        self.assertFalse(interval.is_blocked(5.001))

    def test_from_profiles_orders_by_duration_and_keeps_slower_at_right(self) -> None:
        faster = _profile(2.0)
        slower = _profile(5.0)

        interval = Interval.from_profiles(faster, slower)
        self.assertEqual(interval.left, 2.0)
        self.assertEqual(interval.right, 5.0)
        self.assertIs(interval.profile, slower)

        # Argument order must not matter for left/right/profile: the slower
        # (larger-duration) profile always ends up as `profile`, at `right`.
        interval_swapped = Interval.from_profiles(slower, faster)
        self.assertEqual(interval_swapped.left, 2.0)
        self.assertEqual(interval_swapped.right, 5.0)
        self.assertIs(interval_swapped.profile, slower)

    def test_from_profiles_includes_brake_and_accel_duration(self) -> None:
        faster = _profile(2.0)
        slower = _profile(2.0)
        slower.brake.duration = 1.0
        slower.accel.duration = 1.0

        interval = Interval.from_profiles(faster, slower)
        self.assertEqual(interval.left, 2.0)
        self.assertEqual(interval.right, 4.0)
        self.assertIs(interval.profile, slower)


class TestBlockIsBlockedBoundaries(unittest.TestCase):
    def test_before_t_min_is_blocked(self) -> None:
        block = Block(p_min=Profile(), t_min=2.0)
        self.assertTrue(block.is_blocked(1.999))
        self.assertFalse(block.is_blocked(2.0))
        self.assertFalse(block.is_blocked(2.001))

    def test_no_intervals_only_t_min_governs(self) -> None:
        block = Block(t_min=0.0)
        self.assertFalse(block.is_blocked(0.0))
        self.assertFalse(block.is_blocked(100.0))

    def test_interval_a_edges(self) -> None:
        block = Block(t_min=0.0)
        block.a = Interval(2.0, 5.0)
        self.assertFalse(block.is_blocked(2.0))
        self.assertTrue(block.is_blocked(3.0))
        self.assertFalse(block.is_blocked(5.0))

    def test_interval_b_edges(self) -> None:
        block = Block(t_min=0.0)
        block.a = Interval(2.0, 5.0)
        block.b = Interval(6.0, 9.0)
        self.assertFalse(block.is_blocked(6.0))
        self.assertTrue(block.is_blocked(7.0))
        self.assertFalse(block.is_blocked(9.0))


class TestBlockGetProfile(unittest.TestCase):
    def test_returns_p_min_before_any_interval(self) -> None:
        p_min = _profile(1.0)
        other = _profile(5.0)
        block = Block(p_min=p_min, t_min=1.0)
        block.a = Interval(1.0, 5.0, profile=other)

        self.assertIs(block.get_profile(0.5), p_min)

    def test_returns_interval_a_profile_at_and_after_its_right_edge(self) -> None:
        p_min = _profile(1.0)
        other = _profile(5.0)
        block = Block(p_min=p_min, t_min=1.0)
        block.a = Interval(1.0, 5.0, profile=other)

        self.assertIs(block.get_profile(5.0), other)
        self.assertIs(block.get_profile(6.0), other)

    def test_returns_interval_b_profile_at_and_after_its_right_edge(self) -> None:
        p_min = _profile(1.0)
        mid = _profile(5.0)
        slowest = _profile(9.0)
        block = Block(p_min=p_min, t_min=1.0)
        block.a = Interval(1.0, 5.0, profile=mid)
        block.b = Interval(5.0, 9.0, profile=slowest)

        self.assertIs(block.get_profile(9.0), slowest)
        self.assertIs(block.get_profile(4.9), p_min)

    def test_falls_back_to_p_min_when_interval_profile_is_none(self) -> None:
        p_min = _profile(1.0)
        block = Block(p_min=p_min, t_min=1.0)
        block.a = Interval(1.0, 5.0, profile=None)

        self.assertIs(block.get_profile(6.0), p_min)


class TestBlockSetMinProfile(unittest.TestCase):
    def test_set_min_profile_computes_t_min_and_clears_intervals(self) -> None:
        block = Block()
        block.a = Interval(1.0, 2.0)
        block.b = Interval(3.0, 4.0)

        profile = _profile(7.0)
        profile.brake.duration = 1.0
        profile.accel.duration = 2.0

        block.set_min_profile(profile)

        self.assertIs(block.p_min, profile)
        self.assertEqual(block.t_min, 10.0)
        self.assertIsNone(block.a)
        self.assertIsNone(block.b)


class TestBlockRemoveProfile(unittest.TestCase):
    def test_shifts_left_and_decrements_counter(self) -> None:
        profiles = [_profile(1.0), _profile(2.0), _profile(3.0), _profile(4.0)]
        new_counter = Block.remove_profile(profiles, 4, 1)
        self.assertEqual(new_counter, 3)
        self.assertEqual([p.t_sum[-1] for p in profiles[:new_counter]], [1.0, 3.0, 4.0])


class TestCalculateBlock(unittest.TestCase):
    def test_single_profile_sets_min_and_succeeds(self) -> None:
        block = Block()
        profile = _profile(3.0)
        success, counter = Block.calculate_block(block, [profile], 1)

        self.assertTrue(success)
        self.assertEqual(counter, 1)
        self.assertIs(block.p_min, profile)
        self.assertEqual(block.t_min, 3.0)
        self.assertIsNone(block.a)
        self.assertIsNone(block.b)

    def test_two_nearly_equal_profiles_picks_first_with_no_interval(self) -> None:
        block = Block()
        profiles = [_profile(3.0), _profile(3.0)]
        success, counter = Block.calculate_block(block, profiles, 2)

        self.assertTrue(success)
        self.assertEqual(counter, 2)
        self.assertIs(block.p_min, profiles[0])
        self.assertIsNone(block.a)

    def test_two_distinct_profiles_numerically_robust_creates_interval(self) -> None:
        block = Block()
        faster, slower = _profile(2.0), _profile(6.0)
        success, counter = Block.calculate_block(block, [faster, slower], 2)

        self.assertTrue(success)
        self.assertEqual(counter, 2)
        self.assertIs(block.p_min, faster)
        self.assertIsNotNone(block.a)
        assert block.a is not None
        self.assertEqual(block.a.left, 2.0)
        self.assertEqual(block.a.right, 6.0)
        self.assertIs(block.a.profile, slower)

    def test_two_distinct_profiles_not_numerically_robust_falls_through_false(self) -> None:
        block = Block()
        faster, slower = _profile(2.0), _profile(6.0)
        success, counter = Block.calculate_block(
            block, [faster, slower], 2, numerical_robust=False
        )
        # No branch returns True: falls through with block untouched by this
        # call (still default-constructed) and no explicit success.
        self.assertFalse(success)
        self.assertEqual(counter, 2)

    def test_three_profiles_creates_one_blocking_interval_around_the_fastest(self) -> None:
        block = Block()
        profiles = [_profile(5.0), _profile(1.0), _profile(9.0)]
        success, counter = Block.calculate_block(block, profiles, 3)

        self.assertTrue(success)
        self.assertEqual(counter, 3)
        self.assertIs(block.p_min, profiles[1])
        self.assertIsNotNone(block.a)
        self.assertIsNone(block.b)

    def test_five_profiles_same_direction_creates_two_intervals(self) -> None:
        block = Block()
        profiles = [
            _profile(1.0, Direction.UP),
            _profile(2.0, Direction.UP),
            _profile(3.0, Direction.UP),
            _profile(4.0, Direction.UP),
            _profile(5.0, Direction.UP),
        ]
        success, counter = Block.calculate_block(block, profiles, 5)

        self.assertTrue(success)
        self.assertEqual(counter, 5)
        self.assertIs(block.p_min, profiles[0])
        self.assertIsNotNone(block.a)
        self.assertIsNotNone(block.b)

    def test_four_valid_profiles_even_count_without_duplicate_returns_false(self) -> None:
        block = Block()
        profiles = [_profile(1.0), _profile(9.0), _profile(2.0), _profile(9.5)]
        success, counter = Block.calculate_block(block, profiles, 4)
        self.assertFalse(success)

    def test_even_count_not_specially_handled_returns_false(self) -> None:
        block = Block()
        profiles = [_profile(float(i)) for i in range(6)]
        success, counter = Block.calculate_block(block, profiles, 6)
        self.assertFalse(success)
        self.assertEqual(counter, 6)


if __name__ == "__main__":
    unittest.main()
