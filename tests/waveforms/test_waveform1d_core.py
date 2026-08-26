"""Unit tests for ``Waveform1D`` (core container: no operators, no DSP).

Covers waveformCore.md §Compliance requirements 1, 3, 5, 6, 7, 11, plus
construction, time axis, statistics, indexing/slicing, value_at_*,
mutation, comparison, iteration/array interop, and generator coverage.
"""

import time
import unittest

import numpy as np
from foundationTypes.mathTypes.MathTypes import ScalarWaveformType

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.precision_time.precision_timestamp import PrecisionTimestamp
from math_tools.waveforms.waveform1d import Waveform1D


class TestSpecCompliance11Instantiability(unittest.TestCase):
    """§Compliance 11: bare construction, concreteness, array/iteration interop."""

    def test_bare_construction_with_no_time_args(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(w.dt, PrecisionTimeInterval.from_seconds(1.0))
        self.assertEqual(w.t0, PrecisionTimestamp.EPOCH)

    def test_no_abstract_methods_remain(self) -> None:
        self.assertEqual(Waveform1D.__abstractmethods__, frozenset())

    def test_np_asarray_equals_samples(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(np.asarray(w), np.array([1.0, 2.0, 3.0]))

    def test_iteration_yields_samples(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(list(w), [1.0, 2.0, 3.0])

    def test_np_asarray_then_mean_interop(self) -> None:
        # np.mean(w) directly hits numpy's `a.mean` duck-typing fast path,
        # which collides with our spec-mandated `mean` *property* (not a
        # method) -- np.asarray(w) is the documented interop surface
        # (§Compliance 11), not a bare np.mean(w) call.
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(float(np.mean(np.asarray(w))), 2.0)

    def test_array_copy_false_raises_value_error(self) -> None:
        # NumPy 2's __array__(copy=...) protocol: a copy is unavoidable here
        # (the returned array must not alias the mutable backing store), so
        # copy=False must raise rather than silently copy anyway (finding C-7).
        w = Waveform1D([1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            np.array(w, copy=False)

    def test_waveform_abc_accessor_returns_samples_as_float_list(self) -> None:
        """C-11: the ABC-required ``waveform`` accessor (waveformCore.md's
        load-bearing O(n) materialization path) has no direct test elsewhere
        -- only exercised indirectly via to_dict."""
        w = Waveform1D([1.0, 2.0, 3.0])
        result = w.waveform
        self.assertEqual(result, [1.0, 2.0, 3.0])
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(value, float) for value in result))


class TestSpecCompliance1SerializationRoundTrip(unittest.TestCase):
    """§Compliance 1: to_dict round-trips through ScalarWaveformType."""

    def test_round_trip_equal(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5, t0_seconds=10.0)
        wire = ScalarWaveformType.from_dict(w.to_dict())
        self.assertEqual(w.to_dict(), wire.to_dict())

    def test_from_dict_reconstructs_equal_waveform(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5, t0_seconds=10.0)
        w2 = Waveform1D.from_dict(w.to_dict())
        self.assertEqual(w, w2)

    def test_isinstance_of_abc(self) -> None:
        from foundation_abc.math.waveformABCs import Waveform1dABC

        self.assertIsInstance(Waveform1D([1.0]), Waveform1dABC)


class TestConstruction(unittest.TestCase):
    def test_integer_dtype_preserved(self) -> None:
        w = Waveform1D(np.array([1, 2, 3], dtype=np.int32))
        self.assertEqual(w.values.dtype, np.int32)

    def test_float_dtype_is_float64(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(w.values.dtype, np.float64)

    def test_python_list_of_ints_preserves_integer_dtype(self) -> None:
        w = Waveform1D([1, 2, 3])
        self.assertTrue(np.issubdtype(w.values.dtype, np.integer))

    def test_values_copied_not_aliased(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        w = Waveform1D(arr)
        arr[0] = 99.0
        self.assertEqual(w[0], 1.0)

    def test_non_1d_raises(self) -> None:
        with self.assertRaises(ValueError):
            Waveform1D([[1.0, 2.0], [3.0, 4.0]])

    def test_both_dt_and_dt_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Waveform1D([1.0], dt=PrecisionTimeInterval.ONE_SECOND, dt_seconds=1.0)

    def test_both_t0_and_t0_seconds_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Waveform1D([1.0], t0=PrecisionTimestamp.EPOCH, t0_seconds=1.0)

    def test_zero_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Waveform1D([1.0], dt_seconds=0.0)

    def test_negative_dt_seconds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Waveform1D([1.0], dt_seconds=-1.0)

    def test_dt_seconds_sets_dt(self) -> None:
        w = Waveform1D([1.0, 2.0], dt_seconds=0.25)
        self.assertEqual(w.dt, PrecisionTimeInterval.from_seconds(0.25))

    def test_t0_seconds_sets_t0(self) -> None:
        w = Waveform1D([1.0, 2.0], t0_seconds=5.0)
        self.assertEqual(w.t0, PrecisionTimestamp.EPOCH + PrecisionTimeInterval.from_seconds(5.0))

    def test_negative_t0_seconds_is_pre_epoch(self) -> None:
        w = Waveform1D([1.0], t0_seconds=-2.0)
        self.assertEqual(w.t0, PrecisionTimestamp.EPOCH - PrecisionTimeInterval.from_seconds(2.0))


class TestTimeAxis(unittest.TestCase):
    def test_duration_is_dt_times_n_minus_1(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0], dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.from_seconds(1.5))

    def test_duration_zero_for_single_sample(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.ZERO)

    def test_duration_zero_for_empty(self) -> None:
        w = Waveform1D([], dt_seconds=0.5)
        self.assertEqual(w.duration, PrecisionTimeInterval.ZERO)

    def test_duration_seconds(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=2.0)
        self.assertEqual(w.duration_seconds, 4.0)

    def test_sampling_frequency_hz(self) -> None:
        w = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        self.assertAlmostEqual(w.sampling_frequency_hz, 10.0)

    def test_nyquist_frequency_hz(self) -> None:
        w = Waveform1D([1.0, 2.0], dt_seconds=0.1)
        self.assertAlmostEqual(w.nyquist_frequency_hz, 5.0)

    def test_sample_count_and_len(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(w.sample_count, 3)
        self.assertEqual(len(w), 3)

    def test_time_axis(self) -> None:
        w = Waveform1D([0.0, 0.0, 0.0, 0.0], dt_seconds=0.5)
        np.testing.assert_allclose(w.time_axis(), [0.0, 0.5, 1.0, 1.5])


class TestSpecCompliance5Statistics(unittest.TestCase):
    """§Compliance 5: stats match numpy references; variance/rms pinned literally."""

    def setUp(self) -> None:
        self.w = Waveform1D([1.0, 2.0, 3.0, 4.0])

    def test_minimum(self) -> None:
        self.assertEqual(self.w.minimum, 1.0)

    def test_maximum(self) -> None:
        self.assertEqual(self.w.maximum, 4.0)

    def test_peak_to_peak(self) -> None:
        self.assertEqual(self.w.peak_to_peak, 3.0)

    def test_mean(self) -> None:
        self.assertEqual(self.w.mean, 2.5)

    def test_sum(self) -> None:
        self.assertEqual(self.w.sum, 10.0)

    def test_absolute_sum(self) -> None:
        w = Waveform1D([-1.0, 2.0, -3.0])
        self.assertEqual(w.absolute_sum, 6.0)

    def test_rms_matches_sqrt_mean_square(self) -> None:
        expected = float(np.sqrt(np.mean(np.square([1.0, 2.0, 3.0, 4.0]))))
        rms = self.w.rms
        assert rms is not None
        self.assertAlmostEqual(rms, expected)

    def test_variance_is_population_variance_ddof0_literal(self) -> None:
        # mean = 2.5; squared deviations: 2.25, 0.25, 0.25, 2.25; population
        # variance (ddof=0) = 5.0 / 4 = 1.25. This is the pinned choice
        # (waveformCore.md §Compliance 5) -- ddof=1 (sample variance) would
        # give 5.0 / 3 = 1.6666... instead.
        self.assertEqual(self.w.variance, 1.25)

    def test_standard_deviation_is_sqrt_of_population_variance(self) -> None:
        standard_deviation = self.w.standard_deviation
        assert standard_deviation is not None
        self.assertAlmostEqual(standard_deviation, float(np.sqrt(1.25)))

    def test_stats_none_on_empty(self) -> None:
        empty = Waveform1D([])
        self.assertIsNone(empty.minimum)
        self.assertIsNone(empty.maximum)
        self.assertIsNone(empty.peak_to_peak)
        self.assertIsNone(empty.mean)
        self.assertIsNone(empty.rms)
        self.assertIsNone(empty.standard_deviation)
        self.assertIsNone(empty.variance)
        self.assertIsNone(empty.sum)
        self.assertIsNone(empty.absolute_sum)


class TestSpecCompliance3Slicing(unittest.TestCase):
    """§Compliance 3: slice t0 adjusts by exactly start * dt (attosecond-exact)."""

    def test_slice_t0_shift_is_attosecond_exact(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], dt_seconds=0.1)
        sliced = w[2:5]
        self.assertEqual(sliced.t0 - w.t0, w.dt * 2)

    def test_slice_returns_correct_values(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        sliced = w[2:5]
        self.assertEqual(list(sliced), [2.0, 3.0, 4.0])

    def test_slice_preserves_dt(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0], dt_seconds=0.25)
        sliced = w[1:3]
        self.assertEqual(sliced.dt, w.dt)

    def test_slice_step_not_one_raises(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            _ = w[0:4:2]

    def test_index_returns_scalar(self) -> None:
        w = Waveform1D([10.0, 20.0, 30.0])
        self.assertEqual(w[1], 20.0)


class TestSubsetTime(unittest.TestCase):
    def test_subset_time_with_floats(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0], dt_seconds=1.0)
        sub = w.subset_time(1.0, 3.0)
        self.assertEqual(list(sub), [1.0, 2.0])

    def test_subset_time_with_timestamps(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0], dt_seconds=1.0)
        start = w.t0 + PrecisionTimeInterval.from_seconds(1.0)
        end = w.t0 + PrecisionTimeInterval.from_seconds(3.0)
        sub = w.subset_time(start, end)
        self.assertEqual(list(sub), [1.0, 2.0])

    def test_empty_range_raises(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.subset_time(2.0, 2.0)

    def test_invalid_range_raises(self) -> None:
        w = Waveform1D([0.0, 1.0, 2.0], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.subset_time(2.0, 1.0)

    def test_start_before_t0_clamps_to_first_sample(self) -> None:
        """C-13: a start_time before t0 must clamp rather than raise/skip samples."""
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0], dt_seconds=1.0)
        sub = w.subset_time(-5.0, 2.0)
        self.assertEqual(list(sub), [0.0, 1.0])

    def test_end_past_span_clamps_to_last_sample(self) -> None:
        """C-13: an end_time past the waveform's span must clamp to the end."""
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0], dt_seconds=1.0)
        sub = w.subset_time(2.0, 100.0)
        self.assertEqual(list(sub), [2.0, 3.0, 4.0])

    def test_both_bounds_outside_span_returns_everything(self) -> None:
        """C-13: both bounds clamp simultaneously."""
        w = Waveform1D([0.0, 1.0, 2.0, 3.0, 4.0], dt_seconds=1.0)
        sub = w.subset_time(-100.0, 100.0)
        self.assertEqual(list(sub), [0.0, 1.0, 2.0, 3.0, 4.0])


class TestValueAt(unittest.TestCase):
    def test_value_at_index_exact_sample(self) -> None:
        w = Waveform1D([0.0, 10.0, 20.0])
        self.assertEqual(w.value_at_index(1.0), 10.0)

    def test_value_at_index_interpolates(self) -> None:
        w = Waveform1D([0.0, 10.0, 20.0])
        self.assertEqual(w.value_at_index(0.5), 5.0)

    def test_value_at_index_out_of_range_raises(self) -> None:
        w = Waveform1D([0.0, 10.0, 20.0])
        with self.assertRaises(ValueError):
            w.value_at_index(-0.1)
        with self.assertRaises(ValueError):
            w.value_at_index(2.1)

    def test_value_at_index_empty_raises(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(ValueError):
            w.value_at_index(0.0)

    def test_spec_compliance_6_midpoint_returns_average(self) -> None:
        """§Compliance 6: value_at_time midpoint between two samples returns their average."""
        w = Waveform1D([0.0, 10.0], dt_seconds=1.0)
        self.assertEqual(w.value_at_time(0.5), 5.0)

    def test_value_at_time_exact_sample(self) -> None:
        w = Waveform1D([0.0, 10.0, 20.0], dt_seconds=2.0)
        self.assertEqual(w.value_at_time(2.0), 10.0)

    def test_value_at_time_out_of_range_raises(self) -> None:
        w = Waveform1D([0.0, 10.0], dt_seconds=1.0)
        with self.assertRaises(ValueError):
            w.value_at_time(5.0)

    def test_value_at_time_with_timestamp(self) -> None:
        w = Waveform1D([0.0, 10.0], dt_seconds=1.0)
        t = w.t0 + PrecisionTimeInterval.from_seconds(0.5)
        self.assertEqual(w.value_at_time(t), 5.0)


class TestSpecCompliance7Mutation(unittest.TestCase):
    """§Compliance 7: mutation verbs match stdlib list semantics."""

    def test_append(self) -> None:
        w = Waveform1D([1.0, 2.0])
        w.append(3.0)
        self.assertEqual(list(w), [1.0, 2.0, 3.0])

    def test_append_values(self) -> None:
        w = Waveform1D([1.0])
        w.append_values([2.0, 3.0])
        self.assertEqual(list(w), [1.0, 2.0, 3.0])

    def test_prepend_shifts_t0_back_by_one_dt(self) -> None:
        w = Waveform1D([2.0, 3.0], dt_seconds=1.0)
        original_t0 = w.t0
        w.prepend(1.0)
        self.assertEqual(list(w), [1.0, 2.0, 3.0])
        self.assertEqual(original_t0 - w.t0, w.dt)

    def test_prepend_values_shifts_t0_back_by_k_dt(self) -> None:
        w = Waveform1D([3.0, 4.0], dt_seconds=1.0)
        original_t0 = w.t0
        w.prepend_values([1.0, 2.0])
        self.assertEqual(list(w), [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(original_t0 - w.t0, w.dt * 2)

    def test_insert(self) -> None:
        w = Waveform1D([1.0, 3.0])
        w.insert(1, 2.0)
        self.assertEqual(list(w), [1.0, 2.0, 3.0])

    def test_replace(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        w.replace(1, 99.0)
        self.assertEqual(list(w), [1.0, 99.0, 3.0])

    def test_replace_range(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 4.0])
        w.replace_range(slice(1, 3), [8.0, 9.0])
        self.assertEqual(list(w), [1.0, 8.0, 9.0, 4.0])

    def test_replace_range_longer_replacement_raises_value_error(self) -> None:
        """C-12: waveformCore.md §Compliance 7 says mutation verbs match
        stdlib list semantics, but the storage is numpy, not a Python list.
        A Python list slice-assignment resizes silently
        (``[1,2,3,4][1:3] = [8,9,10]`` -> ``[1,8,9,10,4]``); this numpy-backed
        implementation instead requires the replacement to broadcast onto the
        slice's length, raising ``ValueError`` when it cannot -- pinned here
        as the actual (numpy, not stdlib-list) semantics."""
        w = Waveform1D([1.0, 2.0, 3.0, 4.0])
        with self.assertRaises(ValueError):
            w.replace_range(slice(1, 3), [8.0, 9.0, 10.0])

    def test_replace_range_single_element_broadcasts_not_shrinks(self) -> None:
        """C-12: a single-element replacement *broadcasts* across the slice
        (numpy assignment semantics) rather than shrinking the waveform the
        way ``[1,2,3,4][1:3] = [8]`` (-> ``[1,8,4]``) would under stdlib list
        semantics."""
        w = Waveform1D([1.0, 2.0, 3.0, 4.0])
        w.replace_range(slice(1, 3), [8.0])
        self.assertEqual(list(w), [1.0, 8.0, 8.0, 4.0])

    def test_pop_default_removes_last(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        value = w.pop()
        self.assertEqual(value, 3.0)
        self.assertEqual(list(w), [1.0, 2.0])

    def test_pop_with_index(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        value = w.pop(0)
        self.assertEqual(value, 1.0)
        self.assertEqual(list(w), [2.0, 3.0])

    def test_pop_on_empty_raises_index_error(self) -> None:
        w = Waveform1D([])
        with self.assertRaises(IndexError):
            w.pop()

    def test_pop_out_of_range_raises_index_error(self) -> None:
        w = Waveform1D([1.0, 2.0])
        with self.assertRaises(IndexError):
            w.pop(5)

    def test_clear_empties(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        w.clear()
        self.assertEqual(list(w), [])
        self.assertEqual(len(w), 0)

    def test_append_float_onto_integer_waveform_truncates_to_dtype(self) -> None:
        """C-6: ``append``/``insert`` cast the new value to the storage
        dtype (numpy's ``np.asarray(value, dtype=...)`` semantics), so
        appending a float onto an int waveform silently truncates. Pinning
        the current (confirmed intentional) behavior, not a defect: mutation
        verbs preserve dtype exactly, unlike the in-place arithmetic
        operators (see TestInPlaceOperatorDtypePromotion in
        test_waveform1d_operators.py) which promote it."""
        w = Waveform1D(np.array([1, 2, 3], dtype=np.int64))
        w.append(9.7)
        self.assertEqual(w.values.dtype, np.int64)
        self.assertEqual(list(w), [1, 2, 3, 9])

    def test_insert_float_onto_integer_waveform_truncates_to_dtype(self) -> None:
        w = Waveform1D(np.array([1, 2, 3], dtype=np.int64))
        w.insert(1, 9.7)
        self.assertEqual(w.values.dtype, np.int64)
        self.assertEqual(list(w), [1, 9, 2, 3])


class TestSpecCompliance10VectorizedBulkOps(unittest.TestCase):
    """§Compliance 10: bulk ops never construct per-element objects;
    smoke-test at 1e6 samples, guarding the vectorized design."""

    def test_arithmetic_and_stats_smoke_test_large_n(self) -> None:
        n = 1_000_000
        rng = np.random.default_rng(0)
        w = Waveform1D(rng.standard_normal(n), dt_seconds=0.001)
        start = time.monotonic()
        result = (w + 1.0) * 2.0
        _ = result.mean
        _ = result.rms
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(result), n)


class TestEquality(unittest.TestCase):
    def test_equal_samples_dt_t0(self) -> None:
        w1 = Waveform1D([1.0, 2.0], dt_seconds=0.5, t0_seconds=1.0)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=0.5, t0_seconds=1.0)
        self.assertEqual(w1, w2)

    def test_unequal_samples(self) -> None:
        w1 = Waveform1D([1.0, 2.0])
        w2 = Waveform1D([1.0, 3.0])
        self.assertNotEqual(w1, w2)

    def test_unequal_dt(self) -> None:
        w1 = Waveform1D([1.0, 2.0], dt_seconds=0.5)
        w2 = Waveform1D([1.0, 2.0], dt_seconds=1.0)
        self.assertNotEqual(w1, w2)

    def test_unequal_t0(self) -> None:
        w1 = Waveform1D([1.0, 2.0], t0_seconds=0.0)
        w2 = Waveform1D([1.0, 2.0], t0_seconds=1.0)
        self.assertNotEqual(w1, w2)

    def test_not_equal_to_other_type(self) -> None:
        w = Waveform1D([1.0, 2.0])
        self.assertNotEqual(w, "not a waveform")

    def test_unhashable(self) -> None:
        w = Waveform1D([1.0, 2.0])
        with self.assertRaises(TypeError):
            hash(w)


class TestRepr(unittest.TestCase):
    def test_repr_contains_sample_count(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertIn("3", repr(w))
        self.assertIn("Waveform1D", repr(w))


class TestGenerators(unittest.TestCase):
    def test_sine_matches_np_sin(self) -> None:
        w = Waveform1D.sine(n=100, frequency=5.0, dt_seconds=0.001)
        t = np.arange(100) * 0.001
        expected = np.sin(2.0 * np.pi * 5.0 * t)
        np.testing.assert_allclose(w.values, expected, atol=1e-12)

    def test_cosine_matches_np_cos(self) -> None:
        w = Waveform1D.cosine(n=50, frequency=2.0, dt_seconds=0.01)
        t = np.arange(50) * 0.01
        expected = np.cos(2.0 * np.pi * 2.0 * t)
        np.testing.assert_allclose(w.values, expected, atol=1e-12)

    def test_white_noise_seeded_is_reproducible(self) -> None:
        w1 = Waveform1D.white_noise(n=20, seed=42)
        w2 = Waveform1D.white_noise(n=20, seed=42)
        np.testing.assert_array_equal(w1.values, w2.values)

    def test_white_noise_different_seeds_differ(self) -> None:
        w1 = Waveform1D.white_noise(n=20, seed=1)
        w2 = Waveform1D.white_noise(n=20, seed=2)
        self.assertFalse(np.array_equal(w1.values, w2.values))

    def test_impulse_sums_to_amplitude(self) -> None:
        w = Waveform1D.impulse(n=10, amplitude=3.0, impulse_index=4)
        self.assertEqual(float(np.sum(w.values)), 3.0)
        self.assertEqual(w.values[4], 3.0)

    def test_constant(self) -> None:
        w = Waveform1D.constant(n=5, value=7.0)
        np.testing.assert_array_equal(w.values, np.full(5, 7.0))

    def test_linear_ramp(self) -> None:
        w = Waveform1D.linear_ramp(n=5, start_value=0.0, end_value=4.0)
        np.testing.assert_allclose(w.values, [0.0, 1.0, 2.0, 3.0, 4.0])

    def test_linear_ramp_single_sample_uses_start_value(self) -> None:
        w = Waveform1D.linear_ramp(n=1, start_value=2.0, end_value=8.0)
        np.testing.assert_allclose(w.values, [2.0])

    def test_polynomial_horner(self) -> None:
        # 1 + 2t + 3t^2, dt=1.0 -> t = [0, 1, 2]
        w = Waveform1D.polynomial(n=3, coefficients=[1.0, 2.0, 3.0], dt_seconds=1.0)
        np.testing.assert_allclose(w.values, [1.0, 6.0, 17.0])

    def test_polynomial_empty_coefficients_is_zero(self) -> None:
        w = Waveform1D.polynomial(n=4, coefficients=[])
        np.testing.assert_allclose(w.values, [0.0, 0.0, 0.0, 0.0])

    def test_square_bipolar(self) -> None:
        w = Waveform1D.square(n=4, frequency=0.25, dt_seconds=1.0)
        for value in w.values:
            self.assertIn(value, (1.0, -1.0))

    def test_counter_integer_dtype(self) -> None:
        w = Waveform1D.counter(n=5, start_value=0, increment=2)
        np.testing.assert_array_equal(w.values, [0, 2, 4, 6, 8])
        self.assertTrue(np.issubdtype(w.values.dtype, np.integer))

    def test_digital_square_two_levels(self) -> None:
        w = Waveform1D.digital_square(
            n=8, frequency=0.25, high_value=5, low_value=-5, dt_seconds=1.0
        )
        for value in w.values:
            self.assertIn(value, (5, -5))

    def test_exponential_decay(self) -> None:
        w = Waveform1D.exponential_decay(n=3, time_constant=1.0, dt_seconds=1.0)
        expected = np.exp(-np.arange(3))
        np.testing.assert_allclose(w.values, expected)

    def test_exponential_growth(self) -> None:
        w = Waveform1D.exponential_growth(n=3, time_constant=1.0, dt_seconds=1.0)
        expected = np.exp(np.arange(3))
        np.testing.assert_allclose(w.values, expected)

    def test_generator_time_kwargs_pass_through(self) -> None:
        t0 = PrecisionTimestamp.EPOCH + PrecisionTimeInterval.from_seconds(100.0)
        w = Waveform1D.sine(n=10, frequency=1.0, dt=PrecisionTimeInterval.from_seconds(0.5), t0=t0)
        self.assertEqual(w.dt, PrecisionTimeInterval.from_seconds(0.5))
        self.assertEqual(w.t0, t0)

    def test_damped_sinusoid_decays(self) -> None:
        w = Waveform1D.damped_sinusoid(
            n=1000, frequency=1.0, damping_constant=0.1, dt_seconds=0.001
        )
        # Envelope decays -- later peak magnitude much smaller than earlier one.
        self.assertLess(abs(w.values[-1]), abs(w.values[10]))

    def test_heaviside_step(self) -> None:
        w = Waveform1D.heaviside(n=10, amplitude=1.0, step_time=5.0, dt_seconds=1.0)
        np.testing.assert_array_equal(w.values[:5], [0.0] * 5)
        np.testing.assert_array_equal(w.values[5:], [1.0] * 5)

    def test_relu(self) -> None:
        w = Waveform1D.relu(n=5, threshold=2.0, dt_seconds=1.0)
        np.testing.assert_allclose(w.values, [0.0, 0.0, 0.0, 1.0, 2.0])

    def test_sigmoid_bounded(self) -> None:
        w = Waveform1D.sigmoid(n=100, dt_seconds=0.1)
        self.assertTrue(np.all(w.values > 0.0))
        self.assertTrue(np.all(w.values < 1.0))

    def test_logarithm_and_logarithm10(self) -> None:
        w1 = Waveform1D.logarithm(n=5, offset=1.0, dt_seconds=1.0)
        w2 = Waveform1D.logarithm10(n=5, offset=1.0, dt_seconds=1.0)
        t = np.arange(5) + 1.0
        np.testing.assert_allclose(w1.values, np.log(t))
        np.testing.assert_allclose(w2.values, np.log10(t))

    def test_square_root(self) -> None:
        w = Waveform1D.square_root(n=5, dt_seconds=1.0)
        np.testing.assert_allclose(w.values, np.sqrt(np.arange(5, dtype=np.float64)))

    def test_sawtooth_and_triangle_ranges(self) -> None:
        saw = Waveform1D.sawtooth(n=100, frequency=1.0, dt_seconds=0.01)
        tri = Waveform1D.triangle(n=100, frequency=1.0, dt_seconds=0.01)
        self.assertTrue(np.all(saw.values >= -1.0 - 1e-9))
        self.assertTrue(np.all(saw.values <= 1.0 + 1e-9))
        self.assertTrue(np.all(tri.values >= -1.0 - 1e-9))
        self.assertTrue(np.all(tri.values <= 1.0 + 1e-9))

    def test_chirp_sweeps_frequency(self) -> None:
        w = Waveform1D.chirp(n=1000, start_frequency=1.0, end_frequency=10.0, dt_seconds=0.001)
        self.assertEqual(len(w), 1000)
        self.assertTrue(np.all(np.abs(w.values) <= 1.0 + 1e-9))


if __name__ == "__main__":
    unittest.main()
