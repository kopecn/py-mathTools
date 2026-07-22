"""Step solvers for the third-order (jerk-limited) velocity interface:
Step 1 computes the time-optimal profile, Step 2 computes a profile for a
prescribed duration.

Faithful ports of ``SWIFT_MATH/OTG/velocity/VelocityThirdOrderStep1.swift``
and ``...VelocityThirdOrderStep2.swift`` (class/method names and branch
structure preserved mechanically). See ``.claude/specs/otg.md`` §Internal
fidelity requirements 1, 2, 4, 5 and
``.claude/action-plan/36-otg-velocity-steps.md``.

**Struct-value-copy semantics.** ``Profile`` is a Python class (reference
type); Swift's ``Profile`` is a struct (value type). Every Swift ``var x =
someProfile`` line that is later selectively kept-or-discarded based on a
``check*`` call's success is ported as ``copy.deepcopy(someProfile)`` here,
never a plain assignment -- a plain assignment would alias the two names
and let a failed attempt's partial mutations corrupt the original (or, in
``VelocityThirdOrderStep1._time_acc0``/``_time_none``, corrupt an
*already-recorded successful* candidate from an earlier attempt in the same
call, since both solutions reuse the same local variable). Deep copies
appear at:

- ``VelocityThirdOrderStep1.get_profile``'s zero-limits branch (``var p =
  block.pMin``);
- ``_time_acc0``/``_time_none``'s ``var profile =
  validProfiles[profileCount]`` (the working candidate) and their
  ``validProfiles[profileCount] = profile`` save points (so a
  subsequently-mutated working copy cannot retroactively corrupt an
  already-saved candidate).

``VelocityThirdOrderStep2`` never needs this: its private ``timeAcc0``/
``timeNone``/``checkAll`` mutate a single ``profile`` argument directly and
always return on the first success (Swift ``inout`` maps directly onto
Python's natural pass-by-reference mutable-object semantics there).
"""

from __future__ import annotations

import copy
import math
import sys

from math_tools.otg.block import Block, Interval
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile

__all__: list[str] = []

#: Swift ``Double.ulpOfOne`` (machine epsilon for float64) -- VelocityThirdOrderStep2's
#: own "all zero" special case. Matches ``profile.py``'s identical convention of a
#: module-private epsilon per Swift file (this is NOT ``functional.roots.EPS16``).
_ULP = sys.float_info.epsilon

#: Swift ``Double.leastNormalMagnitude`` (smallest positive normalized
#: float64, ~2.2250738585072014e-308) -- VelocityThirdOrderStep1's
#: near-zero guards. Distinct from ``_ULP``/``Double.ulpOfOne`` above.
_LEAST_NORMAL_MAGNITUDE = sys.float_info.min


class VelocityThirdOrderStep1:
    """Mathematical equations for Step 1 in the third-order velocity
    interface: extremal profiles."""

    def __init__(
        self,
        v0: float,
        a0: float,
        vf: float,
        af: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        self.a0 = a0
        self.af = af
        self._a_max = a_max
        self._a_min = a_min
        self._j_max = j_max

        # Pre-calculated expressions.
        self.vd = vf - v0

        # Max 3 valid profiles.
        self.valid_profiles: list[Profile] = [Profile() for _ in range(3)]
        self._profile_count = 0

    def _add_profile(self) -> None:
        self._profile_count += 1
        if self._profile_count < len(self.valid_profiles):
            self.valid_profiles[self._profile_count].set_boundary(
                self.valid_profiles[self._profile_count - 1]
            )

    def _reset_profiles(self) -> None:
        self._profile_count = 0

    def _has_profiles(self) -> bool:
        return self._profile_count > 0

    def _time_acc0(
        self, a_max: float, a_min: float, j_max: float, return_after_found: bool
    ) -> None:
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        profile.t[0] = (-self.a0 + a_max) / j_max
        profile.t[1] = (
            (self.a0 * self.a0 + self.af * self.af) / (2 * a_max * j_max)
            - a_max / j_max
            + self.vd / a_max
        )
        profile.t[2] = (-self.af + a_max) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_velocity(j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            if return_after_found:
                return

    def _time_none(
        self, a_max: float, a_min: float, j_max: float, return_after_found: bool
    ) -> None:
        profile = copy.deepcopy(self.valid_profiles[self._profile_count])

        h1 = (self.a0 * self.a0 + self.af * self.af) / 2 + j_max * self.vd
        if h1 < 0.0:
            return
        h1 = math.sqrt(h1)

        # Solution 1
        profile.t[0] = -(self.a0 + h1) / j_max
        profile.t[1] = 0.0
        profile.t[2] = -(self.af + h1) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_velocity(j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()
            if return_after_found:
                return

        # Solution 2
        profile.t[0] = (-self.a0 + h1) / j_max
        profile.t[1] = 0.0
        profile.t[2] = (-self.af + h1) / j_max
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_velocity(j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
            self.valid_profiles[self._profile_count] = copy.deepcopy(profile)
            self._add_profile()

    def _time_all_single_step(
        self, profile: Profile, a_max: float, a_min: float, j_max: float
    ) -> bool:
        """Only for the zero-limits case."""
        if abs(self.af - self.a0) > _LEAST_NORMAL_MAGNITUDE:
            return False

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if abs(self.a0) > _LEAST_NORMAL_MAGNITUDE:
            profile.t[3] = self.vd / self.a0
            if profile.check_for_velocity(0.0, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
                return True
        elif abs(self.vd) < _LEAST_NORMAL_MAGNITUDE:
            if profile.check_for_velocity(0.0, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE):
                return True

        return False

    def get_profile(self, input_profile: Profile, block: Block) -> bool:
        # Zero-limits special case.
        if self._j_max == 0.0:
            p = copy.deepcopy(block.p_min)
            p.set_boundary(input_profile)

            if self._time_all_single_step(p, self._a_max, self._a_min, self._j_max):
                block.p_min = p
                block.t_min = p.t_sum[-1] + p.brake.duration + p.accel.duration
                if abs(self.a0) > _LEAST_NORMAL_MAGNITUDE:
                    block.a = Interval(block.t_min, math.inf)
                return True
            return False

        self._reset_profiles()
        self.valid_profiles[self._profile_count].set_boundary(input_profile)

        if abs(self.af) < _LEAST_NORMAL_MAGNITUDE:
            # There is no blocked interval when af==0, so return after first found profile.
            a_max = self._a_max if self.vd >= 0 else self._a_min
            a_min = self._a_min if self.vd >= 0 else self._a_max
            j_max = self._j_max if self.vd >= 0 else -self._j_max

            self._time_none(a_max, a_min, j_max, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success

            self._time_acc0(a_max, a_min, j_max, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success

            self._time_none(a_min, a_max, -j_max, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success

            self._time_acc0(a_min, a_max, -j_max, True)

        else:
            self._time_none(self._a_max, self._a_min, self._j_max, False)
            self._time_none(self._a_min, self._a_max, -self._j_max, False)
            self._time_acc0(self._a_max, self._a_min, self._j_max, False)
            self._time_acc0(self._a_min, self._a_max, -self._j_max, False)

        success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
        return success


class VelocityThirdOrderStep2:
    """Mathematical equations for Step 2 in the third-order velocity
    interface: time synchronization."""

    def __init__(
        self,
        tf: float,
        v0: float,
        a0: float,
        vf: float,
        af: float,
        a_max: float,
        a_min: float,
        j_max: float,
    ) -> None:
        self.tf = tf
        self.a0 = a0
        self.af = af
        self._a_max = a_max
        self._a_min = a_min
        self._j_max = j_max

        # Pre-calculated expressions.
        self.vd = vf - v0
        self.ad = af - a0

    def _time_acc0(self, profile: Profile, a_max: float, a_min: float, j_max: float) -> bool:
        # UD Solution 1/2
        h1 = math.sqrt(
            (-self.ad * self.ad + 2 * j_max * ((self.a0 + self.af) * self.tf - 2 * self.vd))
            / (j_max * j_max)
            + self.tf * self.tf
        )

        profile.t[0] = self.ad / (2 * j_max) + (self.tf - h1) / 2
        profile.t[1] = h1
        profile.t[2] = self.tf - (profile.t[0] + h1)
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_velocity_with_timing(
            self.tf, j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[7]
            return True

        # UU Solution
        h1 = -self.ad + j_max * self.tf

        profile.t[0] = -self.ad * self.ad / (2 * j_max * h1) + (self.vd - self.a0 * self.tf) / h1
        profile.t[1] = -self.ad / j_max + self.tf
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[0] + profile.t[1])

        if profile.check_for_velocity_with_timing(
            self.tf, j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[7]
            return True

        # UU Solution - 2 step
        profile.t[0] = 0.0
        profile.t[1] = -self.ad / j_max + self.tf
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.ad / j_max

        if profile.check_for_velocity_with_timing(
            self.tf, j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[7]
            return True

        return False

    def _time_none(self, profile: Profile, a_max: float, a_min: float, j_max: float) -> bool:
        # Special case: all zero
        if abs(self.a0) < _ULP and abs(self.af) < _ULP and abs(self.vd) < _ULP:
            profile.t[0] = 0.0
            profile.t[1] = self.tf
            profile.t[2] = 0.0
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = 0.0

            if profile.check_for_velocity_with_timing(
                self.tf, j_max, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                profile.pf = profile.p[7]
                return True

        # UD Solution 1/2
        h1 = 2 * (self.af * self.tf - self.vd)

        profile.t[0] = h1 / self.ad
        profile.t[1] = self.tf - profile.t[0]
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        jf = self.ad * self.ad / h1

        if abs(jf) < abs(j_max) + 1e-12 and profile.check_for_velocity_with_timing(
            self.tf, jf, a_max, a_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            profile.pf = profile.p[7]
            return True

        return False

    def _check_all(self, profile: Profile, a_max: float, a_min: float, j_max: float) -> bool:
        return self._time_acc0(profile, a_max, a_min, j_max) or self._time_none(
            profile, a_max, a_min, j_max
        )

    def get_profile(self, profile: Profile) -> bool:
        if self.vd > 0:
            return self._check_all(
                profile, self._a_max, self._a_min, self._j_max
            ) or self._check_all(profile, self._a_min, self._a_max, -self._j_max)

        return self._check_all(profile, self._a_min, self._a_max, -self._j_max) or self._check_all(
            profile, self._a_max, self._a_min, self._j_max
        )
