"""``WaveformQuaternion``: a uniformly-sampled quaternion (orientation) time series.

See ``.claude/specs/waveformCore.md`` (§ABC accessor, §Time axis,
§Aggregate containers with ``Element = Quaternion``). Storage is a private
``(n, 4)`` float64 ``np.ndarray`` in **``(w, x, y, z)`` order** (pinned
repo-wide -- NOT Swift's x-first order); ``dt``/``t0`` are the same Tier-3
``PrecisionTimeInterval``/``PrecisionTimestamp`` time-axis types used by
``Waveform1D`` (``waveforms/waveform1d.py``) -- the ~6 small time properties
are copied rather than shared via a base class, mirroring
``WaveformPosition``'s (chunk 15) own precedent (copying is acceptable; a
shared base is not justified for this small a surface).

The ABC-required ``quaternions`` accessor materializes a fresh list of
:class:`~math_tools.spatial.quaternion.Quaternion` objects on each access
(the serialization/contract surface); bulk paths (``quaternions_array``,
``normalize``/``normalized``, ``component_waveforms``, ``are_all_unit``)
stay vectorized over the numpy storage and never round-trip through
materialized ``Quaternion`` objects (waveformCore.md §Compliance 10).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, NamedTuple, cast, overload

import numpy as np
import numpy.typing as npt
from foundation_abc.math.waveformABCs import QuaternionWaveformABC

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.spatial.quaternion import Quaternion
from math_tools.waveforms.waveform1d import Waveform1D


class QuaternionComponentWaveforms(NamedTuple):
    """Per-component decomposition returned by :attr:`WaveformQuaternion.component_waveforms`.

    Field order is ``(w, x, y, z)`` -- w-first, matching storage order,
    ``from_components``, and ``Quaternion.to_components()``. This is the one
    place this container explicitly diverges from the Swift x-first tuple
    order.
    """

    w: Waveform1D
    x: Waveform1D
    y: Waveform1D
    z: Waveform1D


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
        raise ValueError(f"WaveformQuaternion: quaternions must have shape (n, 4), got {arr.shape}")
    return arr


class WaveformQuaternion(QuaternionWaveformABC):
    """A mutable, uniformly-sampled quaternion time series backed by an ``(n, 4)`` ndarray."""

    # MARK: - Construction

    def __init__(
        self,
        quaternions: Sequence[Quaternion] | npt.ArrayLike,
        dt: PrecisionTimeInterval | None = None,
        dt_seconds: float | None = None,
        t0: PrecisionTimestamp | None = None,
        t0_seconds: float | None = None,
    ) -> None:
        """Construct from a sequence of ``Quaternion`` elements (or raw ``(n, 4)``
        array-like in ``(w, x, y, z)`` order, copied) and an optional time axis.

        ``dt``/``dt_seconds`` are mutually exclusive (``dt_seconds`` defaults
        to ``1.0`` when neither is given); likewise ``t0``/``t0_seconds``
        (``t0`` defaults to ``PrecisionTimestamp.EPOCH``).

        Raises:
            TypeError: If both ``dt`` and ``dt_seconds``, or both ``t0`` and
                ``t0_seconds``, are given.
            ValueError: If ``quaternions`` does not coerce to shape
                ``(n, 4)``, or the resolved ``dt`` is not strictly positive.
        """
        if dt is not None and dt_seconds is not None:
            raise TypeError("WaveformQuaternion: specify at most one of dt, dt_seconds")
        if t0 is not None and t0_seconds is not None:
            raise TypeError("WaveformQuaternion: specify at most one of t0, t0_seconds")

        resolved_dt = (
            dt
            if dt is not None
            else PrecisionTimeInterval.from_seconds(dt_seconds if dt_seconds is not None else 1.0)
        )
        if resolved_dt.total_attoseconds <= 0:
            raise ValueError(
                f"WaveformQuaternion: dt must be strictly positive, got {resolved_dt!r}"
            )

        if t0 is not None:
            resolved_t0 = t0
        elif t0_seconds is not None:
            resolved_t0 = PrecisionTimestamp.from_interval(
                PrecisionTimeInterval.from_seconds(t0_seconds)
            )
        else:
            resolved_t0 = PrecisionTimestamp.EPOCH

        self._quaternions: npt.NDArray[np.float64] = _quaternions_to_array(quaternions)
        self._dt = resolved_dt
        self._t0 = resolved_t0

    @classmethod
    def from_dict(cls, obj: Any) -> WaveformQuaternion:
        """Construct from the ABC wire shape ``{"quaternions", "t0", "dt"}``."""
        if not isinstance(obj, dict):
            raise TypeError(f"expected a dict, got {type(obj).__name__}")
        dt = PrecisionTimeInterval.from_dict(obj["dt"])
        t0 = PrecisionTimestamp.from_dict(obj["t0"])
        quaternions = [Quaternion.from_dict(q) for q in obj.get("quaternions", [])]
        return cls(quaternions, dt=dt, t0=t0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the ABC wire shape ``{"dt", "quaternions", "t0"}``.

        Emits exactly what ``foundationTypes`` ``QuaternionWaveformType.to_dict()``
        emits, so the payload round-trips through either carrier.
        """
        return {
            "dt": self.dt.to_dict(),
            "quaternions": [q.to_dict() for q in self.quaternions],
            "t0": self.t0.to_dict(),
        }

    @classmethod
    def from_components(
        cls, w: Waveform1D, x: Waveform1D, y: Waveform1D, z: Waveform1D
    ) -> WaveformQuaternion:
        """Build from four per-component ``Waveform1D``s (``dt``/``t0`` taken from ``w``).

        Args:
            w: The scalar (real) component waveform.
            x: The x component (vector part) waveform.
            y: The y component (vector part) waveform.
            z: The z component (vector part) waveform.

        Raises:
            ValueError: Unless ``w``, ``x``, ``y``, ``z`` all have equal
                length and equal ``dt`` (Swift's optional-returning ``init?``
                becomes a raise in this port).
        """
        if not (len(w) == len(x) == len(y) == len(z)):
            raise ValueError(
                "WaveformQuaternion.from_components: w, x, y, z must have equal length "
                f"(got {len(w)}, {len(x)}, {len(y)}, {len(z)})"
            )
        if not (w.dt == x.dt == y.dt == z.dt):
            raise ValueError(
                "WaveformQuaternion.from_components: w, x, y, z must have equal dt "
                f"(got {w.dt!r}, {x.dt!r}, {y.dt!r}, {z.dt!r})"
            )
        quaternions = np.stack([w.values, x.values, y.values, z.values], axis=1).astype(np.float64)
        return cls(quaternions, dt=w.dt, t0=w.t0)

    # MARK: - Properties (ABC-required)

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
    def quaternions_array(self) -> npt.NDArray[np.float64]:
        """A copy of the ``(n, 4)`` sample array, ``(w, x, y, z)`` order."""
        return np.array(self._quaternions, dtype=np.float64, copy=True)

    # MARK: - Properties (time axis; copied from Waveform1D, see module docstring)

    @property
    def duration(self) -> PrecisionTimeInterval:
        """The span from the first to the last sample (``ZERO`` when ``n <= 1``)."""
        n = len(self._quaternions)
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
        return len(self._quaternions)

    def __len__(self) -> int:
        return len(self._quaternions)

    def time_axis(self) -> npt.NDArray[np.float64]:
        """Sample times (seconds, relative to ``t0``) as a float64 array."""
        n = len(self._quaternions)
        return np.arange(n, dtype=np.float64) * self._dt.seconds_as_float

    # MARK: - Component decomposition

    @property
    def component_waveforms(self) -> QuaternionComponentWaveforms:
        """Decompose into per-component ``(w, x, y, z)`` ``Waveform1D``s sharing this
        ``dt``/``t0``."""
        return QuaternionComponentWaveforms(
            w=Waveform1D(self._quaternions[:, 0], dt=self._dt, t0=self._t0),
            x=Waveform1D(self._quaternions[:, 1], dt=self._dt, t0=self._t0),
            y=Waveform1D(self._quaternions[:, 2], dt=self._dt, t0=self._t0),
            z=Waveform1D(self._quaternions[:, 3], dt=self._dt, t0=self._t0),
        )

    # MARK: - Normalization

    @property
    def are_all_unit(self) -> bool:
        """Whether every quaternion is (approximately) unit length (vectorized)."""
        if len(self._quaternions) == 0:
            return True
        norms = np.linalg.norm(self._quaternions, axis=1)
        return bool(np.all(np.isclose(norms, 1.0, atol=1e-12)))

    def normalize(self) -> None:
        """Normalize every quaternion to unit length, in place (vectorized).

        Raises:
            ValueError: If any row has zero magnitude (parity with
                ``Position.normalize``'s own zero-magnitude ``ValueError``
                style, mirroring ``WaveformPosition.normalize``).
        """
        norms = np.linalg.norm(self._quaternions, axis=1)
        zero_indices = np.flatnonzero(norms == 0.0)
        if zero_indices.size > 0:
            raise ValueError(
                f"cannot normalize a zero-magnitude quaternion at index {int(zero_indices[0])}"
            )
        self._quaternions = self._quaternions / norms[:, np.newaxis]

    def normalized(self) -> WaveformQuaternion:
        """Return a normalized (unit) copy of this waveform (vectorized).

        Raises:
            ValueError: If any row has zero magnitude.
        """
        result = WaveformQuaternion(self._quaternions, dt=self._dt, t0=self._t0)
        result.normalize()
        return result

    # MARK: - Indexing / slicing

    @overload
    def __getitem__(self, index: int) -> Quaternion: ...
    @overload
    def __getitem__(self, index: slice) -> WaveformQuaternion: ...

    def __getitem__(self, index: int | slice) -> Quaternion | WaveformQuaternion:
        if isinstance(index, slice):
            if index.step is not None and index.step != 1:
                raise ValueError(
                    "WaveformQuaternion slicing does not support step != 1; resampling is "
                    "the explicit API"
                )
            start, stop, _ = index.indices(len(self._quaternions))
            new_t0 = self._t0 + self._dt * start
            return WaveformQuaternion(self._quaternions[start:stop], dt=self._dt, t0=new_t0)
        return Quaternion.from_float_array(self._quaternions[index])

    def get(self, index: int) -> Quaternion | None:
        """Like ``__getitem__(int)`` but returns ``None`` instead of raising when
        ``index`` is out of range (Swift's ``subscript(safe:)``)."""
        n = len(self._quaternions)
        resolved = index + n if index < 0 else index
        if resolved < 0 or resolved >= n:
            return None
        return Quaternion.from_float_array(self._quaternions[resolved])

    def __iter__(self) -> Iterator[Quaternion]:
        return (Quaternion.from_float_array(row) for row in self._quaternions)

    def __array__(
        self, dtype: npt.DTypeLike | None = None, copy: bool | None = None
    ) -> npt.NDArray[Any]:
        """Return the ``(sample_count, 4)`` ``(w, x, y, z)`` quaternion array for
        ``np.asarray(w)`` interop (mathToolsArchitecture.md §API idioms).

        Raises:
            ValueError: If ``copy=False`` is requested -- a copy is always required
                since the returned array must not alias the mutable backing store.
        """
        if copy is False:
            raise ValueError(
                "WaveformQuaternion.__array__: copy=False is not supported (a copy is required)"
            )
        return np.array(self._quaternions, dtype=dtype, copy=True)

    # MARK: - Mutation

    def append(self, value: Quaternion) -> None:
        self._quaternions = np.concatenate(
            [self._quaternions, value.as_float_array().reshape(1, 4)], axis=0
        )

    def append_values(self, values: Sequence[Quaternion]) -> None:
        addition = _quaternions_to_array(values)
        self._quaternions = np.concatenate([self._quaternions, addition], axis=0)

    def prepend(self, value: Quaternion) -> None:
        self._quaternions = np.concatenate(
            [value.as_float_array().reshape(1, 4), self._quaternions], axis=0
        )
        self._t0 = self._t0 - self._dt

    def prepend_values(self, values: Sequence[Quaternion]) -> None:
        addition = _quaternions_to_array(values)
        self._quaternions = np.concatenate([addition, self._quaternions], axis=0)
        self._t0 = self._t0 - self._dt * len(addition)

    def insert(self, index: int, value: Quaternion) -> None:
        self._quaternions = np.insert(self._quaternions, index, value.as_float_array(), axis=0)

    def replace(self, index: int, value: Quaternion) -> None:
        self._quaternions[index] = value.as_float_array()

    def replace_range(self, index: slice, values: Sequence[Quaternion]) -> None:
        self._quaternions[index] = _quaternions_to_array(values)

    def pop(self, index: int = -1) -> Quaternion:
        """Remove and return the quaternion at ``index`` (default: last).

        Raises:
            IndexError: If the waveform is empty, or ``index`` is out of range.
        """
        if len(self._quaternions) == 0:
            raise IndexError("pop from an empty WaveformQuaternion")
        value = Quaternion.from_float_array(self._quaternions[index])
        self._quaternions = np.delete(self._quaternions, index, axis=0)
        return value

    def clear(self) -> None:
        self._quaternions = np.zeros((0, 4), dtype=np.float64)

    # MARK: - Extend / concatenate

    def _check_compatible_dt(self, other: WaveformQuaternion, op_name: str) -> None:
        """Raise ``WaveformCompatibilityError`` unless ``other`` shares this waveform's ``dt``
        (waveformCore.md §Aggregate containers Mutation; no length constraint -- these are
        concatenation ops, not elementwise ones)."""
        if self._dt != other._dt:
            raise WaveformCompatibilityError(
                f"WaveformQuaternion.{op_name}: dt mismatch ({self._dt!r} vs {other._dt!r})"
            )

    def extend(self, other: WaveformQuaternion) -> None:
        """Append ``other``'s quaternions to this waveform, in place.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "extend")
        self._quaternions = np.concatenate([self._quaternions, other._quaternions], axis=0)

    def concatenate(self, other: WaveformQuaternion) -> WaveformQuaternion:
        """Return a new waveform with ``other``'s quaternions appended after this one's.

        Raises:
            WaveformCompatibilityError: If ``other.dt`` differs from ``self.dt``.
        """
        self._check_compatible_dt(other, "concatenate")
        combined = np.concatenate([self._quaternions, other._quaternions], axis=0)
        return WaveformQuaternion(combined, dt=self._dt, t0=self._t0)

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Full equality: quaternions (exact), ``dt``, ``t0``."""
        if not isinstance(other, WaveformQuaternion):
            return NotImplemented
        return (
            self._dt == other._dt
            and self._t0 == other._t0
            and bool(np.array_equal(self._quaternions, other._quaternions))
        )

    def isclose(
        self, other: WaveformQuaternion, rtol: float = 1e-9, atol: float = 1e-11
    ) -> bool:
        """Whole-waveform approximate equality: same ``sample_count``, same ``dt``,
        same ``t0``, all quaternions close (numpy ``rtol``/``atol`` vocabulary and
        defaults mirroring :meth:`~math_tools.spatial.quaternion.Quaternion.isclose`).

        Double-cover aware **per sample**: each row independently may match either
        ``other``'s row or its negation (``q`` and ``-q`` are the same rotation), so
        a copy with every quaternion row negated still compares ``isclose``.
        """
        if self.sample_count != other.sample_count:
            return False
        if self._dt != other._dt or self._t0 != other._t0:
            return False
        if self.sample_count == 0:
            return True
        same_sign = np.isclose(self._quaternions, other._quaternions, rtol=rtol, atol=atol)
        flipped_sign = np.isclose(self._quaternions, -other._quaternions, rtol=rtol, atol=atol)
        row_matches = np.all(same_sign, axis=1) | np.all(flipped_sign, axis=1)
        return bool(np.all(row_matches))

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(sample_count={len(self._quaternions)}, dt={self._dt!r}, "
            f"t0={self._t0!r})"
        )
