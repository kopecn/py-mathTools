"""Structural-misuse exception for the OTG subsystem.

See ``.claude/specs/otg.md`` §Error semantics: per-cycle failures are
``Result`` codes, never exceptions (real-time control-loop contract).
``OtgError`` is the umbrella carve-out -- raised only for structural misuse
(e.g. mismatched DOF counts between the ``Otg`` driver and its parameters, a
non-positive ``control_cycle``) where every future cycle would be invalid.
"""

from __future__ import annotations

from math_tools.errors import MathToolsError

__all__ = ["OtgError"]


class OtgError(MathToolsError):
    """Raised for structural misuse of the OTG driver, never per-cycle failures."""
