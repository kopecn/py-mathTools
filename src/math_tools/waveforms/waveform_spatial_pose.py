"""``WaveformSpatialPose``: a uniformly-sampled 6-DOF pose time series.

See ``.claude/specs/waveformCore.md`` (§ABC accessor, §Time axis,
§Aggregate containers, §Compliance 1, 2, 8, 9). Unlike
:class:`~math_tools.waveforms.waveform_position.WaveformPosition` and
:class:`~math_tools.waveforms.waveform_quaternion.WaveformQuaternion`, this
container is backed by TWO independent parallel arrays -- a private
``(n, 3)`` float64 position array and a private ``(n, 4)`` float64
quaternion array (``(w, x, y, z)`` order, matching
:class:`~math_tools.waveforms.waveform_quaternion.WaveformQuaternion`) --
rather than one, because it composes a position-like array and a
quaternion-like array side by side. ``dt``/``t0`` are the same Tier-3
``PrecisionTimeInterval``/``PrecisionTimestamp`` time-axis types used
elsewhere in this package; the ~6 small time properties are copied rather
than shared via a base class, mirroring ``WaveformPosition``/
``WaveformQuaternion``'s own precedent.

**Load-bearing subtlety (waveformCore.md §Compliance 9):** the two arrays
are allowed to have DIFFERENT lengths. The primary constructor deliberately
does NOT require ``positions`` and ``quaternions`` to have equal length --
only the higher-level ``from_waveforms`` convenience constructor validates
count (and ``dt``) equality, raising ``ValueError``. This keeps
``is_valid``/``sample_count`` real, reachable semantics: ``is_valid`` is
``True`` only when the two arrays have equal length, and ``sample_count``
(and ``__len__``) is ``min(len(positions), len(quaternions))`` -- NOT simply
one array's length. All other time-axis properties (``duration``,
``time_axis()``, slicing, ``get``/iteration bounds) are derived from
``sample_count`` so they stay internally consistent with that "valid
prefix" even when the two arrays have been directly manipulated into an
unequal-length state. Higher-level constructors (``from_poses``,
``from_waveforms``) naturally produce equal-length (valid) instances.

The ABC-required ``positions``/``quaternions`` accessors materialize fresh
lists of :class:`~math_tools.spatial.position.Position` /
:class:`~math_tools.spatial.quaternion.Quaternion` objects on each access
(the serialization/contract surface); bulk paths (``positions_array``,
``quaternions_array``, ``normalize``/``normalized``, ``component_waveforms``,
``are_all_positions_unit``/``are_all_quaternions_unit``) stay vectorized
over the numpy storage and never round-trip through materialized objects
(waveformCore.md §Compliance 10).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, NamedTuple, cast, overload

import numpy as np
import numpy.typing as npt
from foundation_abc.math.waveformABCs import WaveformSpatialABC

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.spatial.position import Position
from math_tools.spatial.quaternion import Quaternion
from math_tools.spatial.spatial_pose import SpatialPose
from math_tools.waveforms.waveform1d import Waveform1D
from math_tools.waveforms.waveform_position import PositionComponentWaveforms, WaveformPosition
from math_tools.waveforms.waveform_quaternion import (
    QuaternionComponentWaveforms,
    WaveformQuaternion,
)


class SpatialPoseComponentWaveforms(NamedTuple):
    """Nested per-component decomposition returned by
    :attr:`WaveformSpatialPose.component_waveforms`.

    ``position`` reuses :class:`PositionComponentWaveforms`
    (``x, y, z``, chunk 15) and ``quaternion`` reuses
    :class:`QuaternionComponentWaveforms` (``w, x, y, z``, w-first, chunk
    16) rather than redefining equivalent ``NamedTuple``s.
    """

    position: PositionComponentWaveforms
    quaternion: QuaternionComponentWaveforms


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
        raise ValueError(f"WaveformSpatialPose: positions must have shape (n, 3), got {arr.shape}")
    return arr


def _quaternions_to_array(
    quaternions: Sequence[Quaternion] | npt.ArrayLike,
) -> npt.NDArray[np.float64]:
    """Coerce constructor/mutation input to a fresh ``(n, 4)`` float64 array in
    ``(w, x, y, z)`` order.

    Accepts a sequence of :class:`Quaternion` elements or any array-like
    coercible to shape ``(n, 4)``; an empty sequence becomes an ``(0, 4)``
    array so empty construction and empty mutation payloads both work.

    Raises:
        ValueError: If the resolved array is not shape ``(n, 4)``.
    """
    if isinstance(quaternions, np.ndarray):
        arr = np.array(quaternions, dtype=np.float64, copy=True)
    elif isinstance(quaternions, Sequence) and len(quaternions) == 0:
        arr = np.zeros((0, 4), dtype=np.float64)
    elif isinstance(quaternions, Sequence) and isinstance(quaternions[0], Quaternion):
        quaternion_items = cast(Sequence[Quaternion], quaternions)
        arr = np.array([q.as_float_array() for q in quaternion_items], dtype=np.float64)
    else:
        arr = np.array(quaternions, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 4:
        raise ValueError(
            f"WaveformSpatialPose: quaternions must have shape (n, 4), got {arr.shape}"
        )
    return arr


def _poses_to_arrays(
    poses: Sequence[SpatialPose],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Decompose a sequence of :class:`SpatialPose` into parallel position/quaternion arrays."""
    if len(poses) == 0:
        return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 4), dtype=np.float64)
    positions = np.array([pose.position.vector for pose in poses], dtype=np.float64)
    quaternions = np.array([pose.orientation.as_float_array() for pose in poses], dtype=np.float64)
    return positions, quaternions


class WaveformSpatialPose(WaveformSpatialABC):
    """A mutable, uniformly-sampled 6-DOF pose time series backed by parallel
    ``(n, 3)`` position and ``(n, 4)`` quaternion ndarrays."""

    # MARK: - Construction

    def __init__(
        self,
        positions: Sequence[Position] | npt.ArrayLike,
        quaternions: Sequence[Quaternion] | npt.ArrayLike,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> None:
        """Construct from parallel position/quaternion sequences (each a
        sequence of elements, or a raw array-like, copied) and an optional
        time axis.

        ``dt``/``dt_seconds`` are mutually exclusive (``dt_seconds`` defaults
        to ``1.0`` when neither is given); likewise ``t0``/``t0_seconds``
        (``t0`` defaults to ``PrecisionTimestamp.EPOCH``).

        Unlike :meth:`from_waveforms`, this primary constructor does NOT
        require ``positions`` and ``quaternions`` to have equal length --
        see the module docstring's note on ``is_valid``/``sample_count``.

        Raises:
            TypeError: If both ``dt`` and ``dt_seconds``, or both ``t0`` and
                ``t0_seconds``, are given.
            ValueError: If ``positions``/``quaternions`` do not coerce to
                shape ``(n, 3)``/``(n, 4)`` respectively, or the resolved
                ``dt`` is not strictly positive.
        """
        if dt is not None and dt_seconds is not None:
            raise TypeError("WaveformSpatialPose: specify at most one of dt, dt_seconds")
        if t0 is not None and t0_seconds is not None:
            raise TypeError("WaveformSpatialPose: specify at most one of t0, t0_seconds")

        resolved_dt = (
            dt
            if dt is not None
            else PrecisionTimeInterval.from_seconds(dt_seconds if dt_seconds is not None else 1.0)
        )
        if resolved_dt.total_attoseconds <= 0:
            raise ValueError(
                f"WaveformSpatialPose: dt must be strictly positive, got {resolved_dt!r}"
            )

        if t0 is not None:
            resolved_t0 = t0
        elif t0_seconds is not None:
            resolved_t0 = PrecisionTimestamp.from_interval(
                PrecisionTimeInterval.from_seconds(t0_seconds)
            )
        else:
            resolved_t0 = PrecisionTimestamp.EPOCH

        self._positions: npt.NDArray[np.float64] = _positions_to_array(positions)
        self._quaternions: npt.NDArray[np.float64] = _quaternions_to_array(quaternions)
        self._dt = resolved_dt
        self._t0 = resolved_t0

    @classmethod
    def from_dict(cls, obj: Any) -> WaveformSpatialPose:
        """Construct from the ABC wire shape ``{"positions", "quaternions", "t0", "dt"}``."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        dt = PrecisionTimeInterval.from_dict(obj["dt"])
        t0 = PrecisionTimestamp.from_dict(obj["t0"])
        positions = [Position.from_dict(p) for p in obj.get("positions", [])]
        quaternions = [Quaternion.from_dict(q) for q in obj.get("quaternions", [])]
        return cls(positions, quaternions, dt=dt, t0=t0)

    @classmethod
    def from_poses(
        cls,
        poses: list[SpatialPose],
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> WaveformSpatialPose:
        """Build from a list of :class:`SpatialPose` objects, decomposing each into
        its ``.position``/``.orientation`` halves.

        Always produces an equal-length (``is_valid``) instance.
        """
        positions = [pose.position for pose in poses]
        quaternions = [pose.orientation for pose in poses]
        return cls(
            positions, quaternions, dt=dt, dt_seconds=dt_seconds, t0=t0, t0_seconds=t0_seconds
        )

    @classmethod
    def from_components(
        cls,
        position_x: Waveform1D,
        position_y: Waveform1D,
        position_z: Waveform1D,
        quaternion_w: Waveform1D,
        quaternion_x: Waveform1D,
        quaternion_y: Waveform1D,
        quaternion_z: Waveform1D,
    ) -> WaveformSpatialPose:
        """Build from seven per-component ``Waveform1D``s -- three for the position
        half (``x, y, z``) and four for the quaternion half (``w, x, y, z``) --
        following :meth:`WaveformPosition.from_components`'s /
        :meth:`WaveformQuaternion.from_components`'s shape exactly (``dt``/``t0``
        taken from ``position_x``; waveformCore.md §Aggregate containers).

        Raises:
            ValueError: Unless all seven inputs have equal length and equal ``dt``
                (Swift's optional-returning ``init?`` becomes a raise in this port).
        """
        components = (
            position_x,
            position_y,
            position_z,
            quaternion_w,
            quaternion_x,
            quaternion_y,
            quaternion_z,
        )
        lengths = {len(component) for component in components}
        if len(lengths) != 1:
            raise ValueError(
                "WaveformSpatialPose.from_components: all seven component waveforms must "
                f"have equal length (got {[len(component) for component in components]})"
            )
        dts = {component.dt for component in components}
        if len(dts) != 1:
            raise ValueError(
                "WaveformSpatialPose.from_components: all seven component waveforms must "
                f"have equal dt (got {[component.dt for component in components]})"
            )
        positions = np.stack(
            [position_x.values, position_y.values, position_z.values], axis=1
        ).astype(np.float64)
        quaternions = np.stack(
            [quaternion_w.values, quaternion_x.values, quaternion_y.values, quaternion_z.values],
            axis=1,
        ).astype(np.float64)
        return cls(positions, quaternions, dt=position_x.dt, t0=position_x.t0)

    @classmethod
    def from_waveforms(
        cls, position_waveform: WaveformPosition, quaternion_waveform: WaveformQuaternion
    ) -> WaveformSpatialPose:
        """Build from a sibling :class:`WaveformPosition` and :class:`WaveformQuaternion`
        pair, sharing ``dt``/``t0`` from ``position_waveform``.

        Raises:
            ValueError: If the two waveforms have unequal length or unequal
                ``dt``.
        """
        if len(position_waveform) != len(quaternion_waveform):
            raise ValueError(
                "WaveformSpatialPose.from_waveforms: position_waveform and quaternion_waveform "
                f"must have equal length (got {len(position_waveform)}, {len(quaternion_waveform)})"
            )
        if position_waveform.dt != quaternion_waveform.dt:
            raise ValueError(
                "WaveformSpatialPose.from_waveforms: position_waveform and quaternion_waveform "
                f"must have equal dt (got {position_waveform.dt!r}, {quaternion_waveform.dt!r})"
            )
        return cls(
            position_waveform.positions_array,
            quaternion_waveform.quaternions_array,
            dt=position_waveform.dt,
            t0=position_waveform.t0,
        )

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
    def quaternions(self) -> Sequence[Quaternion]:
        """A fresh list of materialized ``Quaternion`` objects (the ABC-required accessor).

        Materialized on demand from :attr:`quaternions_array`; bulk/vectorized
        code paths use :attr:`quaternions_array` directly and never go through
        this accessor internally (waveformCore.md §Compliance 10).
        """
        return [Quaternion.from_float_array(row) for row in self._quaternions]

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

    @property
    def quaternions_array(self) -> npt.NDArray[np.float64]:
        """A copy of the ``(n, 4)`` sample array, ``(w, x, y, z)`` order."""
        return np.array(self._quaternions, dtype=np.float64, copy=True)

    # MARK: - Validity (waveformCore.md §Compliance 9)

    @property
    def is_valid(self) -> bool:
        """Whether the parallel position/quaternion arrays have equal length."""
        return len(self._positions) == len(self._quaternions)

    # MARK: - Properties (time axis; copied from Waveform1D, see module docstring)
    #
    # Unlike WaveformPosition/WaveformQuaternion, every quantity below is
    # derived from `sample_count` (the min of the two array lengths, per
    # §Compliance 9) rather than a single array's length, so they stay
    # consistent with each other and with slicing/iteration even when the
    # two arrays have been directly manipulated into an unequal-length state.

    @property
    def duration(self) -> PrecisionTimeInterval:
        """The span from the first to the last sample (``ZERO`` when ``n <= 1``)."""
        n = self.sample_count
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
        """``min(len(positions), len(quaternions))`` -- NOT simply one array's length
        (waveformCore.md §Compliance 9)."""
        return min(len(self._positions), len(self._quaternions))

    def __len__(self) -> int:
        return self.sample_count

    def time_axis(self) -> npt.NDArray[np.float64]:
        """Sample times (seconds, relative to ``t0``) as a float64 array."""
        n = self.sample_count
        return np.arange(n, dtype=np.float64) * self._dt.seconds_as_float

    # MARK: - Component decomposition

    @property
    def component_waveforms(self) -> SpatialPoseComponentWaveforms:
        """Decompose into a nested ``(position, quaternion)`` tuple of per-component
        ``Waveform1D``s sharing this ``dt``/``t0``."""
        return SpatialPoseComponentWaveforms(
            position=PositionComponentWaveforms(
                x=Waveform1D(self._positions[:, 0], dt=self._dt, t0=self._t0),
                y=Waveform1D(self._positions[:, 1], dt=self._dt, t0=self._t0),
                z=Waveform1D(self._positions[:, 2], dt=self._dt, t0=self._t0),
            ),
            quaternion=QuaternionComponentWaveforms(
                w=Waveform1D(self._quaternions[:, 0], dt=self._dt, t0=self._t0),
                x=Waveform1D(self._quaternions[:, 1], dt=self._dt, t0=self._t0),
                y=Waveform1D(self._quaternions[:, 2], dt=self._dt, t0=self._t0),
                z=Waveform1D(self._quaternions[:, 3], dt=self._dt, t0=self._t0),
            ),
        )

    @property
    def position_waveform(self) -> WaveformPosition:
        """The position half of this pose waveform, as a standalone ``WaveformPosition``
        sharing this waveform's ``dt``/``t0`` (built directly from the stored array, not
        via :attr:`component_waveforms`)."""
        return WaveformPosition(self._positions, dt=self._dt, t0=self._t0)

    @property
    def quaternion_waveform(self) -> WaveformQuaternion:
        """The orientation half of this pose waveform, as a standalone
        ``WaveformQuaternion`` sharing this waveform's ``dt``/``t0`` (built directly
        from the stored array, not via :attr:`component_waveforms`)."""
        return WaveformQuaternion(self._quaternions, dt=self._dt, t0=self._t0)

    # MARK: - Normalization

    @property
    def are_all_positions_unit(self) -> bool:
        """Whether every position is (approximately) a unit vector (vectorized)."""
        if len(self._positions) == 0:
            return True
        norms = np.linalg.norm(self._positions, axis=1)
        return bool(np.all(np.isclose(norms, 1.0, atol=1e-12)))

    @property
    def are_all_quaternions_unit(self) -> bool:
        """Whether every quaternion is (approximately) unit length (vectorized)."""
        if len(self._quaternions) == 0:
            return True
        norms = np.linalg.norm(self._quaternions, axis=1)
        return bool(np.all(np.isclose(norms, 1.0, atol=1e-12)))

    def normalize(self) -> None:
        """Normalize every position AND every quaternion to unit length, in place
        (vectorized).

        Both arrays are checked for zero-magnitude rows before either is
        mutated, so a failure leaves this waveform unchanged.

        Raises:
            ValueError: If any row of either array has zero magnitude
                (parity with ``WaveformPosition.normalize`` /
                ``WaveformQuaternion.normalize``'s own zero-magnitude
                ``ValueError``).
        """
        position_norms = np.linalg.norm(self._positions, axis=1)
        position_zero_indices = np.flatnonzero(position_norms == 0.0)
        if position_zero_indices.size > 0:
            raise ValueError(
                "cannot normalize a zero-magnitude position at index "
                f"{int(position_zero_indices[0])}"
            )
        quaternion_norms = np.linalg.norm(self._quaternions, axis=1)
        quaternion_zero_indices = np.flatnonzero(quaternion_norms == 0.0)
        if quaternion_zero_indices.size > 0:
            raise ValueError(
                "cannot normalize a zero-magnitude quaternion at index "
                f"{int(quaternion_zero_indices[0])}"
            )
        self._positions = self._positions / position_norms[:, np.newaxis]
        self._quaternions = self._quaternions / quaternion_norms[:, np.newaxis]

    def normalized(self) -> WaveformSpatialPose:
        """Return a copy of this waveform with both arrays normalized (vectorized).

        Raises:
            ValueError: If any row of either array has zero magnitude.
        """
        result = WaveformSpatialPose(self._positions, self._quaternions, dt=self._dt, t0=self._t0)
        result.normalize()
        return result

    # MARK: - Indexing / slicing

    def _resolve_index(self, index: int) -> int:
        """Normalize ``index`` against :attr:`sample_count` (the valid prefix, per
        waveformCore.md §Compliance 9) to a non-negative raw-array index.

        The single shared bounds helper for every entry point that indexes the
        raw ``positions``/``quaternions`` arrays with an integer -- see the
        module docstring's note that all index paths must derive from
        ``sample_count``, not either raw array's own length.

        Raises:
            IndexError: If ``index`` is out of range for ``sample_count``.
        """
        n = self.sample_count
        resolved = index + n if index < 0 else index
        if resolved < 0 or resolved >= n:
            raise IndexError(
                f"WaveformSpatialPose index {index!r} out of range for sample_count={n}"
            )
        return resolved

    @overload
    def __getitem__(self, index: int) -> SpatialPose: ...
    @overload
    def __getitem__(self, index: slice) -> WaveformSpatialPose: ...

    def __getitem__(self, index: int | slice) -> SpatialPose | WaveformSpatialPose:
        if isinstance(index, slice):
            if index.step is not None and index.step != 1:
                raise ValueError(
                    "WaveformSpatialPose slicing does not support step != 1; resampling is "
                    "the explicit API"
                )
            start, stop, _ = index.indices(self.sample_count)
            new_t0 = self._t0 + self._dt * start
            return WaveformSpatialPose(
                self._positions[start:stop],
                self._quaternions[start:stop],
                dt=self._dt,
                t0=new_t0,
            )
        resolved = self._resolve_index(index)
        return SpatialPose(
            Position.from_vector(self._positions[resolved]),
            Quaternion.from_float_array(self._quaternions[resolved]),
        )

    def get(self, index: int) -> SpatialPose | None:
        """Like ``__getitem__(int)`` but returns ``None`` instead of raising when
        ``index`` is out of range (Swift's ``subscript(safe:)``)."""
        try:
            resolved = self._resolve_index(index)
        except IndexError:
            return None
        return SpatialPose(
            Position.from_vector(self._positions[resolved]),
            Quaternion.from_float_array(self._quaternions[resolved]),
        )

    def __iter__(self) -> Iterator[SpatialPose]:
        return (
            SpatialPose(
                Position.from_vector(self._positions[i]),
                Quaternion.from_float_array(self._quaternions[i]),
            )
            for i in range(self.sample_count)
        )

    def __array__(
        self, dtype: npt.DTypeLike | None = None, copy: bool | None = None
    ) -> npt.NDArray[Any]:
        """Return this waveform's ``(sample_count, 7)`` stacked array, columns
        ``[x, y, z, w, i, j, k]`` (position ``xyz`` then quaternion ``wxyz``, both
        truncated to :attr:`sample_count` -- waveformCore.md §Array shape contract;
        mathToolsArchitecture.md §API idioms).

        Raises:
            ValueError: If ``copy=False`` is requested -- a copy is always required
                since the returned array must not alias the mutable backing stores.
        """
        if copy is False:
            raise ValueError(
                "WaveformSpatialPose.__array__: copy=False is not supported (a copy is "
                "required)"
            )
        n = self.sample_count
        combined = np.concatenate([self._positions[:n], self._quaternions[:n]], axis=1)
        return np.array(combined, dtype=dtype, copy=True)

    # MARK: - Mutation

    def append(self, value: SpatialPose) -> None:
        self._positions = np.concatenate(
            [self._positions, value.position.vector.reshape(1, 3)], axis=0
        )
        self._quaternions = np.concatenate(
            [self._quaternions, value.orientation.as_float_array().reshape(1, 4)], axis=0
        )

    def append_values(self, values: Sequence[SpatialPose]) -> None:
        position_addition, quaternion_addition = _poses_to_arrays(values)
        self._positions = np.concatenate([self._positions, position_addition], axis=0)
        self._quaternions = np.concatenate([self._quaternions, quaternion_addition], axis=0)

    def prepend(self, value: SpatialPose) -> None:
        self._positions = np.concatenate(
            [value.position.vector.reshape(1, 3), self._positions], axis=0
        )
        self._quaternions = np.concatenate(
            [value.orientation.as_float_array().reshape(1, 4), self._quaternions], axis=0
        )
        self._t0 = self._t0 - self._dt

    def prepend_values(self, values: Sequence[SpatialPose]) -> None:
        position_addition, quaternion_addition = _poses_to_arrays(values)
        self._positions = np.concatenate([position_addition, self._positions], axis=0)
        self._quaternions = np.concatenate([quaternion_addition, self._quaternions], axis=0)
        self._t0 = self._t0 - self._dt * len(values)

    def insert(self, index: int, value: SpatialPose) -> None:
        self._positions = np.insert(self._positions, index, value.position.vector, axis=0)
        self._quaternions = np.insert(
            self._quaternions, index, value.orientation.as_float_array(), axis=0
        )

    def replace(self, index: int, value: SpatialPose) -> None:
        self._positions[index] = value.position.vector
        self._quaternions[index] = value.orientation.as_float_array()

    def replace_range(self, index: slice, values: Sequence[SpatialPose]) -> None:
        position_values, quaternion_values = _poses_to_arrays(values)
        self._positions[index] = position_values
        self._quaternions[index] = quaternion_values

    def pop(self, index: int = -1) -> SpatialPose:
        """Remove and return the pose at ``index`` (default: last), from both arrays.

        ``index`` is normalized against :attr:`sample_count`, so it removes the
        same sample from both arrays even when they differ in length
        (waveformCore.md §Compliance 9).

        Raises:
            IndexError: If the waveform is empty, or ``index`` is out of range.
        """
        if self.sample_count == 0:
            raise IndexError("pop from an empty WaveformSpatialPose")
        resolved = self._resolve_index(index)
        value = SpatialPose(
            Position.from_vector(self._positions[resolved]),
            Quaternion.from_float_array(self._quaternions[resolved]),
        )
        self._positions = np.delete(self._positions, resolved, axis=0)
        self._quaternions = np.delete(self._quaternions, resolved, axis=0)
        return value

    def clear(self) -> None:
        self._positions = np.zeros((0, 3), dtype=np.float64)
        self._quaternions = np.zeros((0, 4), dtype=np.float64)

    # MARK: - Extend / concatenate

    def _check_compatible_dt(self, other: WaveformSpatialPose, op_name: str) -> None:
        """Raise ``WaveformCompatibilityError`` unless ``other`` shares this waveform's ``dt``
        (waveformCore.md §Aggregate containers Mutation; no length constraint -- these are
        concatenation ops, not elementwise ones)."""
        if self._dt != other._dt:
            raise WaveformCompatibilityError(
                f"WaveformSpatialPose.{op_name}: dt mismatch ({self._dt!r} vs {other._dt!r})"
            )

    def extend(self, other: WaveformSpatialPose) -> None:
        """Append ``other``'s poses to this waveform, in place.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "extend")
        self._positions = np.concatenate([self._positions, other._positions], axis=0)
        self._quaternions = np.concatenate([self._quaternions, other._quaternions], axis=0)

    def concatenate(self, other: WaveformSpatialPose) -> WaveformSpatialPose:
        """Return a new waveform with ``other``'s poses appended after this one's.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "concatenate")
        combined_positions = np.concatenate([self._positions, other._positions], axis=0)
        combined_quaternions = np.concatenate([self._quaternions, other._quaternions], axis=0)
        return WaveformSpatialPose(
            combined_positions, combined_quaternions, dt=self._dt, t0=self._t0
        )

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Full equality: positions (exact), quaternions (exact), ``dt``, ``t0``."""
        if not isinstance(other, WaveformSpatialPose):
            return NotImplemented
        return (
            self._dt == other._dt
            and self._t0 == other._t0
            and bool(np.array_equal(self._positions, other._positions))
            and bool(np.array_equal(self._quaternions, other._quaternions))
        )

    def isclose(self, other: WaveformSpatialPose, rtol: float = 1e-9, atol: float = 0.0) -> bool:
        """Whole-waveform approximate equality: same ``sample_count``, same ``dt``,
        same ``t0``, all positions AND quaternions close (numpy ``rtol``/``atol``
        vocabulary, mirroring :meth:`~math_tools.spatial.position.Position.isclose`'s
        parameter order/defaults; the same ``rtol``/``atol`` is applied to both halves).

        Double-cover aware **per sample** on the quaternion half: each row
        independently may match either ``other``'s quaternion row or its negation
        (``q`` and ``-q`` are the same rotation), mirroring
        :meth:`WaveformQuaternion.isclose`.
        """
        n = self.sample_count
        if n != other.sample_count:
            return False
        if self._dt != other._dt or self._t0 != other._t0:
            return False
        if n == 0:
            return True
        positions_close = np.allclose(
            self._positions[:n], other._positions[:n], rtol=rtol, atol=atol
        )
        if not positions_close:
            return False
        self_quaternions = self._quaternions[:n]
        other_quaternions = other._quaternions[:n]
        same_sign = np.isclose(self_quaternions, other_quaternions, rtol=rtol, atol=atol)
        flipped_sign = np.isclose(self_quaternions, -other_quaternions, rtol=rtol, atol=atol)
        row_matches = np.all(same_sign, axis=1) | np.all(flipped_sign, axis=1)
        return bool(np.all(row_matches))

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(sample_count={self.sample_count}, dt={self._dt!r}, "
            f"t0={self._t0!r})"
        )
