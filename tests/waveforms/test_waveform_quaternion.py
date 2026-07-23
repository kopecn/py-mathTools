"""Unit tests for ``WaveformQuaternion`` (the quaternion time-series container).

Covers waveformCore.md §Aggregate containers with ``Element = Quaternion``,
and §Compliance requirements 1, 2, 8, 10 (see 16-waveform-quaternion.md for
the governing chunk).
"""

import time
import unittest

import numpy as np
from foundation_abc.math.waveformABCs import QuaternionWaveformABC
from foundationTypes.mathTypes.MathTypes import QuaternionWaveformType

from math_tools.errors import WaveformCompatibilityError
from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.spatial.quaternion import Quaternion
from math_tools.waveforms.waveform1d import Waveform1D
from math_tools.waveforms.waveform_quaternion import WaveformQuaternion


def _make(n: int = 3, dt_seconds: float = 1.0, t0_seconds: float = 0.0) -> WaveformQuaternion:
    quaternions = [
        Quaternion.from_components(float(i), float(i) * 2.0, float(i) * 3.0, float(i) * 4.0)
        for i in range(n)
    ]
    return WaveformQuaternion(quaternions, dt_seconds=dt_seconds, t0_seconds=t0_seconds)


class TestSpecCompliance1SerializationRoundTrip(unittest.TestCase):
    """§Compliance 1: to_dict round-trips through QuaternionWaveformType."""

    def test_round_trip_equal(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=10.0)
        wire = QuaternionWaveformType.from_dict(w.to_dict())
        self.assertEqual(w.to_dict(), wire.to_dict())

    def test_from_dict_reconstructs_equal_waveform(self) -> None:
        w = _make(n=3, dt_seconds=0.5, t0_seconds=10.0)
        w2 = WaveformQuaternion.from_dict(w.to_dict())
        self.assertEqual(w, w2)

    def test_isinstance_of_abc(self) -> None:
        self.assertIsInstance(_make(), QuaternionWaveformABC)

    def test_no_abstract_methods_remain(self) -> None:
        self.assertEqual(WaveformQuaternion.__abstractmethods__, frozenset())

    def test_wire_dict_is_per_element_w_x_y_z(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 2.0, 3.0, 4.0)])
        wire = w.to_dict()
        self.assertEqual(set(wire["quaternions"][0].keys()), {"w", "x", "y", "z"})
        self.assertEqual(
            wire["quaternions"][0],
            {"w": 1.0, "x": 2.0, "y": 3.0, "z": 4.0},
        )


class TestConstruction(unittest.TestCase):
    def test_from_quaternion_list(self) -> None:
        quaternions = [
            Quaternion.from_components(1.0, 2.0, 3.0, 4.0),
            Quaternion.from_components(5.0, 6.0, 7.0, 8.0),
        ]
        w = WaveformQuaternion(quaternions)
        np.testing.assert_array_equal(
            w.quaternions_array, np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]])
        )

    def test_from_raw_array(self) -> None:
        arr = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]])
        w = WaveformQuaternion(arr)
        np.testing.assert_array_equal(w.quaternions_array, arr)

    def test_quaternions_array_copied_not_aliased(self) -> None:
        arr = np.array([[1.0, 2.0, 3.0, 4.0]])
        w = WaveformQuaternion(arr)
        arr[0, 0] = 99.0
        self.assertEqual(w[0].w, 1.0)

    def test_empty_construction(self) -> None:
        w = WaveformQuaternion([])
        self.assertEqual(len(w), 0)
        self.assertEqual(w.quaternions_array.shape, (0, 4))

    def test_wrong_shape_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformQuaternion(np.array([[1.0, 2.0], [3.0, 4.0]]))

    def test_both_dt_and_dt_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            WaveformQuaternion([], dt=PrecisionTimeInterval.ONE_SECOND, dt_seconds=1.0)

    def test_both_t0_and_t0_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            WaveformQuaternion([], t0=PrecisionTimestamp.EPOCH, t0_seconds=1.0)

    def test_zero_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformQuaternion([], dt_seconds=0.0)

    def test_negative_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            WaveformQuaternion([], dt_seconds=-1.0)

    def test_default_dt_is_one_second(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 2.0, 3.0, 4.0)])
        self.assertEqual(w.dt, PrecisionTimeInterval.from_seconds(1.0))
        self.assertEqual(w.t0, PrecisionTimestamp.EPOCH)


class TestTimeAxis(unittest.TestCase):
    def test_duration_is_dt_times_n_minus_1(self) -> None:
        w = _make(n=4, dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.from_seconds(1.5))

    def test_duration_zero_for_single_sample(self) -> None:
        w = _make(n=1, dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.ZERO)

    def test_duration_zero_for_empty(self) -> None:
        w = WaveformQuaternion([], dt_seconds=0.5)
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


class TestSpecCompliance8FromComponents(unittest.TestCase):
    """§Compliance 8: component_waveforms -> from_components round-trips exactly,
    with the w-first field order pinned by name access."""

    def test_round_trip(self) -> None:
        w = _make(n=5, dt_seconds=0.25, t0_seconds=3.0)
        components = w.component_waveforms
        rebuilt = WaveformQuaternion.from_components(
            components.w, components.x, components.y, components.z
        )
        self.assertEqual(w, rebuilt)

    def test_component_waveforms_share_dt_and_t0(self) -> None:
        w = _make(n=3, dt_seconds=0.25, t0_seconds=3.0)
        components = w.component_waveforms
        for component in (components.w, components.x, components.y, components.z):
            self.assertEqual(component.dt, w.dt)
            self.assertEqual(component.t0, w.t0)

    def test_component_waveforms_field_order_is_w_x_y_z(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 2.0, 3.0, 4.0)])
        components = w.component_waveforms
        self.assertEqual(components.w[0], 1.0)
        self.assertEqual(components.x[0], 2.0)
        self.assertEqual(components.y[0], 3.0)
        self.assertEqual(components.z[0], 4.0)

    def test_mismatched_length_raises_value_error(self) -> None:
        w_wave = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        x = Waveform1D([1.0, 2.0, 3.0], dt_seconds=1.0)
        y = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        z = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            WaveformQuaternion.from_components(w_wave, x, y, z)

    def test_mismatched_dt_raises_value_error(self) -> None:
        w_wave = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        x = Waveform1D([1.0, 2.0], dt_seconds=2.0)
        y = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        z = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            WaveformQuaternion.from_components(w_wave, x, y, z)


class TestElementAccess(unittest.TestCase):
    def test_index_returns_quaternion_equal_to_stored_row(self) -> None:
        w = _make(n=3)
        self.assertEqual(w[1], Quaternion.from_components(1.0, 2.0, 3.0, 4.0))

    def test_slice_returns_waveform_quaternion(self) -> None:
        w = _make(n=5, dt_seconds=0.1)
        sliced = w[1:3]
        self.assertIsInstance(sliced, WaveformQuaternion)
        self.assertEqual(len(sliced), 2)
        self.assertEqual(sliced[0], Quaternion.from_components(1.0, 2.0, 3.0, 4.0))

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
        self.assertEqual(w.get(1), Quaternion.from_components(1.0, 2.0, 3.0, 4.0))

    def test_get_out_of_range_returns_none(self) -> None:
        w = _make(n=3)
        self.assertIsNone(w.get(10))
        self.assertIsNone(w.get(-10))

    def test_iteration_yields_quaternions(self) -> None:
        w = _make(n=3)
        materialized = list(w)
        self.assertEqual(
            materialized,
            [
                Quaternion.from_components(0.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(1.0, 2.0, 3.0, 4.0),
                Quaternion.from_components(2.0, 4.0, 6.0, 8.0),
            ],
        )

    def test_materialized_quaternions_are_fresh_objects(self) -> None:
        w = _make(n=1)
        q1 = w[0]
        q2 = w[0]
        self.assertEqual(q1, q2)
        self.assertIsNot(q1, q2)


class TestAreAllUnit(unittest.TestCase):
    def test_all_unit_true(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(0.0, 1.0, 0.0, 0.0),
            ]
        )
        self.assertTrue(w.are_all_unit)

    def test_all_unit_false(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(2.0, 0.0, 0.0, 0.0),
            ]
        )
        self.assertFalse(w.are_all_unit)

    def test_all_unit_true_on_empty(self) -> None:
        w = WaveformQuaternion([])
        self.assertTrue(w.are_all_unit)

    def test_are_all_unit_flips_after_appending_non_unit(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(0.0, 1.0, 0.0, 0.0),
            ]
        )
        self.assertTrue(w.are_all_unit)
        w.append(Quaternion.from_components(2.0, 0.0, 0.0, 0.0))
        self.assertFalse(w.are_all_unit)


class TestNormalize(unittest.TestCase):
    def test_normalize_in_place(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(2.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(0.0, 3.0, 0.0, 0.0),
            ]
        )
        w.normalize()
        np.testing.assert_allclose(
            w.quaternions_array, [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
        )

    def test_normalized_returns_copy(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(2.0, 0.0, 0.0, 0.0)])
        result = w.normalized()
        np.testing.assert_allclose(result.quaternions_array, [[1.0, 0.0, 0.0, 0.0]])
        # original left unmodified
        np.testing.assert_allclose(w.quaternions_array, [[2.0, 0.0, 0.0, 0.0]])

    def test_normalize_zero_row_raises_value_error(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 0.0, 0.0, 0.0),
                Quaternion.from_components(0.0, 0.0, 0.0, 0.0),
            ]
        )
        with self.assertRaises(ValueError):
            w.normalize()

    def test_normalized_zero_row_raises_value_error(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(0.0, 0.0, 0.0, 0.0)])
        with self.assertRaises(ValueError):
            w.normalized()


class TestSpecCompliance10VectorizedBulkOps(unittest.TestCase):
    """§Compliance 10: bulk ops never construct per-element objects; smoke-test at scale."""

    def test_normalize_smoke_test_large_n(self) -> None:
        n = 100_000
        rng = np.random.default_rng(0)
        arr = rng.standard_normal((n, 4)) + 1.0  # avoid zero rows
        w = WaveformQuaternion(arr)
        start = time.monotonic()
        w.normalize()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)

    def test_component_waveforms_smoke_test_large_n(self) -> None:
        n = 100_000
        rng = np.random.default_rng(0)
        arr = rng.standard_normal((n, 4))
        w = WaveformQuaternion(arr)
        start = time.monotonic()
        components = w.component_waveforms
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(components.w), n)


class TestMutation(unittest.TestCase):
    def test_append(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 1.0, 1.0, 1.0)])
        w.append(Quaternion.from_components(2.0, 2.0, 2.0, 2.0))
        self.assertEqual(
            list(w),
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ],
        )

    def test_append_values(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 1.0, 1.0, 1.0)])
        w.append_values(
            [
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
                Quaternion.from_components(3.0, 3.0, 3.0, 3.0),
            ]
        )
        self.assertEqual(len(w), 3)

    def test_prepend_shifts_t0_back_by_one_dt(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(2.0, 2.0, 2.0, 2.0)], dt_seconds=1.0)
        original_t0 = w.t0
        w.prepend(Quaternion.from_components(1.0, 1.0, 1.0, 1.0))
        self.assertEqual(
            list(w),
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ],
        )
        self.assertEqual(original_t0 - w.t0, w.dt)

    def test_prepend_values_shifts_t0_back_by_k_dt(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(3.0, 3.0, 3.0, 3.0)], dt_seconds=1.0)
        original_t0 = w.t0
        w.prepend_values(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ]
        )
        self.assertEqual(len(w), 3)
        self.assertEqual(original_t0 - w.t0, w.dt * 2)

    def test_insert(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(3.0, 3.0, 3.0, 3.0),
            ]
        )
        w.insert(1, Quaternion.from_components(2.0, 2.0, 2.0, 2.0))
        self.assertEqual(
            list(w),
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
                Quaternion.from_components(3.0, 3.0, 3.0, 3.0),
            ],
        )

    def test_replace(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ]
        )
        w.replace(1, Quaternion.from_components(99.0, 99.0, 99.0, 99.0))
        self.assertEqual(w[1], Quaternion.from_components(99.0, 99.0, 99.0, 99.0))

    def test_replace_range(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
                Quaternion.from_components(3.0, 3.0, 3.0, 3.0),
            ]
        )
        w.replace_range(
            slice(1, 3),
            [
                Quaternion.from_components(8.0, 8.0, 8.0, 8.0),
                Quaternion.from_components(9.0, 9.0, 9.0, 9.0),
            ],
        )
        self.assertEqual(
            list(w)[1:],
            [
                Quaternion.from_components(8.0, 8.0, 8.0, 8.0),
                Quaternion.from_components(9.0, 9.0, 9.0, 9.0),
            ],
        )

    def test_pop_default_removes_last(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ]
        )
        value = w.pop()
        self.assertEqual(value, Quaternion.from_components(2.0, 2.0, 2.0, 2.0))
        self.assertEqual(len(w), 1)

    def test_pop_with_index(self) -> None:
        w = WaveformQuaternion(
            [
                Quaternion.from_components(1.0, 1.0, 1.0, 1.0),
                Quaternion.from_components(2.0, 2.0, 2.0, 2.0),
            ]
        )
        value = w.pop(0)
        self.assertEqual(value, Quaternion.from_components(1.0, 1.0, 1.0, 1.0))

    def test_pop_on_empty_raises_index_error(self) -> None:
        w = WaveformQuaternion([])
        with self.assertRaises(IndexError):
            w.pop()

    def test_clear_empties(self) -> None:
        w = WaveformQuaternion([Quaternion.from_components(1.0, 1.0, 1.0, 1.0)])
        w.clear()
        self.assertEqual(len(w), 0)


class TestSpecCompliance2ExtendConcatenate(unittest.TestCase):
    """§Compliance 2: dt mismatch on extend/concatenate raises WaveformCompatibilityError."""

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


class TestEquality(unittest.TestCase):
    def test_equal_quaternions_dt_t0(self) -> None:
        w1 = _make(n=2, dt_seconds=0.5, t0_seconds=1.0)
        w2 = _make(n=2, dt_seconds=0.5, t0_seconds=1.0)
        self.assertEqual(w1, w2)

    def test_unequal_quaternions(self) -> None:
        w1 = WaveformQuaternion([Quaternion.from_components(1.0, 1.0, 1.0, 1.0)])
        w2 = WaveformQuaternion([Quaternion.from_components(2.0, 2.0, 2.0, 2.0)])
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


class TestRepr(unittest.TestCase):
    def test_repr_contains_sample_count(self) -> None:
        w = _make(n=3)
        self.assertIn("3", repr(w))
        self.assertIn("WaveformQuaternion", repr(w))


def _make_unit(n: int = 3, dt_seconds: float = 1.0, t0_seconds: float = 0.0) -> WaveformQuaternion:
    quaternions = [
        Quaternion.from_components(1.0, float(i) * 0.01, 0.0, 0.0).normalized() for i in range(n)
    ]
    return WaveformQuaternion(quaternions, dt_seconds=dt_seconds, t0_seconds=t0_seconds)


class TestArrayInterop(unittest.TestCase):
    """mathToolsArchitecture.md §API idioms: ``__array__`` so ``np.asarray(w)`` works."""

    def test_asarray_matches_quaternions_array(self) -> None:
        w = _make_unit(n=4)
        np.testing.assert_array_equal(np.asarray(w), w.quaternions_array)

    def test_asarray_shape_is_sample_count_by_4(self) -> None:
        w = _make_unit(n=4)
        self.assertEqual(np.asarray(w).shape, (4, 4))

    def test_asarray_returns_a_copy(self) -> None:
        w = _make_unit(n=2)
        arr = np.asarray(w)
        arr[0, 0] = 99.0
        self.assertNotEqual(w[0].w, 99.0)

    def test_array_copy_false_raises_value_error(self) -> None:
        w = _make_unit(n=2)
        with self.assertRaises(ValueError):
            np.array(w, copy=False)


class TestIsClose(unittest.TestCase):
    def test_true_within_tolerance(self) -> None:
        w1 = _make_unit(n=3)
        arr = w1.quaternions_array
        arr[0, 0] += 1e-12
        w2 = WaveformQuaternion(arr, dt=w1.dt, t0=w1.t0)
        self.assertTrue(w1.isclose(w2))

    def test_false_outside_tolerance(self) -> None:
        w1 = _make_unit(n=3)
        arr = w1.quaternions_array
        arr[0, 0] += 1.0
        w2 = WaveformQuaternion(arr, dt=w1.dt, t0=w1.t0)
        self.assertFalse(w1.isclose(w2))

    def test_false_on_differing_sample_count(self) -> None:
        w1 = _make_unit(n=3)
        w2 = _make_unit(n=4)
        self.assertFalse(w1.isclose(w2))

    def test_false_on_differing_dt(self) -> None:
        w1 = _make_unit(n=3, dt_seconds=1.0)
        w2 = _make_unit(n=3, dt_seconds=2.0)
        self.assertFalse(w1.isclose(w2))

    def test_double_cover_negated_waveform_is_close(self) -> None:
        w = _make_unit(n=3)
        negated = WaveformQuaternion(-w.quaternions_array, dt=w.dt, t0=w.t0)
        self.assertTrue(w.isclose(negated))

    def test_true_for_identical_waveform(self) -> None:
        w1 = _make_unit(n=3)
        w2 = _make_unit(n=3)
        self.assertTrue(w1.isclose(w2))


if __name__ == "__main__":
    unittest.main()
