"""3D Cartesian position, the numpy-backed Tier-3 subclass of ``PositionABC``.

See ``.claude/specs/spatialMath.md`` (§Position, §Coordinate conventions).
Storage is a private ``(3,)`` float64 ndarray; ``x``/``y``/``z`` are settable
properties indexing into it (mutable, matching the incumbent
``Quaternion`` idiom).

Two spherical conventions are supported and are NOT interchangeable:

- ``spherical`` (geographic): ``elevation`` measured from the xy-plane, range
  ``[-pi/2, pi/2]``.
- ``spherical_iso`` (ISO 80000-2 physics/colatitude): ``polar`` measured from
  +z, range ``[0, pi]`` — the same convention documented in
  ``math_tools.spherical.spherical_generators``.
"""

from __future__ import annotations

from typing import Any, NamedTuple, TypeVar

import numpy as np
import numpy.typing as npt
from foundation_abc.math.spatialABCs import PositionABC

from math_tools.hints import FloatArray3

T = TypeVar("T", bound="Position")


class CylindricalCoordinates(NamedTuple):
    """Inverse accessor for :attr:`Position.cylindrical`."""

    radius: float
    angle: float
    height: float


class SphericalCoordinates(NamedTuple):
    """Inverse accessor for :attr:`Position.spherical` (geographic convention)."""

    radius: float
    azimuth: float
    elevation: float


class SphericalIsoCoordinates(NamedTuple):
    """Inverse accessor for :attr:`Position.spherical_iso` (ISO 80000-2 convention)."""

    radius: float
    azimuth: float
    polar: float


def _from_float(x: Any) -> float:
    assert isinstance(x, (float, int)) and not isinstance(x, bool)
    return float(x)


class Position(PositionABC):
    """A mutable 3D Cartesian position (the translation component of SE(3))."""

    __slots__ = ("_vector",)

    # MARK: - Constructors

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self._vector: FloatArray3 = np.array([x, y, z], dtype=np.float64)

    @classmethod
    def from_vector(cls: type[T], v: npt.ArrayLike) -> T:
        """Create a position from an array-like ``[x, y, z]``.

        Args:
            v: Array-like coercible to a ``(3,)`` float array. The input is
                copied, never aliased.

        Raises:
            ValueError: If ``v`` does not coerce to shape ``(3,)``.
        """
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (3,):
            raise ValueError(f"Position.from_vector requires shape (3,), got {arr.shape}")
        return cls(float(arr[0]), float(arr[1]), float(arr[2]))

    @classmethod
    def from_components(cls: type[T], x: float = 0.0, y: float = 0.0, z: float = 0.0) -> T:
        """Create a position from individual x, y, z components."""
        return cls(x, y, z)

    @classmethod
    def from_cylindrical(cls: type[T], radius: float, angle: float, height: float) -> T:
        """Create a position from cylindrical coordinates (radius, angle, height)."""
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        return cls(float(x), float(y), float(height))

    @classmethod
    def from_spherical(cls: type[T], radius: float, azimuth: float, elevation: float) -> T:
        """Create a position from spherical coordinates (geographic convention).

        Args:
            radius: Radial distance from the origin.
            azimuth: Angle in the xy-plane from +x, in radians.
            elevation: Angle from the xy-plane (equator), in radians;
                range ``[-pi/2, pi/2]``.
        """
        radius_xy = radius * np.cos(elevation)
        x = radius_xy * np.cos(azimuth)
        y = radius_xy * np.sin(azimuth)
        z = radius * np.sin(elevation)
        return cls(float(x), float(y), float(z))

    @classmethod
    def from_spherical_iso(cls: type[T], radius: float, azimuth: float, polar: float) -> T:
        """Create a position from spherical coordinates (ISO 80000-2 convention).

        Args:
            radius: Radial distance from the origin.
            azimuth: Angle in the xy-plane from +x, in radians.
            polar: Angle from +z (colatitude), in radians; range ``[0, pi]``.
        """
        radius_xy = radius * np.sin(polar)
        x = radius_xy * np.cos(azimuth)
        y = radius_xy * np.sin(azimuth)
        z = radius * np.cos(polar)
        return cls(float(x), float(y), float(z))

    @classmethod
    def origin(cls: type[T]) -> T:
        """The origin position ``(0, 0, 0)``."""
        return cls(0.0, 0.0, 0.0)

    @classmethod
    def unit_x(cls: type[T]) -> T:
        """Unit position along the x-axis ``(1, 0, 0)``."""
        return cls(1.0, 0.0, 0.0)

    @classmethod
    def unit_y(cls: type[T]) -> T:
        """Unit position along the y-axis ``(0, 1, 0)``."""
        return cls(0.0, 1.0, 0.0)

    @classmethod
    def unit_z(cls: type[T]) -> T:
        """Unit position along the z-axis ``(0, 0, 1)``."""
        return cls(0.0, 0.0, 1.0)

    @classmethod
    def from_dict(cls: type[T], obj: Any) -> T:
        """Create a position instance from a ``{"x", "y", "z"}`` dict."""
        assert isinstance(obj, dict)
        x = _from_float(obj.get("x"))
        y = _from_float(obj.get("y"))
        z = _from_float(obj.get("z"))
        return cls(x, y, z)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the ABC wire shape ``{"x", "y", "z"}``.

        Emits exactly what ``foundationTypes`` ``PositionType.to_dict()`` emits,
        so the payload round-trips through either carrier.
        """
        return {"x": self.x, "y": self.y, "z": self.z}

    # MARK: - Properties

    @property
    def x(self) -> float:
        return float(self._vector[0])

    @x.setter
    def x(self, value: float) -> None:
        self._vector[0] = value

    @property
    def y(self) -> float:
        return float(self._vector[1])

    @y.setter
    def y(self, value: float) -> None:
        self._vector[1] = value

    @property
    def z(self) -> float:
        return float(self._vector[2])

    @z.setter
    def z(self, value: float) -> None:
        self._vector[2] = value

    @property
    def vector(self) -> FloatArray3:
        """The ``(3,)`` float64 vector, copied out."""
        return np.array(self._vector, dtype=np.float64)

    @property
    def components(self) -> list[float]:
        """The ``[x, y, z]`` components as a plain list."""
        return [self.x, self.y, self.z]

    @property
    def cylindrical(self) -> CylindricalCoordinates:
        """Cylindrical coordinates ``(radius, angle, height)``."""
        radius = float(np.hypot(self.x, self.y))
        angle = float(np.arctan2(self.y, self.x))
        return CylindricalCoordinates(radius=radius, angle=angle, height=self.z)

    @property
    def spherical(self) -> SphericalCoordinates:
        """Spherical coordinates ``(radius, azimuth, elevation)`` (geographic convention)."""
        radius = self.magnitude
        azimuth = float(np.arctan2(self.y, self.x))
        elevation = float(np.arcsin(self.z / radius)) if radius > 0.0 else 0.0
        return SphericalCoordinates(radius=radius, azimuth=azimuth, elevation=elevation)

    @property
    def spherical_iso(self) -> SphericalIsoCoordinates:
        """Spherical coordinates ``(radius, azimuth, polar)`` (ISO 80000-2 convention)."""
        radius = self.magnitude
        azimuth = float(np.arctan2(self.y, self.x))
        polar = float(np.arccos(np.clip(self.z / radius, -1.0, 1.0))) if radius > 0.0 else 0.0
        return SphericalIsoCoordinates(radius=radius, azimuth=azimuth, polar=polar)

    @property
    def magnitude_squared(self) -> float:
        """The squared magnitude (length) of the position vector."""
        return float(np.dot(self._vector, self._vector))

    @property
    def magnitude(self) -> float:
        """The magnitude (length) of the position vector."""
        return float(np.sqrt(self.magnitude_squared))

    @property
    def norm(self) -> float:
        """Alias of :attr:`magnitude` (parity with ``Quaternion.norm``)."""
        return self.magnitude

    @property
    def is_unit(self) -> bool:
        """Whether this is (approximately) a unit vector."""
        return bool(np.isclose(self.magnitude, 1.0, rtol=0.0, atol=1e-12))

    def __abs__(self) -> float:
        """Return the magnitude of the position vector."""
        return self.magnitude

    # MARK: - Arithmetic Operators

    def __add__(self, other: Position | float) -> Position:
        """Add another position (vector addition) or a scalar (broadcast)."""
        if isinstance(other, Position):
            return Position.from_vector(self._vector + other._vector)
        elif isinstance(other, (float, int)) and not isinstance(other, bool):
            return Position.from_vector(self._vector + other)
        return NotImplemented

    def __radd__(self, other: float) -> Position:
        """Right addition (scalar + position)."""
        return self.__add__(other)

    def __sub__(self, other: Position | float) -> Position:
        """Subtract another position (vector subtraction) or a scalar (broadcast)."""
        if isinstance(other, Position):
            return Position.from_vector(self._vector - other._vector)
        elif isinstance(other, (float, int)) and not isinstance(other, bool):
            return Position.from_vector(self._vector - other)
        return NotImplemented

    def __rsub__(self, other: float) -> Position:
        """Right subtraction (scalar - position, component-wise)."""
        if isinstance(other, (float, int)) and not isinstance(other, bool):
            return Position.from_vector(other - self._vector)
        return NotImplemented

    def __mul__(self, other: float) -> Position:
        """Scale this position by a scalar."""
        if isinstance(other, (float, int)) and not isinstance(other, bool):
            return Position.from_vector(self._vector * other)
        return NotImplemented

    def __rmul__(self, other: float) -> Position:
        """Right multiplication (scalar * position)."""
        return self.__mul__(other)

    def __truediv__(self, other: float) -> Position:
        """Divide this position by a scalar."""
        if isinstance(other, (float, int)) and not isinstance(other, bool):
            return Position.from_vector(self._vector / other)
        return NotImplemented

    def __iadd__(self, other: Position | float) -> Position:
        """In-place addition."""
        if isinstance(other, Position):
            self._vector += other._vector
            return self
        elif isinstance(other, (float, int)) and not isinstance(other, bool):
            self._vector += other
            return self
        return NotImplemented

    def __isub__(self, other: Position | float) -> Position:
        """In-place subtraction."""
        if isinstance(other, Position):
            self._vector -= other._vector
            return self
        elif isinstance(other, (float, int)) and not isinstance(other, bool):
            self._vector -= other
            return self
        return NotImplemented

    def __imul__(self, other: float) -> Position:
        """In-place scaling."""
        if isinstance(other, (float, int)) and not isinstance(other, bool):
            self._vector *= other
            return self
        return NotImplemented

    def __itruediv__(self, other: float) -> Position:
        """In-place division."""
        if isinstance(other, (float, int)) and not isinstance(other, bool):
            self._vector /= other
            return self
        return NotImplemented

    def __neg__(self) -> Position:
        """Negate the position (flip direction)."""
        return Position.from_vector(-self._vector)

    def __pos__(self) -> Position:
        """Unary positive (returns a copy)."""
        return Position.from_vector(self._vector)

    # MARK: - Vector Operations

    def dot(self, other: Position) -> float:
        """Compute the dot product with another position."""
        return float(np.dot(self._vector, other._vector))

    def cross(self, other: Position) -> Position:
        """Compute the cross product with another position (right-hand rule)."""
        return Position.from_vector(np.cross(self._vector, other._vector))

    def distance(self, to: Position) -> float:
        """Compute the Euclidean distance to another position."""
        return float(np.linalg.norm(self._vector - to._vector))

    def distance_squared(self, to: Position) -> float:
        """Compute the squared Euclidean distance to another position."""
        diff = self._vector - to._vector
        return float(np.dot(diff, diff))

    # MARK: - Normalization

    def normalize(self) -> None:
        """Normalize this position to unit length, in place.

        Raises:
            ValueError: If this position is the zero vector.
        """
        magnitude = self.magnitude
        if magnitude == 0.0:
            raise ValueError("cannot normalize a zero-magnitude position")
        self._vector /= magnitude

    def normalized(self) -> Position:
        """Return a normalized (unit) copy of this position.

        Raises:
            ValueError: If this position is the zero vector.
        """
        result = Position.from_vector(self._vector)
        result.normalize()
        return result

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Check exact equality with another position."""
        if isinstance(other, Position):
            return bool(np.array_equal(self._vector, other._vector))
        return False

    def isclose(self, other: Position, rtol: float = 1e-9, atol: float = 0.0) -> bool:
        """Check approximate equality with another position."""
        return bool(np.allclose(self._vector, other._vector, rtol=rtol, atol=atol))

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Return a detailed string representation."""
        return f"Position(x={self.x}, y={self.y}, z={self.z})"

    # MARK: - Array Conversion

    def __array__(
        self, dtype: npt.DTypeLike | None = None, copy: bool | None = None
    ) -> FloatArray3:
        """Return the ``(3,)`` vector for ``np.asarray(position)`` interop."""
        return np.array(self._vector, dtype=dtype, copy=True)
