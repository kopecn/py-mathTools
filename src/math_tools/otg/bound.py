"""Position-extremum record for a computed motion ``Profile``.

Faithful port of ``SWIFT_MATH/OTG/Bound.swift``. See ``.claude/specs/otg.md``
§Internal fidelity requirements and
``.claude/action-plan/34-otg-block-brake-bound.md`` design constraint 1.

Structurally satisfies ``math_tools.otg.profile``'s module-private
``_PositionExtremumSink`` Protocol (``min``, ``max``, ``t_min``, ``t_max``
floats) by field name -- see that chunk's Resolution notes for why
``profile.py`` does not import this module directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["Bound"]


@dataclass
class Bound:
    """Position extrema (min/max) reached during a motion ``Profile``, and
    the times at which they occur.

    Plain mutable dataclass (otg.md §Internal fidelity, design constraint
    1) -- ``Profile.check_position_extremum``/
    ``check_step_for_position_extremum`` mutate instances of this type in
    place. Defaults mirror Swift's parameterless ``init()``
    (``min = +infinity``, ``max = -infinity``, so any real position
    trivially becomes a new extremum on first comparison).
    """

    min: float = math.inf
    max: float = -math.inf
    t_min: float = 0.0
    t_max: float = 0.0
