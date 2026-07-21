"""Online trajectory generation (OTG): a faithful Ruckig port.

See ``.claude/specs/otg.md``. Pure Python + stdlib in the per-cycle path --
this package (and everything under it) never imports numpy (real-time
control-loop constraint, enforced by ``tests/test_package_layering.py``).

Public re-exports grow per chunk (otg.md §Module layout); this chunk adds
``InputParameter`` to the wire-stable enums and the structural-misuse error.
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

__all__ = [
    "ControlInterface",
    "DurationDiscretization",
    "InputParameter",
    "OtgError",
    "Result",
    "Synchronization",
]
