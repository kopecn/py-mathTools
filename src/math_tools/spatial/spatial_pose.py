"""``SpatialPose``: the SE(3) pose type composing :class:`Position` and
:class:`Quaternion`.

See ``.claude/specs/spatialMath.md`` (§SpatialPose, §Compliance 4-8). Storage
is a composed ``Position`` (translation) + ``Quaternion`` (rotation); the
ABC's rotation accessor name is ``orientation`` (not Swift's ``quaternion``).

``*`` is the universal robotics "apply" reading: ``pose * pose`` composes two
transforms, ``pose * position`` applies the full SE(3) transform to a point
(identical to :meth:`SpatialPose.transform`). Swift's ``pose + position`` /
``pose - position`` operators are deliberately NOT ported: a bare ``+`` that
silently drops rotation is a footgun; :meth:`SpatialPose.translated` is the
explicit, named replacement.
"""

from __future__ import annotations

from typing import Any, TypeVar, overload

import numpy as np
import numpy.typing as npt
from foundation_abc.math.spatialABCs import SpatialTransformABC

from math_tools.spatial.position import Position
from math_tools.spatial.quaternion import Quaternion

T = TypeVar("T", bound="SpatialPose")


class SpatialPose(SpatialTransformABC):
    """A 6-DOF pose: one element of SE(3), the Lie group of rigid transforms."""

    # MARK: - Constructors

    def __init__(
        self, position: Position | None = None, orientation: Quaternion | None = None
    ) -> None:
        # Position is mutable (settable x/y/z); copy it so this pose's state
        # cannot be silently changed via a caller's outstanding reference.
        # Quaternion has no in-place mutators, so aliasing it is safe.
        self._position = (
            Position.from_vector(position.vector) if position is not None else Position.origin()
        )
        self._orientation = orientation if orientation is not None else Quaternion.identity()

    @classmethod
    def from_components(
        cls: type[T],
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        qw: float = 1.0,
        qx: float = 0.0,
        qy: float = 0.0,
        qz: float = 0.0,
    ) -> T:
        """Create a pose from individual position and quaternion (w-first) components."""
        return cls(Position(x, y, z), Quaternion.from_components(qw, qx, qy, qz))

    @classmethod
    def from_homogeneous(cls: type[T], matrix: npt.ArrayLike) -> T:
        """Create a pose from a ``(4, 4)`` homogeneous transformation matrix.

        Args:
            matrix: A ``(4, 4)`` array-like with a rotation submatrix in the
                top-left 3x3 block, a translation in the top-right column,
                and a rigid bottom row ``[0, 0, 0, 1]``.

        Raises:
            ValueError: If ``matrix`` is not ``(4, 4)`` or its bottom row is
                not (approximately) ``[0, 0, 0, 1]``.
        """
        arr = np.asarray(matrix, dtype=np.float64)
        if arr.shape != (4, 4):
            raise ValueError(f"SpatialPose.from_homogeneous requires shape (4, 4), got {arr.shape}")
        bottom_row = arr[3, :]
        if not np.allclose(bottom_row, [0.0, 0.0, 0.0, 1.0], atol=1e-9):
            raise ValueError(
                "SpatialPose.from_homogeneous requires a rigid bottom row "
                f"[0, 0, 0, 1], got {bottom_row.tolist()}"
            )
        orientation = Quaternion.from_rotation_matrix(arr[:3, :3])
        position = Position.from_vector(arr[:3, 3])
        return cls(position, orientation)

    @classmethod
    def from_denavit_hartenberg(cls: type[T], a: float, alpha: float, d: float, theta: float) -> T:
        """Create a pose from standard Denavit-Hartenberg parameters.

        [See DH Parameters](https://en.wikipedia.org/wiki/Denavit-Hartenberg_parameters)

        Args:
            a: Link length (distance along x axis).
            alpha: Link twist (angle in radians around x axis).
            d: Link offset (distance along z axis).
            theta: Joint angle (angle in radians around z axis).
        """
        ct, st = float(np.cos(theta)), float(np.sin(theta))
        ca, sa = float(np.cos(alpha)), float(np.sin(alpha))
        position = Position(a * ct, a * st, d)
        rotation_matrix = np.array(
            [
                [ct, -st * ca, st * sa],
                [st, ct * ca, -ct * sa],
                [0.0, sa, ca],
            ],
            dtype=np.float64,
        )
        orientation = Quaternion.from_rotation_matrix(rotation_matrix)
        return cls(position, orientation)

    @classmethod
    def identity(cls: type[T]) -> T:
        """The identity pose: origin position, identity orientation."""
        return cls(Position.origin(), Quaternion.identity())

    @classmethod
    def from_dict(cls: type[T], obj: Any) -> T:
        """Create a pose from a ``{"position", "orientation"}`` dict."""
        assert isinstance(obj, dict)
        position = Position.from_dict(obj.get("position"))
        orientation = Quaternion.from_dict(obj.get("orientation"))
        return cls(position, orientation)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the ABC wire shape ``{"orientation", "position"}``.

        Emits exactly what ``foundationTypes`` ``SpatialTransformType.to_dict()``
        emits (nested ``QuaternionType``/``PositionType`` payloads), so the
        payload round-trips through either carrier.
        """
        return {
            "orientation": self.orientation.to_dict(),
            "position": self.position.to_dict(),
        }

    # MARK: - Properties

    @property
    def position(self) -> Position:
        return self._position

    @property
    def orientation(self) -> Quaternion:
        return self._orientation

    @property
    def x(self) -> float:
        return self._position.x

    @property
    def y(self) -> float:
        return self._position.y

    @property
    def z(self) -> float:
        return self._position.z

    @property
    def qw(self) -> float:
        return self._orientation.w

    @property
    def qx(self) -> float:
        return self._orientation.x

    @property
    def qy(self) -> float:
        return self._orientation.y

    @property
    def qz(self) -> float:
        return self._orientation.z

    @property
    def homogeneous(self) -> npt.NDArray[np.float64]:
        """The ``(4, 4)`` homogeneous transformation matrix.

        The orientation is normalized before export (Swift parity), even if
        this pose's stored orientation is not currently a unit quaternion.
        """
        orientation = self._orientation.normalized()
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = orientation.to_rotation_matrix()
        matrix[:3, 3] = self._position.vector
        return matrix

    @property
    def is_unit(self) -> bool:
        """Whether the orientation component is (approximately) a unit quaternion."""
        return self._orientation.is_unit

    # MARK: - Operators

    @overload
    def __mul__(self, other: SpatialPose) -> SpatialPose: ...

    @overload
    def __mul__(self, other: Position) -> Position: ...

    def __mul__(self, other: SpatialPose | Position) -> SpatialPose | Position:
        """Apply: ``pose * pose`` composes; ``pose * position`` transforms the point."""
        if isinstance(other, SpatialPose):
            return SpatialPose(
                self._position + self._orientation.rotate_position(other.position),
                self._orientation * other.orientation,
            )
        if isinstance(other, Position):
            return self.transform(other)
        return NotImplemented

    def transform(self, p: Position) -> Position:
        """Apply the full SE(3) transform (rotate then translate) to a position."""
        return self._orientation.rotate_position(p) + self._position

    def translated(self, by: Position) -> SpatialPose:
        """Return a copy of this pose shifted by ``by`` (orientation unchanged)."""
        return SpatialPose(self._position + by, self._orientation)

    def inverse(self) -> SpatialPose:
        """Return the inverse pose: ``q^-1``, ``-(q^-1.rotate(p))``."""
        inverse_orientation = self._orientation.inverse()
        inverse_position = -(inverse_orientation.rotate_position(self._position))
        return SpatialPose(inverse_position, inverse_orientation)

    def relative_pose(self, to: SpatialPose) -> SpatialPose:
        """Return the pose that transforms from ``self`` to ``to``."""
        return self.inverse() * to

    def interpolate(self, to: SpatialPose, t: float) -> SpatialPose:
        """Interpolate toward ``to``: position lerp + quaternion slerp.

        ``t`` is unclamped: ``t=0`` returns (a copy of) ``self``, ``t=1``
        returns ``to``, and values outside ``[0, 1]`` extrapolate.
        """
        position = self._position + (to.position - self._position) * t
        orientation = self._orientation.slerp(to.orientation, t)
        return SpatialPose(position, orientation)

    def position_distance(self, to: SpatialPose) -> float:
        """The Euclidean distance between this pose's position and ``to``'s."""
        return self._position.distance(to.position)

    def position_distance_squared(self, to: SpatialPose) -> float:
        """The squared Euclidean distance between this pose's position and ``to``'s."""
        return self._position.distance_squared(to.position)

    def angular_distance(self, to: SpatialPose) -> float:
        """The angular distance (radians) between this pose's orientation and ``to``'s.

        Double-cover safe: uses ``|dot|`` so ``q`` and ``-q`` (the same
        rotation) yield the same distance.
        """
        cos_half_angle = abs(self._orientation.dot(to.orientation))
        return float(2.0 * np.arccos(np.clip(cos_half_angle, -1.0, 1.0)))

    # MARK: - Normalization

    def normalize(self) -> None:
        """Normalize the orientation component, in place."""
        self._orientation = self._orientation.normalized()

    def normalized(self) -> SpatialPose:
        """Return a copy of this pose with the orientation normalized."""
        return SpatialPose(self._position, self._orientation.normalized())

    # MARK: - Comparison

    def __eq__(self, other: object) -> bool:
        """Check exact equality with another pose."""
        if isinstance(other, SpatialPose):
            return self._position == other.position and self._orientation == other.orientation
        return False

    def isclose(self, other: SpatialPose, rtol: float = 1e-9, atol: float = 0.0) -> bool:
        """Check approximate equality (double-cover aware via ``Quaternion.isclose``)."""
        return self._position.isclose(
            other.position, rtol=rtol, atol=atol
        ) and self._orientation.isclose(other.orientation, rtol=rtol, atol=atol)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """Return a detailed string representation."""
        return f"SpatialPose(position={self._position!r}, orientation={self._orientation!r})"
