"""Unit tests for the chunk 07 ``Quaternion`` additions.

Covers spatialMath.md §Quaternion additions: ``dot``,
``rotation_matrix_elements``, ``rotate_position``, ``__array__``, and the
snake_case aliases ``from_numpy_quaternion`` / ``to_unit_spherical_small_circle``.

The existing ``tests/test_quaternion.py`` (~90 tests) is untouched by this
chunk; this file only exercises the additive surface.
"""

import unittest
from dataclasses import FrozenInstanceError

import numpy as np
from numpy.testing import assert_allclose

from math_tools.spatial.position import Position
from math_tools.spatial.quaternion import Quaternion, RotationMatrixElements


class TestDot(unittest.TestCase):
    def test_orthogonal_is_zero(self) -> None:
        q1 = Quaternion.from_components(1.0, 0.0, 0.0, 0.0)
        q2 = Quaternion.from_components(0.0, 1.0, 0.0, 0.0)
        self.assertEqual(q1.dot(q2), 0.0)

    def test_self_dot_is_norm_squared(self) -> None:
        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        assert_allclose(q.dot(q), q.norm**2, rtol=1e-12)

    def test_general_dot(self) -> None:
        q1 = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        q2 = Quaternion.from_components(5.0, 6.0, 7.0, 8.0)
        expected = 1.0 * 5.0 + 2.0 * 6.0 + 3.0 * 7.0 + 4.0 * 8.0
        assert_allclose(q1.dot(q2), expected, rtol=1e-12)


class TestRotationMatrixElements(unittest.TestCase):
    def test_matches_to_rotation_matrix(self) -> None:
        q = Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 3)
        matrix = q.to_rotation_matrix()
        elements = q.rotation_matrix_elements

        self.assertIsInstance(elements, RotationMatrixElements)
        assert_allclose(elements.xx, matrix[0, 0])
        assert_allclose(elements.xy, matrix[0, 1])
        assert_allclose(elements.xz, matrix[0, 2])
        assert_allclose(elements.yx, matrix[1, 0])
        assert_allclose(elements.yy, matrix[1, 1])
        assert_allclose(elements.yz, matrix[1, 2])
        assert_allclose(elements.zx, matrix[2, 0])
        assert_allclose(elements.zy, matrix[2, 1])
        assert_allclose(elements.zz, matrix[2, 2])

    def test_is_frozen(self) -> None:
        q = Quaternion.identity()
        elements = q.rotation_matrix_elements
        with self.assertRaises(FrozenInstanceError):
            elements.xx = 99.0  # type: ignore[misc]


class TestRotatePosition(unittest.TestCase):
    def test_matches_rotate_vector(self) -> None:
        q = Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        p = Position(1.0, 0.0, 0.0)

        rotated = q.rotate_position(p)
        expected = q.rotate_vector(p.vector)

        self.assertIsInstance(rotated, Position)
        assert_allclose(rotated.vector, expected, atol=1e-12)

    def test_identity_leaves_position_unchanged(self) -> None:
        q = Quaternion.identity()
        p = Position(1.0, 2.0, 3.0)
        rotated = q.rotate_position(p)
        assert_allclose(rotated.vector, p.vector)


class TestArrayConversion(unittest.TestCase):
    def test_array_order_is_wxyz(self) -> None:
        q = Quaternion.from_components(1.0, 2.0, 3.0, 4.0)
        arr = np.asarray(q)
        assert_allclose(arr, [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(arr.dtype, np.float64)

    def test_array_via_dunder_directly(self) -> None:
        q = Quaternion.from_components(0.5, 0.5, 0.5, 0.5)
        arr = q.__array__()
        assert_allclose(arr, [0.5, 0.5, 0.5, 0.5])


class TestSnakeCaseAliases(unittest.TestCase):
    def test_from_numpy_quaternion_is_same_as_camel_case(self) -> None:
        self.assertIs(Quaternion.from_numpy_quaternion, Quaternion.fromNumpyQuaternion)

    def test_from_numpy_quaternion_behaves_the_same(self) -> None:
        import quaternion as npq  # type: ignore[import-untyped]

        raw = npq.quaternion(1.0, 2.0, 3.0, 4.0)
        q = Quaternion.from_numpy_quaternion(raw)
        self.assertEqual((q.w, q.x, q.y, q.z), (1.0, 2.0, 3.0, 4.0))

    def test_to_unit_spherical_small_circle_is_same_as_camel_case(self) -> None:
        self.assertIs(
            Quaternion.to_unit_spherical_small_circle,
            Quaternion.to_unitSphericalSmallCircle,
        )

    def test_to_unit_spherical_small_circle_behaves_the_same(self) -> None:
        q = Quaternion.identity()
        result = q.to_unit_spherical_small_circle()
        expected = q.to_unitSphericalSmallCircle()
        self.assertEqual(result.azimuth, expected.azimuth)
        self.assertEqual(result.polar, expected.polar)
        self.assertEqual(result.radius_angle, expected.radius_angle)


if __name__ == "__main__":
    unittest.main()
