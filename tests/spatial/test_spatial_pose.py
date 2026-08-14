"""Unit tests for ``SpatialPose``.

Covers spatialMath.md §SpatialPose and §Compliance requirements 4-8:
Denavit-Hartenberg construction (4), composition algebra (5), interpolation
(6), double-cover-safe angular distance (7), and the homogeneous-matrix
round trip (8). Also covers construction, passthrough properties,
translation, inverse/relative pose, distances, normalization, comparison,
and wire-format round trip against ``SpatialTransformType``.
"""

import unittest
from typing import Any

import numpy as np
from foundation_abc.math.spatialABCs import SpatialTransformABC
from foundationTypes.mathTypes.MathTypes import SpatialTransformType
from numpy.testing import assert_allclose

from math_tools.spatial.position import Position
from math_tools.spatial.quaternion import Quaternion
from math_tools.spatial.spatial_pose import SpatialPose


class TestConstruction(unittest.TestCase):
    def test_default_is_identity(self) -> None:
        pose = SpatialPose()
        self.assertEqual((pose.x, pose.y, pose.z), (0.0, 0.0, 0.0))
        self.assertEqual((pose.qw, pose.qx, pose.qy, pose.qz), (1.0, 0.0, 0.0, 0.0))

    def test_explicit_components(self) -> None:
        position = Position(1.0, 2.0, 3.0)
        orientation = Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        pose = SpatialPose(position, orientation)
        self.assertEqual((pose.x, pose.y, pose.z), (1.0, 2.0, 3.0))
        self.assertIs(pose.orientation, orientation)

    def test_position_is_copied_not_aliased(self) -> None:
        """Position is mutable; SpatialPose must not alias the caller's instance."""
        position = Position(1.0, 2.0, 3.0)
        pose = SpatialPose(position)
        position.x = 99.0
        self.assertEqual(pose.x, 1.0)

    def test_identity_classmethod(self) -> None:
        pose = SpatialPose.identity()
        self.assertEqual((pose.x, pose.y, pose.z), (0.0, 0.0, 0.0))
        self.assertEqual((pose.qw, pose.qx, pose.qy, pose.qz), (1.0, 0.0, 0.0, 0.0))

    def test_from_components_defaults(self) -> None:
        pose = SpatialPose.from_components()
        self.assertTrue(pose.isclose(SpatialPose.identity()))

    def test_from_components_explicit(self) -> None:
        pose = SpatialPose.from_components(x=1.0, y=2.0, z=3.0, qw=0.0, qx=1.0, qy=0.0, qz=0.0)
        self.assertEqual((pose.x, pose.y, pose.z), (1.0, 2.0, 3.0))
        self.assertEqual((pose.qw, pose.qx, pose.qy, pose.qz), (0.0, 1.0, 0.0, 0.0))

    def test_isinstance_of_abc(self) -> None:
        pose = SpatialPose()
        self.assertIsInstance(pose, SpatialTransformABC)


class TestFromHomogeneous(unittest.TestCase):
    def test_wrong_shape_raises(self) -> None:
        with self.assertRaises(ValueError):
            SpatialPose.from_homogeneous(np.eye(3))

    def test_non_rigid_bottom_row_raises(self) -> None:
        matrix = np.eye(4)
        matrix[3, 3] = 2.0
        with self.assertRaises(ValueError):
            SpatialPose.from_homogeneous(matrix)

    def test_non_rigid_bottom_row_nonzero_raises(self) -> None:
        matrix = np.eye(4)
        matrix[3, 0] = 1.0
        with self.assertRaises(ValueError):
            SpatialPose.from_homogeneous(matrix)

    def test_identity_round_trip(self) -> None:
        pose = SpatialPose.identity()
        recovered = SpatialPose.from_homogeneous(pose.homogeneous)
        self.assertTrue(recovered.isclose(pose, atol=1e-9))

    def test_round_trip_general(self) -> None:
        """Compliance 8: homogeneous / from_homogeneous round-trip."""
        position = Position(1.0, -2.0, 3.5)
        orientation = Quaternion.from_axis_angle(np.array([1.0, 1.0, 0.0]), 1.234)
        pose = SpatialPose(position, orientation)
        recovered = SpatialPose.from_homogeneous(pose.homogeneous)
        self.assertTrue(recovered.isclose(pose, atol=1e-9))

    def test_round_trip_non_normalized_orientation(self) -> None:
        """Compliance 8: non-normalized input quaternion is normalized on export."""
        position = Position(1.0, 2.0, 3.0)
        non_unit_orientation = Quaternion.from_components(2.0, 0.0, 0.0, 0.0)  # norm == 2
        pose = SpatialPose(position, non_unit_orientation)

        matrix = pose.homogeneous
        recovered = SpatialPose.from_homogeneous(matrix)

        self.assertTrue(recovered.position.isclose(position, atol=1e-9))
        self.assertTrue(recovered.orientation.isclose(Quaternion.identity(), atol=1e-9))
        self.assertAlmostEqual(recovered.orientation.norm, 1.0, places=9)


class TestDenavitHartenberg(unittest.TestCase):
    """Compliance 4: pinned against published DH parameter sets."""

    def test_two_link_planar_arm(self) -> None:
        """a1 = a2 = 1, alpha = d = 0, theta = (90deg, 0deg).

        Link 1 (a=1, alpha=0, d=0, theta=90deg): position (0, 1, 0),
        rotation = +90deg about z.
        Link 2, expressed in link 1's frame (a=1, alpha=0, d=0, theta=0deg):
        position (1, 0, 0), identity rotation.
        Chained: end_effector = pose1 * pose2.
        position = pos1 + R1 @ pos2 = (0, 1, 0) + R_z(90deg) @ (1, 0, 0)
                 = (0, 1, 0) + (0, 1, 0) = (0, 2, 0).
        """
        pose1 = SpatialPose.from_denavit_hartenberg(a=1.0, alpha=0.0, d=0.0, theta=np.pi / 2)
        pose2 = SpatialPose.from_denavit_hartenberg(a=1.0, alpha=0.0, d=0.0, theta=0.0)

        end_effector = pose1 * pose2

        assert_allclose(end_effector.position.vector, [0.0, 2.0, 0.0], atol=1e-9)

    def test_non_planar_link_with_nonzero_alpha(self) -> None:
        """a=1, alpha=90deg, d=1, theta=90deg (a non-planar set: alpha != 0).

        ct=cos(90deg)=0, st=sin(90deg)=1, ca=cos(90deg)=0, sa=sin(90deg)=1.
        position = (a*ct, a*st, d) = (0, 1, 1).
        rotation matrix (standard DH form):
            [ ct, -st*ca,  st*sa ]   [ 0, 0, 1 ]
            [ st,  ct*ca, -ct*sa ] = [ 1, 0, 0 ]
            [  0,     sa,     ca ]   [ 0, 1, 0 ]
        (a proper rotation: e_x -> e_y, e_y -> e_z, e_z -> e_x, a 120deg
        rotation about the (1, 1, 1) axis).
        """
        pose = SpatialPose.from_denavit_hartenberg(a=1.0, alpha=np.pi / 2, d=1.0, theta=np.pi / 2)

        expected_position = [0.0, 1.0, 1.0]
        expected_rotation_matrix = np.array(
            [
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ]
        )

        assert_allclose(pose.position.vector, expected_position, atol=1e-9)
        assert_allclose(pose.orientation.to_rotation_matrix(), expected_rotation_matrix, atol=1e-9)


class TestComposition(unittest.TestCase):
    """Compliance 5: composition algebra."""

    def _sample_poses(self) -> tuple[SpatialPose, SpatialPose]:
        a = SpatialPose(
            Position(1.0, 2.0, 3.0),
            Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 3),
        )
        b = SpatialPose(
            Position(-1.0, 0.5, 2.0),
            Quaternion.from_axis_angle(np.array([1.0, 0.0, 0.0]), np.pi / 5),
        )
        return a, b

    def test_composition_recipe(self) -> None:
        a, b = self._sample_poses()
        result = a * b

        expected_position = a.position + a.orientation.rotate_position(b.position)
        expected_orientation = a.orientation * b.orientation

        self.assertTrue(result.position.isclose(expected_position, atol=1e-12))
        self.assertTrue(result.orientation.isclose(expected_orientation, atol=1e-12))

    def test_pose_times_position_equals_transform(self) -> None:
        a, _ = self._sample_poses()
        p = Position(0.5, -0.25, 1.5)

        self.assertTrue((a * p).isclose(a.transform(p), atol=1e-12))

    def test_pose_times_inverse_is_identity(self) -> None:
        a, _ = self._sample_poses()
        result = a * a.inverse()
        self.assertTrue(result.isclose(SpatialPose.identity(), atol=1e-9))

    def test_composition_associativity_via_transform(self) -> None:
        a, b = self._sample_poses()
        p = Position(2.0, -3.0, 0.5)

        composed = (a * b).transform(p)
        chained = a.transform(b.transform(p))

        self.assertTrue(composed.isclose(chained, atol=1e-9))


class TestTranslated(unittest.TestCase):
    def test_shifts_position_only(self) -> None:
        orientation = Quaternion.from_axis_angle(np.array([0.0, 1.0, 0.0]), 0.7)
        pose = SpatialPose(Position(1.0, 1.0, 1.0), orientation)
        shifted = pose.translated(Position(1.0, 2.0, 3.0))

        assert_allclose(shifted.position.vector, [2.0, 3.0, 4.0])
        self.assertTrue(shifted.orientation.isclose(orientation))


class TestRelativePose(unittest.TestCase):
    def test_relative_pose_matches_inverse_times_other(self) -> None:
        a = SpatialPose(
            Position(1.0, 0.0, 0.0),
            Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 4),
        )
        b = SpatialPose(
            Position(0.0, 1.0, 0.0),
            Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2),
        )

        relative = a.relative_pose(b)
        expected = a.inverse() * b

        self.assertTrue(relative.isclose(expected, atol=1e-12))

    def test_relative_pose_to_self_is_identity(self) -> None:
        a = SpatialPose(
            Position(3.0, -1.0, 2.0),
            Quaternion.from_axis_angle(np.array([1.0, 1.0, 1.0]), 1.1),
        )
        self.assertTrue(a.relative_pose(a).isclose(SpatialPose.identity(), atol=1e-9))


class TestInterpolate(unittest.TestCase):
    """Compliance 6: endpoints + half-angle midpoint."""

    def _rotation_only_poses(self) -> tuple[SpatialPose, SpatialPose]:
        start = SpatialPose.identity()
        end = SpatialPose(
            Position.origin(), Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        )
        return start, end

    def test_t_zero_returns_self(self) -> None:
        start, end = self._rotation_only_poses()
        result = start.interpolate(end, 0.0)
        self.assertTrue(result.isclose(start, atol=1e-12))

    def test_t_one_returns_other(self) -> None:
        start, end = self._rotation_only_poses()
        result = start.interpolate(end, 1.0)
        self.assertTrue(result.isclose(end, atol=1e-9))

    def test_midpoint_is_half_angle_for_pure_rotation(self) -> None:
        start, end = self._rotation_only_poses()
        midpoint = start.interpolate(end, 0.5)
        self.assertAlmostEqual(midpoint.orientation.angle, (np.pi / 2) / 2.0, places=9)

    def test_position_lerp(self) -> None:
        start = SpatialPose(Position(0.0, 0.0, 0.0))
        end = SpatialPose(Position(4.0, 0.0, 0.0))
        result = start.interpolate(end, 0.25)
        assert_allclose(result.position.vector, [1.0, 0.0, 0.0], atol=1e-12)

    def test_t_unclamped_extrapolates(self) -> None:
        start, end = self._rotation_only_poses()
        result = start.interpolate(end, 2.0)
        # 2x the 90deg rotation from start to end
        self.assertAlmostEqual(result.orientation.angle, np.pi, places=9)


class TestAngularDistance(unittest.TestCase):
    """Compliance 7: angular_distance(q, -q) == 0."""

    def test_double_cover_distance_is_zero(self) -> None:
        orientation = Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        a = SpatialPose(Position.origin(), orientation)
        b = SpatialPose(Position.origin(), -orientation)

        self.assertAlmostEqual(a.angular_distance(b), 0.0, places=9)

    def test_identity_to_self_is_zero(self) -> None:
        a = SpatialPose.identity()
        self.assertAlmostEqual(a.angular_distance(a), 0.0, places=9)

    def test_known_angle(self) -> None:
        a = SpatialPose.identity()
        b = SpatialPose(
            Position.origin(), Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 3)
        )
        self.assertAlmostEqual(a.angular_distance(b), np.pi / 3, places=9)


class TestPositionDistance(unittest.TestCase):
    def test_position_distance_matches_position_distance(self) -> None:
        a = SpatialPose(Position(0.0, 0.0, 0.0))
        b = SpatialPose(Position(3.0, 4.0, 0.0))
        self.assertAlmostEqual(a.position_distance(b), 5.0, places=12)

    def test_position_distance_squared(self) -> None:
        a = SpatialPose(Position(0.0, 0.0, 0.0))
        b = SpatialPose(Position(3.0, 4.0, 0.0))
        self.assertAlmostEqual(a.position_distance_squared(b), 25.0, places=12)


class TestNormalize(unittest.TestCase):
    def test_normalized_returns_copy_with_unit_orientation(self) -> None:
        position = Position(1.0, 2.0, 3.0)
        non_unit = Quaternion.from_components(2.0, 0.0, 0.0, 0.0)
        pose = SpatialPose(position, non_unit)

        result = pose.normalized()

        self.assertAlmostEqual(result.orientation.norm, 1.0, places=12)
        self.assertTrue(result.position.isclose(position))
        # original is untouched
        self.assertAlmostEqual(pose.orientation.norm, 2.0, places=12)

    def test_normalize_mutates_in_place(self) -> None:
        non_unit = Quaternion.from_components(2.0, 0.0, 0.0, 0.0)
        pose = SpatialPose(Position(1.0, 2.0, 3.0), non_unit)
        pose.normalize()
        self.assertAlmostEqual(pose.orientation.norm, 1.0, places=12)

    def test_is_unit_delegates_to_orientation(self) -> None:
        pose = SpatialPose(Position(1.0, 2.0, 3.0), Quaternion.from_components(2.0, 0.0, 0.0, 0.0))
        self.assertFalse(pose.is_unit)
        pose.normalize()
        self.assertTrue(pose.is_unit)


class TestComparison(unittest.TestCase):
    def test_equal_poses(self) -> None:
        a = SpatialPose(Position(1.0, 2.0, 3.0), Quaternion.from_components(1.0, 0.0, 0.0, 0.0))
        b = SpatialPose(Position(1.0, 2.0, 3.0), Quaternion.from_components(1.0, 0.0, 0.0, 0.0))
        self.assertEqual(a, b)

    def test_unequal_poses(self) -> None:
        a = SpatialPose(Position(1.0, 2.0, 3.0))
        b = SpatialPose(Position(1.0, 2.0, 3.1))
        self.assertNotEqual(a, b)

    def test_equal_to_non_pose_is_false(self) -> None:
        a = SpatialPose()
        self.assertFalse(a == object())

    def test_isclose(self) -> None:
        a = SpatialPose(Position(1.0, 2.0, 3.0))
        b = SpatialPose(Position(1.0 + 1e-12, 2.0, 3.0))
        self.assertTrue(a.isclose(b))

    def test_isclose_double_cover_orientation(self) -> None:
        """Compliance 7 / spatialMath double-cover: q and -q are the same
        rotation, so isclose must treat them as equal poses."""
        position = Position(1.0, 2.0, 3.0)
        orientation = Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 3)
        a = SpatialPose(position, orientation)
        b = SpatialPose(Position(1.0, 2.0, 3.0), -orientation)
        self.assertTrue(a.isclose(b))

    def test_isclose_false_for_different_orientation(self) -> None:
        a = SpatialPose(Position(1.0, 2.0, 3.0), Quaternion.from_components(1.0, 0.0, 0.0, 0.0))
        b = SpatialPose(
            Position(1.0, 2.0, 3.0),
            Quaternion.from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2),
        )
        self.assertFalse(a.isclose(b))

    def test_hash_is_none(self) -> None:
        """Mutable, numpy-backed: unhashable, pinned by test."""
        self.assertIsNone(SpatialPose.__hash__)

    def test_repr(self) -> None:
        pose = SpatialPose()
        self.assertIn("SpatialPose", repr(pose))


class TestSerializationRoundTrip(unittest.TestCase):
    """Compliance 1: round-trip with SpatialTransformType wire dicts."""

    def _round_trip(self, payload: dict[str, Any]) -> None:
        wire = SpatialTransformType.from_dict(payload).to_dict()
        result = SpatialPose.from_dict(wire).to_dict()
        self.assertEqual(result, payload)

    def test_round_trip_identity(self) -> None:
        self._round_trip(
            {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
            }
        )

    def test_round_trip_general(self) -> None:
        self._round_trip(
            {
                "position": {"x": 1.0, "y": -2.0, "z": 3.5},
                "orientation": {
                    "w": 0.7071067811865476,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.7071067811865476,
                },
            }
        )

    def test_to_dict_keys(self) -> None:
        pose = SpatialPose(Position(1.0, 2.0, 3.0), Quaternion.from_components(1.0, 0.0, 0.0, 0.0))
        d = pose.to_dict()
        self.assertEqual(set(d.keys()), {"position", "orientation"})
        self.assertEqual(d["position"], {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(d["orientation"], {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0})


if __name__ == "__main__":
    unittest.main()
