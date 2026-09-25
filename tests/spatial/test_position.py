"""Unit tests for ``Position``.

Covers spatialMath.md §Compliance requirements 1 (position half), 2, 3, 10,
plus construction, accessors, arithmetic, normalization, and serialization
round-trip.
"""

import unittest
from typing import Any

import numpy as np
from foundation_abc.math.spatialABCs import PositionABC
from foundationTypes.mathTypes.MathTypes import PositionType

from math_tools.spatial.position import (
    CylindricalCoordinates,
    Position,
    SphericalCoordinates,
    SphericalIsoCoordinates,
)


class TestConstruction(unittest.TestCase):
    def test_default_is_origin(self) -> None:
        p = Position()
        self.assertEqual(p.x, 0.0)
        self.assertEqual(p.y, 0.0)
        self.assertEqual(p.z, 0.0)

    def test_basic_components(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        self.assertEqual(p.x, 1.0)
        self.assertEqual(p.y, 2.0)
        self.assertEqual(p.z, 3.0)

    def test_settable_components(self) -> None:
        """Mutable: p.x = 1.0 is allowed."""
        p = Position()
        p.x = 1.0
        p.y = 2.0
        p.z = 3.0
        self.assertEqual((p.x, p.y, p.z), (1.0, 2.0, 3.0))

    def test_from_vector(self) -> None:
        p = Position.from_vector([1.0, 2.0, 3.0])
        self.assertEqual((p.x, p.y, p.z), (1.0, 2.0, 3.0))

    def test_from_vector_copies(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        p = Position.from_vector(arr)
        arr[0] = 99.0
        self.assertEqual(p.x, 1.0)

    def test_from_vector_wrong_shape_raises(self) -> None:
        with self.assertRaises(ValueError):
            Position.from_vector([1.0, 2.0])

    def test_from_vector_wrong_shape_raises_too_many(self) -> None:
        with self.assertRaises(ValueError):
            Position.from_vector([1.0, 2.0, 3.0, 4.0])

    def test_from_components(self) -> None:
        p = Position.from_components(x=1.0, y=2.0, z=3.0)
        self.assertEqual((p.x, p.y, p.z), (1.0, 2.0, 3.0))

    def test_from_components_default(self) -> None:
        p = Position.from_components()
        self.assertEqual((p.x, p.y, p.z), (0.0, 0.0, 0.0))

    def test_origin(self) -> None:
        p = Position.origin()
        self.assertEqual((p.x, p.y, p.z), (0.0, 0.0, 0.0))

    def test_unit_x(self) -> None:
        p = Position.unit_x()
        self.assertEqual((p.x, p.y, p.z), (1.0, 0.0, 0.0))

    def test_unit_y(self) -> None:
        p = Position.unit_y()
        self.assertEqual((p.x, p.y, p.z), (0.0, 1.0, 0.0))

    def test_unit_z(self) -> None:
        p = Position.unit_z()
        self.assertEqual((p.x, p.y, p.z), (0.0, 0.0, 1.0))


class TestCylindrical(unittest.TestCase):
    def test_from_cylindrical_quarter_turn(self) -> None:
        p = Position.from_cylindrical(radius=2.0, angle=np.pi / 2, height=5.0)
        self.assertAlmostEqual(p.x, 0.0, places=12)
        self.assertAlmostEqual(p.y, 2.0, places=12)
        self.assertAlmostEqual(p.z, 5.0, places=12)

    def test_cylindrical_accessor_type(self) -> None:
        p = Position.from_cylindrical(radius=1.0, angle=0.3, height=1.0)
        self.assertIsInstance(p.cylindrical, CylindricalCoordinates)

    def test_cylindrical_inverse_grid(self) -> None:
        """Compliance 2: init/accessor are mutual inverses over a grid."""
        radii = [0.1, 1.0, 3.5, 10.0]
        angles = np.linspace(-np.pi, np.pi, 13)
        heights = [-2.0, 0.0, 4.0]
        for radius in radii:
            for angle in angles:
                for height in heights:
                    p = Position.from_cylindrical(radius, float(angle), height)
                    result = p.cylindrical
                    self.assertAlmostEqual(result.radius, radius, places=12)
                    self.assertAlmostEqual(result.height, height, places=12)
                    # angle is only well-defined when radius > 0
                    self.assertAlmostEqual(
                        np.arctan2(np.sin(result.angle - angle), np.cos(result.angle - angle)),
                        0.0,
                        places=12,
                    )


class TestSpherical(unittest.TestCase):
    def test_from_spherical_equator(self) -> None:
        p = Position.from_spherical(radius=1.0, azimuth=0.0, elevation=0.0)
        self.assertAlmostEqual(p.x, 1.0, places=12)
        self.assertAlmostEqual(p.y, 0.0, places=12)
        self.assertAlmostEqual(p.z, 0.0, places=12)

    def test_from_spherical_north_pole(self) -> None:
        p = Position.from_spherical(radius=1.0, azimuth=0.0, elevation=np.pi / 2)
        self.assertAlmostEqual(p.x, 0.0, places=12)
        self.assertAlmostEqual(p.y, 0.0, places=12)
        self.assertAlmostEqual(p.z, 1.0, places=12)

    def test_spherical_accessor_type(self) -> None:
        p = Position.from_spherical(radius=1.0, azimuth=0.3, elevation=0.2)
        self.assertIsInstance(p.spherical, SphericalCoordinates)

    def test_spherical_inverse_grid(self) -> None:
        """Compliance 2: both spherical conventions inverse-tested over a
        radius/angle grid, atol 1e-12."""
        radii = [0.1, 1.0, 5.0]
        azimuths = np.linspace(-np.pi + 1e-6, np.pi - 1e-6, 9)
        elevations = np.linspace(-np.pi / 2 + 1e-6, np.pi / 2 - 1e-6, 9)
        for radius in radii:
            for azimuth in azimuths:
                for elevation in elevations:
                    p = Position.from_spherical(radius, float(azimuth), float(elevation))
                    result = p.spherical
                    self.assertAlmostEqual(result.radius, radius, delta=1e-9)
                    self.assertAlmostEqual(result.elevation, float(elevation), delta=1e-9)
                    self.assertAlmostEqual(
                        np.arctan2(
                            np.sin(result.azimuth - azimuth), np.cos(result.azimuth - azimuth)
                        ),
                        0.0,
                        delta=1e-9,
                    )


class TestSphericalIso(unittest.TestCase):
    def test_from_spherical_iso_north_pole(self) -> None:
        p = Position.from_spherical_iso(radius=1.0, azimuth=0.0, polar=0.0)
        self.assertAlmostEqual(p.x, 0.0, places=12)
        self.assertAlmostEqual(p.y, 0.0, places=12)
        self.assertAlmostEqual(p.z, 1.0, places=12)

    def test_from_spherical_iso_equator(self) -> None:
        p = Position.from_spherical_iso(radius=1.0, azimuth=0.0, polar=np.pi / 2)
        self.assertAlmostEqual(p.x, 1.0, places=12)
        self.assertAlmostEqual(p.y, 0.0, places=12)
        self.assertAlmostEqual(p.z, 0.0, places=12)

    def test_spherical_iso_accessor_type(self) -> None:
        p = Position.from_spherical_iso(radius=1.0, azimuth=0.3, polar=0.2)
        self.assertIsInstance(p.spherical_iso, SphericalIsoCoordinates)

    def test_spherical_iso_inverse_grid(self) -> None:
        """Compliance 2: ISO convention inverse-tested over a radius/angle
        grid, atol 1e-12. Distinct convention from geographic ``spherical``:
        polar (colatitude from +z) vs. elevation (from xy-plane)."""
        radii = [0.1, 1.0, 5.0]
        azimuths = np.linspace(-np.pi + 1e-6, np.pi - 1e-6, 9)
        polars = np.linspace(1e-6, np.pi - 1e-6, 9)
        for radius in radii:
            for azimuth in azimuths:
                for polar in polars:
                    p = Position.from_spherical_iso(radius, float(azimuth), float(polar))
                    result = p.spherical_iso
                    self.assertAlmostEqual(result.radius, radius, delta=1e-9)
                    self.assertAlmostEqual(result.polar, float(polar), delta=1e-9)
                    self.assertAlmostEqual(
                        np.arctan2(
                            np.sin(result.azimuth - azimuth), np.cos(result.azimuth - azimuth)
                        ),
                        0.0,
                        delta=1e-9,
                    )

    def test_spherical_and_spherical_iso_are_distinct_conventions(self) -> None:
        """Same inputs (radius, azimuth, angle) produce different points
        under the two conventions, except at shared reference points."""
        p_geo = Position.from_spherical(radius=1.0, azimuth=0.3, elevation=0.3)
        p_iso = Position.from_spherical_iso(radius=1.0, azimuth=0.3, polar=0.3)
        self.assertFalse(p_geo.isclose(p_iso))


class TestVectorProperties(unittest.TestCase):
    def test_vector_returns_copy(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        v = p.vector
        v[0] = 99.0
        self.assertEqual(p.x, 1.0)

    def test_vector_values(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        np.testing.assert_array_equal(p.vector, np.array([1.0, 2.0, 3.0]))

    def test_components(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        self.assertEqual(p.components, [1.0, 2.0, 3.0])

    def test_magnitude(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        self.assertEqual(p.magnitude, 5.0)

    def test_magnitude_squared(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        self.assertEqual(p.magnitude_squared, 25.0)

    def test_norm_is_alias_of_magnitude(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        self.assertEqual(p.norm, p.magnitude)

    def test_abs_is_magnitude(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        self.assertEqual(abs(p), p.magnitude)

    def test_is_unit_true(self) -> None:
        p = Position.unit_x()
        self.assertTrue(p.is_unit)

    def test_is_unit_false(self) -> None:
        p = Position(2.0, 0.0, 0.0)
        self.assertFalse(p.is_unit)

    def test_is_unit_false_just_outside_tolerance(self) -> None:
        """B-1: rtol must not leak in; 1e-5 relative slack is far outside the
        spec's 1e-12 absolute tolerance."""
        p = Position(1.00001, 0.0, 0.0)
        self.assertFalse(p.is_unit)

    def test_is_unit_true_just_inside_tolerance(self) -> None:
        p = Position(1.0 + 1e-13, 0.0, 0.0)
        self.assertTrue(p.is_unit)


class TestCrossProduct(unittest.TestCase):
    def test_unit_x_cross_unit_y_is_unit_z(self) -> None:
        """Compliance 3: cross follows the right-hand rule."""
        result = Position.unit_x().cross(Position.unit_y())
        self.assertTrue(result.isclose(Position.unit_z()))

    def test_unit_y_cross_unit_z_is_unit_x(self) -> None:
        result = Position.unit_y().cross(Position.unit_z())
        self.assertTrue(result.isclose(Position.unit_x()))

    def test_unit_z_cross_unit_x_is_unit_y(self) -> None:
        result = Position.unit_z().cross(Position.unit_x())
        self.assertTrue(result.isclose(Position.unit_y()))

    def test_cross_returns_position(self) -> None:
        result = Position.unit_x().cross(Position.unit_y())
        self.assertIsInstance(result, Position)


class TestDotProduct(unittest.TestCase):
    def test_dot_orthogonal_is_zero(self) -> None:
        self.assertEqual(Position.unit_x().dot(Position.unit_y()), 0.0)

    def test_dot_parallel(self) -> None:
        self.assertEqual(Position(2.0, 0.0, 0.0).dot(Position(3.0, 0.0, 0.0)), 6.0)

    def test_dot_general(self) -> None:
        a = Position(1.0, 2.0, 3.0)
        b = Position(4.0, 5.0, 6.0)
        self.assertEqual(a.dot(b), 1 * 4 + 2 * 5 + 3 * 6)


class TestDistance(unittest.TestCase):
    def test_distance(self) -> None:
        a = Position(0.0, 0.0, 0.0)
        b = Position(3.0, 4.0, 0.0)
        self.assertEqual(a.distance(b), 5.0)

    def test_distance_squared(self) -> None:
        a = Position(0.0, 0.0, 0.0)
        b = Position(3.0, 4.0, 0.0)
        self.assertEqual(a.distance_squared(b), 25.0)

    def test_distance_to_self_is_zero(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        self.assertEqual(p.distance(p), 0.0)


class TestArithmeticOperators(unittest.TestCase):
    def test_add_position(self) -> None:
        result = Position(1.0, 2.0, 3.0) + Position(4.0, 5.0, 6.0)
        self.assertEqual((result.x, result.y, result.z), (5.0, 7.0, 9.0))

    def test_add_scalar(self) -> None:
        result = Position(1.0, 2.0, 3.0) + 1.0
        self.assertEqual((result.x, result.y, result.z), (2.0, 3.0, 4.0))

    def test_radd_scalar(self) -> None:
        result = 1.0 + Position(1.0, 2.0, 3.0)
        self.assertEqual((result.x, result.y, result.z), (2.0, 3.0, 4.0))

    def test_sub_position(self) -> None:
        result = Position(4.0, 5.0, 6.0) - Position(1.0, 2.0, 3.0)
        self.assertEqual((result.x, result.y, result.z), (3.0, 3.0, 3.0))

    def test_sub_scalar(self) -> None:
        result = Position(4.0, 5.0, 6.0) - 1.0
        self.assertEqual((result.x, result.y, result.z), (3.0, 4.0, 5.0))

    def test_rsub_scalar(self) -> None:
        """scalar - position: component-wise."""
        result = 10.0 - Position(1.0, 2.0, 3.0)
        self.assertEqual((result.x, result.y, result.z), (9.0, 8.0, 7.0))

    def test_mul_scalar(self) -> None:
        result = Position(1.0, 2.0, 3.0) * 2.0
        self.assertEqual((result.x, result.y, result.z), (2.0, 4.0, 6.0))

    def test_rmul_scalar(self) -> None:
        result = 2.0 * Position(1.0, 2.0, 3.0)
        self.assertEqual((result.x, result.y, result.z), (2.0, 4.0, 6.0))

    def test_truediv_scalar(self) -> None:
        result = Position(2.0, 4.0, 6.0) / 2.0
        self.assertEqual((result.x, result.y, result.z), (1.0, 2.0, 3.0))

    def test_iadd_position(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        p += Position(1.0, 1.0, 1.0)
        self.assertEqual((p.x, p.y, p.z), (2.0, 3.0, 4.0))

    def test_iadd_scalar(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        p += 1.0
        self.assertEqual((p.x, p.y, p.z), (2.0, 3.0, 4.0))

    def test_isub_position(self) -> None:
        p = Position(4.0, 5.0, 6.0)
        p -= Position(1.0, 1.0, 1.0)
        self.assertEqual((p.x, p.y, p.z), (3.0, 4.0, 5.0))

    def test_imul_scalar(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        p *= 2.0
        self.assertEqual((p.x, p.y, p.z), (2.0, 4.0, 6.0))

    def test_itruediv_scalar(self) -> None:
        p = Position(2.0, 4.0, 6.0)
        p /= 2.0
        self.assertEqual((p.x, p.y, p.z), (1.0, 2.0, 3.0))

    def test_neg(self) -> None:
        result = -Position(1.0, -2.0, 3.0)
        self.assertEqual((result.x, result.y, result.z), (-1.0, 2.0, -3.0))

    def test_pos(self) -> None:
        p = Position(1.0, -2.0, 3.0)
        result = +p
        self.assertEqual((result.x, result.y, result.z), (1.0, -2.0, 3.0))
        self.assertIsNot(result, p)

    def test_add_unsupported_type_returns_not_implemented(self) -> None:
        with self.assertRaises(TypeError):
            Position(1.0, 2.0, 3.0) + "not a position"  # type: ignore[operator]

    def test_mul_unsupported_type_raises(self) -> None:
        with self.assertRaises(TypeError):
            Position(1.0, 2.0, 3.0) * Position(1.0, 2.0, 3.0)  # type: ignore[operator]


class TestNormalization(unittest.TestCase):
    def test_normalize_in_place(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        p.normalize()
        self.assertAlmostEqual(p.magnitude, 1.0, places=12)
        self.assertAlmostEqual(p.x, 0.6, places=12)
        self.assertAlmostEqual(p.y, 0.8, places=12)

    def test_normalize_zero_vector_raises(self) -> None:
        p = Position(0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            p.normalize()

    def test_normalized_returns_copy(self) -> None:
        p = Position(3.0, 4.0, 0.0)
        result = p.normalized()
        self.assertIsNot(result, p)
        self.assertEqual(p.magnitude, 5.0)  # original unchanged
        self.assertAlmostEqual(result.magnitude, 1.0, places=12)

    def test_normalized_zero_vector_raises(self) -> None:
        p = Position(0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            p.normalized()

    def test_normalized_is_unit(self) -> None:
        p = Position(1.0, 2.0, 3.0).normalized()
        self.assertTrue(p.is_unit)


class TestComparison(unittest.TestCase):
    def test_equality_exact(self) -> None:
        self.assertEqual(Position(1.0, 2.0, 3.0), Position(1.0, 2.0, 3.0))

    def test_equality_different_values(self) -> None:
        self.assertNotEqual(Position(1.0, 2.0, 3.0), Position(1.0, 2.0, 3.1))

    def test_equality_with_foreign_type_is_false(self) -> None:
        self.assertFalse(Position(1.0, 2.0, 3.0) == "not a position")
        self.assertNotEqual(Position(1.0, 2.0, 3.0), object())

    def test_isclose_within_tolerance(self) -> None:
        a = Position(1.0, 2.0, 3.0)
        b = Position(1.0 + 1e-10, 2.0, 3.0)
        self.assertTrue(a.isclose(b, rtol=1e-9, atol=1e-9))

    def test_isclose_outside_tolerance(self) -> None:
        a = Position(1.0, 2.0, 3.0)
        b = Position(1.1, 2.0, 3.0)
        self.assertFalse(a.isclose(b, rtol=1e-9, atol=0.0))

    def test_repr_contains_components(self) -> None:
        text = repr(Position(1.0, 2.0, 3.0))
        self.assertIn("Position", text)
        self.assertIn("1.0", text)
        self.assertIn("2.0", text)
        self.assertIn("3.0", text)


class TestHashability(unittest.TestCase):
    def test_hash_is_none(self) -> None:
        """Compliance 10: __hash__ is None (mutable -> unhashable)."""
        self.assertIsNone(Position.__hash__)

    def test_unhashable_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            hash(Position(1.0, 2.0, 3.0))


class TestArrayConversion(unittest.TestCase):
    def test_asarray_shape(self) -> None:
        """Compliance 10: np.asarray(p) returns the (3,) vector."""
        p = Position(1.0, 2.0, 3.0)
        arr = np.asarray(p)
        self.assertEqual(arr.shape, (3,))
        np.testing.assert_array_equal(arr, np.array([1.0, 2.0, 3.0]))

    def test_asarray_is_independent_copy(self) -> None:
        p = Position(1.0, 2.0, 3.0)
        arr = np.asarray(p)
        arr[0] = 99.0
        self.assertEqual(p.x, 1.0)


class TestIsinstanceAndAbc(unittest.TestCase):
    def test_structural_conformance_to_abc(self) -> None:
        """Position structurally conforms to PositionABC (a non-runtime_checkable
        ``typing.Protocol``), verified by member presence rather than
        ``isinstance``."""
        p = Position(1.0, 2.0, 3.0)
        for member in PositionABC.__abstractmethods__:
            self.assertTrue(hasattr(p, member), member)


class TestSerializationRoundTrip(unittest.TestCase):
    """Compliance 1 (position half): round-trip with PositionType wire dicts."""

    def _round_trip(self, payload: dict[str, Any]) -> None:
        wire = PositionType.from_dict(payload).to_dict()
        result = Position.from_dict(wire).to_dict()
        self.assertEqual(result, payload)

    def test_round_trip_origin(self) -> None:
        self._round_trip({"x": 0.0, "y": 0.0, "z": 0.0})

    def test_round_trip_general(self) -> None:
        self._round_trip({"x": 1.0, "y": 2.0, "z": 3.0})

    def test_round_trip_negative(self) -> None:
        self._round_trip({"x": -1.5, "y": 2.5, "z": -3.5})

    def test_to_dict_keys(self) -> None:
        d = Position(1.0, 2.0, 3.0).to_dict()
        self.assertEqual(d, {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_from_dict_with_integers(self) -> None:
        p = Position.from_dict({"x": 1, "y": 2, "z": 3})
        self.assertEqual((p.x, p.y, p.z), (1.0, 2.0, 3.0))


if __name__ == "__main__":
    unittest.main()
