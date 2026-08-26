"""Per-cycle input parameter for the OTG subsystem.

Field-for-field port of ``SWIFT_MATH/OTG/InputParameter.swift`` (state,
limits, and ``validate``) plus the wire codec from
``SWIFT_MATH/OTG/extensions/InputParameter+codable.swift``. See
``.claude/specs/otg.md`` §Public API (InputParameter) and
``.claude/action-plan/32-otg-input-parameter.md``.

Deviation from the Swift source: ``validate`` returns ``bool`` instead of
throwing (``otg.md`` §Error semantics -- per-cycle failures are never
exceptions in this port), so the private helpers below return ``False`` at
the first violation instead of raising ``RuckigError`` with a message.
"""

from __future__ import annotations

import math
from typing import Any

from math_tools.otg.enums import (
    ControlInterface,
    DurationDiscretization,
    Synchronization,
)

__all__ = ["InputParameter"]


class InputParameter:
    """Mutable per-cycle input: kinematic state, limits, and DOF config.

    Construct with :class:`InputParameter` ``(dofs)``; all arrays are sized
    to ``dofs`` and filled with the Swift defaults. Never numpy-backed
    (``otg.md`` §Internal fidelity requirement 5).
    """

    def __init__(self, dofs: int) -> None:
        if dofs <= 0:
            raise ValueError(f"degrees of freedom must be positive, got {dofs}")

        self.degrees_of_freedom = dofs

        # Control configuration
        self.control_interface: ControlInterface = ControlInterface.POSITION
        self.synchronization: Synchronization = Synchronization.TIME
        self.duration_discretization: DurationDiscretization = DurationDiscretization.CONTINUOUS

        # Current kinematic state
        self.current_position: list[float] = [0.0] * dofs
        self.current_velocity: list[float] = [0.0] * dofs
        self.current_acceleration: list[float] = [0.0] * dofs

        # Target kinematic state
        self.target_position: list[float] = [0.0] * dofs
        self.target_velocity: list[float] = [0.0] * dofs
        self.target_acceleration: list[float] = [0.0] * dofs

        # Global limits
        self.max_velocity: list[float] = [0.0] * dofs
        self.max_acceleration: list[float] = [math.inf] * dofs
        self.max_jerk: list[float] = [math.inf] * dofs
        self.min_velocity: list[float] | None = None
        self.min_acceleration: list[float] | None = None
        self.max_position: list[float] | None = None
        self.min_position: list[float] | None = None

        # Per-section constraints
        self.intermediate_positions: list[list[float]] = []
        self.per_section_max_velocity: list[list[float]] | None = None
        self.per_section_max_acceleration: list[list[float]] | None = None
        self.per_section_max_jerk: list[list[float]] | None = None
        self.per_section_min_velocity: list[list[float]] | None = None
        self.per_section_min_acceleration: list[list[float]] | None = None
        self.per_section_max_position: list[list[float]] | None = None
        self.per_section_min_position: list[list[float]] | None = None

        # DOF-specific configuration
        self.enabled: list[bool] = [True] * dofs
        self.per_dof_control_interface: list[ControlInterface] | None = None
        self.per_dof_synchronization: list[Synchronization] | None = None

        # Duration constraints
        self.minimum_duration: float | None = None
        self.per_section_minimum_duration: list[float] | None = None
        self.interrupt_calculation_duration: float | None = None

    # MARK: - Validation

    def validate(
        self,
        check_current_state_within_limits: bool = False,
        check_target_state_within_limits: bool = True,
    ) -> bool:
        """Validate limits and kinematic state; never raises.

        Args:
            check_current_state_within_limits: also validate the current
                kinematic state against velocity/acceleration limits.
            check_target_state_within_limits: also validate the target
                kinematic state against velocity/acceleration limits
                (default ``True``, matching Swift).

        Returns:
            ``True`` iff every check passes.
        """
        if not self._validate_jerk_limits():
            return False
        if not self._validate_acceleration_limits(
            check_current_state_within_limits, check_target_state_within_limits
        ):
            return False
        if not self._validate_velocity_limits(
            check_current_state_within_limits, check_target_state_within_limits
        ):
            return False
        if not self._validate_position_limits():
            return False
        return self._validate_intermediate_positions()

    def _validate_jerk_limits(self) -> bool:
        for j_max in self.max_jerk:
            if math.isnan(j_max) or j_max < 0.0:
                return False
        return True

    def _validate_acceleration_limits(self, check_current: bool, check_target: bool) -> bool:
        for dof in range(self.degrees_of_freedom):
            a_max = self.max_acceleration[dof]
            if math.isnan(a_max) or a_max < 0.0:
                return False

            a_min = self.min_acceleration[dof] if self.min_acceleration is not None else -a_max
            if math.isnan(a_min) or a_min > 0.0:
                return False

            a0 = self.current_acceleration[dof]
            if math.isnan(a0):
                return False

            af = self.target_acceleration[dof]
            if math.isnan(af):
                return False

            if check_current and (a0 > a_max or a0 < a_min):
                return False

            if check_target and (af > a_max or af < a_min):
                return False

        return True

    def _validate_velocity_limits(self, check_current: bool, check_target: bool) -> bool:
        for dof in range(self.degrees_of_freedom):
            v0 = self.current_velocity[dof]
            if math.isnan(v0):
                return False

            vf = self.target_velocity[dof]
            if math.isnan(vf):
                return False

            if self._control_interface_for(dof) != ControlInterface.POSITION:
                continue

            v_max = self.max_velocity[dof]
            if math.isnan(v_max) or v_max < 0.0:
                return False

            v_min = self.min_velocity[dof] if self.min_velocity is not None else -v_max
            if math.isnan(v_min) or v_min > 0.0:
                return False

            if check_current and not self._check_current_velocity(dof, v0, v_max, v_min):
                return False

            if check_target and not self._check_target_velocity(dof, vf, v_max, v_min):
                return False

        return True

    def _check_current_velocity(self, dof: int, v0: float, v_max: float, v_min: float) -> bool:
        if v0 > v_max or v0 < v_min:
            return False

        a0 = self.current_acceleration[dof]
        j_max = self.max_jerk[dof]
        if a0 > 0 and j_max > 0:
            if _velocity_at_acceleration_zero(v0, a0, j_max) > v_max:
                return False
        if a0 < 0 and j_max > 0:
            if _velocity_at_acceleration_zero(v0, a0, -j_max) < v_min:
                return False
        return True

    def _check_target_velocity(self, dof: int, vf: float, v_max: float, v_min: float) -> bool:
        if vf > v_max or vf < v_min:
            return False

        af = self.target_acceleration[dof]
        j_max = self.max_jerk[dof]
        if af < 0 and j_max > 0:
            if _velocity_at_acceleration_zero(vf, af, j_max) > v_max:
                return False
        if af > 0 and j_max > 0:
            if _velocity_at_acceleration_zero(vf, af, -j_max) < v_min:
                return False
        return True

    def _validate_position_limits(self) -> bool:
        for dof in range(self.degrees_of_freedom):
            if self._control_interface_for(dof) != ControlInterface.POSITION:
                continue
            if math.isnan(self.current_position[dof]):
                return False
            if math.isnan(self.target_position[dof]):
                return False
        return True

    def _validate_intermediate_positions(self) -> bool:
        if not self.intermediate_positions or self.control_interface != ControlInterface.POSITION:
            return True

        duration_is_continuous = self.duration_discretization == DurationDiscretization.CONTINUOUS
        if self.minimum_duration is not None or not duration_is_continuous:
            return False

        if self.per_dof_control_interface is not None or self.per_dof_synchronization is not None:
            return False

        for j_max in self.max_jerk:
            if math.isinf(j_max):
                return False

        return True

    def _control_interface_for(self, dof: int) -> ControlInterface:
        if self.per_dof_control_interface is not None:
            return self.per_dof_control_interface[dof]
        return self.control_interface

    # MARK: - Equality

    def __eq__(self, other: object) -> bool:
        """Full field equality."""
        if not isinstance(other, InputParameter):
            return NotImplemented
        return (
            self.degrees_of_freedom == other.degrees_of_freedom
            and self.control_interface == other.control_interface
            and self.synchronization == other.synchronization
            and self.duration_discretization == other.duration_discretization
            and self.current_position == other.current_position
            and self.current_velocity == other.current_velocity
            and self.current_acceleration == other.current_acceleration
            and self.target_position == other.target_position
            and self.target_velocity == other.target_velocity
            and self.target_acceleration == other.target_acceleration
            and self.max_velocity == other.max_velocity
            and self.max_acceleration == other.max_acceleration
            and self.max_jerk == other.max_jerk
            and self.min_velocity == other.min_velocity
            and self.min_acceleration == other.min_acceleration
            and self.max_position == other.max_position
            and self.min_position == other.min_position
            and self.intermediate_positions == other.intermediate_positions
            and self.per_section_max_velocity == other.per_section_max_velocity
            and self.per_section_max_acceleration == other.per_section_max_acceleration
            and self.per_section_max_jerk == other.per_section_max_jerk
            and self.per_section_min_velocity == other.per_section_min_velocity
            and self.per_section_min_acceleration == other.per_section_min_acceleration
            and self.per_section_max_position == other.per_section_max_position
            and self.per_section_min_position == other.per_section_min_position
            and self.enabled == other.enabled
            and self.per_dof_control_interface == other.per_dof_control_interface
            and self.per_dof_synchronization == other.per_dof_synchronization
            and self.minimum_duration == other.minimum_duration
            and self.per_section_minimum_duration == other.per_section_minimum_duration
            and self.interrupt_calculation_duration == other.interrupt_calculation_duration
        )

    # MARK: - Codec

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the camelCase wire format (Swift ``Codable`` parity).

        Optional (``None``) fields are omitted, mirroring the Swift
        ``encodeIfPresent`` calls in ``InputParameter+codable.swift``.
        """
        data: dict[str, Any] = {
            "degreesOfFreedom": self.degrees_of_freedom,
            "controlInterface": self.control_interface.value,
            "synchronization": self.synchronization.value,
            "durationDiscretization": self.duration_discretization.value,
            "currentPosition": list(self.current_position),
            "currentVelocity": list(self.current_velocity),
            "currentAcceleration": list(self.current_acceleration),
            "targetPosition": list(self.target_position),
            "targetVelocity": list(self.target_velocity),
            "targetAcceleration": list(self.target_acceleration),
            "intermediatePositions": [list(p) for p in self.intermediate_positions],
            "enabled": list(self.enabled),
            "maxVelocity": list(self.max_velocity),
            "maxAcceleration": list(self.max_acceleration),
            "maxJerk": list(self.max_jerk),
        }

        if self.min_velocity is not None:
            data["minVelocity"] = list(self.min_velocity)
        if self.min_acceleration is not None:
            data["minAcceleration"] = list(self.min_acceleration)

        if self.per_section_max_velocity is not None:
            data["perSectionMaxVelocity"] = [list(s) for s in self.per_section_max_velocity]
        if self.per_section_max_acceleration is not None:
            data["perSectionMaxAcceleration"] = [list(s) for s in self.per_section_max_acceleration]
        if self.per_section_max_jerk is not None:
            data["perSectionMaxJerk"] = [list(s) for s in self.per_section_max_jerk]
        if self.per_section_min_velocity is not None:
            data["perSectionMinVelocity"] = [list(s) for s in self.per_section_min_velocity]
        if self.per_section_min_acceleration is not None:
            data["perSectionMinAcceleration"] = [list(s) for s in self.per_section_min_acceleration]
        if self.per_section_max_position is not None:
            data["perSectionMaxPosition"] = [list(s) for s in self.per_section_max_position]
        if self.per_section_min_position is not None:
            data["perSectionMinPosition"] = [list(s) for s in self.per_section_min_position]

        if self.max_position is not None:
            data["maxPosition"] = list(self.max_position)
        if self.min_position is not None:
            data["minPosition"] = list(self.min_position)

        if self.per_dof_control_interface is not None:
            data["perDofControlInterface"] = [ci.value for ci in self.per_dof_control_interface]
        if self.per_dof_synchronization is not None:
            data["perDofSynchronization"] = [sync.value for sync in self.per_dof_synchronization]

        if self.minimum_duration is not None:
            data["minimumDuration"] = self.minimum_duration
        if self.per_section_minimum_duration is not None:
            data["perSectionMinimumDuration"] = list(self.per_section_minimum_duration)
        if self.interrupt_calculation_duration is not None:
            data["interruptCalculationDuration"] = self.interrupt_calculation_duration

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputParameter:
        """Deserialize from the camelCase wire format.

        Unknown keys (e.g. the classification corpus' ``"error"`` field on
        failed cases, otg.md §Oracle and test strategy) are ignored.
        """
        inst = cls(int(data["degreesOfFreedom"]))

        inst.control_interface = ControlInterface(data["controlInterface"])
        inst.synchronization = Synchronization(data["synchronization"])
        inst.duration_discretization = DurationDiscretization(data["durationDiscretization"])

        inst.current_position = list(data["currentPosition"])
        inst.current_velocity = list(data["currentVelocity"])
        inst.current_acceleration = list(data["currentAcceleration"])
        inst.target_position = list(data["targetPosition"])
        inst.target_velocity = list(data["targetVelocity"])
        inst.target_acceleration = list(data["targetAcceleration"])

        inst.intermediate_positions = [list(p) for p in data["intermediatePositions"]]
        inst.enabled = list(data["enabled"])

        inst.max_velocity = list(data["maxVelocity"])
        inst.max_acceleration = list(data["maxAcceleration"])
        inst.max_jerk = list(data["maxJerk"])

        if "minVelocity" in data:
            inst.min_velocity = list(data["minVelocity"])
        if "minAcceleration" in data:
            inst.min_acceleration = list(data["minAcceleration"])

        if "perSectionMaxVelocity" in data:
            inst.per_section_max_velocity = [list(s) for s in data["perSectionMaxVelocity"]]
        if "perSectionMaxAcceleration" in data:
            inst.per_section_max_acceleration = [list(s) for s in data["perSectionMaxAcceleration"]]
        if "perSectionMaxJerk" in data:
            inst.per_section_max_jerk = [list(s) for s in data["perSectionMaxJerk"]]
        if "perSectionMinVelocity" in data:
            inst.per_section_min_velocity = [list(s) for s in data["perSectionMinVelocity"]]
        if "perSectionMinAcceleration" in data:
            inst.per_section_min_acceleration = [list(s) for s in data["perSectionMinAcceleration"]]
        if "perSectionMaxPosition" in data:
            inst.per_section_max_position = [list(s) for s in data["perSectionMaxPosition"]]
        if "perSectionMinPosition" in data:
            inst.per_section_min_position = [list(s) for s in data["perSectionMinPosition"]]

        if "maxPosition" in data:
            inst.max_position = list(data["maxPosition"])
        if "minPosition" in data:
            inst.min_position = list(data["minPosition"])

        if "perDofControlInterface" in data:
            inst.per_dof_control_interface = [
                ControlInterface(v) for v in data["perDofControlInterface"]
            ]
        if "perDofSynchronization" in data:
            inst.per_dof_synchronization = [
                Synchronization(v) for v in data["perDofSynchronization"]
            ]

        if "minimumDuration" in data:
            inst.minimum_duration = float(data["minimumDuration"])
        if "perSectionMinimumDuration" in data:
            inst.per_section_minimum_duration = list(data["perSectionMinimumDuration"])
        if "interruptCalculationDuration" in data:
            inst.interrupt_calculation_duration = float(data["interruptCalculationDuration"])

        return inst


def _velocity_at_acceleration_zero(v0: float, a0: float, j: float) -> float:
    """Velocity reached when acceleration decays to zero under jerk ``j``."""
    return v0 + (a0 * a0) / (2 * j)
