"""
Comprehensive unit tests for the Quaternion class using unittest.

Tests cover:
- Construction methods
- Properties and attributes
- Arithmetic operations
- Comparison operations
- Unary operations
- Rotation conversions
- Vector operations
- Interpolation (SLERP)
"""

import unittest

import numpy as np
from numpy.testing import assert_allclose, assert_array_almost_equal

from math_tools.spatial.quaternion import Quaternion


class TestQuaternionConstruction(unittest.TestCase):
    """Test various construction methods for Quaternion."""

    def test_from_components_identity(self) -> None:
        """Test creating identity quaternion from components."""
        q = Quaternion.from_components(1, 0, 0, 0)
        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 0.0)
        self.assertEqual(q.y, 0.0)
        self.assertEqual(q.z, 0.0)

    def test_from_components_general(self) -> None:
        """Test creating general quaternion from components."""
        q = Quaternion.from_components(0.7071, 0.0, 0.0, 0.7071)
        assert_allclose(q.w, 0.7071, rtol=1e-4)
        assert_allclose(q.x, 0.0, atol=1e-10)
        assert_allclose(q.y, 0.0, atol=1e-10)
        assert_allclose(q.z, 0.7071, rtol=1e-4)

    def test_from_components_default(self) -> None:
        """Test default values in from_components."""
        q = Quaternion.from_components()
        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 0.0)
        self.assertEqual(q.y, 0.0)
        self.assertEqual(q.z, 0.0)

    def test_identity(self) -> None:
        """Test identity quaternion constructor."""
        q = Quaternion.identity()
        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 0.0)
        self.assertEqual(q.y, 0.0)
        self.assertEqual(q.z, 0.0)
        self.assertTrue(q.is_unit)

    def test_from_axis_angle_z_90(self) -> None:
        """Test construction from axis-angle (90° around Z)."""
        axis = np.array([0, 0, 1])
        angle = np.pi / 2
        q = Quaternion.from_axis_angle(axis, angle)

        assert_allclose(q.w, np.cos(np.pi / 4), rtol=1e-10)
        assert_allclose(q.x, 0.0, atol=1e-10)
        assert_allclose(q.y, 0.0, atol=1e-10)
        assert_allclose(q.z, np.sin(np.pi / 4), rtol=1e-10)

    def test_from_axis_angle_x_180(self) -> None:
        """Test construction from axis-angle (180° around X)."""
        axis = np.array([1, 0, 0])
        angle = np.pi
        q = Quaternion.from_axis_angle(axis, angle)

        assert_allclose(q.w, 0.0, atol=1e-10)
        assert_allclose(q.x, 1.0, rtol=1e-10)
        assert_allclose(q.y, 0.0, atol=1e-10)
        assert_allclose(q.z, 0.0, atol=1e-10)

    def test_from_axis_angle_unnormalized(self) -> None:
        """Test that axis gets normalized automatically."""
        axis = np.array([2, 0, 0])  # Not normalized
        angle = np.pi / 2
        q = Quaternion.from_axis_angle(axis, angle)

        # Should be same as normalized axis
        self.assertTrue(q.is_unit)

    def test_from_vector_part(self) -> None:
        """Test creating pure quaternion from vector."""
        vec = np.array([1.0, 2.0, 3.0])
        q = Quaternion.from_vector_part(vec)

        self.assertEqual(q.w, 0.0)
        self.assertEqual(q.x, 1.0)
        self.assertEqual(q.y, 2.0)
        self.assertEqual(q.z, 3.0)


class TestQuaternionProperties(unittest.TestCase):
    """Test quaternion properties and attributes."""

    def test_norm_identity(self) -> None:
        """Test norm of identity quaternion."""
        q = Quaternion.identity()
        assert_allclose(q.norm, 1.0)

    def test_norm_general(self) -> None:
        """Test norm of general quaternion."""
        q = Quaternion.from_components(1, 2, 3, 4)
        expected_norm = np.sqrt(1 + 4 + 9 + 16)
        assert_allclose(q.norm, expected_norm)

    def test_is_unit_true(self) -> None:
        """Test is_unit for unit quaternion."""
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        self.assertTrue(q.is_unit)

    def test_is_unit_false(self) -> None:
        """Test is_unit for non-unit quaternion."""
        q = Quaternion.from_components(1, 1, 1, 1)
        self.assertFalse(q.is_unit)

    def test_angle_identity(self) -> None:
        """Test angle of identity quaternion."""
        q = Quaternion.identity()
        assert_allclose(q.angle, 0.0, atol=1e-10)

    def test_angle_90_degrees(self) -> None:
        """Test angle extraction for 90° rotation."""
        q = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi / 2)
        assert_allclose(q.angle, np.pi / 2, rtol=1e-10)

    def test_angle_180_degrees(self) -> None:
        """Test angle extraction for 180° rotation."""
        q = Quaternion.from_axis_angle(np.array([0, 1, 0]), np.pi)
        assert_allclose(q.angle, np.pi, rtol=1e-10)

    def test_axis_z(self) -> None:
        """Test axis extraction for Z-axis rotation."""
        axis = np.array([0, 0, 1])
        q = Quaternion.from_axis_angle(axis, np.pi / 2)
        assert_array_almost_equal(q.axis, axis, decimal=10)

    def test_axis_general(self) -> None:
        """Test axis extraction for general rotation."""
        axis = np.array([1, 1, 1]) / np.sqrt(3)
        q = Quaternion.from_axis_angle(axis, np.pi / 4)
        assert_array_almost_equal(q.axis, axis, decimal=10)

    def test_axis_identity(self) -> None:
        """Test axis for identity quaternion (defaults to Z)."""
        q = Quaternion.identity()
        # Identity should return default axis
        self.assertEqual(q.axis.shape, (3,))

    def test_to_components(self) -> None:
        """Test components tuple extraction."""
        q = Quaternion.from_components(1, 2, 3, 4)
        w, x, y, z = q.to_components()
        self.assertEqual(w, 1.0)
        self.assertEqual(x, 2.0)
        self.assertEqual(y, 3.0)
        self.assertEqual(z, 4.0)


class TestQuaternionArithmetic(unittest.TestCase):
    """Test arithmetic operations on quaternions."""

    def test_add_quaternions(self) -> None:
        """Test quaternion addition."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = Quaternion.from_components(5, 6, 7, 8)
        q3 = q1 + q2

        self.assertEqual(q3.w, 6.0)
        self.assertEqual(q3.x, 8.0)
        self.assertEqual(q3.y, 10.0)
        self.assertEqual(q3.z, 12.0)

    def test_add_scalar(self) -> None:
        """Test adding scalar to quaternion."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = q1 + 5

        self.assertEqual(q2.w, 6.0)
        self.assertEqual(q2.x, 2.0)
        self.assertEqual(q2.y, 3.0)
        self.assertEqual(q2.z, 4.0)

    def test_radd_scalar(self) -> None:
        """Test right addition with scalar."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = 5 + q1

        self.assertEqual(q2.w, 6.0)
        self.assertEqual(q2.x, 2.0)
        self.assertEqual(q2.y, 3.0)
        self.assertEqual(q2.z, 4.0)

    def test_subtract_quaternions(self) -> None:
        """Test quaternion subtraction."""
        q1 = Quaternion.from_components(5, 6, 7, 8)
        q2 = Quaternion.from_components(1, 2, 3, 4)
        q3 = q1 - q2

        self.assertEqual(q3.w, 4.0)
        self.assertEqual(q3.x, 4.0)
        self.assertEqual(q3.y, 4.0)
        self.assertEqual(q3.z, 4.0)

    def test_multiply_quaternions(self) -> None:
        """Test quaternion multiplication (Hamilton product)."""
        # 90° rotation around Z followed by 90° rotation around X
        q1 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        q2 = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi / 2)
        q3 = q1 * q2

        # Result should be a valid rotation
        self.assertTrue(q3.is_unit)

    def test_multiply_scalar(self) -> None:
        """Test multiplying quaternion by scalar."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = q1 * 2

        self.assertEqual(q2.w, 2.0)
        self.assertEqual(q2.x, 4.0)
        self.assertEqual(q2.y, 6.0)
        self.assertEqual(q2.z, 8.0)

    def test_divide_quaternions(self) -> None:
        """Test quaternion division."""
        q1 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 4)
        q3 = q1 / q2

        # Should give approximately pi/4 rotation around Z
        self.assertTrue(q3.is_unit)
        assert_allclose(q3.angle, np.pi / 4, rtol=1e-10)

    def test_divide_scalar(self) -> None:
        """Test dividing quaternion by scalar."""
        q1 = Quaternion.from_components(2, 4, 6, 8)
        q2 = q1 / 2

        self.assertEqual(q2.w, 1.0)
        self.assertEqual(q2.x, 2.0)
        self.assertEqual(q2.y, 3.0)
        self.assertEqual(q2.z, 4.0)

    def test_power(self) -> None:
        """Test quaternion power operation."""
        q1 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        q2 = q1**2

        # (90° rotation)^2 should be 180° rotation
        assert_allclose(q2.angle, np.pi, rtol=1e-10)

    def test_negate(self) -> None:
        """Test quaternion negation."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = -q1

        self.assertEqual(q2.w, -1.0)
        self.assertEqual(q2.x, -2.0)
        self.assertEqual(q2.y, -3.0)
        self.assertEqual(q2.z, -4.0)

    def test_positive(self) -> None:
        """Test unary positive."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = +q1

        self.assertEqual(q2.w, 1.0)
        self.assertEqual(q2.x, 2.0)
        self.assertEqual(q2.y, 3.0)
        self.assertEqual(q2.z, 4.0)

    def test_abs(self) -> None:
        """Test absolute value (norm)."""
        q = Quaternion.from_components(1, 2, 3, 4)
        expected_norm = np.sqrt(30)
        assert_allclose(abs(q), expected_norm)


class TestQuaternionComparison(unittest.TestCase):
    """Test comparison operations."""

    def test_equality_same(self) -> None:
        """Test equality for identical quaternions."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = Quaternion.from_components(1, 2, 3, 4)
        self.assertEqual(q1, q2)

    def test_equality_different(self) -> None:
        """Test equality for different quaternions."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = Quaternion.from_components(1, 2, 3, 5)
        self.assertNotEqual(q1, q2)

    def test_inequality(self) -> None:
        """Test inequality operator."""
        q1 = Quaternion.from_components(1, 2, 3, 4)
        q2 = Quaternion.from_components(1, 2, 3, 5)
        self.assertNotEqual(q1, q2)

    def test_isclose_true(self) -> None:
        """Test isclose for nearly equal quaternions."""
        q1 = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        q2 = Quaternion.from_components(1.0 + 1e-10, 2.0, 3.0, 4.0)
        self.assertTrue(q1.isclose(q2))

    def test_isclose_false(self) -> None:
        """Test isclose for different quaternions."""
        q1 = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        q2 = Quaternion.from_components(1.1, 2.0, 3.0, 4.0)
        self.assertFalse(q1.isclose(q2))

    def test_allclose_true(self) -> None:
        """Test static allclose method."""
        q1 = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        q2 = Quaternion.from_components(1.0 + 1e-10, 2.0, 3.0, 4.0)
        self.assertTrue(Quaternion.allclose(q1, q2))

    def test_repr(self) -> None:
        """Test __repr__ output."""
        q = Quaternion.from_components(1, 2, 3, 4)
        repr_str = repr(q)
        self.assertIn("Quaternion", repr_str)
        self.assertIn("w=1", repr_str)
        self.assertIn("x=2", repr_str)

    def test_str(self) -> None:
        """Test __str__ output."""
        q = Quaternion.from_components(1, 2, 3, 4)
        str_repr = str(q)
        self.assertIn("quaternion", str_repr)


class TestQuaternionUnaryOperations(unittest.TestCase):
    """Test unary operations on quaternions."""

    def test_conjugate(self) -> None:
        """Test quaternion conjugate."""
        q = Quaternion.from_components(1, 2, 3, 4)
        q_conj = q.conjugate()

        self.assertEqual(q_conj.w, 1.0)
        self.assertEqual(q_conj.x, -2.0)
        self.assertEqual(q_conj.y, -3.0)
        self.assertEqual(q_conj.z, -4.0)

    def test_conjugate_identity(self) -> None:
        """Test conjugate of identity."""
        q = Quaternion.identity()
        q_conj = q.conjugate()
        self.assertEqual(q, q_conj)

    def test_inverse_unit(self) -> None:
        """Test inverse of unit quaternion."""
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        q_inv = q.inverse()

        # For unit quaternions, inverse equals conjugate
        self.assertTrue(q_inv.isclose(q.conjugate()))

    def test_inverse_times_quaternion(self) -> None:
        """Test that q * q^-1 = identity."""
        q = Quaternion.from_components(1, 2, 3, 4)
        q_inv = q.inverse()
        result = q * q_inv

        # Should be close to identity
        identity = Quaternion.identity()
        self.assertTrue(result.isclose(identity, atol=1e-10))

    def test_normalized_general(self) -> None:
        """Test normalization of general quaternion."""
        q = Quaternion.from_components(1, 2, 3, 4)
        q_norm = q.normalized()

        self.assertTrue(q_norm.is_unit)
        assert_allclose(q_norm.norm, 1.0)

    def test_normalized_already_unit(self) -> None:
        """Test normalizing already unit quaternion."""
        q = Quaternion.identity()
        q_norm = q.normalized()

        self.assertTrue(q.isclose(q_norm))


class TestRotationMatrixConversions(unittest.TestCase):
    """Test conversions to/from rotation matrices."""

    def test_to_rotation_matrix_identity(self) -> None:
        """Test identity quaternion to rotation matrix."""
        q = Quaternion.identity()
        matrix = q.to_rotation_matrix()

        expected = np.eye(3)
        assert_array_almost_equal(matrix, expected, decimal=10)

    def test_to_rotation_matrix_90z(self) -> None:
        """Test 90° Z rotation to matrix."""
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        matrix = q.to_rotation_matrix()

        # 90° Z rotation matrix
        expected = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        assert_array_almost_equal(matrix, expected, decimal=10)

    def test_to_rotation_matrix_180x(self) -> None:
        """Test 180° X rotation to matrix."""
        q = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi)
        matrix = q.to_rotation_matrix()

        # 180° X rotation matrix
        expected = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
        assert_array_almost_equal(matrix, expected, decimal=10)

    def test_from_rotation_matrix_identity(self) -> None:
        """Test creating quaternion from identity matrix."""
        matrix = np.eye(3)
        q = Quaternion.from_rotation_matrix(matrix)

        self.assertTrue(q.isclose(Quaternion.identity()))

    def test_from_rotation_matrix_90z(self) -> None:
        """Test creating quaternion from 90° Z rotation matrix."""
        matrix = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        q = Quaternion.from_rotation_matrix(matrix)

        expected = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        self.assertTrue(q.isclose(expected))

    def test_roundtrip_matrix_conversion(self) -> None:
        """Test quaternion -> matrix -> quaternion roundtrip."""
        q_original = Quaternion.from_axis_angle(np.array([1, 1, 1]) / np.sqrt(3), np.pi / 3)
        matrix = q_original.to_rotation_matrix()
        q_recovered = Quaternion.from_rotation_matrix(matrix)

        # Should be close (up to sign ambiguity)
        self.assertTrue(q_recovered.isclose(q_original) or q_recovered.isclose(-q_original))


class TestRotationVectorConversions(unittest.TestCase):
    """Test conversions to/from rotation vectors (axis-angle)."""

    def test_to_rotation_vector_identity(self) -> None:
        """Test identity quaternion to rotation vector."""
        q = Quaternion.identity()
        vec = q.to_rotation_vector()

        assert_array_almost_equal(vec, np.zeros(3), decimal=10)

    def test_to_rotation_vector_90z(self) -> None:
        """Test 90° Z rotation to rotation vector."""
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        vec = q.to_rotation_vector()

        expected = np.array([0, 0, np.pi / 2])
        assert_array_almost_equal(vec, expected, decimal=10)

    def test_from_rotation_vector_identity(self) -> None:
        """Test creating quaternion from zero rotation vector."""
        vec = np.zeros(3)
        q = Quaternion.from_rotation_vector(vec)

        self.assertTrue(q.isclose(Quaternion.identity()))

    def test_from_rotation_vector_general(self) -> None:
        """Test creating quaternion from rotation vector."""
        vec = np.array([0, np.pi / 2, 0])  # 90° around Y
        q = Quaternion.from_rotation_vector(vec)

        expected = Quaternion.from_axis_angle(np.array([0, 1, 0]), np.pi / 2)
        self.assertTrue(q.isclose(expected))

    def test_roundtrip_rotation_vector(self) -> None:
        """Test quaternion -> rotation vector -> quaternion roundtrip."""
        q_original = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi / 4)
        vec = q_original.to_rotation_vector()
        q_recovered = Quaternion.from_rotation_vector(vec)

        self.assertTrue(q_recovered.isclose(q_original))


class TestEulerAngleConversions(unittest.TestCase):
    """Test conversions to/from Euler angles."""

    def test_to_euler_angles_identity(self) -> None:
        """Test identity quaternion to Euler angles."""
        q = Quaternion.identity()
        euler = q.to_euler_angles()

        # Identity should give zero or small angles
        self.assertEqual(euler.shape, (3,))

    def test_from_euler_angles_zeros(self) -> None:
        """Test creating quaternion from zero Euler angles."""
        q = Quaternion.from_euler_angles(0, 0, 0)

        self.assertTrue(q.isclose(Quaternion.identity()))

    def test_roundtrip_euler_angles(self) -> None:
        """Test quaternion -> Euler -> quaternion roundtrip."""
        q_original = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        euler = q_original.to_euler_angles()
        q_recovered = Quaternion.from_euler_angles(euler[0], euler[1], euler[2])

        # Should be close (Euler angles have ambiguities)
        self.assertTrue(q_recovered.isclose(q_original) or q_recovered.isclose(-q_original))


class TestVectorOperations(unittest.TestCase):
    """Test vector-related operations."""

    def test_to_vector_part(self) -> None:
        """Test extracting vector part."""
        q = Quaternion.from_components(1, 2, 3, 4)
        vec = q.to_vector_part()

        assert_array_almost_equal(vec, np.array([2, 3, 4]))

    def test_rotate_vector_identity(self) -> None:
        """Test rotating vector with identity quaternion."""
        q = Quaternion.identity()
        vec = np.array([1, 2, 3])
        rotated = q.rotate_vector(vec)

        assert_array_almost_equal(rotated, vec, decimal=10)

    def test_rotate_vector_90z(self) -> None:
        """Test rotating vector 90° around Z."""
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
        vec = np.array([1, 0, 0])
        rotated = q.rotate_vector(vec)

        expected = np.array([0, 1, 0])
        assert_array_almost_equal(rotated, expected, decimal=10)

    def test_rotate_vector_180x(self) -> None:
        """Test rotating vector 180° around X."""
        q = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi)
        vec = np.array([0, 1, 0])
        rotated = q.rotate_vector(vec)

        expected = np.array([0, -1, 0])
        assert_array_almost_equal(rotated, expected, decimal=10)

    def test_rotate_vector_general(self) -> None:
        """Test general vector rotation."""
        q = Quaternion.from_axis_angle(np.array([1, 1, 1]) / np.sqrt(3), 2 * np.pi / 3)
        vec = np.array([1, 0, 0])
        rotated = q.rotate_vector(vec)

        # 120° rotation around (1,1,1) should permute coordinates
        expected = np.array([0, 1, 0])
        assert_array_almost_equal(rotated, expected, decimal=8)


class TestSLERP(unittest.TestCase):
    """Test spherical linear interpolation."""

    def test_slerp_endpoints(self) -> None:
        """Test SLERP at endpoints."""
        q1 = Quaternion.identity()
        q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)

        # At t=0, should get q1
        q_start = q1.slerp(q2, 0.0)
        self.assertTrue(q_start.isclose(q1))

        # At t=1, should get q2
        q_end = q1.slerp(q2, 1.0)
        self.assertTrue(q_end.isclose(q2))

    def test_slerp_midpoint(self) -> None:
        """Test SLERP at midpoint."""
        q1 = Quaternion.identity()
        q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)

        q_mid = q1.slerp(q2, 0.5)

        # At t=0.5, should be 45° rotation
        expected = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 4)
        self.assertTrue(q_mid.isclose(expected))

    def test_slerp_unit_preservation(self) -> None:
        """Test that SLERP preserves unit norm."""
        q1 = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi / 4)
        q2 = Quaternion.from_axis_angle(np.array([0, 1, 0]), np.pi / 3)

        for t in np.linspace(0, 1, 10):
            q_interp = q1.slerp(q2, t)
            self.assertTrue(q_interp.is_unit)

    def test_slerp_smooth_interpolation(self) -> None:
        """Test that SLERP produces smooth interpolation."""
        q1 = Quaternion.identity()
        q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi)

        angles = []
        for t in np.linspace(0, 1, 11):
            q_interp = q1.slerp(q2, t)
            angles.append(q_interp.angle)

        # Angles should increase monotonically
        for i in range(len(angles) - 1):
            self.assertLessEqual(angles[i], angles[i + 1])

    def test_slerp_opposite_quaternions(self) -> None:
        """Test SLERP between opposite quaternions."""
        q1 = Quaternion.from_axis_angle(np.array([0, 0, 1]), 0)
        q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi)

        q_mid = q1.slerp(q2, 0.5)

        # Should interpolate correctly
        assert_allclose(q_mid.angle, np.pi / 2, rtol=1e-10)


class TestArrayConversions(unittest.TestCase):
    """Test array conversion methods."""

    def test_as_float_array(self) -> None:
        """Test conversion to float array."""
        q = Quaternion.from_components(1, 2, 3, 4)
        arr = q.as_float_array()

        expected = np.array([1, 2, 3, 4])
        assert_array_almost_equal(arr, expected)

    def test_as_float_array_shape(self) -> None:
        """Test shape of float array."""
        q = Quaternion.from_components(1, 2, 3, 4)
        arr = q.as_float_array()

        self.assertEqual(arr.shape, (4,))


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and special scenarios."""

    def test_very_small_rotation(self) -> None:
        """Test very small rotation angle."""
        q = Quaternion.from_axis_angle(np.array([1, 0, 0]), 1e-10)

        self.assertTrue(q.isclose(Quaternion.identity()))

    def test_very_large_angle(self) -> None:
        """Test angle larger than 2π."""
        # Should wrap around
        q = Quaternion.from_axis_angle(np.array([0, 0, 1]), 3 * np.pi)

        # 3π should be equivalent to π rotation
        expected = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi)
        self.assertTrue(q.isclose(expected) or q.isclose(-expected))

    def test_zero_norm_handling(self) -> None:
        """Test that operations handle near-zero quaternions appropriately."""
        # This would be an invalid quaternion, but we test defensive handling
        # Note: actual zero quaternion would cause division by zero in some operations
        q = Quaternion.from_components(1e-15, 1e-15, 1e-15, 1e-15)

        # Should still be able to normalize
        q_norm = q.normalized()
        self.assertTrue(q_norm.is_unit)


class TestQuaternionSerialization(unittest.TestCase):
    """Test serialization/deserialization methods and QuaternionABC inheritance."""

    def test_to_dict_identity(self) -> None:
        """Test to_dict for identity quaternion."""
        q = Quaternion.identity()
        d = q.to_dict()

        self.assertIsInstance(d, dict)
        self.assertIn("w", d)
        self.assertIn("x", d)
        self.assertIn("y", d)
        self.assertIn("z", d)
        self.assertEqual(d["w"], 1.0)
        self.assertEqual(d["x"], 0.0)
        self.assertEqual(d["y"], 0.0)
        self.assertEqual(d["z"], 0.0)

    def test_to_dict_general(self) -> None:
        """Test to_dict for general quaternion."""
        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        d = q.to_dict()

        self.assertEqual(d["w"], 1.0)
        self.assertEqual(d["x"], 2.0)
        self.assertEqual(d["y"], 3.0)
        self.assertEqual(d["z"], 4.0)

    def test_to_dict_normalized(self) -> None:
        """Test to_dict preserves values for normalized quaternion."""
        q = Quaternion.from_axis_angle(np.array([1, 0, 0]), np.pi / 2)
        d = q.to_dict()

        # Check that all components are present and are floats
        self.assertIsInstance(d["w"], float)
        self.assertIsInstance(d["x"], float)
        self.assertIsInstance(d["y"], float)
        self.assertIsInstance(d["z"], float)

        # Verify components match
        self.assertAlmostEqual(d["w"], q.w)
        self.assertAlmostEqual(d["x"], q.x)
        self.assertAlmostEqual(d["y"], q.y)
        self.assertAlmostEqual(d["z"], q.z)

    def test_from_dict_identity(self) -> None:
        """Test from_dict for identity quaternion."""
        d = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}
        q = Quaternion.from_dict(d)

        self.assertIsInstance(q, Quaternion)
        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 0.0)
        self.assertEqual(q.y, 0.0)
        self.assertEqual(q.z, 0.0)

    def test_from_dict_general(self) -> None:
        """Test from_dict for general quaternion."""
        d = {"w": 1.0, "x": 2.0, "y": 3.0, "z": 4.0}
        q = Quaternion.from_dict(d)

        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 2.0)
        self.assertEqual(q.y, 3.0)
        self.assertEqual(q.z, 4.0)

    def test_from_dict_with_integers(self) -> None:
        """Test from_dict accepts integer values."""
        d = {"w": 1, "x": 2, "y": 3, "z": 4}
        q = Quaternion.from_dict(d)

        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 2.0)
        self.assertEqual(q.y, 3.0)
        self.assertEqual(q.z, 4.0)

    def test_roundtrip_serialization_identity(self) -> None:
        """Test roundtrip: quaternion -> dict -> quaternion for identity."""
        q_original = Quaternion.identity()
        d = q_original.to_dict()
        q_recovered = Quaternion.from_dict(d)

        self.assertTrue(q_original.isclose(q_recovered))

    def test_roundtrip_serialization_general(self) -> None:
        """Test roundtrip: quaternion -> dict -> quaternion for general quaternion."""
        q_original = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        d = q_original.to_dict()
        q_recovered = Quaternion.from_dict(d)

        self.assertTrue(q_original.isclose(q_recovered))

    def test_roundtrip_serialization_rotation(self) -> None:
        """Test roundtrip for rotation quaternion."""
        q_original = Quaternion.from_axis_angle(np.array([1, 1, 1]) / np.sqrt(3), np.pi / 3)
        d = q_original.to_dict()
        q_recovered = Quaternion.from_dict(d)

        self.assertTrue(q_original.isclose(q_recovered))

    def test_roundtrip_with_negatives(self) -> None:
        """Test roundtrip with negative components."""
        q_original = Quaternion.from_components(-0.5, -0.5, 0.5, 0.5)
        d = q_original.to_dict()
        q_recovered = Quaternion.from_dict(d)

        self.assertEqual(q_recovered.w, -0.5)
        self.assertEqual(q_recovered.x, -0.5)
        self.assertEqual(q_recovered.y, 0.5)
        self.assertEqual(q_recovered.z, 0.5)

    def test_to_dict_returns_new_dict(self) -> None:
        """Test that to_dict returns a new dictionary each time."""
        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        d1 = q.to_dict()
        d2 = q.to_dict()

        self.assertIsNot(d1, d2)
        self.assertEqual(d1, d2)

    def test_dict_modification_doesnt_affect_quaternion(self) -> None:
        """Test that modifying the dict doesn't affect the quaternion."""
        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        d = q.to_dict()

        # Modify the dictionary
        d["w"] = 999.0
        d["x"] = 999.0

        # Original quaternion should be unchanged
        self.assertEqual(q.w, 1.0)
        self.assertEqual(q.x, 2.0)

    def test_structural_conformance_to_abc(self) -> None:
        """Quaternion structurally conforms to QuaternionABC.

        The Tier-2 ABC is a non-runtime_checkable ``typing.Protocol``, so
        conformance is verified by member presence rather than ``isinstance``.
        """
        from foundation_abc.math.spatialABCs import QuaternionABC

        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        for member in QuaternionABC.__abstractmethods__:
            self.assertTrue(hasattr(q, member), member)

    def test_conforms_to_abc_without_carrier_inheritance(self) -> None:
        """Quaternion conforms to QuaternionABC structurally and does not inherit
        the Tier-1 ``DataModelHelper`` carrier base (ABC-only conformance)."""
        from foundation_abc.math.spatialABCs import QuaternionABC

        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        for member in QuaternionABC.__abstractmethods__:
            self.assertTrue(hasattr(q, member), member)
        mro_names = {base.__name__ for base in type(q).__mro__}
        self.assertNotIn("DataModelHelper", mro_names)

    def test_has_serialization_methods(self) -> None:
        """Test that Quaternion has the required serialization methods."""
        q = Quaternion.identity()

        # Check methods exist
        self.assertTrue(hasattr(q, "to_dict"))
        self.assertTrue(hasattr(Quaternion, "from_dict"))

        # Check they're callable
        self.assertTrue(callable(q.to_dict))
        self.assertTrue(callable(Quaternion.from_dict))


if __name__ == "__main__":
    unittest.main()
