"""
Fully-typed OOP wrapper around numpy-quaternions library
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

import numpy as np
from foundationTypes.mathTypes.MathTypes import UnitSphericalSmallCircleType
from foundationTypes.mathTypes.quaternionABC import QuaternionABC
from quaternion import allclose as quat_allclose  # type: ignore[import-untyped]
from quaternion import (
    as_euler_angles,
    as_float_array,
    as_quat_array,
    as_rotation_matrix,
    as_rotation_vector,
    as_vector_part,
    from_euler_angles,
    from_float_array,
    from_rotation_matrix,
    from_rotation_vector,
    from_vector_part,
    rotate_vectors,
)
from quaternion import (
    isclose as quat_isclose,
)
from quaternion import quaternion as np_quaternion
from quaternion.quaternion_time_series import slerp as quat_slerp  # type: ignore[import-untyped]

# Import custom type hints
from pyMathTools.hints import (
    FloatArray3,
    FloatArray4,
    FloatOrQuaternion,
    RotationMatrix,
)

T = TypeVar("T", bound="Quaternion")


def from_float(x: Any) -> float:
    assert isinstance(x, (float, int)) and not isinstance(x, bool)
    return float(x)


@dataclass
class Quaternion(QuaternionABC):
    """
    wrapper class for numpy-quaternion for allowing
    """

    __q: np_quaternion

    # MARK: - Constructors

    @staticmethod
    def fromNumpyQuaternion(q: np_quaternion) -> Quaternion:
        return Quaternion(q)

    @classmethod
    def from_components(cls: type[T], w: float = 1, x: float = 0, y: float = 0, z: float = 0) -> T:
        """Create a quaternion instance from individual w, x, y, z components.

        Args:
            w: The scalar (real) component
            x: The x component of the vector part
            y: The y component of the vector part
            z: The z component of the vector part

        Returns:
            A concrete QuaternionType instance of the calling class type
        """
        return cls(np_quaternion(w, x, y, z))

    @classmethod
    def from_float_array(cls: type[T], array: FloatArray4) -> T:
        """Create a quaternion from a 4-element float array [w, x, y, z].

        Args:
            array: 4-element array in [w, x, y, z] order

        Returns:
            A concrete QuaternionType instance of the calling class type

        Raises:
            ValueError: If array doesn't have exactly 4 elements
        """
        q = from_float_array(array)
        return cls(q)

    @staticmethod
    def as_quat_array(array: np.ndarray) -> np.ndarray:
        """View a float array as an array of quaternions.

        The input array must have a final dimension whose size is 4.
        Each set of 4 components will be interpreted as [w, x, y, z].

        This is a fast operation (no data copy) when the array is C-contiguous.

        Args:
            array: Float array with last dimension of size 4
                  Shape can be (..., 4) where ... represents any number of dimensions
                  Examples:
                    - [w, x, y, z] -> single quaternion
                    - [[w1,x1,y1,z1], [w2,x2,y2,z2]] -> array of 2 quaternions

        Returns:
            NumPy array of quaternions with shape (...)

        Examples:
            >>> # Single quaternion
            >>> Quaternion.as_quat_array([1, 0, 0, 0])
            quaternion(1, 0, 0, 0)

            >>> # Array of quaternions
            >>> Quaternion.as_quat_array([[1,0,0,0], [0.707,0,0,0.707]])
            array([quaternion(1, 0, 0, 0), quaternion(0.707, 0, 0, 0.707)])
        """
        return as_quat_array(array)

    # MARK: - Properties

    @property
    def w(self) -> float:
        return self.__q.w

    @property
    def x(self) -> float:
        return self.__q.x

    @property
    def y(self) -> float:
        return self.__q.y

    @property
    def z(self) -> float:
        return self.__q.z

    @property
    def q(self) -> np_quaternion:
        return self.__q

    # MARK: - Arithmetic Operators

    def __add__(self, other: FloatOrQuaternion) -> Quaternion:
        """Add two quaternions or a quaternion and a scalar."""
        if isinstance(other, Quaternion):
            return Quaternion(self.__q + other.q)
        elif isinstance(other, (float, int)):
            return Quaternion(self.__q + other)
        elif isinstance(other, np_quaternion):
            return Quaternion(self.__q + other)
        return NotImplemented

    def __radd__(self, other: FloatOrQuaternion) -> Quaternion:
        """Right addition."""
        return self.__add__(other)

    def __sub__(self, other: FloatOrQuaternion) -> Quaternion:
        """Subtract two quaternions or a scalar from a quaternion."""
        if isinstance(other, Quaternion):
            return Quaternion(self.__q - other.q)
        elif isinstance(other, (float, int)):
            return Quaternion(self.__q - other)
        elif isinstance(other, np_quaternion):
            return Quaternion(self.__q - other)
        return NotImplemented

    def __rsub__(self, other: FloatOrQuaternion) -> Quaternion:
        """Right subtraction."""
        if isinstance(other, (float, int)):
            return Quaternion(other - self.__q)
        elif isinstance(other, np_quaternion):
            return Quaternion(other - self.__q)
        return NotImplemented

    def __mul__(self, other: FloatOrQuaternion) -> Quaternion:
        """Multiply two quaternions or a quaternion by a scalar."""
        if isinstance(other, Quaternion):
            return Quaternion(self.__q * other.q)
        elif isinstance(other, (float, int)):
            return Quaternion(self.__q * other)
        elif isinstance(other, np_quaternion):
            return Quaternion(self.__q * other)
        return NotImplemented

    def __rmul__(self, other: FloatOrQuaternion) -> Quaternion:
        """Right multiplication."""
        return self.__mul__(other)

    def __truediv__(self, other: FloatOrQuaternion) -> Quaternion:
        """Divide a quaternion by another quaternion or scalar."""
        if isinstance(other, Quaternion):
            return Quaternion(self.__q / other.q)
        elif isinstance(other, (float, int)):
            return Quaternion(self.__q / other)
        elif isinstance(other, np_quaternion):
            return Quaternion(self.__q / other)
        return NotImplemented

    def __rtruediv__(self, other: FloatOrQuaternion) -> Quaternion:
        """Right division."""
        if isinstance(other, (float, int)):
            return Quaternion(other / self.__q)
        elif isinstance(other, np_quaternion):
            return Quaternion(other / self.__q)
        return NotImplemented

    def __pow__(self, exponent: float) -> Quaternion:
        """Raise quaternion to a power."""
        return Quaternion(self.__q**exponent)

    def __neg__(self) -> Quaternion:
        """Negate the quaternion."""
        return Quaternion(-self.__q)

    def __pos__(self) -> Quaternion:
        """Unary positive."""
        return Quaternion(+self.__q)

    def __abs__(self) -> float:
        """Return the absolute value (norm) of the quaternion."""
        return float(abs(self.__q))

    # MARK: - Comparison Operators

    def __eq__(self, other: object) -> bool:
        """Check equality with another quaternion."""
        if isinstance(other, Quaternion):
            return bool(self.__q == other.q)
        elif isinstance(other, np_quaternion):
            return bool(self.__q == other)
        return False

    def __ne__(self, other: object) -> bool:
        """Check inequality with another quaternion."""
        return not self.__eq__(other)

    def __repr__(self) -> str:
        """Return a detailed string representation."""
        return f"Quaternion(w={self.w}, x={self.x}, y={self.y}, z={self.z})"

    def __str__(self) -> str:
        """Return a user-friendly string representation."""
        return f"quaternion({self.w}, {self.x}, {self.y}, {self.z})"

    # MARK: - Unary Operations

    def conjugate(self) -> Quaternion:
        """Return the conjugate of this quaternion.

        The conjugate of q = w + xi + yj + zk is q* = w - xi - yj - zk
        """
        return Quaternion(self.__q.conjugate())

    def inverse(self) -> Quaternion:
        """Return the inverse of this quaternion.

        The inverse is defined as q^-1 = q* / |q|^2
        """
        return Quaternion(1.0 / self.__q)

    def normalized(self) -> Quaternion:
        """Return a normalized (unit) version of this quaternion."""
        return Quaternion(self.__q / abs(self.__q))

    # MARK: - Utility Properties

    @property
    def norm(self) -> float:
        """Return the norm (magnitude) of the quaternion."""
        return float(abs(self.__q))

    @property
    def is_unit(self) -> bool:
        """Check if this is a unit quaternion (norm approximately 1)."""
        return bool(np.isclose(abs(self.__q), 1.0))

    @property
    def angle(self) -> float:
        """Return the rotation angle in radians (for unit quaternions)."""
        return float(2.0 * np.arccos(np.clip(self.w, -1.0, 1.0)))

    @property
    def axis(self) -> FloatArray3:
        """Return the rotation axis as a unit vector (for unit quaternions).

        Returns the zero vector for the identity quaternion.
        """
        vect = np.array([self.x, self.y, self.z])
        norm = np.linalg.norm(vect)
        if norm < 1e-10:
            return np.array([0.0, 0.0, 1.0])  # Default axis for identity
        return vect / norm

    @property
    def vector_spherical(self) -> tuple[float, float]:
        """
        Return the quaternion's pointing direction in spherical coordinates
        (ISO physics convention).

        The quaternion is applied to a reference direction (+X axis) to get the
        pointing direction, which is then converted to spherical coordinates.

        Returns:
            tuple[azimuth, polar] where:
                - azimuth (φ): angle in xy-plane from +x axis, range (-π, π]
                - polar (θ): angle from +z axis (colatitude), range [0, π]

        Notes:
            Reference direction is +X axis: [1, 0, 0]
            - Identity quaternion (1,0,0,0) points to +X: azimuth=0, polar=π/2
        """
        # Reference direction: positive X-axis
        reference_direction = np.array([1.0, 0.0, 0.0])

        # Apply quaternion rotation to the reference direction
        rotated_vector = self.rotate_vector(reference_direction)

        # Normalize to ensure it's a unit vector
        x, y, z = rotated_vector
        r = np.sqrt(x**2 + y**2 + z**2)
        if r > 1e-10:
            x, y, z = x / r, y / r, z / r

        # Convert to spherical coordinates (physics convention)
        polar = float(np.arccos(np.clip(z, -1, 1)))  # colatitude (0 to π)
        azimuth = float(np.arctan2(y, x))  # azimuth (-π to π)

        return (azimuth, polar)

    @property
    def vector_cartesian(self) -> tuple[float, float, float]:
        """Return the quaternion's pointing direction as a cartesian unit vector.

        The quaternion is applied to a reference direction (+X axis) to get the
        pointing direction as a unit vector in cartesian coordinates.

        Returns:
            tuple[x, y, z] - unit vector components

        Notes:
            Reference direction is +X axis: [1, 0, 0]
            - Identity quaternion (1,0,0,0) points to +X: (1, 0, 0)
        """
        # Reference direction: positive X-axis
        reference_direction = np.array([1.0, 0.0, 0.0])

        # Apply quaternion rotation to the reference direction
        rotated_vector = self.rotate_vector(reference_direction)

        # Normalize to ensure it's a unit vector
        x, y, z = rotated_vector
        r = np.sqrt(x**2 + y**2 + z**2)
        if r > 1e-10:
            x, y, z = x / r, y / r, z / r

        return (float(x), float(y), float(z))

    # MARK: - Array Conversion Methods

    def as_float_array(self) -> FloatArray4:
        """View the quaternion as a float array [w, x, y, z].

        This function is fast because no data is copied; the returned
        quantity is just a "view" of the original.
        """
        return as_float_array(self.__q)

    def to_components(self) -> tuple[float, float, float, float]:
        """Return quaternion components as a tuple (w, x, y, z)."""
        return (self.w, self.x, self.y, self.z)

    # MARK: - Rotation Matrix Conversions

    def to_rotation_matrix(self) -> RotationMatrix:
        """Convert this quaternion to a 3x3 rotation matrix.

        For any quaternion q, this returns a matrix m such that, for every
        vector v, we have:
            m @ v.vec == q * v * q.conjugate()

        Returns:
            3x3 rotation matrix as a numpy array

        Raises:
            ZeroDivisionError: If this quaternion has zero norm
        """
        return as_rotation_matrix(self.__q)

    @classmethod
    def from_rotation_matrix(cls: type[T], matrix: RotationMatrix) -> T:
        """Create a quaternion from a 3x3 rotation matrix.

        Args:
            matrix: 3x3 rotation matrix. Should be orthogonal, but the
                   algorithm handles non-orthogonal matrices by finding
                   the closest orthogonal matrix.

        Returns:
            Unit quaternion representing the rotation

        Raises:
            ValueError: If matrix is not 3x3
        """
        q = from_rotation_matrix(matrix)
        return cls(q)

    # MARK: - Rotation Vector (Axis-Angle) Conversions

    def to_rotation_vector(self) -> FloatArray3:
        """Convert this quaternion to axis-angle representation.

        Returns a vector whose direction is the rotation axis and whose
        magnitude is the rotation angle in radians.

        Returns:
            3-element array representing axis-angle rotation
        """
        return as_rotation_vector(self.__q)

    @classmethod
    def from_rotation_vector(cls: type[T], rotation_vector: FloatArray3) -> T:
        """Create a quaternion from axis-angle representation.

        Args:
            rotation_vector: 3-element vector where the direction is the
                           rotation axis and the magnitude is the angle
                           in radians.

        Returns:
            Unit quaternion representing the rotation
        """
        q = from_rotation_vector(rotation_vector)
        return cls(q)

    # MARK: - Euler Angle Conversions

    def to_euler_angles(self) -> FloatArray3:
        """Convert this quaternion to Euler angles (alpha, beta, gamma).

        WARNING: Euler angles are problematic and should be avoided when
        possible. Use quaternions or rotation matrices instead.

        Assumes the Euler angles correspond to the quaternion R via:
            R = exp(alpha*z/2) * exp(beta*y/2) * exp(gamma*z/2)

        Returns:
            Array of (alpha, beta, gamma) in radians
        """
        return as_euler_angles(self.__q)

    @classmethod
    def from_euler_angles(
        cls: type[T],
        alpha: float,
        beta: float,
        gamma: float,
    ) -> T:
        """Create a quaternion from Euler angles.

        WARNING: Euler angles are problematic and should be avoided when
        possible. Use quaternions or rotation matrices instead.

        Assumes the Euler angles correspond to the quaternion R via:
            R = exp(alpha*z/2) * exp(beta*y/2) * exp(gamma*z/2)

        Args:
            alpha: First Euler angle (radians)
            beta: Second Euler angle (radians)
            gamma: Third Euler angle (radians)

        Returns:
            Quaternion representing the rotation
        """
        q = from_euler_angles(alpha, beta, gamma)
        return cls(q)

    # MARK: - Vector Part Operations

    @classmethod
    def from_vector_part(cls: type[T], vector: FloatArray3) -> T:
        """Create a quaternion from a 3D vector (pure quaternion).

        This creates a quaternion with w=0 and vector part equal to the input.

        Args:
            vector: 3-element array representing the vector part

        Returns:
            Pure quaternion (w=0)
        """
        q = from_vector_part(vector)
        return cls(q)

    def to_vector_part(self) -> FloatArray3:
        """Extract the vector (imaginary) part as a 3D array.

        Returns:
            3-element array [x, y, z]
        """
        return as_vector_part(self.__q)

    def rotate_vector(self, vector: FloatArray3) -> FloatArray3:
        """Rotate a 3D vector by this quaternion.

        This computes: q * v * q.conjugate()
        where v is treated as a pure quaternion (w=0).

        Args:
            vector: 3-element vector to rotate

        Returns:
            Rotated 3-element vector
        """
        return rotate_vectors(self.__q, vector)

    # MARK: - Interpolation Methods

    def slerp(self, other: Quaternion, t: float) -> Quaternion:
        """Spherical linear interpolation between this and another quaternion.

        Uses the numpy-quaternions implementation for robust and efficient SLERP.

        Args:
            other: Target quaternion
            t: Interpolation parameter in [0, 1], where 0 returns self
               and 1 returns other

        Returns:
            Interpolated quaternion
        """
        # Use the package's slerp with t1=0.0, t2=1.0 for normalized interpolation
        result = quat_slerp(self.__q, other.q, 0.0, 1.0, t)
        return Quaternion(result)

    # MARK: - Comparison Utilities

    def isclose(
        self,
        other: Quaternion,
        rtol: float = 1e-9,
        atol: float = 1e-11,
    ) -> bool:
        """Check if this quaternion is close to another within a tolerance.

        This method accounts for the double cover property of quaternions:
        q and -q represent the same rotation, so both are checked.

        Args:
            other: Quaternion to compare with
            rtol: Relative tolerance (default: 1e-9)
            atol: Absolute tolerance (default: 1e-11)

        Returns:
            True if quaternions are close within tolerance (accounting for double cover)
        """
        # Check both q and -q due to double cover
        return bool(
            quat_isclose(self.__q, other.q, rtol=rtol, atol=atol)
            or quat_isclose(self.__q, -other.q, rtol=rtol, atol=atol)
        )

    @staticmethod
    def allclose(
        q1: Quaternion,
        q2: Quaternion,
        rtol: float = 1e-9,
        atol: float = 1e-11,
    ) -> bool:
        """Check if two quaternions are close within a tolerance.

        This method accounts for the double cover property of quaternions:
        q and -q represent the same rotation, so both are checked.

        Args:
            q1: First quaternion
            q2: Second quaternion
            rtol: Relative tolerance (default: 1e-9)
            atol: Absolute tolerance (default: 1e-11)

        Returns:
            True if quaternions are close within tolerance (accounting for double cover)
        """
        # Check both q2 and -q2 due to double cover
        return bool(
            quat_allclose(q1.q, q2.q, rtol=rtol, atol=atol)
            or quat_allclose(q1.q, -q2.q, rtol=rtol, atol=atol)
        )

    # MARK: - Special Constructors

    @classmethod
    def identity(cls: type[T]) -> T:
        """Create an identity quaternion (no rotation).

        Returns:
            Quaternion(1, 0, 0, 0)
        """
        return cls.from_components(w=1.0, x=0.0, y=0.0, z=0.0)

    @classmethod
    def from_axis_angle(cls: type[T], axis: FloatArray3, angle: float) -> T:
        """Create a quaternion from a rotation axis and angle.

        Args:
            axis: 3D rotation axis (will be normalized)
            angle: Rotation angle in radians

        Returns:
            Unit quaternion representing the rotation
        """
        axis_normalized = axis / np.linalg.norm(axis)
        half_angle = angle / 2.0
        sin_half = np.sin(half_angle)
        return cls.from_components(
            w=np.cos(half_angle),
            x=axis_normalized[0] * sin_half,
            y=axis_normalized[1] * sin_half,
            z=axis_normalized[2] * sin_half,
        )

    @classmethod
    def _from_unit_direction_to_vector(
        cls: type[T],
        start_direction: FloatArray3,
        target_vector: FloatArray3,
        perpendicular_axis: FloatArray3,
    ) -> T:
        """Helper method to create a quaternion rotating from a unit direction to target.

        Args:
            start_direction: Starting unit direction vector
            target_vector: Target direction vector (will be normalized)
            perpendicular_axis: Axis to use for 180° rotation case

        Returns:
            Unit quaternion representing the rotation
        """
        # Normalize target vector
        target = np.array(target_vector, dtype=float)
        target_norm = np.linalg.norm(target)
        if target_norm < 1e-10:
            # Zero vector, return identity
            return cls.identity()
        target = target / target_norm

        # Compute dot product
        dot = np.dot(start_direction, target)

        # Check for special cases
        if dot > 0.9999:
            # Vectors are parallel (same direction)
            return cls.identity()
        elif dot < -0.9999:
            # Vectors are opposite (180° rotation needed)
            # Use the provided perpendicular axis
            perp = np.array(perpendicular_axis, dtype=float)
            perp = perp / np.linalg.norm(perp)
            return cls.from_components(w=0.0, x=perp[0], y=perp[1], z=perp[2])

        # General case: compute rotation axis and angle
        # Rotation axis is perpendicular to both vectors
        axis = np.cross(start_direction, target)
        axis = axis / np.linalg.norm(axis)

        # Compute rotation angle
        angle = np.arccos(np.clip(dot, -1.0, 1.0))

        # Create quaternion from axis-angle
        return cls.from_axis_angle(axis, angle)

    @classmethod
    def from_unit_x_to_vector(cls: type[T], target_vector: FloatArray3) -> T:
        """Create a quaternion that rotates the +X axis to point toward target_vector.

        This constructor computes the rotation that transforms the unit X direction
        [1, 0, 0] to align with the given target vector.

        Args:
            target_vector: Target direction vector (will be normalized)

        Returns:
            Unit quaternion representing the rotation from +X to target_vector

        Notes:
            - If target_vector points in +X direction, returns identity quaternion
            - If target_vector points in -X direction, returns 180° rotation about +Z axis
            - For all other directions, uses the shortest rotation path

        Examples:
            >>> # Rotate +X to point toward +Y
            >>> q = Quaternion.from_unit_x_to_vector([0, 1, 0])
            >>> # Rotate +X to point toward +Z
            >>> q = Quaternion.from_unit_x_to_vector([0, 0, 1])
        """
        start = np.array([1.0, 0.0, 0.0])
        perpendicular = np.array([0.0, 0.0, 1.0])  # +Z for 180° case
        return cls._from_unit_direction_to_vector(start, target_vector, perpendicular)

    @classmethod
    def from_unit_y_to_vector(cls: type[T], target_vector: FloatArray3) -> T:
        """Create a quaternion that rotates the +Y axis to point toward target_vector.

        This constructor computes the rotation that transforms the unit Y direction
        [0, 1, 0] to align with the given target vector.

        Args:
            target_vector: Target direction vector (will be normalized)

        Returns:
            Unit quaternion representing the rotation from +Y to target_vector

        Notes:
            - If target_vector points in +Y direction, returns identity quaternion
            - If target_vector points in -Y direction, returns 180° rotation about +Z axis
            - For all other directions, uses the shortest rotation path

        Examples:
            >>> # Rotate +Y to point toward +X
            >>> q = Quaternion.from_unit_y_to_vector([1, 0, 0])
            >>> # Rotate +Y to point toward +Z
            >>> q = Quaternion.from_unit_y_to_vector([0, 0, 1])
        """
        start = np.array([0.0, 1.0, 0.0])
        perpendicular = np.array([0.0, 0.0, 1.0])  # +Z for 180° case
        return cls._from_unit_direction_to_vector(start, target_vector, perpendicular)

    @classmethod
    def from_unit_z_to_vector(cls: type[T], target_vector: FloatArray3) -> T:
        """Create a quaternion that rotates the +Z axis to point toward target_vector.

        This constructor computes the rotation that transforms the unit Z direction
        [0, 0, 1] to align with the given target vector.

        Args:
            target_vector: Target direction vector (will be normalized)

        Returns:
            Unit quaternion representing the rotation from +Z to target_vector

        Notes:
            - If target_vector points in +Z direction, returns identity quaternion
            - If target_vector points in -Z direction, returns 180° rotation about +X axis
            - For all other directions, uses the shortest rotation path

        Examples:
            >>> # Rotate +Z to point toward +X
            >>> q = Quaternion.from_unit_z_to_vector([1, 0, 0])
            >>> # Rotate +Z to point toward +Y
            >>> q = Quaternion.from_unit_z_to_vector([0, 1, 0])
        """
        start = np.array([0.0, 0.0, 1.0])
        perpendicular = np.array([1.0, 0.0, 0.0])  # +X for 180° case
        return cls._from_unit_direction_to_vector(start, target_vector, perpendicular)

    @classmethod
    def from_dict(cls, obj: Any) -> Quaternion:
        """Create a quaternion instance from a dictionary representation.

        Args:
            obj: Dictionary containing 'w', 'x', 'y', 'z' keys

        Returns:
            A concrete Quaternion instance of the calling class type
        """
        w = from_float(obj.get("w"))
        x = from_float(obj.get("x"))
        y = from_float(obj.get("y"))
        z = from_float(obj.get("z"))
        # Note: This calls the concrete implementation's from_components
        # cls ensures the correct subclass type is returned
        return cls.from_components(w, x, y, z)

    def to_unitSphericalSmallCircle(
        q: Quaternion, radius_angle: float = np.pi / 4
    ) -> UnitSphericalSmallCircleType:
        """ """
        a, p = q.vector_spherical
        return UnitSphericalSmallCircleType(azimuth=a, polar=p, radius_angle=radius_angle)
