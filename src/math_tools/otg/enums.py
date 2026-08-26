"""Enums for the OTG (online trajectory generation) subsystem.

Faithful port of ``SWIFT_MATH/OTG/enums/*.swift``. See
``.claude/specs/otg.md`` §Public API and §Internal fidelity requirements.

``Result`` is wire-stable (Ruckig parity): its integer values, including the
intentional gap at -103 (``ErrorNoPhaseSynchronization``, commented out in
the Swift source and never a valid member here), MUST NOT change.

``ControlInterface``, ``Synchronization``, and ``DurationDiscretization`` are
public string enums (Swift ``Codable`` raw values, transcribed verbatim for
``to_dict``/``from_dict`` wire parity). ``ControlSigns``, ``Direction``, and
``ReachedLimits`` are internal (Swift ``internal`` visibility) -- they are
defined here but excluded from ``__all__``.
"""

from __future__ import annotations

import enum

__all__ = [
    "ControlInterface",
    "DurationDiscretization",
    "Result",
    "Synchronization",
]


class Result(enum.IntEnum):
    """Result of one ``Otg.update``/``Otg.calculate`` cycle (Ruckig parity)."""

    WORKING = 0
    """The trajectory is calculated normally."""

    FINISHED = 1
    """The trajectory has reached its final position."""

    ERROR = -1
    """Unclassified error."""

    ERROR_INVALID_INPUT = -100
    """Error in the input parameter."""

    ERROR_TRAJECTORY_DURATION = -101
    """The trajectory duration exceeds its numerical limits."""

    ERROR_POSITIONAL_LIMITS = -102
    """The trajectory exceeds the given positional limits (Ruckig Pro only)."""

    # -103 is intentionally unassigned: Swift's ErrorNoPhaseSynchronization is
    # commented out in the source (Ruckig Pro only feature, never shipped in
    # the ported subsystem). The gap is real and MUST NOT be filled in.

    ERROR_ZERO_LIMITS = -104
    """The trajectory is not valid due to a conflict with zero limits."""

    ERROR_EXECUTION_TIME_CALCULATION = -110
    """Error during the extremal time calculation (Step 1)."""

    ERROR_SYNCHRONIZATION_CALCULATION = -111
    """Error during the synchronization calculation (Step 2)."""


class ControlInterface(str, enum.Enum):
    """Kinematic control interface for a DOF."""

    POSITION = "Position"
    """Position-control: full control over the entire kinematic state (default)."""

    VELOCITY = "Velocity"
    """Velocity-control: ignores current/target position and velocity limits."""


class Synchronization(str, enum.Enum):
    """DOF synchronization strategy for the trajectory calculation."""

    TIME = "Time"
    """Always synchronize the DOFs to reach the target at the same time (default)."""

    TIME_IF_NECESSARY = "TimeIfNecessary"
    """Synchronize only when necessary (e.g. non-zero target velocity/acceleration)."""

    PHASE = "Phase"
    """Phase synchronize the DOFs when possible, else fall back to ``TIME``."""

    NONE = "None"
    """Calculate every DOF independently."""


class DurationDiscretization(str, enum.Enum):
    """Discretization policy for the synchronized trajectory duration."""

    CONTINUOUS = "Continuous"
    """Every trajectory synchronization duration is allowed (default)."""

    DISCRETE = "Discrete"
    """The trajectory synchronization duration must be a multiple of the control cycle."""


class ControlSigns(str, enum.Enum):
    """Internal: sign pattern of a per-DOF jerk profile (up-down vs. up-down-up-down)."""

    UDDU = "UDDU"
    UDUD = "UDUD"


class Direction(str, enum.Enum):
    """Internal: net direction of a per-DOF profile."""

    UP = "UP"
    DOWN = "DOWN"


class ReachedLimits(str, enum.Enum):
    """Internal: which kinematic limits a per-DOF profile saturates."""

    ACC0_ACC1_VEL = "ACC0_ACC1_VEL"
    VEL = "VEL"
    ACC0 = "ACC0"
    ACC1 = "ACC1"
    ACC0_ACC1 = "ACC0_ACC1"
    ACC0_VEL = "ACC0_VEL"
    ACC1_VEL = "ACC1_VEL"
    NONE = "NONE"
