"""``WaveformPosition``: a uniformly-sampled 3D position time series.

See ``.claude/specs/waveformCore.md`` (§ABC accessor, §Time axis,
§Aggregate containers with ``Element = Position``). Storage is a private
``(n, 3)`` float64 ``np.ndarray``; ``dt``/``t0`` are the same Tier-3
``PrecisionTimeInterval``/``PrecisionTimestamp`` time-axis types used by
``Waveform1D`` (``waveforms/waveform1d.py``) -- the ~6 small time properties
are copied rather than shared via a base class, per the chunk's own design
constraint (copying is acceptable; a shared base is not justified for this
small a surface).

The ABC-required ``positions`` accessor materializes a fresh list of
:class:`~math_tools.spatial.position.Position` objects on each access (the
serialization/contract surface); bulk paths (``positions_array``,
``normalize``/``normalized``, ``component_waveforms``) stay vectorized over
the numpy storage and never round-trip through materialized ``Position``
objects (waveformCore.md §Compliance 10).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, NamedTuple, cast, overload

import numpy as np
import numpy.typing as npt
from foundation_abc.math.waveformABCs import PositionWaveformABC

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.spatial.position import Position
from math_tools.waveforms.waveform1d import Waveform1D


class PositionComponentWaveforms(NamedTuple):
    """Per-axis decomposition returned by :attr:`WaveformPosition.component_waveforms`."""

    x: Waveform1D
    y: Waveform1D
    z: Waveform1D


def _positions_to_array(positions: Sequence[Position] | npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Coerce constructor/mutation input to a fresh ``(n, 3)`` float64 array.

    Accepts a sequence of :class:`Position` elements or any array-like
    coercible to shape ``(n, 3)``; an empty sequence becomes an ``(0, 3)``
    array so empty construction and empty mutation payloads both work.

    Raises:
        ValueError: If the resolved array is not shape ``(n, 3)``.
    """
    if isinstance(positions, np.ndarray):
        arr = np.array(positions, dtype=np.float64, copy=True)
    elif isinstance(positions, Sequence) and len(positions) == 0:
        arr = np.zeros((0, 3), dtype=np.float64)
    elif isinstance(positions, Sequence) and isinstance(positions[0], Position):
        position_items = cast(Sequence[Position], positions)
        arr = np.array([p.vector for p in position_items], dtype=np.float64)
    else:
        arr = np.array(positions, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"WaveformPosition: positions must have shape (n, 3), got {arr.shape}")
    return arr


class WaveformPosition(PositionWaveformABC):
    """A mutable, uniformly-sampled 3D position time series backed by an ``(n, 3)`` ndarray."""

    # MARK: - Construction

    def __init__(
        self,
        positions: Sequence[Position] | npt.ArrayLike,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> None:
        """Construct from a sequence of ``Position`` elements (or raw ``(n, 3)``
        array-like, copied) and an optional time axis.

        ``dt``/``dt_seconds`` are mutually exclusive (``dt_seconds`` defaults
        to ``1.0`` when neither is given); likewise ``t0``/``t0_seconds``
        (``t0`` defaults to ``PrecisionTimestamp.EPOCH``).

        Raises:
            TypeError: If both ``dt`` and ``dt_seconds``, or both ``t0`` and
                ``t0_seconds``, are given.
            ValueError: If ``positions`` does not coerce to shape ``(n, 3)``,
                or the resolved ``dt`` is not strictly positive.
        """
        if dt is not None and dt_seconds is not None:
            raise TypeError("WaveformPosition: specify at most one of dt, dt_seconds")
        if t0 is not None and t0_seconds is not None:
            raise TypeError("WaveformPosition: specify at most one of t0, t0_seconds")

        resolved_dt = (
            dt
            if dt is not None
            else PrecisionTimeInterval.from_seconds(dt_seconds if dt_seconds is not None else 1.0)
        )
        if resolved_dt.total_attoseconds <= 0:
            raise ValueError(f"WaveformPosition: dt must be strictly positive, got {resolved_dt!r}")

        if t0 is not None:
            resolved_t0 = t0
        elif t0_seconds is not None:
            resolved_t0 = PrecisionTimestamp.from_interval(
                PrecisionTimeInterval.from_seconds(t0_seconds)
            )
        else:
            resolved_t0 = PrecisionTimestamp.EPOCH

        self._positions: npt.NDArray[np.float64] = _positions_to_array(positions)
        self._dt = resolved_dt
        self._t0 = resolved_t0

    @classmethod
    def from_dict(cls, obj: Any) -> WaveformPosition:
        """Construct from the ABC wire shape ``{"positions", "t0", "dt"}``."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        dt = PrecisionTimeInterval.from_dict(obj["dt"])
        t0 = PrecisionTimestamp.from_dict(obj["t0"])
        positions = [Position.from_dict(p) for p in obj.get("positions", [])]
        return cls(positions, dt=dt, t0=t0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the ABC wire shape ``{"dt", "positions", "t0"}``.

        Emits exactly what ``foundationTypes`` ``PositionWaveformType.to_dict()``
        emits, so the payload round-trips through either carrier.
        """
        return {
            "dt": self.dt.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "t0": self.t0.to_dict(),
        }

    @classmethod
    def from_components(cls, x: Waveform1D, y: Waveform1D, z: Waveform1D) -> WaveformPosition:
        """Build from three per-axis ``Waveform1D``s (``dt``/``t0`` taken from ``x``).

        Raises:
            ValueError: Unless ``x``, ``y``, ``z`` all have equal length and
                equal ``dt`` (Swift's optional-returning ``init?`` becomes a
                raise in this port).
        """
        if not (len(x) == len(y) == len(z)):
            raise ValueError(
                "WaveformPosition.from_components: x, y, z must have equal length "
                f"(got {len(x)}, {len(y)}, {len(z)})"
            )
        if not (x.dt == y.dt == z.dt):
            raise ValueError(
                "WaveformPosition.from_components: x, y, z must have equal dt "
                f"(got {x.dt!r}, {y.dt!r}, {z.dt!r})"
            )
        positions = np.stack([x.values, y.values, z.values], axis=1).astype(np.float64)
        return cls(positions, dt=x.dt, t0=x.t0)

    # MARK: - Properties (ABC-required)

    @property
    def positions(self) -> Sequence[Position]:
        """A fresh list of materialized ``Position`` objects (the ABC-required accessor).

        Materialized on demand from :attr:`positions_array`; bulk/vectorized
        code paths use :attr:`positions_array` directly and never go through
        this accessor internally (waveformCore.md §Compliance 10).
        """
        return [Position.from_vector(row) for row in self._positions]

    @property
    def t0(self) -> PrecisionTimestamp:
        return self._t0

    @property
    def dt(self) -> PrecisionTimeInterval:
        return self._dt

    # MARK: - Properties (numpy bulk accessor)

    @property
    def positions_array(self) -> npt.NDArray[np.float64]:
        """A copy of the ``(n, 3)`` sample array."""
        return np.array(self._positions, dtype=np.float64, copy=True)

    # MARK: - Properties (time axis; copied from Waveform1D, see module docstring)

    @property
    def duration(self) -> PrecisionTimeInterval:
        """The span from the first to the last sample (``ZERO`` when ``n <= 1``)."""
        n = len(self._positions)
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
        return len(self._positions)

    def __len__(self) -> int:
        return len(self._positions)

    def time_axis(self) -> npt.NDArray[np.float64]:
        """Sample times (seconds, relative to ``t0``) as a float64 array."""
        n = len(self._positions)
        return np.arange(n, dtype=np.float64) * self._dt.seconds_as_float

    # MARK: - Component decomposition

    @property
    def component_waveforms(self) -> PositionComponentWaveforms:
        """Decompose into per-axis ``(x, y, z)`` ``Waveform1D``s sharing this ``dt``/``t0``."""
        return PositionComponentWaveforms(
            x=Waveform1D(self._positions[:, 0], dt=self._dt, t0=self._t0),
            y=Waveform1D(self._positions[:, 1], dt=self._dt, t0=self._t0),
            z=Waveform1D(self._positions[:, 2], dt=self._dt, t0=self._t0),
        )

    # MARK: - Normalization

    @property
    def are_all_unit(self) -> bool:
        """Whether every position is (approximately) a unit vector (vectorized)."""
        if len(self._positions) == 0:
            return True
        norms = np.linalg.norm(self._positions, axis=1)
        return bool(np.all(np.isclose(norms, 1.0, atol=1e-12)))

    def normalize(self) -> None:
        """Normalize every position to unit length, in place (vectorized).

        Raises:
            ValueError: If any row has zero magnitude (parity with
                ``Position.normalize``'s own zero-magnitude ``ValueError``).
        """
        norms = np.linalg.norm(self._positions, axis=1)
        zero_indices = np.flatnonzero(norms == 0.0)
        if zero_indices.size > 0:
            raise ValueError(
                f"cannot normalize a zero-magnitude position at index {int(zero_indices[0])}"
            )
        self._positions = self._positions / norms[:, np.newaxis]

    def normalized(self) -> WaveformPosition:
        """Return a normalized (unit) copy of this waveform (vectorized).

        Raises:
            ValueError: If any row has zero magnitude.
        """
        result = WaveformPosition(self._positions, dt=self._dt, t0=self._t0)
        result.normalize()
        return result

    # MARK: - Indexing / slicing

    @overload
    def __getitem__(self, index: int) -> Position: ...
    @overload
    def __getitem__(self, index: slice) -> WaveformPosition: ...

    def __getitem__(self, index: int | slice) -> Position | WaveformPosition:
        if isinstance(index, slice):
            if index.step is not None and index.step != 1:
                raise ValueError(
                    "WaveformPosition slicing does not support step != 1; resampling is "
                    "the explicit API"
                )
            start, stop, _ = index.indices(len(self._positions))
            new_t0 = self._t0 + self._dt * start
            return WaveformPosition(self._positions[start:stop], dt=self._dt, t0=new_t0)
        return Position.from_vector(self._positions[index])

    def get(self, index: int) -> Position | None:
        """Like ``__getitem__(int)`` but returns ``None`` instead of raising when
        ``index`` is out of range (Swift's ``subscript(safe:)``)."""
        n = len(self._positions)
        resolved = index + n if index < 0 else index
        if resolved < 0 or resolved >= n:
            return None
        return Position.from_vector(self._positions[resolved])

    def __iter__(self) -> Iterator[Position]:
        return (Position.from_vector(row) for row in self._positions)

    def __array__(
        self, dtype: npt.DTypeLike | None = None, copy: bool | None = None
    ) -> npt.NDArray[Any]:
        """Return the ``(sample_count, 3)`` position array for ``np.asarray(w)`` interop
        (mathToolsArchitecture.md §API idioms).

        Raises:
            ValueError: If ``copy=False`` is requested -- a copy is always required
                since the returned array must not alias the mutable backing store.
        """
        if copy is False:
            raise ValueError(
                "WaveformPosition.__array__: copy=False is not supported (a copy is required)"
            )
        return np.array(self._positions, dtype=dtype, copy=True)

    # MARK: - Mutation

    def append(self, value: Position) -> None:
        self._positions = np.concatenate([self._positions, value.vector.reshape(1, 3)], axis=0)

    def append_values(self, values: Sequence[Position]) -> None:
        addition = _positions_to_array(values)
        self._positions = np.concatenate([self._positions, addition], axis=0)

    def prepend(self, value: Position) -> None:
        self._positions = np.concatenate([value.vector.reshape(1, 3), self._positions], axis=0)
        self._t0 = self._t0 - self._dt

    def prepend_values(self, values: Sequence[Position]) -> None:
        addition = _positions_to_array(values)
        self._positions = np.concatenate([addition, self._positions], axis=0)
        self._t0 = self._t0 - self._dt * len(addition)

    def insert(self, index: int, value: Position) -> None:
        self._positions = np.insert(self._positions, index, value.vector, axis=0)

    def replace(self, index: int, value: Position) -> None:
        self._positions[index] = value.vector

    def replace_range(self, index: slice, values: Sequence[Position]) -> None:
        self._positions[index] = _positions_to_array(values)

    def pop(self, index: int = -1) -> Position:
        """Remove and return the position at ``index`` (default: last).

        Raises:
            IndexError: If the waveform is empty, or ``index`` is out of range.
        """
        if len(self._positions) == 0:
            raise IndexError("pop from an empty WaveformPosition")
        value = Position.from_vector(self._positions[index])
        self._positions = np.delete(self._positions, index, axis=0)
        return value

    def clear(self) -> None:
        self._positions = np.zeros((0, 3), dtype=np.float64)

    # MARK: - Extend / concatenate

    def _check_compatible_dt(self, other: WaveformPosition, op_name: str) -> None:
        """Raise ``WaveformCompatibilityError`` unless ``other`` shares this waveform's ``dt``
        (waveformCore.md §Aggregate containers Mutation; no length constraint -- these are
        concatenation ops, not elementwise ones)."""
        if self._dt != other._dt:
            raise WaveformCompatibilityError(
                f"WaveformPosition.{op_name}: dt mismatch ({self._dt!r} vs {other._dt!r})"
            )

    def extend(self, other: WaveformPosition) -> None:
        """Append ``other``'s positions to this waveform, in place.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "extend")
        self._positions = np.concatenate([self._positions, other._positions], axis=0)

    def concatenate(self, other: WaveformPosition) -> WaveformPosition:
        """Return a new waveform with ``other``'s positions appended after this one's.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "concatenate")
        combined = np.concatenate([self._positions, other._positions], axis=0)
        return WaveformPosition(combined, dt=self._dt, t0=self._t0)

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Full equality: positions (exact), ``dt``, ``t0``."""
        if not isinstance(other, WaveformPosition):
            return NotImplemented
        return (
            self._dt == other._dt
            and self._t0 == other._t0
            and bool(np.array_equal(self._positions, other._positions))
        )

    def isclose(self, other: WaveformPosition, rtol: float = 1e-9, atol: float = 0.0) -> bool:
        """Whole-waveform approximate equality: same ``sample_count``, same ``dt``,
        same ``t0``, all positions close (numpy ``rtol``/``atol`` vocabulary, mirroring
        :meth:`~math_tools.spatial.position.Position.isclose`'s parameter order/defaults).
        """
        if self.sample_count != other.sample_count:
            return False
        if self._dt != other._dt or self._t0 != other._t0:
            return False
        return bool(np.allclose(self._positions, other._positions, rtol=rtol, atol=atol))

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(sample_count={len(self._positions)}, dt={self._dt!r}, "
            f"t0={self._t0!r})"
        )
