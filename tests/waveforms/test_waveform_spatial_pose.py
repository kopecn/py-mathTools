"""Unit tests for ``WaveformSpatialPose`` (the 6-DOF pose time-series container).

Covers waveformCore.md §Aggregate containers with ``Element = SpatialPose``,
and §Compliance requirements 1, 2, 8, 9 (see 17-waveform-spatial-pose.md for
the governing chunk).
"""

import time
import unittest

import numpy as np
from foundation_abc.math.waveformABCs import WaveformSpatialABC
from foundationTypes.mathTypes.MathTypes import SpatialTransformWaveformType

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.spatial.position import Position
from math_tools.spatial.quaternion import Quaternion
from math_tools.spatial.spatial_pose import SpatialPose
from math_tools.waveforms.waveform_position import WaveformPosition
from math_tools.waveforms.waveform_quaternion import WaveformQuaternion
from math_tools.waveforms.waveform_spatial_pose import WaveformSpatialPose


def _pose(i: int) -> SpatialPose:
    return SpatialPose(
        Position(float(i), float(i) * 2.0, float(i) * 3.0),
        Quaternion.from_components(1.0, 0.0, 0.0, 0.0)
        if i == 0
        else Quaternion.from_components(0.0, 1.0, 0.0, 0.0),
    )


def _make_poses(n: int = 3) -> list[SpatialPose]:
    return [_pose(i) for i in range(n)]


def _make(n: int = 3, dt_seconds: float = 1.0, t0_seconds: float = 0.0) -> WaveformSpatialPose:
    return WaveformSpatialPose.from_poses(
        _make_poses(n), dt_seconds=dt_seconds, t0_seconds=t0_seconds
    )


class TestSpecCompliance1SerializationRoundTrip(unittest.TestCase):
    """§Compliance 1: to_dict round-trips through SpatialTransformWaveformType."""

    def test_round_trip_equal(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=10.0)
        wire = SpatialTransformWaveformType.from_dict(w.to_dict())
        self.assertEqual(w.to_dict(), wire.to_dict())

    def test_from_dict_reconstructs_equal_waveform(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=10.0)
        w2 = WaveformSpatialPose.from_dict(w.to_dict())
        self.assertEqual(w, w2)

    def test_isinstance_of_abc(self) -> None:
        self.assertIsInstance(_make(), WaveformSpatialABC)

    def test_no_abstract_methods_remain(self) -> None:
        self.assertEqual(WaveformSpatialPose.__abstractmethods__, frozenset())


class TestConstruction(unittest.TestCase):
    def test_from_parallel_arrays(self) -> None:
        positions = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        quaternions = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        w = WaveformSpatialPose(positions, quaternions)
        np.testing.assert_array_equal(w.positions_array, positions)
        np.testing.assert_array_equal(w.quaternions_array, quaternions)

    def test_from_element_lists(self) -> None:
        positions = [Position(1.0, 2.0, 3.0), Position(4.0, 5.0, 6.0)]
        quaternions = [
            Quaternion.from_components(1.0, 0.0, 0.0, 0.0),
            Quaternion.from_components(0.0, 1.0, 0.0, 0.0),
        ]
        w = WaveformSpatialPose(positions, quaternions)
        self.assertEqual(len(w), 2)

    def test_empty_construction(self) -> None:
        w = WaveformSpatialPose([], [])
        self.assertEqual(len(w), 0)
        self.assertEqual(w.positions_array.shape, (0, 3))
        self.assertEqual(w.quaternions_array.shape, (0, 4))

    def test_wrong_position_shape_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformSpatialPose(np.array([[1.0, 2.0], [3.0, 4.0]]), np.zeros((2, 4)))

    def test_wrong_quaternion_shape_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformSpatialPose(np.zeros((2, 3)), np.array([[1.0, 2.0], [3.0, 4.0]]))

    def test_both_dt_and_dt_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            WaveformSpatialPose([], [], dt=PrecisionTimeInterval.ONE_SECOND, dt_seconds=1.0)

    def test_both_t0_and_t0_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            WaveformSpatialPose([], [], t0=PrecisionTimestamp.EPOCH, t0_seconds=1.0)

    def test_zero_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformSpatialPose([], [], dt_seconds=0.0)

    def test_negative_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformSpatialPose([], [], dt_seconds=-1.0)

    def test_default_dt_is_one_second(self) -> None:
        w = WaveformSpatialPose([Position(1.0, 2.0, 3.0)], [Quaternion.identity()])
        self.assertEqual(w.dt, PrecisionTimeInterval.from_seconds(1.0))
        self.assertEqual(w.t0, PrecisionTimestamp.EPOCH)

    def test_primary_constructor_allows_unequal_length_arrays(self) -> None:
        """Unlike from_waveforms/from_poses, the primary constructor does not validate
        equal length (design constraint 3)."""
        positions = np.zeros((3, 3))
        quaternions = np.zeros((5, 4))
        w = WaveformSpatialPose(positions, quaternions)
        self.assertEqual(len(w.positions_array), 3)
        self.assertEqual(len(w.quaternions_array), 5)


class TestTimeAxis(unittest.TestCase):
    def test_duration_is_dt_times_n_minus_1(self) -> None:
        w = _make(n=4, dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.from_seconds(1.5))

    def test_duration_zero_for_single_sample(self) -> None:
        w = _make(n=1, dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.ZERO)

    def test_duration_zero_for_empty(self) -> None:
        w = WaveformSpatialPose([], [], dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.ZERO)

    def test_duration_seconds(self) -> None:
        w = _make(n=3, dt_seconds=2.0)
        self.assertEqual(w.duration_seconds, 4.0)

    def test_sampling_frequency_hz(self) -> None:
        w = _make(n=2, dt_seconds=0.1)
        self.assertAlmostEqual(w.sampling_frequency_hz, 10.0)

    def test_nyquist_frequency_hz(self) -> None:
        w = _make(n=2, dt_seconds=0.1)
        self.assertAlmostEqual(w.nyquist_frequency_hz, 5.0)

    def test_sample_count_and_len(self) -> None:
        w = _make(n=3)
        self.assertEqual(w.sample_count, 3)
        self.assertEqual(len(w), 3)

    def test_time_axis(self) -> None:
        w = _make(n=4, dt_seconds=0.5)
        np.testing.assert_allclose(w.time_axis(), [0.0, 0.5, 1.0, 1.5])


class TestSpecCompliance8FromComponentsAndPoseRoundTrip(unittest.TestCase):
    """§Compliance 8: component_waveforms nested tuple round-trips; from_poses -> w[i]
    recovers an equal SpatialPose for each i."""

    def test_component_waveforms_field_order(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 2.0, 3.0)], [Quaternion.from_components(0.5, 0.5, 0.5, 0.5)]
        )
        components = w.component_waveforms
        self.assertEqual(components.position.x[0], 1.0)
        self.assertEqual(components.position.y[0], 2.0)
        self.assertEqual(components.position.z[0], 3.0)
        self.assertEqual(components.quaternion.w[0], 0.5)
        self.assertEqual(components.quaternion.x[0], 0.5)
        self.assertEqual(components.quaternion.y[0], 0.5)
        self.assertEqual(components.quaternion.z[0], 0.5)

    def test_component_waveforms_share_dt_and_t0(self) -> None:
        w = _make(n=3, dt_seconds=0.25, t0_seconds=3.0)
        components = w.component_waveforms
        for component in (
            components.position.x,
            components.position.y,
            components.position.z,
            components.quaternion.w,
            components.quaternion.x,
            components.quaternion.y,
            components.quaternion.z,
        ):
            self.assertEqual(component.dt, w.dt)
            self.assertEqual(component.t0, w.t0)

    def test_pose_round_trip_from_poses_then_index(self) -> None:
        poses = _make_poses(n=5)
        w = WaveformSpatialPose.from_poses(poses, dt_seconds=0.1, t0_seconds=1.0)
        for i, pose in enumerate(poses):
            self.assertEqual(w[i], pose)

    def test_position_waveform_matches_positions_array(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=1.0)
        pw = w.position_waveform
        self.assertIsInstance(pw, WaveformPosition)
        np.testing.assert_array_equal(pw.positions_array, w.positions_array)
        self.assertEqual(pw.dt, w.dt)
        self.assertEqual(pw.t0, w.t0)

    def test_quaternion_waveform_matches_quaternions_array(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=1.0)
        qw = w.quaternion_waveform
        self.assertIsInstance(qw, WaveformQuaternion)
        np.testing.assert_array_equal(qw.quaternions_array, w.quaternions_array)
        self.assertEqual(qw.dt, w.dt)
        self.assertEqual(qw.t0, w.t0)

    def test_from_waveforms_of_own_slices_recovers_equal_waveform(self) -> None:
        """Acceptance criterion: from_waveforms(w.position_waveform, w.quaternion_waveform) == w."""
        w = _make(n=4, dt_seconds=0.2, t0_seconds=5.0)
        rebuilt = WaveformSpatialPose.from_waveforms(w.position_waveform, w.quaternion_waveform)
        self.assertEqual(rebuilt, w)

    def test_from_components_round_trips_against_from_poses(self) -> None:
        w = _make(n=5, dt_seconds=0.25, t0_seconds=3.0)
        components = w.component_waveforms
        rebuilt = WaveformSpatialPose.from_components(
            components.position.x,
            components.position.y,
            components.position.z,
            components.quaternion.w,
            components.quaternion.x,
            components.quaternion.y,
            components.quaternion.z,
        )
        self.assertEqual(rebuilt, w)

    def test_from_components_mismatched_length_raises_value_error(self) -> None:
        short = WaveformPosition([Position(1.0, 2.0, 3.0)]).component_waveforms
        w = _make(n=3)
        components = w.component_waveforms
        with self.assertRaises(ValueError):
            WaveformSpatialPose.from_components(
                short.x,
                short.y,
                short.z,
                components.quaternion.w,
                components.quaternion.x,
                components.quaternion.y,
                components.quaternion.z,
            )

    def test_from_components_mismatched_dt_raises_value_error(self) -> None:
        w1 = _make(n=3, dt_seconds=1.0)
        w2 = _make(n=3, dt_seconds=2.0)
        c1 = w1.component_waveforms
        c2 = w2.component_waveforms
        with self.assertRaises(ValueError):
            WaveformSpatialPose.from_components(
                c1.position.x,
                c1.position.y,
                c1.position.z,
                c2.quaternion.w,
                c2.quaternion.x,
                c2.quaternion.y,
                c2.quaternion.z,
            )


class TestSpecCompliance9UnequalArrays(unittest.TestCase):
    """§Compliance 9: unequal parallel arrays -> is_valid False, sample_count = min."""

    def test_is_valid_true_for_equal_length(self) -> None:
        w = _make(n=3)
        self.assertTrue(w.is_valid)

    def test_is_valid_false_for_unequal_length(self) -> None:
        w = WaveformSpatialPose(np.zeros((3, 3)), np.zeros((5, 4)))
        self.assertFalse(w.is_valid)

    def test_sample_count_is_min_positions_longer(self) -> None:
        w = WaveformSpatialPose(np.zeros((7, 3)), np.zeros((4, 4)))
        self.assertEqual(w.sample_count, 4)
        self.assertEqual(len(w), 4)

    def test_sample_count_is_min_quaternions_longer(self) -> None:
        w = WaveformSpatialPose(np.zeros((2, 3)), np.zeros((9, 4)))
        self.assertEqual(w.sample_count, 2)
        self.assertEqual(len(w), 2)

    def test_direct_array_manipulation_produces_unequal_state(self) -> None:
        """Directly mutating the private arrays (as the chunk doc anticipates) also
        exercises is_valid/sample_count."""
        w = _make(n=5)
        w._positions = w._positions[:2]  # noqa: SLF001
        self.assertFalse(w.is_valid)
        self.assertEqual(w.sample_count, 2)
        self.assertEqual(len(w), 2)

    def test_from_poses_produces_valid_instance(self) -> None:
        w = WaveformSpatialPose.from_poses(_make_poses(n=4))
        self.assertTrue(w.is_valid)

    def test_from_waveforms_produces_valid_instance(self) -> None:
        w = _make(n=4)
        rebuilt = WaveformSpatialPose.from_waveforms(w.position_waveform, w.quaternion_waveform)
        self.assertTrue(rebuilt.is_valid)


class TestSpecCompliance9IndexingRespectsSampleCount(unittest.TestCase):
    """Post-audit C-4/C-5: negative indexing, ``get``, and ``pop`` must resolve
    against ``sample_count`` (the valid prefix), not each raw array's own
    length, on a deliberately unequal-length instance (3 positions, 2
    quaternions, ``sample_count == 2``)."""

    def _make_unequal(self) -> WaveformSpatialPose:
        positions = [Position(0.0, 0.0, 0.0), Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0)]
        quaternions = [Quaternion.identity(), Quaternion.from_components(0.0, 1.0, 0.0, 0.0)]
        return WaveformSpatialPose(positions, quaternions)

    def test_negative_index_agrees_with_sample_count_bound_positive_index(self) -> None:
        w = self._make_unequal()
        self.assertEqual(w.sample_count, 2)
        self.assertEqual(w[-1], w[1])

    def test_negative_index_agrees_with_get(self) -> None:
        w = self._make_unequal()
        self.assertEqual(w[-1], w.get(-1))

    def test_index_past_sample_count_raises_index_error_even_if_longer_array_has_it(
        self,
    ) -> None:
        w = self._make_unequal()
        with self.assertRaises(IndexError):
            _ = w[2]

    def test_pop_negative_removes_sample_count_bound_sample_from_both_arrays(self) -> None:
        w = self._make_unequal()
        popped = w.pop(-1)
        self.assertEqual(
            popped,
            SpatialPose(
                Position(1.0, 1.0, 1.0), Quaternion.from_components(0.0, 1.0, 0.0, 0.0)
            ),
        )
        self.assertEqual(w.sample_count, 1)
        self.assertEqual(len(w.positions_array), 2)
        self.assertEqual(len(w.quaternions_array), 1)


class TestElementAccess(unittest.TestCase):
    def test_index_returns_spatial_pose_equal_to_stored_row(self) -> None:
        w = _make(n=3)
        self.assertEqual(w[1], _pose(1))

    def test_slice_returns_waveform_spatial_pose(self) -> None:
        w = _make(n=5, dt_seconds=0.1)
        sliced = w[1:3]
        self.assertIsInstance(sliced, WaveformSpatialPose)
        self.assertEqual(len(sliced), 2)
        self.assertEqual(sliced[0], _pose(1))

    def test_slice_t0_shift_is_attosecond_exact(self) -> None:
        w = _make(n=5, dt_seconds=0.1)
        sliced = w[2:4]
        self.assertEqual(sliced.t0 - w.t0, w.dt * 2)

    def test_slice_step_not_one_raises(self) -> None:
        w = _make(n=4)
        with self.assertRaises(ValueError):
            _ = w[0:4:2]

    def test_get_in_range(self) -> None:
        w = _make(n=3)
        self.assertEqual(w.get(1), _pose(1))

    def test_get_out_of_range_returns_none(self) -> None:
        w = _make(n=3)
        self.assertIsNone(w.get(10))
        self.assertIsNone(w.get(-10))

    def test_iteration_yields_spatial_poses(self) -> None:
        w = _make(n=3)
        materialized = list(w)
        self.assertEqual(materialized, _make_poses(n=3))

    def test_materialized_poses_are_independent_objects(self) -> None:
        w = _make(n=1)
        p1 = w[0]
        p1.position.x = 99.0
        p2 = w[0]
        self.assertEqual(p2.position.x, 0.0)


class TestAreAllUnit(unittest.TestCase):
    def test_all_positions_unit_true(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 0.0, 0.0), Position(0.0, 1.0, 0.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        self.assertTrue(w.are_all_positions_unit)

    def test_all_positions_unit_false(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 0.0, 0.0), Position(2.0, 0.0, 0.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        self.assertFalse(w.are_all_positions_unit)

    def test_all_quaternions_unit_true(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 0.0, 0.0), Position(0.0, 1.0, 0.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        self.assertTrue(w.are_all_quaternions_unit)

    def test_all_quaternions_unit_false(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 0.0, 0.0)], [Quaternion.from_components(2.0, 0.0, 0.0, 0.0)]
        )
        self.assertFalse(w.are_all_quaternions_unit)

    def test_all_unit_true_on_empty(self) -> None:
        w = WaveformSpatialPose([], [])
        self.assertTrue(w.are_all_positions_unit)
        self.assertTrue(w.are_all_quaternions_unit)


class TestNormalize(unittest.TestCase):
    def test_normalize_in_place_normalizes_both_arrays(self) -> None:
        w = WaveformSpatialPose(
            [Position(2.0, 0.0, 0.0)], [Quaternion.from_components(2.0, 0.0, 0.0, 0.0)]
        )
        w.normalize()
        np.testing.assert_allclose(w.positions_array, [[1.0, 0.0, 0.0]])
        np.testing.assert_allclose(w.quaternions_array, [[1.0, 0.0, 0.0, 0.0]])

    def test_normalized_returns_copy(self) -> None:
        w = WaveformSpatialPose(
            [Position(2.0, 0.0, 0.0)], [Quaternion.from_components(2.0, 0.0, 0.0, 0.0)]
        )
        result = w.normalized()
        np.testing.assert_allclose(result.positions_array, [[1.0, 0.0, 0.0]])
        np.testing.assert_allclose(w.positions_array, [[2.0, 0.0, 0.0]])

    def test_normalize_zero_position_raises_value_error(self) -> None:
        w = WaveformSpatialPose([Position(0.0, 0.0, 0.0)], [Quaternion.identity()])
        with self.assertRaises(ValueError):
            w.normalize()

    def test_normalize_zero_quaternion_raises_value_error(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 0.0, 0.0)], [Quaternion.from_components(0.0, 0.0, 0.0, 0.0)]
        )
        with self.assertRaises(ValueError):
            w.normalize()

    def test_normalize_zero_position_leaves_quaternions_unmodified(self) -> None:
        """Position is checked first; a failure there must not mutate quaternions."""
        w = WaveformSpatialPose(
            [Position(0.0, 0.0, 0.0)], [Quaternion.from_components(2.0, 0.0, 0.0, 0.0)]
        )
        with self.assertRaises(ValueError):
            w.normalize()
        np.testing.assert_allclose(w.quaternions_array, [[2.0, 0.0, 0.0, 0.0]])


class TestSpecCompliance10VectorizedBulkOps(unittest.TestCase):
    """§Compliance 10: bulk ops never construct per-element objects; smoke-test at scale."""

    def test_normalize_smoke_test_large_n(self) -> None:
        n = 1_000_000
        rng = np.random.default_rng(0)
        positions = rng.standard_normal((n, 3)) + 1.0
        quaternions = rng.standard_normal((n, 4)) + 1.0
        w = WaveformSpatialPose(positions, quaternions)
        start = time.monotonic()
        w.normalize()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)

    def test_component_waveforms_smoke_test_large_n(self) -> None:
        n = 1_000_000
        rng = np.random.default_rng(0)
        positions = rng.standard_normal((n, 3))
        quaternions = rng.standard_normal((n, 4))
        w = WaveformSpatialPose(positions, quaternions)
        start = time.monotonic()
        components = w.component_waveforms
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(components.position.x), n)


class TestMutation(unittest.TestCase):
    def test_append(self) -> None:
        w = WaveformSpatialPose([Position(1.0, 1.0, 1.0)], [Quaternion.identity()])
        w.append(SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()))
        self.assertEqual(len(w), 2)
        self.assertEqual(w[1], SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()))

    def test_append_values(self) -> None:
        w = WaveformSpatialPose([Position(1.0, 1.0, 1.0)], [Quaternion.identity()])
        w.append_values(
            [
                SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()),
                SpatialPose(Position(3.0, 3.0, 3.0), Quaternion.identity()),
            ]
        )
        self.assertEqual(len(w), 3)

    def test_prepend_shifts_t0_back_by_one_dt(self) -> None:
        w = WaveformSpatialPose(
            [Position(2.0, 2.0, 2.0)], [Quaternion.identity()], dt_seconds=1.0
        )
        original_t0 = w.t0
        w.prepend(SpatialPose(Position(1.0, 1.0, 1.0), Quaternion.identity()))
        self.assertEqual(len(w), 2)
        self.assertEqual(w[0], SpatialPose(Position(1.0, 1.0, 1.0), Quaternion.identity()))
        self.assertEqual(original_t0 - w.t0, w.dt)

    def test_prepend_values_shifts_t0_back_by_k_dt(self) -> None:
        w = WaveformSpatialPose(
            [Position(3.0, 3.0, 3.0)], [Quaternion.identity()], dt_seconds=1.0
        )
        original_t0 = w.t0
        w.prepend_values(
            [
                SpatialPose(Position(1.0, 1.0, 1.0), Quaternion.identity()),
                SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()),
            ]
        )
        self.assertEqual(len(w), 3)
        self.assertEqual(original_t0 - w.t0, w.dt * 2)

    def test_insert(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(3.0, 3.0, 3.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        w.insert(1, SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()))
        self.assertEqual(len(w), 3)
        self.assertEqual(w[1], SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()))

    def test_replace(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        w.replace(1, SpatialPose(Position(99.0, 99.0, 99.0), Quaternion.identity()))
        self.assertEqual(w[1], SpatialPose(Position(99.0, 99.0, 99.0), Quaternion.identity()))

    def test_replace_range(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0), Position(3.0, 3.0, 3.0)],
            [Quaternion.identity(), Quaternion.identity(), Quaternion.identity()],
        )
        w.replace_range(
            slice(1, 3),
            [
                SpatialPose(Position(8.0, 8.0, 8.0), Quaternion.identity()),
                SpatialPose(Position(9.0, 9.0, 9.0), Quaternion.identity()),
            ],
        )
        self.assertEqual(w[1], SpatialPose(Position(8.0, 8.0, 8.0), Quaternion.identity()))
        self.assertEqual(w[2], SpatialPose(Position(9.0, 9.0, 9.0), Quaternion.identity()))

    def test_pop_default_removes_last(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        value = w.pop()
        self.assertEqual(value, SpatialPose(Position(2.0, 2.0, 2.0), Quaternion.identity()))
        self.assertEqual(len(w), 1)

    def test_pop_with_index(self) -> None:
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        value = w.pop(0)
        self.assertEqual(value, SpatialPose(Position(1.0, 1.0, 1.0), Quaternion.identity()))

    def test_pop_on_empty_raises_index_error(self) -> None:
        w = WaveformSpatialPose([], [])
        with self.assertRaises(IndexError):
            w.pop()

    def test_pop_out_of_range_raises_index_error(self) -> None:
        """C-14: only the empty case was previously pinned."""
        w = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0), Position(2.0, 2.0, 2.0)],
            [Quaternion.identity(), Quaternion.identity()],
        )
        with self.assertRaises(IndexError):
            w.pop(5)

    def test_clear_empties_both_arrays(self) -> None:
        w = WaveformSpatialPose([Position(1.0, 1.0, 1.0)], [Quaternion.identity()])
        w.clear()
        self.assertEqual(len(w), 0)
        self.assertEqual(w.positions_array.shape, (0, 3))
        self.assertEqual(w.quaternions_array.shape, (0, 4))


class TestSpecCompliance2ExtendConcatenateAndFromWaveforms(unittest.TestCase):
    """§Compliance 2: dt mismatch on extend/concatenate raises WaveformCompatibilityError;
    dt/count mismatch on from_waveforms raises ValueError."""

    def test_extend_equal_dt_appends(self) -> None:
        w1 = _make(n=2, dt_seconds=1.0)
        w2 = _make(n=2, dt_seconds=1.0)
        w1.extend(w2)
        self.assertEqual(len(w1), 4)

    def test_extend_dt_mismatch_raises(self) -> None:
        w1 = _make(n=2, dt_seconds=1.0)
        w2 = _make(n=2, dt_seconds=2.0)
        with self.assertRaises(WaveformCompatibilityError):
            w1.extend(w2)

    def test_concatenate_equal_dt(self) -> None:
        w1 = _make(n=2, dt_seconds=1.0)
        w2 = _make(n=2, dt_seconds=1.0)
        result = w1.concatenate(w2)
        self.assertEqual(len(result), 4)
        self.assertEqual(len(w1), 2)  # original unmodified

    def test_concatenate_dt_mismatch_raises(self) -> None:
        w1 = _make(n=2, dt_seconds=1.0)
        w2 = _make(n=2, dt_seconds=2.0)
        with self.assertRaises(WaveformCompatibilityError):
            w1.concatenate(w2)

    def test_from_waveforms_count_mismatch_raises_value_error(self) -> None:
        position_waveform = WaveformPosition([Position(1.0, 1.0, 1.0)], dt_seconds=1.0)
        quaternion_waveform = WaveformQuaternion(
            [Quaternion.identity(), Quaternion.identity()], dt_seconds=1.0
        )
        with self.assertRaises(ValueError):
            WaveformSpatialPose.from_waveforms(position_waveform, quaternion_waveform)

    def test_from_waveforms_dt_mismatch_raises_value_error(self) -> None:
        position_waveform = WaveformPosition([Position(1.0, 1.0, 1.0)], dt_seconds=1.0)
        quaternion_waveform = WaveformQuaternion([Quaternion.identity()], dt_seconds=2.0)
        with self.assertRaises(ValueError):
            WaveformSpatialPose.from_waveforms(position_waveform, quaternion_waveform)

    def test_from_waveforms_dt_mismatch_is_not_compatibility_error(self) -> None:
        """Design constraint 2: from_waveforms raises plain ValueError, not
        WaveformCompatibilityError (unlike extend/concatenate)."""
        position_waveform = WaveformPosition([Position(1.0, 1.0, 1.0)], dt_seconds=1.0)
        quaternion_waveform = WaveformQuaternion([Quaternion.identity()], dt_seconds=2.0)
        try:
            WaveformSpatialPose.from_waveforms(position_waveform, quaternion_waveform)
        except WaveformCompatibilityError:
            self.fail("from_waveforms raised WaveformCompatibilityError, expected plain ValueError")
        except ValueError:
            pass


class TestEquality(unittest.TestCase):
    def test_equal_positions_quaternions_dt_t0(self) -> None:
        w1 = _make(n=2, dt_seconds=0.5, t0_seconds=1.0)
        w2 = _make(n=2, dt_seconds=0.5, t0_seconds=1.0)
        self.assertEqual(w1, w2)

    def test_unequal_positions(self) -> None:
        w1 = WaveformSpatialPose([Position(1.0, 1.0, 1.0)], [Quaternion.identity()])
        w2 = WaveformSpatialPose([Position(2.0, 2.0, 2.0)], [Quaternion.identity()])
        self.assertNotEqual(w1, w2)

    def test_unequal_quaternions(self) -> None:
        w1 = WaveformSpatialPose([Position(1.0, 1.0, 1.0)], [Quaternion.identity()])
        w2 = WaveformSpatialPose(
            [Position(1.0, 1.0, 1.0)], [Quaternion.from_components(0.0, 1.0, 0.0, 0.0)]
        )
        self.assertNotEqual(w1, w2)

    def test_unequal_dt(self) -> None:
        w1 = _make(n=2, dt_seconds=0.5)
        w2 = _make(n=2, dt_seconds=1.0)
        self.assertNotEqual(w1, w2)

    def test_unequal_t0(self) -> None:
        w1 = _make(n=2, t0_seconds=0.0)
        w2 = _make(n=2, t0_seconds=1.0)
        self.assertNotEqual(w1, w2)

    def test_not_equal_to_other_type(self) -> None:
        w = _make(n=2)
        self.assertNotEqual(w, "not a waveform")

    def test_unhashable(self) -> None:
        w = _make(n=2)
        with self.assertRaises(TypeError):
            hash(w)


class TestArrayInterop(unittest.TestCase):
    """mathToolsArchitecture.md §API idioms: ``__array__`` so ``np.asarray(w)`` works.

    waveformCore.md §Array shape contract: ``(sample_count, 7)``, columns
    ``[x, y, z, w, i, j, k]``.
    """

    def test_asarray_shape_is_sample_count_by_7(self) -> None:
        w = _make(n=4)
        self.assertEqual(np.asarray(w).shape, (4, 7))

    def test_asarray_columns_are_position_then_quaternion(self) -> None:
        w = _make(n=3)
        arr = np.asarray(w)
        np.testing.assert_array_equal(arr[:, :3], w.positions_array)
        np.testing.assert_array_equal(arr[:, 3:], w.quaternions_array)

    def test_asarray_reads_the_sample_count_prefix_for_unequal_arrays(self) -> None:
        """Depends on chunk 49: sample_count is min(len(positions), len(quaternions))."""
        w = WaveformSpatialPose(np.zeros((5, 3)), np.zeros((2, 4)))
        arr = np.asarray(w)
        self.assertEqual(arr.shape, (2, 7))

    def test_asarray_returns_a_copy(self) -> None:
        w = _make(n=2)
        arr = np.asarray(w)
        arr[0, 0] = 99.0
        self.assertNotEqual(w[0].position.x, 99.0)

    def test_array_copy_false_raises_value_error(self) -> None:
        w = _make(n=2)
        with self.assertRaises(ValueError):
            np.array(w, copy=False)


class TestIsClose(unittest.TestCase):
    def test_true_within_tolerance(self) -> None:
        # index 1's x-component is nonzero (_pose(1) = Position(1, 2, 3)); atol
        # defaults to 0.0 (mirroring Position.isclose), so a perturbation at an
        # exact-zero component would not be "close" -- perturb a nonzero one.
        w1 = _make(n=3)
        positions = w1.positions_array
        positions[1, 0] += 1e-10
        w2 = WaveformSpatialPose(positions, w1.quaternions_array, dt=w1.dt, t0=w1.t0)
        self.assertTrue(w1.isclose(w2))

    def test_false_outside_tolerance(self) -> None:
        w1 = _make(n=3)
        positions = w1.positions_array
        positions[1, 0] += 1.0
        w2 = WaveformSpatialPose(positions, w1.quaternions_array, dt=w1.dt, t0=w1.t0)
        self.assertFalse(w1.isclose(w2))

    def test_false_on_differing_sample_count(self) -> None:
        w1 = _make(n=3)
        w2 = _make(n=4)
        self.assertFalse(w1.isclose(w2))

    def test_false_on_differing_dt(self) -> None:
        w1 = _make(n=3, dt_seconds=1.0)
        w2 = _make(n=3, dt_seconds=2.0)
        self.assertFalse(w1.isclose(w2))

    def test_double_cover_negated_quaternions_is_close(self) -> None:
        w = _make(n=3)
        negated = WaveformSpatialPose(
            w.positions_array, -w.quaternions_array, dt=w.dt, t0=w.t0
        )
        self.assertTrue(w.isclose(negated))

    def test_true_for_identical_waveform(self) -> None:
        w1 = _make(n=3)
        w2 = _make(n=3)
        self.assertTrue(w1.isclose(w2))


class TestRepr(unittest.TestCase):
    def test_repr_contains_sample_count(self) -> None:
        w = _make(n=3)
        self.assertIn("3", repr(w))
        self.assertIn("WaveformSpatialPose", repr(w))

    def test_repr_uses_min_sample_count_for_unequal_arrays(self) -> None:
        w = WaveformSpatialPose(np.zeros((5, 3)), np.zeros((2, 4)))
        self.assertIn("2", repr(w))


if __name__ == "__main__":
    unittest.main()
