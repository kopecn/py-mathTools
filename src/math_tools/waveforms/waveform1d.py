"""``Waveform1D``: a uniformly-sampled scalar time series.

See ``.claude/specs/waveformCore.md`` (§ABC accessor, §Instantiability,
§Time axis, §Waveform1D). Storage is a private 1-D ``np.ndarray`` (dtype
preserved on construction; float64 default for non-integer input); ``dt``/
``t0`` are the Tier-3 ``PrecisionTimeInterval``/``PrecisionTimestamp`` types
so the time axis is attosecond-exact rather than float-accumulated.

This core chunk ships ``class Waveform1D(Waveform1dABC)`` with **no DSP
mixin bases** (those compose in a much later chunk, see
``waveformDsp.md``). Constructors, statistics, indexing, and mutation below
are a fresh numpy-idiomatic implementation, NOT a faithful port of the
Swift ``Waveform1D``: the Swift generator API is duration/samplingRate
based, this one is sample-count (``n``) based, matching this repo's other
constructors.

Arithmetic/bitwise/comparison operators (``+ - * / // %``, ``& | ^ << >> ~``,
``isclose``, ``elements_equal``, etc.) are chunk 12 -- see §Waveform1D
Operators.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Iterator, Sequence
from typing import Any, overload

import numpy as np
import numpy.typing as npt
from foundation_abc.math.waveformABCs import Waveform1dABC

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp


def _resolve_dt_seconds(dt: PrecisionTimeInterval | None, dt_seconds: float | None) -> float:
    """Resolve the axis spacing (seconds) for generator time-axis construction.

    Mirrors the constructor's mutual-exclusivity rule between ``dt`` and
    ``dt_seconds``, but does not validate strict positivity -- that is left
    to the ``Waveform1D`` constructor the generator ultimately delegates to.
    """
    if dt is not None and dt_seconds is not None:
        raise TypeError("Waveform1D: specify at most one of dt, dt_seconds")
    if dt is not None:
        return dt.seconds_as_float
    return dt_seconds if dt_seconds is not None else 1.0


_SCALAR_TYPES: tuple[type, ...] = (int, float, np.integer, np.floating, np.bool_)


def _is_valid_operand(other: object) -> bool:
    """True if ``other`` is a ``Waveform1D`` or a plain/numpy scalar -- the only operand
    kinds the elementwise operators accept. Anything else must yield ``NotImplemented``
    so Python's operator protocol (reflected methods, ``np.float64 + w``, etc.) behaves
    correctly instead of us raising (waveformCore.md §Waveform1D Operators)."""
    return isinstance(other, Waveform1D) or isinstance(other, _SCALAR_TYPES)


class Waveform1D(Waveform1dABC):
    """A mutable, uniformly-sampled scalar time series backed by a 1-D ndarray."""

    # Opt out of numpy's ufunc protocol: without this, `np.float64(2.0) + w` or
    # `np.array([...]) * w` silently unwraps `w` via `__array__` and returns a bare
    # ndarray (dropping dt/t0) instead of calling `w.__radd__`/`w.__rmul__`. Setting
    # this to None forces numpy to return NotImplemented, so Python's normal operator
    # protocol (and this class's reflected dunders) takes over.
    __array_ufunc__ = None

    # MARK: - Construction

    def __init__(
        self,
        values: npt.ArrayLike,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> None:
        """Construct from array-like ``values`` (copied) and an optional time axis.

        ``dt``/``dt_seconds`` are mutually exclusive (``dt_seconds`` defaults
        to ``1.0`` when neither is given); likewise ``t0``/``t0_seconds``
        (``t0`` defaults to ``PrecisionTimestamp.EPOCH``).

        Raises:
            TypeError: If both ``dt`` and ``dt_seconds``, or both ``t0`` and
                ``t0_seconds``, are given.
            ValueError: If ``values`` is not 1-D, or the resolved ``dt`` is
                not strictly positive.
        """
        if dt is not None and dt_seconds is not None:
            raise TypeError("Waveform1D: specify at most one of dt, dt_seconds")
        if t0 is not None and t0_seconds is not None:
            raise TypeError("Waveform1D: specify at most one of t0, t0_seconds")

        resolved_dt = (
            dt
            if dt is not None
            else PrecisionTimeInterval.from_seconds(dt_seconds if dt_seconds is not None else 1.0)
        )
        if resolved_dt.total_attoseconds <= 0:
            raise ValueError(f"Waveform1D: dt must be strictly positive, got {resolved_dt!r}")

        if t0 is not None:
            resolved_t0 = t0
        elif t0_seconds is not None:
            resolved_t0 = PrecisionTimestamp.from_interval(
                PrecisionTimeInterval.from_seconds(t0_seconds)
            )
        else:
            resolved_t0 = PrecisionTimestamp.EPOCH

        arr = np.asarray(values)
        if arr.ndim != 1:
            raise ValueError(f"Waveform1D: values must be 1-D, got shape {arr.shape}")
        if np.issubdtype(arr.dtype, np.integer):
            self._values: npt.NDArray[Any] = arr.copy()
        else:
            self._values = arr.astype(np.float64, copy=True)
        self._dt = resolved_dt
        self._t0 = resolved_t0

    @classmethod
    def from_dict(cls, obj: Any) -> Waveform1D:
        """Construct from the ABC wire shape ``{"waveform", "t0", "dt"}``."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        dt = PrecisionTimeInterval.from_dict(obj["dt"])
        t0 = PrecisionTimestamp.from_dict(obj["t0"])
        return cls(obj.get("waveform", []), dt=dt, t0=t0)

    # MARK: - Generators (sinusoidal)

    @classmethod
    def sine(
        cls,
        n: int,
        frequency: float = 1.0,
        amplitude: float = 1.0,
        phase: float = 0.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a sine wave: ``amplitude * sin(2*pi*frequency*t + phase)``.

        ``frequency`` defaults to ``1.0`` Hz so that ``Waveform1D.sine(n=1000)``
        is legal on its own (waveformCore.md's pinned example, §Time axis /
        Compliance 4).
        """
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.sin(2.0 * np.pi * frequency * t + phase)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def cosine(
        cls,
        n: int,
        frequency: float,
        amplitude: float = 1.0,
        phase: float = 0.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a cosine wave: ``amplitude * cos(2*pi*frequency*t + phase)``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.cos(2.0 * np.pi * frequency * t + phase)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def square(
        cls,
        n: int,
        frequency: float,
        amplitude: float = 1.0,
        duty_cycle: float = 0.5,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a bipolar square wave with the given ``duty_cycle`` (clamped to [0, 1])."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        period = 1.0 / frequency
        duty = min(1.0, max(0.0, duty_cycle))
        phase_in_period = np.mod(t, period) / period
        values = np.where(phase_in_period < duty, amplitude, -amplitude)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def triangle(
        cls,
        n: int,
        frequency: float,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a triangle wave."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        period = 1.0 / frequency
        phase_in_period = np.mod(t, period) / period
        values = amplitude * np.where(
            phase_in_period < 0.5,
            4.0 * phase_in_period - 1.0,
            3.0 - 4.0 * phase_in_period,
        )
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def sawtooth(
        cls,
        n: int,
        frequency: float,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a sawtooth wave ramping from ``-amplitude`` to ``amplitude``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        period = 1.0 / frequency
        phase_in_period = np.mod(t, period) / period
        values = amplitude * (2.0 * phase_in_period - 1.0)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    # MARK: - Generators (chirp / exponential / polynomial)

    @classmethod
    def chirp(
        cls,
        n: int,
        start_frequency: float,
        end_frequency: float,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a linear chirp sweeping from ``start_frequency`` to ``end_frequency``
        over the waveform's span (``n * dt``)."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        duration = n * dt_s
        sweep_rate = (end_frequency - start_frequency) / duration if duration != 0.0 else 0.0
        phase = 2.0 * np.pi * (start_frequency * t + 0.5 * sweep_rate * t * t)
        values = amplitude * np.sin(phase)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def exponential_decay(
        cls,
        n: int,
        time_constant: float,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``amplitude * exp(-t / time_constant)``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.exp(-t / time_constant)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def exponential_growth(
        cls,
        n: int,
        time_constant: float,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``amplitude * exp(t / time_constant)``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.exp(t / time_constant)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def polynomial(
        cls,
        n: int,
        coefficients: Sequence[float],
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``a0 + a1*t + a2*t**2 + ...`` for ``coefficients = [a0, a1, a2, ...]``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values: npt.NDArray[Any]
        if not coefficients:
            values = np.zeros(n, dtype=np.float64)
        else:
            # np.polyval expects highest-degree coefficient first.
            values = np.polyval(list(reversed(coefficients)), t)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def linear_ramp(
        cls,
        n: int,
        start_value: float,
        end_value: float,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a linear ramp from ``start_value`` to ``end_value`` over ``n`` samples."""
        if n > 1:
            progress = np.arange(n, dtype=np.float64) / (n - 1)
        else:
            progress = np.zeros(n, dtype=np.float64)
        values = start_value + (end_value - start_value) * progress
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    # MARK: - Generators (logarithmic / power)

    @classmethod
    def logarithm(
        cls,
        n: int,
        amplitude: float = 1.0,
        offset: float = 0.01,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``amplitude * ln(t + offset)`` (``offset`` avoids ``log(0)``)."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.log(t + offset)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def logarithm10(
        cls,
        n: int,
        amplitude: float = 1.0,
        offset: float = 0.01,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``amplitude * log10(t + offset)`` (``offset`` avoids ``log10(0)``)."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.log10(t + offset)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def square_root(
        cls,
        n: int,
        amplitude: float = 1.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``amplitude * sqrt(t)``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        values = amplitude * np.sqrt(t)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    # MARK: - Generators (step / activation)

    @classmethod
    def heaviside(
        cls,
        n: int,
        amplitude: float = 1.0,
        step_time: float | None = None,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a Heaviside step: ``amplitude`` for ``t >= step_time`` else ``0``.

        ``step_time`` defaults to the midpoint of the waveform's span.
        """
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        actual_step_time = step_time if step_time is not None else (n * dt_s) / 2.0
        values = np.where(t >= actual_step_time, amplitude, 0.0)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def relu(
        cls,
        n: int,
        slope: float = 1.0,
        threshold: float = 0.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate ``slope * (t - threshold)`` where positive, else ``0``."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        x = t - threshold
        values = np.where(x > 0.0, slope * x, 0.0)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def sigmoid(
        cls,
        n: int,
        amplitude: float = 1.0,
        steepness: float = 1.0,
        center: float | None = None,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a logistic sigmoid; ``center`` defaults to the span's midpoint."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        actual_center = center if center is not None else (n * dt_s) / 2.0
        x = steepness * (t - actual_center)
        values = amplitude / (1.0 + np.exp(-x))
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    # MARK: - Generators (noise / constant / impulse / composite)

    @classmethod
    def white_noise(
        cls,
        n: int,
        amplitude: float = 1.0,
        seed: int | None = None,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate Gaussian white noise; reproducible for a given ``seed``."""
        rng = np.random.default_rng(seed)
        values = amplitude * rng.standard_normal(n)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def constant(
        cls,
        n: int,
        value: float,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a constant (DC) signal of ``n`` samples."""
        values = np.full(n, value)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def impulse(
        cls,
        n: int,
        amplitude: float = 1.0,
        impulse_index: int = 0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a unit impulse: ``amplitude`` at ``impulse_index``, ``0`` elsewhere."""
        values = np.zeros(n, dtype=np.float64)
        if 0 <= impulse_index < n:
            values[impulse_index] = amplitude
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def damped_sinusoid(
        cls,
        n: int,
        frequency: float,
        damping_constant: float,
        amplitude: float = 1.0,
        phase: float = 0.0,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate an exponentially-decaying sinusoid."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        envelope = np.exp(-t / damping_constant)
        values = amplitude * envelope * np.sin(2.0 * np.pi * frequency * t + phase)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def counter(
        cls,
        n: int,
        start_value: float = 0,
        increment: float = 1,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate an integer-friendly counter/ramp: ``start_value + i * increment``."""
        values = start_value + increment * np.arange(n)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    @classmethod
    def digital_square(
        cls,
        n: int,
        frequency: float,
        high_value: float,
        low_value: float,
        duty_cycle: float = 0.5,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> Waveform1D:
        """Generate a two-level (``high_value``/``low_value``) square wave."""
        dt_s = _resolve_dt_seconds(dt, dt_seconds)
        t = np.arange(n, dtype=np.float64) * dt_s
        period = 1.0 / frequency
        duty = min(1.0, max(0.0, duty_cycle))
        phase_in_period = np.mod(t, period) / period
        values = np.where(phase_in_period < duty, high_value, low_value)
        return cls(values, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds)

    # MARK: - Properties (ABC-required)

    @property
    def waveform(self) -> Sequence[float]:
        """The samples as a plain list of floats (the ABC-required accessor)."""
        return [float(v) for v in self._values]

    @property
    def t0(self) -> PrecisionTimestamp:
        return self._t0

    @property
    def dt(self) -> PrecisionTimeInterval:
        return self._dt

    # MARK: - Properties (numpy bulk accessor)

    @property
    def values(self) -> npt.NDArray[Any]:
        """A copy of the sample array (dtype preserved)."""
        return np.array(self._values, copy=True)

    # MARK: - Properties (time axis)

    @property
    def duration(self) -> PrecisionTimeInterval:
        """The span from the first to the last sample (``ZERO`` when ``n <= 1``)."""
        n = len(self._values)
        if n <= 1:
            return PrecisionTimeInterval.ZERO
        return self._dt * (n - 1)

    @property
    def duration_seconds(self) -> float:
        return self.duration.seconds_as_float

    @property
    def sampling_frequency_hz(self) -> float:
        return 1.0 / self._dt.seconds_as_float

    @property
    def nyquist_frequency_hz(self) -> float:
        return self.sampling_frequency_hz / 2.0

    @property
    def sample_count(self) -> int:
        return len(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def time_axis(self) -> npt.NDArray[np.float64]:
        """Sample times (seconds, relative to ``t0``) as a float64 array."""
        n = len(self._values)
        return np.arange(n, dtype=np.float64) * self._dt.seconds_as_float

    # MARK: - Properties (statistics; None on empty)

    @property
    def minimum(self) -> float | None:
        return float(np.min(self._values)) if len(self._values) else None

    @property
    def maximum(self) -> float | None:
        return float(np.max(self._values)) if len(self._values) else None

    @property
    def peak_to_peak(self) -> float | None:
        if len(self._values) == 0:
            return None
        return float(np.max(self._values) - np.min(self._values))

    @property
    def mean(self) -> float | None:
        return float(np.mean(self._values)) if len(self._values) else None

    @property
    def rms(self) -> float | None:
        if len(self._values) == 0:
            return None
        return float(np.sqrt(np.mean(np.square(self._values.astype(np.float64)))))

    @property
    def standard_deviation(self) -> float | None:
        """Population standard deviation (``ddof=0``, matches :attr:`variance`)."""
        return float(np.std(self._values)) if len(self._values) else None

    @property
    def variance(self) -> float | None:
        """Population variance (``ddof=0``) -- a deliberate, pinned choice.

        See waveformCore.md §Compliance 5: pinned with a literal expected
        value in the test suite, not merely asserted against ``np.var``.
        """
        return float(np.var(self._values)) if len(self._values) else None

    @property
    def sum(self) -> float | None:
        return float(np.sum(self._values)) if len(self._values) else None

    @property
    def absolute_sum(self) -> float | None:
        return float(np.sum(np.abs(self._values))) if len(self._values) else None

    # MARK: - Indexing / slicing / sampling

    @overload
    def __getitem__(self, index: int) -> float: ...
    @overload
    def __getitem__(self, index: slice) -> Waveform1D: ...

    def __getitem__(self, index: int | slice) -> float | Waveform1D:
        if isinstance(index, slice):
            if index.step is not None and index.step != 1:
                raise ValueError(
                    "Waveform1D slicing does not support step != 1; resampling is the "
                    "explicit API"
                )
            start, stop, _ = index.indices(len(self._values))
            new_t0 = self._t0 + self._dt * start
            return Waveform1D(self._values[start:stop], dt=self._dt, t0=new_t0)
        return float(self._values[index])

    def _seconds_from_t0(self, t: PrecisionTimestamp | float) -> float:
        if isinstance(t, PrecisionTimestamp):
            return (t - self._t0).seconds_as_float
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            return float(t)
        raise TypeError(f"expected a PrecisionTimestamp or float seconds, got {type(t).__name__}")

    def subset_time(
        self, start_time: PrecisionTimestamp | float, end_time: PrecisionTimestamp | float
    ) -> Waveform1D:
        """Half-open time-range subset: samples with ``start_time <= t < end_time``.

        Args:
            start_time: A ``PrecisionTimestamp`` or float seconds relative to ``t0``.
            end_time: Same units as ``start_time``.

        Raises:
            ValueError: If the resolved range is empty or invalid.
        """
        start_seconds = self._seconds_from_t0(start_time)
        end_seconds = self._seconds_from_t0(end_time)
        if end_seconds <= start_seconds:
            raise ValueError("subset_time requires end_time > start_time")
        axis = self.time_axis()
        start_index = int(np.searchsorted(axis, start_seconds, side="left"))
        end_index = int(np.searchsorted(axis, end_seconds, side="left"))
        if start_index >= end_index or start_index >= len(self._values):
            raise ValueError("subset_time selects an empty range")
        return self[start_index:end_index]

    def value_at_index(self, index: float) -> float:
        """Linear interpolation between ``floor(index)`` and ``ceil(index)``.

        Raises:
            ValueError: If ``index`` is outside ``[0, sample_count - 1]``, or
                the waveform is empty.
        """
        n = len(self._values)
        if n == 0:
            raise ValueError("value_at_index on an empty Waveform1D")
        if index < 0 or index > n - 1:
            raise ValueError(f"index {index} outside valid range [0, {n - 1}]")
        lower = int(np.floor(index))
        if lower == index:
            return float(self._values[lower])
        fraction = index - lower
        return float(self._values[lower] * (1.0 - fraction) + self._values[lower + 1] * fraction)

    def value_at_time(self, t: PrecisionTimestamp | float) -> float:
        """Linear interpolation at time ``t`` (``PrecisionTimestamp`` or seconds from ``t0``).

        Raises:
            ValueError: If ``t`` falls outside the waveform's time span.
        """
        seconds = self._seconds_from_t0(t)
        index = seconds / self._dt.seconds_as_float
        try:
            return self.value_at_index(index)
        except ValueError as exc:
            raise ValueError(f"time {seconds}s outside the waveform's span") from exc

    # MARK: - Mutation

    def append(self, value: float) -> None:
        addition = np.asarray([value], dtype=self._values.dtype)
        self._values = np.concatenate([self._values, addition])

    def append_values(self, values: Sequence[float]) -> None:
        addition = np.asarray(values, dtype=self._values.dtype)
        self._values = np.concatenate([self._values, addition])

    def prepend(self, value: float) -> None:
        addition = np.asarray([value], dtype=self._values.dtype)
        self._values = np.concatenate([addition, self._values])
        self._t0 = self._t0 - self._dt

    def prepend_values(self, values: Sequence[float]) -> None:
        addition = np.asarray(values, dtype=self._values.dtype)
        self._values = np.concatenate([addition, self._values])
        self._t0 = self._t0 - self._dt * len(addition)

    def insert(self, index: int, value: float) -> None:
        self._values = np.insert(self._values, index, value)

    def replace(self, index: int, value: float) -> None:
        self._values[index] = value

    def replace_range(self, index: slice, values: Sequence[float]) -> None:
        self._values[index] = np.asarray(values, dtype=self._values.dtype)

    def pop(self, index: int = -1) -> float:
        """Remove and return the sample at ``index`` (default: last).

        Raises:
            IndexError: If the waveform is empty, or ``index`` is out of range.
        """
        if len(self._values) == 0:
            raise IndexError("pop from an empty Waveform1D")
        value = float(self._values[index])
        self._values = np.delete(self._values, index)
        return value

    def clear(self) -> None:
        self._values = np.array([], dtype=self._values.dtype)

    # MARK: - Arithmetic / bitwise operators

    def _check_compatible(self, other: Waveform1D, op_name: str) -> None:
        """Raise ``WaveformCompatibilityError`` unless ``other`` shares this waveform's
        ``dt`` and length (waveformCore.md §Compliance 2)."""
        if self._dt != other._dt:
            raise WaveformCompatibilityError(
                f"Waveform1D.{op_name}: dt mismatch ({self._dt!r} vs {other._dt!r})"
            )
        if len(self._values) != len(other._values):
            raise WaveformCompatibilityError(
                f"Waveform1D.{op_name}: length mismatch "
                f"({len(self._values)} vs {len(other._values)})"
            )

    def _elementwise(
        self, other: object, op: Callable[[Any, Any], Any], op_name: str
    ) -> Waveform1D:
        """``op(self, other)``; ``dt``/``t0`` carried from ``self`` (the left operand)."""
        if isinstance(other, Waveform1D):
            self._check_compatible(other, op_name)
            result = op(self._values, other._values)
        else:
            result = op(self._values, other)
        return Waveform1D(result, dt=self._dt, t0=self._t0)

    def _elementwise_reflected(
        self, other: object, op: Callable[[Any, Any], Any], op_name: str
    ) -> Waveform1D:
        """``op(other, self)`` for reflected operators; ``dt``/``t0`` still carried from
        ``self`` -- the only ``Waveform1D`` operand present when this is invoked."""
        if isinstance(other, Waveform1D):
            self._check_compatible(other, op_name)
            result = op(other._values, self._values)
        else:
            result = op(other, self._values)
        return Waveform1D(result, dt=self._dt, t0=self._t0)

    def __add__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.add, "__add__")

    def __radd__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.add, "__radd__")

    def __iadd__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.add, "__iadd__")._values
        return self

    def __sub__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.sub, "__sub__")

    def __rsub__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.sub, "__rsub__")

    def __isub__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.sub, "__isub__")._values
        return self

    def __mul__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.mul, "__mul__")

    def __rmul__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.mul, "__rmul__")

    def __imul__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.mul, "__imul__")._values
        return self

    def __truediv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.truediv, "__truediv__")

    def __rtruediv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.truediv, "__rtruediv__")

    def __itruediv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.truediv, "__itruediv__")._values
        return self

    def __floordiv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.floordiv, "__floordiv__")

    def __rfloordiv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.floordiv, "__rfloordiv__")

    def __ifloordiv__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.floordiv, "__ifloordiv__")._values
        return self

    def __mod__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.mod, "__mod__")

    def __rmod__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.mod, "__rmod__")

    def __imod__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.mod, "__imod__")._values
        return self

    # MARK: - Bitwise operators (integer dtype only; numpy raises TypeError otherwise)

    def __and__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.and_, "__and__")

    def __rand__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.and_, "__rand__")

    def __iand__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.and_, "__iand__")._values
        return self

    def __or__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.or_, "__or__")

    def __ror__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.or_, "__ror__")

    def __ior__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.or_, "__ior__")._values
        return self

    def __xor__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.xor, "__xor__")

    def __rxor__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.xor, "__rxor__")

    def __ixor__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.xor, "__ixor__")._values
        return self

    def __lshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.lshift, "__lshift__")

    def __rlshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.lshift, "__rlshift__")

    def __ilshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.lshift, "__ilshift__")._values
        return self

    def __rshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise(other, operator.rshift, "__rshift__")

    def __rrshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        return self._elementwise_reflected(other, operator.rshift, "__rrshift__")

    def __irshift__(self, other: object) -> Waveform1D:
        if not _is_valid_operand(other):
            return NotImplemented
        self._values = self._elementwise(other, operator.rshift, "__irshift__")._values
        return self

    def __invert__(self) -> Waveform1D:
        return Waveform1D(~self._values, dt=self._dt, t0=self._t0)

    # MARK: - Unary operators

    def __neg__(self) -> Waveform1D:
        return Waveform1D(-self._values, dt=self._dt, t0=self._t0)

    def __pos__(self) -> Waveform1D:
        return Waveform1D(+self._values, dt=self._dt, t0=self._t0)

    def __abs__(self) -> Waveform1D:
        return Waveform1D(np.abs(self._values), dt=self._dt, t0=self._t0)

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Full equality: samples (exact), ``dt``, ``t0``."""
        if not isinstance(other, Waveform1D):
            return NotImplemented
        return (
            self._dt == other._dt
            and self._t0 == other._t0
            and bool(np.array_equal(self._values, other._values))
        )

    __hash__ = None  # type: ignore[assignment]

    def _comparable_values(
        self, other: Waveform1D | npt.ArrayLike, op_name: str
    ) -> npt.NDArray[Any]:
        """Resolve ``other`` to a bare ndarray for elementwise comparison producers,
        enforcing the same dt/length compatibility as the arithmetic operators when
        ``other`` is a ``Waveform1D``."""
        if isinstance(other, Waveform1D):
            self._check_compatible(other, op_name)
            return other._values
        return np.asarray(other)

    def elements_equal(self, other: Waveform1D | npt.ArrayLike) -> npt.NDArray[np.bool_]:
        """Elementwise equality (see :meth:`isclose_elementwise` for tolerance)."""
        result: npt.NDArray[np.bool_] = np.equal(
            self._values, self._comparable_values(other, "elements_equal")
        )
        return result

    def elements_less_than(self, other: Waveform1D | npt.ArrayLike) -> npt.NDArray[np.bool_]:
        """Elementwise ``<``."""
        result: npt.NDArray[np.bool_] = np.less(
            self._values, self._comparable_values(other, "elements_less_than")
        )
        return result

    def elements_greater_than(self, other: Waveform1D | npt.ArrayLike) -> npt.NDArray[np.bool_]:
        """Elementwise ``>``."""
        result: npt.NDArray[np.bool_] = np.greater(
            self._values, self._comparable_values(other, "elements_greater_than")
        )
        return result

    def isclose_elementwise(
        self, other: Waveform1D | npt.ArrayLike, rtol: float = 1e-9, atol: float = 0.0
    ) -> npt.NDArray[np.bool_]:
        """Elementwise ``np.isclose`` (numpy ``rtol``/``atol`` vocabulary)."""
        other_values = self._comparable_values(other, "isclose_elementwise")
        result: npt.NDArray[np.bool_] = np.isclose(
            self._values, other_values, rtol=rtol, atol=atol
        )
        return result

    def isclose(self, other: Waveform1D, rtol: float = 1e-9, atol: float = 0.0) -> bool:
        """Whole-waveform approximate equality: same ``dt``, same ``t0``, all samples close."""
        if self._dt != other._dt or self._t0 != other._t0:
            return False
        if len(self._values) != len(other._values):
            return False
        return bool(np.all(np.isclose(self._values, other._values, rtol=rtol, atol=atol)))

    # MARK: - Iteration / array interop

    def __iter__(self) -> Iterator[float]:
        return (float(v) for v in self._values)

    def __array__(
        self, dtype: npt.DTypeLike | None = None, copy: bool | None = None
    ) -> npt.NDArray[Any]:
        return np.array(self._values, dtype=dtype, copy=True)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(sample_count={len(self._values)}, dt={self._dt!r}, "
            f"t0={self._t0!r})"
        )
