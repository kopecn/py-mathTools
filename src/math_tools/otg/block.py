"""Block-interval synchronization support types: the fastest per-DOF motion
profile plus zero, one, or two "blocked" time intervals during which a
slower profile must not be selected.

Faithful port of ``SWIFT_MATH/OTG/Block.swift`` and ``Interval.swift`` (the
branch structure of ``calculate_block`` is preserved exactly -- it drives
``TargetCalculator.synchronize``, chunk 40). See ``.claude/specs/otg.md``
§Internal fidelity requirement 3 and
``.claude/action-plan/34-otg-block-brake-bound.md`` design constraint 3.

Swift's ``inout`` ``validProfileCounter`` parameter on
``Block.calculateBlock``/``Block.removeProfile`` becomes a returned,
possibly-decremented counter here -- Python ints are immutable and cannot
be mutated by reference. ``block`` and ``valid_profiles`` (a class instance
and a list, both mutable Python objects) ARE mutated in place, matching the
Swift ``inout`` semantics for those two parameters.
"""

from __future__ import annotations

import sys

from math_tools.otg.profile import Profile

__all__ = ["Block", "Interval"]

#: Swift ``Double.ulpOfOne`` -- used (not ``functional.roots.EPS16``) for
#: the near-equality tolerances in ``calculate_block``, matching
#: ``profile.py``'s identical convention for its own private epsilons.
_ULP = sys.float_info.epsilon


class Interval:
    """A time interval ``[left, right]`` during which a slower profile
    (``profile``, valid starting at ``right``) blocks synchronization at
    the faster profile's duration.
    """

    def __init__(self, left: float, right: float, profile: Profile | None = None) -> None:
        self.left = left
        self.right = right
        self.profile = profile

    @classmethod
    def from_profiles(cls, profile_left: Profile, profile_right: Profile) -> Interval:
        """``Interval(profileLeft:profileRight:)`` -- orders the pair by
        total duration (``t_sum[-1] + brake.duration + accel.duration``)
        and stores the *slower* profile at ``right``.
        """
        left_duration = (
            profile_left.t_sum[-1] + profile_left.brake.duration + profile_left.accel.duration
        )
        right_duration = (
            profile_right.t_sum[-1] + profile_right.brake.duration + profile_right.accel.duration
        )
        if left_duration < right_duration:
            return cls(left_duration, right_duration, profile_right)
        return cls(right_duration, left_duration, profile_left)

    def is_blocked(self, t: float) -> bool:
        """``isBlocked`` -- strictly inside the open interval ``(left, right)``."""
        return self.left < t < self.right


class Block:
    """The fastest profile (``p_min``) among a set of synchronization
    candidates, plus up to two blocked ``Interval``s during which a slower
    profile must not be selected.
    """

    def __init__(self, p_min: Profile | None = None, t_min: float = 0.0) -> None:
        self.p_min: Profile = p_min if p_min is not None else Profile()
        self.t_min: float = t_min
        self.a: Interval | None = None
        self.b: Interval | None = None

    @staticmethod
    def remove_profile(
        valid_profiles: list[Profile], valid_profile_counter: int, index: int
    ) -> int:
        """``removeProfile`` -- shifts elements past ``index`` left by one
        in place; returns the decremented counter."""
        for i in range(index, valid_profile_counter - 1):
            valid_profiles[i] = valid_profiles[i + 1]
        return valid_profile_counter - 1

    def set_min_profile(self, profile: Profile) -> None:
        """``setMinProfile`` -- adopts ``profile`` as the fastest candidate
        and clears any previously computed blocked intervals."""
        self.p_min = profile
        self.t_min = profile.t_sum[-1] + profile.brake.duration + profile.accel.duration
        self.a = None
        self.b = None

    @staticmethod
    def calculate_block(
        block: Block,
        valid_profiles: list[Profile],
        valid_profile_counter: int,
        numerical_robust: bool = True,
    ) -> tuple[bool, int]:
        """``calculateBlock`` -- computes ``block``'s minimal profile and
        (for 3 or 5 valid candidates) one or two blocked intervals.

        Mutates ``block`` and ``valid_profiles`` in place. Returns
        ``(success, updated_valid_profile_counter)``: the counter can
        shrink (the ``validProfileCounter == 4`` numerical-duplicate-removal
        path), and Python ints can't be passed by reference the way Swift's
        ``inout`` counter is, so the (possibly unchanged) value is always
        returned alongside the success flag.
        """
        if valid_profile_counter == 1:
            block.set_min_profile(valid_profiles[0])
            return True, valid_profile_counter

        elif valid_profile_counter == 2:
            if abs(valid_profiles[0].t_sum[-1] - valid_profiles[1].t_sum[-1]) < 8.0 * _ULP:
                block.set_min_profile(valid_profiles[0])
                return True, valid_profile_counter

            if numerical_robust:
                idx_min = 0 if valid_profiles[0].t_sum[-1] < valid_profiles[1].t_sum[-1] else 1
                idx_else1 = (idx_min + 1) % 2

                block.set_min_profile(valid_profiles[idx_min])
                block.a = Interval.from_profiles(
                    valid_profiles[idx_min], valid_profiles[idx_else1]
                )
                return True, valid_profile_counter

        elif valid_profile_counter == 4:
            if (
                abs(valid_profiles[0].t_sum[-1] - valid_profiles[1].t_sum[-1]) < 32 * _ULP
                and valid_profiles[0].direction != valid_profiles[1].direction
            ):
                valid_profile_counter = Block.remove_profile(
                    valid_profiles, valid_profile_counter, 1
                )
            elif (
                abs(valid_profiles[2].t_sum[-1] - valid_profiles[3].t_sum[-1]) < 256 * _ULP
                and valid_profiles[2].direction != valid_profiles[3].direction
            ):
                valid_profile_counter = Block.remove_profile(
                    valid_profiles, valid_profile_counter, 3
                )
            elif (
                abs(valid_profiles[0].t_sum[-1] - valid_profiles[3].t_sum[-1]) < 256 * _ULP
                and valid_profiles[0].direction != valid_profiles[3].direction
            ):
                valid_profile_counter = Block.remove_profile(
                    valid_profiles, valid_profile_counter, 3
                )
            else:
                return False, valid_profile_counter

        elif valid_profile_counter % 2 == 0:
            return False, valid_profile_counter

        # validProfileCounter is 3 or 5 here (or was 4 above and just got
        # reduced to 3 by remove_profile) -- all other counts returned
        # above -- so this is never an empty sequence.
        candidates = list(enumerate(valid_profiles[:valid_profile_counter]))
        if not candidates:
            return False, valid_profile_counter  # unreachable -- see note above
        idx_min, _ = min(candidates, key=lambda pair: pair[1].t_sum[-1])

        block.set_min_profile(valid_profiles[idx_min])

        if valid_profile_counter == 3:
            idx_else1 = (idx_min + 1) % 3
            idx_else2 = (idx_min + 2) % 3

            block.a = Interval.from_profiles(valid_profiles[idx_else1], valid_profiles[idx_else2])
            return True, valid_profile_counter

        elif valid_profile_counter == 5:
            idx_else1 = (idx_min + 1) % 5
            idx_else2 = (idx_min + 2) % 5
            idx_else3 = (idx_min + 3) % 5
            idx_else4 = (idx_min + 4) % 5

            if valid_profiles[idx_else1].direction == valid_profiles[idx_else2].direction:
                block.a = Interval.from_profiles(
                    valid_profiles[idx_else1], valid_profiles[idx_else2]
                )
                block.b = Interval.from_profiles(
                    valid_profiles[idx_else3], valid_profiles[idx_else4]
                )
            else:
                block.a = Interval.from_profiles(
                    valid_profiles[idx_else1], valid_profiles[idx_else4]
                )
                block.b = Interval.from_profiles(
                    valid_profiles[idx_else2], valid_profiles[idx_else3]
                )
            return True, valid_profile_counter

        return False, valid_profile_counter

    def is_blocked(self, t: float) -> bool:
        """``isBlocked`` -- before the fastest profile's duration, or
        inside either blocked interval."""
        if t < self.t_min:
            return True
        if self.a is not None and self.a.is_blocked(t):
            return True
        if self.b is not None and self.b.is_blocked(t):
            return True
        return False

    def get_profile(self, t: float) -> Profile:
        """``getProfile`` -- the profile that should be selected at time
        ``t``, given the blocked intervals."""
        if self.b is not None and t >= self.b.right:
            return self.b.profile if self.b.profile is not None else self.p_min
        if self.a is not None and t >= self.a.right:
            return self.a.profile if self.a.profile is not None else self.p_min
        return self.p_min
