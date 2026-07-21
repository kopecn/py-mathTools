"""Per-cycle output parameter: the calculated trajectory + current kinematic state.

Faithful port of ``SWIFT_MATH/OTG/OutputParameter.swift``. See
``.claude/specs/otg.md`` §Public API (OutputParameter) and
``.claude/action-plan/35-otg-trajectory-and-output.md``.

Collapses Swift's two constructor overloads (``init(DOFs:)`` and
``init(dofs:maxNumberOfWaypoints:)``) into one Python signature,
``OutputParameter(dofs, max_number_of_waypoints=0)``, matching
``trajectory.py``'s identical collapse (``max_number_of_waypoints=0``
already produces the same single-section ``Trajectory`` as the
no-waypoints overload).
"""

from __future__ import annotations

from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.trajectory import Trajectory

__all__ = ["OutputParameter"]


class OutputParameter:
    """Mutable per-cycle output: the calculated ``Trajectory`` plus the
    current position/velocity/acceleration/jerk and timing/section state.

    Construct with :class:`OutputParameter` ``(dofs,
    max_number_of_waypoints=0)``.
    """

    def __init__(self, dofs: int, max_number_of_waypoints: int = 0) -> None:
        if dofs <= 0:
            raise ValueError(f"degrees of freedom must be positive, got {dofs}")

        self.degrees_of_freedom = dofs
        self.trajectory: Trajectory = Trajectory(dofs, max_number_of_waypoints)

        # Current kinematic state.
        self.new_position: list[float] = [0.0] * dofs
        self.new_velocity: list[float] = [0.0] * dofs
        self.new_acceleration: list[float] = [0.0] * dofs
        self.new_jerk: list[float] = [0.0] * dofs

        # Trajectory state.
        self.time: float = 0.0
        self.new_section: int = 0

        # State flags.
        self.did_section_change: bool = False
        self.new_calculation: bool = False
        self.calculation_duration: float = 0.0
        """Computational duration of the last update call, in microseconds
        (Swift parity -- otg.md §Public API)."""

    # MARK: - Public methods

    def pass_to_input(self, input_parameter: InputParameter) -> None:
        """``passToInput`` -- copies this output's current kinematic state
        into ``input_parameter``'s current state, for trajectory
        continuation across cycles. If a section change occurred and
        intermediate positions remain, the first one is removed."""
        if (
            len(self.new_position) != self.degrees_of_freedom
            or len(self.new_velocity) != self.degrees_of_freedom
            or len(self.new_acceleration) != self.degrees_of_freedom
        ):
            raise ValueError("output parameter arrays must match degrees_of_freedom")

        input_parameter.current_position = list(self.new_position)
        input_parameter.current_velocity = list(self.new_velocity)
        input_parameter.current_acceleration = list(self.new_acceleration)

        if self.did_section_change and input_parameter.intermediate_positions:
            input_parameter.intermediate_positions.pop(0)

    # MARK: - String representation

    def __repr__(self) -> str:
        def fmt(values: list[float]) -> str:
            return ", ".join(f"{v:.6f}" for v in values)

        return (
            f"\nout.new_position = [{fmt(self.new_position)}]\n"
            f"out.new_velocity = [{fmt(self.new_velocity)}]\n"
            f"out.new_acceleration = [{fmt(self.new_acceleration)}]\n"
            f"out.new_jerk = [{fmt(self.new_jerk)}]\n"
            f"out.time = [{self.time:.16f}]\n"
            f"out.calculation_duration = [{self.calculation_duration:.16f}]\n"
        )
