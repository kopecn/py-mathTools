"""Step solvers for the second-order (velocity + acceleration limits, no
jerk limit) position interface: Step 1 computes the time-optimal profile,
Step 2 computes a profile for a prescribed duration.

Faithful ports of
``SWIFT_MATH/OTG/position/PositionSecondOrderStep1.swift`` and
``...PositionSecondOrderStep2.swift`` (class/method names and branch
structure preserved mechanically). See ``.claude/specs/otg.md`` §Internal
fidelity requirements 1, 2, 4, 5 and
``.claude/action-plan/37-otg-position-first-second-steps.md``.

**Struct-value-copy semantics.** ``Profile`` is a Python class (reference
type); Swift's ``Profile`` is a struct (value type). Two spots need
``copy.deepcopy`` to reproduce Swift's value semantics (matching the pattern
established in ``steps/velocity_second_order.py`` and
``steps/velocity_third_order.py``): ``PositionFirstOrderStep1``-style ``var
p = block.pMin`` reads, both of which appear in
``PositionSecondOrderStep1.get_profile`` (the zero-``vMax``/``vMin``
special case).

``PositionSecondOrderStep1._time_acc0``/``_time_none`` do **not** need a
deep copy, unlike ``VelocityThirdOrderStep1``'s equivalent helpers: the
Swift source mutates ``validProfiles[profileCount]`` directly through the
array subscript on every line (never capturing a local ``var profile =
validProfiles[profileCount]`` first), so each solution attempt writes
straight into the current candidate slot. Python's list indexing has the
same direct-mutation semantics (``self.valid_profiles[self._profile_count]``
is the actual object at that index, not a copy), and ``_add_profile``
advances to a fresh, distinct ``Profile()`` instance before the next
attempt -- so a plain mechanical port (no ``copy.deepcopy``) already
reproduces Swift's behavior exactly. All three ``valid_profiles`` slots are
constructed as genuinely separate ``Profile()`` instances (never
``[Profile()] * 3``), matching ``VelocityThirdOrderStep1``'s identical
comment about the hazard of accidentally sharing one instance across slots.

``PositionSecondOrderStep2`` needs no copy at all: its methods mutate a
single ``profile`` argument passed straight through (Swift ``inout`` on one
object) and always return on first success, matching
``VelocityThirdOrderStep2``'s identical "no copy needed" case.
"""

from __future__ import annotations

import copy
import math
import sys

from math_tools.otg.block import Block, Interval
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile

__all__: list[str] = []

#: Swift ``Double.leastNormalMagnitude`` (smallest positive normalized
#: float64, ~2.2250738585072014e-308) -- ``PositionSecondOrderStep1``'s
#: near-zero guards. Matches ``steps/velocity_third_order.py``'s identical
#: module-private constant, transcribed per Swift file per that module's
#: convention.
_LEAST_NORMAL_MAGNITUDE = sys.float_info.min


class PositionSecondOrderStep1:
    """Mathematical equations for Step 1 in second-order position
    interface: extremal profiles."""

    def __init__(
        self,
        p0: float,
        v0: float,
        pf: float,
        vf: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> None:
        self.v0 = v0
        self.vf = vf
        self._v_max = v_max
        self._v_min = v_min
        self._a_max = a_max
        self._a_min = a_min

        # Pre-calculated expressions.
        self.pd = pf - p0

        # Max 3 valid profiles. Separate instances, not shared references
        # (using `[Profile()] * 3` would create multiple references to the
        # SAME object).
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

    def get_profile(self, input_profile: Profile, block: Block) -> bool:
        # Zero-limits special case.
        if self._v_max == 0.0 and self._v_min == 0.0:
            p = copy.deepcopy(block.p_min)
            p.set_boundary(input_profile)

            if self._time_all_single_step(p, self._v_max, self._v_min, self._a_max, self._a_min):
                block.p_min = p
                block.t_min = p.t_sum[-1] + p.brake.duration + p.accel.duration
                if abs(self.v0) > _LEAST_NORMAL_MAGNITUDE:
                    block.a = Interval(block.t_min, math.inf)
                return True
            return False

        self._reset_profiles()
        self.valid_profiles[self._profile_count].set_boundary(input_profile)

        if abs(self.vf) < _LEAST_NORMAL_MAGNITUDE:
            # There is no blocked interval when vf==0, so return after the
            # first found profile.
            v_max = self._v_max if self.pd >= 0 else self._v_min
            v_min = self._v_min if self.pd >= 0 else self._v_max
            a_max = self._a_max if self.pd >= 0 else self._a_min
            a_min = self._a_min if self.pd >= 0 else self._a_max

            self._time_none(v_max, v_min, a_max, a_min, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success
            self._time_acc0(v_max, v_min, a_max, a_min, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success

            self._time_none(v_min, v_max, a_min, a_max, True)
            if self._has_profiles():
                success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
                return success
            self._time_acc0(v_min, v_max, a_min, a_max, True)

        else:
            self._time_none(self._v_max, self._v_min, self._a_max, self._a_min, False)
            self._time_none(self._v_min, self._v_max, self._a_min, self._a_max, False)
            self._time_acc0(self._v_max, self._v_min, self._a_max, self._a_min, False)
            self._time_acc0(self._v_min, self._v_max, self._a_min, self._a_max, False)

        success, _ = Block.calculate_block(block, self.valid_profiles, self._profile_count)
        return success

    def _time_acc0(
        self,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        return_after_found: bool,
    ) -> None:
        # Unused in the Swift source too (single candidate, nothing to short-circuit).
        del return_after_found
        self.valid_profiles[self._profile_count].t[0] = (-self.v0 + v_max) / a_max
        self.valid_profiles[self._profile_count].t[1] = (
            (a_min * self.v0 * self.v0 - a_max * self.vf * self.vf) / (2 * a_max * a_min * v_max)
            + v_max * (a_max - a_min) / (2 * a_max * a_min)
            + self.pd / v_max
        )
        self.valid_profiles[self._profile_count].t[2] = (self.vf - v_max) / a_min
        self.valid_profiles[self._profile_count].t[3] = 0.0
        self.valid_profiles[self._profile_count].t[4] = 0.0
        self.valid_profiles[self._profile_count].t[5] = 0.0
        self.valid_profiles[self._profile_count].t[6] = 0.0

        if self.valid_profiles[self._profile_count].check_for_second_order(
            a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            self._add_profile()

    def _time_none(
        self,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
        return_after_found: bool,
    ) -> None:
        h1 = (
            a_max * self.vf * self.vf - a_min * self.v0 * self.v0 - 2 * a_max * a_min * self.pd
        ) / (a_max - a_min)
        if h1 >= 0.0:
            h1 = math.sqrt(h1)

            # Solution 1
            self.valid_profiles[self._profile_count].t[0] = -(self.v0 + h1) / a_max
            self.valid_profiles[self._profile_count].t[1] = 0.0
            self.valid_profiles[self._profile_count].t[2] = (self.vf + h1) / a_min
            self.valid_profiles[self._profile_count].t[3] = 0.0
            self.valid_profiles[self._profile_count].t[4] = 0.0
            self.valid_profiles[self._profile_count].t[5] = 0.0
            self.valid_profiles[self._profile_count].t[6] = 0.0

            if self.valid_profiles[self._profile_count].check_for_second_order(
                a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                self._add_profile()
                if return_after_found:
                    return

            # Solution 2
            self.valid_profiles[self._profile_count].t[0] = (-self.v0 + h1) / a_max
            self.valid_profiles[self._profile_count].t[1] = 0.0
            self.valid_profiles[self._profile_count].t[2] = (self.vf - h1) / a_min
            self.valid_profiles[self._profile_count].t[3] = 0.0
            self.valid_profiles[self._profile_count].t[4] = 0.0
            self.valid_profiles[self._profile_count].t[5] = 0.0
            self.valid_profiles[self._profile_count].t[6] = 0.0

            if self.valid_profiles[self._profile_count].check_for_second_order(
                a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                self._add_profile()

    def _time_all_single_step(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> bool:
        del a_max, a_min  # unused in the Swift source too (zero-limits case)
        if abs(self.vf - self.v0) > _LEAST_NORMAL_MAGNITUDE:
            return False

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if abs(self.v0) > _LEAST_NORMAL_MAGNITUDE:
            profile.t[3] = self.pd / self.v0
            if profile.check_for_second_order(
                0.0, 0.0, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True
        elif abs(self.pd) < _LEAST_NORMAL_MAGNITUDE:
            if profile.check_for_second_order(
                0.0, 0.0, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                return True

        return False


class PositionSecondOrderStep2:
    """Mathematical equations for Step 2 in second-order position
    interface: time synchronization."""

    def __init__(
        self,
        tf: float,
        p0: float,
        v0: float,
        pf: float,
        vf: float,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> None:
        self.v0 = v0
        self.tf = tf
        self.vf = vf
        self._v_max = v_max
        self._v_min = v_min
        self._a_max = a_max
        self._a_min = a_min

        # Pre-calculated expressions.
        self.pd = pf - p0
        self.vd = vf - v0

    def time_acc0(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> bool:
        # UD Solution 1/2
        h1_1 = math.sqrt(
            (
                2 * a_max * (self.pd - self.tf * self.vf)
                - 2 * a_min * (self.pd - self.tf * self.v0)
                + self.vd * self.vd
            )
            / (a_max * a_min)
            + self.tf * self.tf
        )

        profile.t[0] = (a_max * self.vd - a_max * a_min * (self.tf - h1_1)) / (
            a_max * (a_max - a_min)
        )
        profile.t[1] = h1_1
        profile.t[2] = self.tf - (profile.t[0] + h1_1)
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_second_order_with_timing(
            self.tf, a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[-1]
            return True

        # UU Solution
        h1_2 = -self.vd + a_max * self.tf

        profile.t[0] = -self.vd * self.vd / (2 * a_max * h1_2) + (
            self.pd - self.v0 * self.tf
        ) / h1_2
        profile.t[1] = -self.vd / a_max + self.tf
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.tf - (profile.t[0] + profile.t[1])

        if profile.check_for_second_order_with_timing(
            self.tf, a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[-1]
            return True

        # UU Solution - 2 step
        profile.t[0] = 0.0
        profile.t[1] = -self.vd / a_max + self.tf
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = self.vd / a_max

        if profile.check_for_second_order_with_timing(
            self.tf, a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.ACC0
        ):
            profile.pf = profile.p[-1]
            return True

        return False

    def time_none(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> bool:
        if (
            abs(self.v0) < _LEAST_NORMAL_MAGNITUDE
            and abs(self.vf) < _LEAST_NORMAL_MAGNITUDE
            and abs(self.pd) < _LEAST_NORMAL_MAGNITUDE
        ):
            profile.t[0] = 0.0
            profile.t[1] = self.tf
            profile.t[2] = 0.0
            profile.t[3] = 0.0
            profile.t[4] = 0.0
            profile.t[5] = 0.0
            profile.t[6] = 0.0

            if profile.check_for_second_order_with_timing(
                self.tf, a_max, a_min, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
            ):
                profile.pf = profile.p[-1]
                return True

        # UD Solution 1/2
        h1 = 2 * (self.vf * self.tf - self.pd)

        profile.t[0] = h1 / self.vd
        profile.t[1] = self.tf - profile.t[0]
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        af = self.vd * self.vd / h1

        if (a_min - 1e-12 < af < a_max + 1e-12) and profile.check_for_second_order_with_timing(
            self.tf, af, -af, v_max, v_min, ControlSigns.UDDU, ReachedLimits.NONE
        ):
            profile.pf = profile.p[-1]
            return True

        return False

    def get_profile(self, profile: Profile) -> bool:
        # Test all cases to get ones that match. However we should guess
        # which one is correct and try them first...
        if self.pd > 0:
            return self.check_all(
                profile, self._v_max, self._v_min, self._a_max, self._a_min
            ) or self.check_all(profile, self._v_min, self._v_max, self._a_min, self._a_max)

        return self.check_all(
            profile, self._v_min, self._v_max, self._a_min, self._a_max
        ) or self.check_all(profile, self._v_max, self._v_min, self._a_max, self._a_min)

    def check_all(
        self,
        profile: Profile,
        v_max: float,
        v_min: float,
        a_max: float,
        a_min: float,
    ) -> bool:
        return self.time_acc0(profile, v_max, v_min, a_max, a_min) or self.time_none(
            profile, v_max, v_min, a_max, a_min
        )
