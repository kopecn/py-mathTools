"""Step solvers for the second-order (no jerk limit) velocity interface:
Step 1 computes the time-optimal profile, Step 2 computes a profile for a
prescribed duration.

Faithful ports of
``SWIFT_MATH/OTG/velocity/VelocitySecondOrderStep1.swift`` and
``...VelocitySecondOrderStep2.swift`` (class/method names and branch
structure preserved mechanically). See ``.claude/specs/otg.md`` §Internal
fidelity requirements 1, 2, 4, 5 and
``.claude/action-plan/36-otg-velocity-steps.md``.

``VelocitySecondOrderStep1.get_profile`` ports Swift's ``var p =
block.pMin`` (a struct value copy) as ``copy.deepcopy(block.p_min)``:
``Profile`` is a Python class (reference type), so a plain assignment would
alias ``block.p_min`` and let ``p.set_boundary(...)``/the failed-check path
mutate ``block.p_min`` in place even when this function returns ``False``
(Swift's local copy is simply discarded on failure, leaving ``block.pMin``
untouched). ``deepcopy`` is safe here: ``Profile`` holds only plain floats,
lists, ``BrakeProfile`` (itself plain floats/lists), and immutable ``str``
enum members.
"""

from __future__ import annotations

import copy

from math_tools.otg.block import Block
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile

__all__: list[str] = []


class VelocitySecondOrderStep1:
    """Mathematical equations for Step 1 in the second-order velocity
    interface: extremal profiles."""

    def __init__(self, v0: float, vf: float, a_max: float, a_min: float) -> None:
        self._a_max = a_max
        self._a_min = a_min

        # Pre-calculated expressions.
        self.vd = vf - v0

    def get_profile(self, input_profile: Profile, block: Block) -> bool:
        p = copy.deepcopy(block.p_min)
        p.set_boundary(input_profile)

        af = self._a_max if self.vd > 0 else self._a_min
        p.t[0] = 0.0
        p.t[1] = self.vd / af
        p.t[2] = 0.0
        p.t[3] = 0.0
        p.t[4] = 0.0
        p.t[5] = 0.0
        p.t[6] = 0.0

        if p.check_for_second_order_velocity(af, ControlSigns.UDDU, ReachedLimits.ACC0):
            block.t_min = p.t_sum[-1] + p.brake.duration + p.accel.duration
            block.p_min = p
            return True
        return False


class VelocitySecondOrderStep2:
    """Mathematical equations for Step 2 in the second-order velocity
    interface: time synchronization."""

    def __init__(self, tf: float, v0: float, vf: float, a_max: float, a_min: float) -> None:
        self.tf = tf
        self._a_max = a_max
        self._a_min = a_min

        # Pre-calculated expressions.
        self.vd = vf - v0

    def get_profile(self, profile: Profile) -> bool:
        af = self.vd / self.tf

        profile.t[0] = 0.0
        profile.t[1] = self.tf
        profile.t[2] = 0.0
        profile.t[3] = 0.0
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        if profile.check_for_second_order_velocity_with_timing(
            self.tf,
            af,
            ControlSigns.UDDU,
            ReachedLimits.NONE,
            a_max=self._a_max,
            a_min=self._a_min,
        ):
            profile.pf = profile.p[-1]
            return True

        return False
