"""``Otg``: the per-cycle trajectory-generation driver.

Faithful port of ``SWIFT_MATH/OTG/spmOTG.swift`` (Swift class ``OTG``). See
``.claude/specs/otg.md`` §Public API (Otg), §Error semantics, §Compliance 5
and ``.claude/action-plan/41-otg-driver.md``.

**Deviation from the Swift constructor.** Swift's ``OTG.init`` accepts a
defaulted ``deltaTime: Double = -1.0`` sentinel and only rejects a
non-positive value lazily, inside ``validateInput``, and only when
``durationDiscretization != .Continuous``. This port instead requires
``control_cycle`` to be positive at construction time and raises
:class:`~math_tools.otg.errors.OtgError` immediately otherwise (the chunk
brief: "non-positive control_cycle" is structural misuse -- a condition
that makes every future cycle invalid). Consequently the Swift
``deltaTime <= 0.0`` branch inside ``validateInput`` can never fire once
the constructor's own guard holds, and is not ported here (dead code under
this port's stricter constructor contract). Likewise, Swift's fixed-size
arrays make a DOF mismatch between the driver and its per-cycle parameters
a compile-time impossibility in typical use, so ``OTG.swift`` never checks
for one; this port adds an explicit runtime check (raising ``OtgError``)
since Python's lists carry no static size, per the chunk's design
constraint 1 ("DOF mismatch between constructor and parameters").

**Alias-mutation hazard (otg.md's cross-chunk pattern -- see
``calculator_target.py``'s module docstring for the fuller treatment).**
Swift's ``currentInput: InputParameter`` is a struct field, so
``currentInput = input`` is a value copy. This port's ``InputParameter``
(chunk 32) is a reference type, so the equivalent assignment goes through
``copy.deepcopy`` -- a bare ``self._current_input = input_parameter`` would
alias the caller's own object, and the next cycle's ``input_parameter !=
self._current_input`` change-detection compare would then always be
``False`` (an object trivially equals itself) regardless of what the
caller mutates in between, silently breaking recalculation-on-change.

``filterIntermediatePositions`` is ported nowhere: it is dead code in the
Swift source too (defined on ``OTG`` but never called from ``calculate``/
``update``, and not part of otg.md §Public API), so porting it would add
untested surface outside this chunk's scope.

``interrupt_calculation_duration`` needs no driver-side handling here: it
is a Swift ``InputParameter`` field read only by the Codable wire format
(``InputParameter+codable.swift``, ported in chunk 32's ``to_dict``/
``from_dict``) and never read by ``OTG.swift`` or ``CalculatorTarget.swift``
-- there is no "interrupt" behavior to port because the Swift source itself
never implements one against this field.
"""

from __future__ import annotations

import copy
import time

from math_tools.functional.roots import integrate_jerk
from math_tools.otg.calculator_target import TargetCalculator
from math_tools.otg.enums import ControlInterface, Result
from math_tools.otg.errors import OtgError
from math_tools.otg.input_parameter import InputParameter
from math_tools.otg.output_parameter import OutputParameter

__all__ = ["Otg"]


class Otg:
    """Real-time online trajectory generator: one instance per control loop.

    **Threading contract (Swift parity):** not thread-safe. Designed to be
    owned exclusively by a single real-time control-loop thread; do not
    share an instance across threads.

    Construct with :class:`Otg` ``(control_cycle, dofs,
    max_number_of_waypoints=0)``.
    """

    def __init__(self, control_cycle: float, dofs: int, max_number_of_waypoints: int = 0) -> None:
        if control_cycle <= 0.0:
            raise OtgError(f"control_cycle must be positive, got {control_cycle}")
        if dofs <= 0:
            raise OtgError(f"degrees of freedom must be positive, got {dofs}")

        self.degrees_of_freedom = dofs
        self._control_cycle = control_cycle
        self._max_number_of_waypoints = max_number_of_waypoints

        self._calculator = TargetCalculator(dofs)
        self._current_input = InputParameter(dofs)
        self._current_input_initialized = False

    # MARK: - Structural-misuse guards

    def _check_degrees_of_freedom(
        self, input_parameter: InputParameter, output: OutputParameter
    ) -> None:
        """Raise :class:`OtgError` on a DOF mismatch between this driver
        and either per-cycle parameter (otg.md §Error semantics: structural
        misuse, not a per-cycle ``Result`` failure)."""
        if input_parameter.degrees_of_freedom != self.degrees_of_freedom:
            raise OtgError(
                f"InputParameter has {input_parameter.degrees_of_freedom} degrees of "
                f"freedom, Otg was constructed with {self.degrees_of_freedom}"
            )
        if output.degrees_of_freedom != self.degrees_of_freedom:
            raise OtgError(
                f"OutputParameter has {output.degrees_of_freedom} degrees of "
                f"freedom, Otg was constructed with {self.degrees_of_freedom}"
            )

    # MARK: - Validation

    def _validate_input(self, input_parameter: InputParameter) -> bool:
        """``validateInput`` -- the OTG-specific waypoint-count check plus
        ``InputParameter.validate``. Never raises for per-cycle failures
        (otg.md §Error semantics)."""
        if (
            input_parameter.intermediate_positions
            and input_parameter.control_interface == ControlInterface.POSITION
            and len(input_parameter.intermediate_positions) > self._max_number_of_waypoints
        ):
            return False
        return input_parameter.validate()

    # MARK: - Public API

    def calculate(self, input_parameter: InputParameter, output: OutputParameter) -> Result:
        """Full-trajectory calculation, without time stepping."""
        self._check_degrees_of_freedom(input_parameter, output)

        if not self._validate_input(input_parameter):
            return Result.ERROR_INVALID_INPUT

        return self._calculator.calculate(input_parameter, output.trajectory, self._control_cycle)

    def update(self, input_parameter: InputParameter, output: OutputParameter) -> Result:
        """Advance the trajectory by one control cycle (``control_cycle``).

        Validates the input, recalculates the trajectory when the input has
        changed since the last cycle, steps ``output.time`` forward, and
        samples the trajectory into ``output.new_*``. Returns ``WORKING``,
        ``FINISHED``, or an error :class:`~math_tools.otg.enums.Result`
        (never raises for per-cycle failures).
        """
        self._check_degrees_of_freedom(input_parameter, output)

        start = time.perf_counter_ns()
        output.new_calculation = False

        result = Result.WORKING
        if not self._current_input_initialized or input_parameter != self._current_input:
            result = self.calculate(input_parameter, output)
            if result != Result.WORKING and result != Result.ERROR_POSITIONAL_LIMITS:
                return result

            self._current_input = copy.deepcopy(input_parameter)
            self._current_input_initialized = True
            output.time = 0.0
            output.new_calculation = True

        old_section = output.new_section
        output.time += self._control_cycle

        new_section, integrate_args = output.trajectory._state_to_integrate_from(output.time)
        for dof, (t, p0, v0, a0, j) in enumerate(integrate_args):
            p, v, a = integrate_jerk(t, p0, v0, a0, j)
            output.new_position[dof] = p
            output.new_velocity[dof] = v
            output.new_acceleration[dof] = a
            output.new_jerk[dof] = j
        output.new_section = new_section
        output.did_section_change = output.new_section > old_section

        stop = time.perf_counter_ns()
        output.calculation_duration = (stop - start) / 1_000.0

        output.pass_to_input(self._current_input)

        if output.time > output.trajectory.duration:
            return Result.FINISHED
        return result

    def reset(self) -> None:
        """Forget the cached input, forcing a fresh calculation on the next
        ``update`` call regardless of whether the input has changed."""
        self._current_input_initialized = False
