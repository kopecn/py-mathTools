"""Step solvers for the first-order (velocity interface only, no
acceleration/jerk limits) position interface: Step 1 computes the
time-optimal profile, Step 2 computes a profile for a prescribed duration.

Faithful ports of
``SWIFT_MATH/OTG/position/PositionFirstOrderStep1.swift`` and
``...PositionFirstOrderStep2.swift`` (class/method names and branch
structure preserved mechanically). See ``.claude/specs/otg.md`` §Internal
fidelity requirements 1, 2, 4, 5 and
``.claude/action-plan/37-otg-position-first-second-steps.md``.

``PositionFirstOrderStep1.get_profile`` ports Swift's ``var p = block.pMin``
(a struct value copy) as ``copy.deepcopy(block.p_min)``, matching
``VelocitySecondOrderStep1.get_profile``'s identical pattern (see
``steps/velocity_second_order.py``'s module docstring): ``Profile`` is a
Python class (reference type), so a plain assignment would alias
``block.p_min`` and let ``p.set_boundary(...)``/the failed-check path mutate
``block.p_min`` in place even when this function returns ``False`` (Swift's
local copy is simply discarded on failure, leaving ``block.pMin``
untouched).
"""

from __future__ import annotations

import copy

from math_tools.otg.block import Block
from math_tools.otg.enums import ControlSigns, ReachedLimits
from math_tools.otg.profile import Profile

__all__: list[str] = []


class PositionFirstOrderStep1:
    """Mathematical equations for Step 1 in first-order position interface:
    extremal profiles."""

    def __init__(self, p0: float, pf: float, v_max: float, v_min: float) -> None:
        self._v_max = v_max
        self._v_min = v_min

        # Pre-calculated expressions.
        self.pd = pf - p0

    def get_profile(self, input_profile: Profile, block: Block) -> bool:
        p = copy.deepcopy(block.p_min)
        p.set_boundary(input_profile)

        vf = self._v_max if self.pd > 0 else self._v_min
        p.t[0] = 0.0
        p.t[1] = 0.0
        p.t[2] = 0.0
        p.t[3] = self.pd / vf
        p.t[4] = 0.0
        p.t[5] = 0.0
        p.t[6] = 0.0

        if p.check_for_first_order(vf, ControlSigns.UDDU, ReachedLimits.VEL):
            block.p_min = p
            block.t_min = p.t_sum[-1] + p.brake.duration + p.accel.duration
            return True
        return False


class PositionFirstOrderStep2:
    """Mathematical equations for Step 2 in first-order position interface:
    time synchronization."""

    def __init__(self, tf: float, p0: float, pf: float, v_max: float, v_min: float) -> None:
        self.tf = tf
        self._v_max = v_max
        self._v_min = v_min

        # Pre-calculated expressions.
        self.pd = pf - p0

    def get_profile(self, profile: Profile) -> bool:
        vf = self.pd / self.tf

        profile.t[0] = 0.0
        profile.t[1] = 0.0
        profile.t[2] = 0.0
        profile.t[3] = self.tf
        profile.t[4] = 0.0
        profile.t[5] = 0.0
        profile.t[6] = 0.0

        return profile.check_for_first_order_with_timing(
            self.tf,
            vf,
            ControlSigns.UDDU,
            ReachedLimits.NONE,
            v_max=self._v_max,
            v_min=self._v_min,
        )
