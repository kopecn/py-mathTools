"""Online trajectory generation (OTG): a faithful Ruckig port.

See ``.claude/specs/otg.md``. Pure Python + stdlib in the per-cycle path --
this package (and everything under it) never imports numpy (real-time
control-loop constraint, enforced by ``tests/test_package_layering.py``).

This chunk (41) lands the final public re-export: ``Otg``, the per-cycle
driver, plus ``Profile`` (already public in ``profile.py``'s own
``__all__`` since chunk 33, but not yet wired into this module). The
``__all__`` list below now matches otg.md §Module layout's re-export list
exactly (otg.md §Compliance 5) -- the finished public surface for this
subsystem.
"""

from __future__ import annotations

from math_tools.otg.enums import (
    ControlInterface,
    DurationDiscretization,
    Result,
    Synchronization,
)
from math_tools.otg.errors import OtgError
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.otg import Otg
from math_tools.otg.output_parameter import OutputParameter
from math_tools.otg.profile import Profile
from math_tools.otg.trajectory import Trajectory

__all__ = [
    "ControlInterface",
    "DurationDiscretization",
    "InputParameter",
    "Otg",
    "OtgError",
    "OutputParameter",
    "Profile",
    "Result",
    "Synchronization",
    "Trajectory",
]
