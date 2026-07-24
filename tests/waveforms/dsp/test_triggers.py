"""Unit tests for ``dsp/_triggers.py`` (``TriggerMixin``).

Covers waveformDsp.md §Family contracts (``TriggerMixin``), §Numerical
conventions, §Compliance 1-2. Exercises the mixin directly on ``Waveform1D``, which
composes every DSP mixin from the compose chunk (30) onward.
"""

import unittest

import numpy as np

from math_tools.precision_time.precision_time_interval import PrecisionTimeInterval
from math_tools.waveforms.support import (
    WaveformEdgeType,
    WaveformTrigger,
    WaveformTriggerType,
    WaveformWindowTriggerType,
)
from math_tools.waveforms.waveform1d import Waveform1D


def _square_pulses(cycles: int, samples_per_phase: int, low: float, high: float) -> np.ndarray:
    """A LOW/HIGH pulse train bracketed by LOW on both ends: LOW, HIGH, LOW, HIGH, ..., LOW.

    Every HIGH pulse is a fully interior block (a real sample precedes and follows
    it), so this yields exactly ``cycles`` low->high (rising) transitions and
    exactly ``cycles`` high->low (falling) transitions -- no boundary ambiguity.
    """
    low_block = np.full(samples_per_phase, low, dtype=np.float64)
    high_block = np.full(samples_per_phase, high, dtype=np.float64)
    blocks = [low_block]
    for _ in range(cycles):
        blocks.append(high_block)
        blocks.append(low_block)
    return np.concatenate(blocks)


class TestDetectEdgeTriggersOnSquareWave(unittest.TestCase):
    """Acceptance criterion: square-wave edge counts exact."""

    def setUp(self) -> None:
        self.cycles = 5
        values = _square_pulses(self.cycles, samples_per_phase=20, low=-1.0, high=1.0)
        self.w = Waveform1D(values, dt_seconds=0.01)

    def test_rising_edge_count_equals_cycle_count(self) -> None:
        events = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        self.assertEqual(len(events), self.cycles)
        for event in events:
            self.assertEqual(event.kind, WaveformTriggerType.EDGE)
            self.assertAlmostEqual(event.time_seconds, event.index * 0.01, places=9)

    def test_falling_edge_count_equals_cycle_count(self) -> None:
        events = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.FALLING)
        self.assertEqual(len(events), self.cycles)

    def test_both_is_sum_of_rising_and_falling(self) -> None:
        rising = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        falling = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.FALLING)
        both = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.BOTH)
        self.assertEqual(len(both), len(rising) + len(falling))
        self.assertEqual(
            sorted(e.index for e in both),
            sorted([e.index for e in rising] + [e.index for e in falling]),
        )

    def test_rising_and_falling_alternate(self) -> None:
        rising = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        falling = self.w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.FALLING)
        rising_indices = [e.index for e in rising]
        falling_indices = [e.index for e in falling]
        # Bracketed by LOW on both ends: every rising is followed by a later falling
        # before the next rising.
        for rise, fall in zip(rising_indices, falling_indices, strict=True):
            self.assertLess(rise, fall)


class TestDetectEdgeTriggersNoHit(unittest.TestCase):
    def test_level_outside_range_returns_empty(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0, 2.0, 1.0], dt_seconds=0.1)
        self.assertEqual(w.detect_edge_triggers(level=100.0), [])

    def test_too_short_returns_empty(self) -> None:
        w = Waveform1D([1.0], dt_seconds=0.1)
        self.assertEqual(w.detect_edge_triggers(level=0.0), [])

    def test_empty_waveform_returns_empty(self) -> None:
        w = Waveform1D([], dt_seconds=0.1)
        self.assertEqual(w.detect_edge_triggers(level=0.0), [])


class TestDetectEdgeTriggersMinimumInterval(unittest.TestCase):
    """Two rising edges closer together than ``minimum_interval`` collapse to one event."""

    def test_second_close_rising_edge_is_dropped(self) -> None:
        # Rising at index 1, falling at 2, rising again at 3 (too close), falling at 4.
        values = [-1.0, 1.0, -1.0, 1.0, -1.0]
        w = Waveform1D(values, dt_seconds=1.0)
        events = w.detect_edge_triggers(
            level=0.0,
            edge=WaveformEdgeType.RISING,
            minimum_interval=PrecisionTimeInterval.from_seconds(5.0),
        )
        self.assertEqual([e.index for e in events], [1])

    def test_far_apart_rising_edges_both_kept(self) -> None:
        values = [-1.0, 1.0, -1.0, 1.0, -1.0]
        w = Waveform1D(values, dt_seconds=1.0)
        events = w.detect_edge_triggers(
            level=0.0,
            edge=WaveformEdgeType.RISING,
            minimum_interval=PrecisionTimeInterval.from_seconds(0.5),
        )
        self.assertEqual([e.index for e in events], [1, 3])


class TestDetectLevelTriggersMinimumInterval(unittest.TestCase):
    """§Gap 21 (chunk 55): ``minimum_interval`` dedup was verified through only
    ``detect_edge_triggers`` -- this closes the ``detect_level_triggers`` entry
    point (2 of 5)."""

    def test_second_close_rising_level_is_dropped(self) -> None:
        values = [-1.0, 1.0, -1.0, 1.0, -1.0]
        w = Waveform1D(values, dt_seconds=1.0)
        events = w.detect_level_triggers(
            level=0.0, minimum_interval=PrecisionTimeInterval.from_seconds(5.0)
        )
        self.assertEqual([e.index for e in events], [1])

    def test_far_apart_rising_levels_both_kept(self) -> None:
        values = [-1.0, 1.0, -1.0, 1.0, -1.0]
        w = Waveform1D(values, dt_seconds=1.0)
        events = w.detect_level_triggers(
            level=0.0, minimum_interval=PrecisionTimeInterval.from_seconds(0.5)
        )
        self.assertEqual([e.index for e in events], [1, 3])


class TestDetectLevelTriggers(unittest.TestCase):
    def test_default_rising_matches_edge_rising(self) -> None:
        values = _square_pulses(3, samples_per_phase=10, low=-1.0, high=1.0)
        w = Waveform1D(values, dt_seconds=0.1)
        level_events = w.detect_level_triggers(level=0.0)
        edge_events = w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        self.assertEqual([e.index for e in level_events], [e.index for e in edge_events])
        for event in level_events:
            self.assertEqual(event.kind, WaveformTriggerType.LEVEL)

    def test_falling_direction(self) -> None:
        values = _square_pulses(3, samples_per_phase=10, low=-1.0, high=1.0)
        w = Waveform1D(values, dt_seconds=0.1)
        level_events = w.detect_level_triggers(level=0.0, edge=WaveformEdgeType.FALLING)
        edge_events = w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.FALLING)
        self.assertEqual([e.index for e in level_events], [e.index for e in edge_events])

    def test_no_hit_returns_empty(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        self.assertEqual(w.detect_level_triggers(level=100.0), [])


class TestDetectWindowTriggersPairUp(unittest.TestCase):
    """Acceptance criterion: window ENTER/EXIT pair up on a sine crossing a band."""

    def setUp(self) -> None:
        self.cycles = 3
        samples_per_cycle = 300
        n = self.cycles * samples_per_cycle
        # sin(0) == 0 at both the first and last sample, safely below `low` -- no
        # boundary ambiguity at either end of the array.
        self.w = Waveform1D(
            Waveform1D.sine(n, frequency=1.0, dt_seconds=1.0 / samples_per_cycle).values,
            dt_seconds=1.0 / samples_per_cycle,
        )
        self.low = 0.3
        self.high = 0.8

    def test_enter_and_exit_counts_match_and_are_nonzero(self) -> None:
        enters = self.w.detect_window_triggers(self.low, self.high, WaveformWindowTriggerType.ENTER)
        exits = self.w.detect_window_triggers(self.low, self.high, WaveformWindowTriggerType.EXIT)
        self.assertGreater(len(enters), 0)
        self.assertEqual(len(enters), len(exits))
        for event in enters:
            self.assertEqual(event.kind, WaveformTriggerType.WINDOW)

    def test_each_enter_is_followed_by_its_exit_before_the_next_enter(self) -> None:
        enters = self.w.detect_window_triggers(self.low, self.high, WaveformWindowTriggerType.ENTER)
        exits = self.w.detect_window_triggers(self.low, self.high, WaveformWindowTriggerType.EXIT)
        enter_indices = [e.index for e in enters]
        exit_indices = [e.index for e in exits]
        for i, enter_index in enumerate(enter_indices):
            self.assertLess(enter_index, exit_indices[i])
            if i + 1 < len(enter_indices):
                self.assertLess(exit_indices[i], enter_indices[i + 1])

    def test_low_greater_than_high_returns_empty(self) -> None:
        self.assertEqual(
            self.w.detect_window_triggers(0.8, 0.3, WaveformWindowTriggerType.ENTER), []
        )

    def test_band_never_reached_returns_empty(self) -> None:
        self.assertEqual(
            self.w.detect_window_triggers(10.0, 20.0, WaveformWindowTriggerType.ENTER), []
        )


class TestDetectWindowTriggersMinimumInterval(unittest.TestCase):
    """§Gap 21 (chunk 55): ``minimum_interval`` dedup entry point 3 of 5
    (``detect_window_triggers``)."""

    def test_second_close_enter_is_dropped(self) -> None:
        values = [0.0, 0.5, 0.0, 0.5, 0.0]
        w = Waveform1D(values, dt_seconds=1.0)
        no_dedup = w.detect_window_triggers(0.3, 0.8, WaveformWindowTriggerType.ENTER)
        self.assertEqual([e.index for e in no_dedup], [1, 3])

        deduped = w.detect_window_triggers(
            0.3, 0.8, WaveformWindowTriggerType.ENTER,
            minimum_interval=PrecisionTimeInterval.from_seconds(5.0),
        )
        self.assertEqual([e.index for e in deduped], [1])


class TestDetectPatternTriggersFindsPlantedIndices(unittest.TestCase):
    """Acceptance criterion: pattern trigger finds an embedded motif at the planted indices."""

    def setUp(self) -> None:
        self.motif = [1.0, 2.0, 3.0, 2.0, 1.0]
        self.planted_indices = [5, 30, 60]
        values = np.zeros(90, dtype=np.float64)
        for index in self.planted_indices:
            values[index : index + len(self.motif)] = self.motif
        self.w = Waveform1D(values, dt_seconds=0.1)

    def test_exact_match_finds_planted_indices(self) -> None:
        events = self.w.detect_pattern_triggers(self.motif, tolerance=1e-9)
        self.assertEqual([e.index for e in events], self.planted_indices)
        for event, index in zip(events, self.planted_indices, strict=True):
            self.assertEqual(event.kind, WaveformTriggerType.PATTERN)
            self.assertAlmostEqual(event.time_seconds, index * 0.1, places=9)

    def test_within_tolerance_still_matches(self) -> None:
        noisy_pattern = [v + 0.01 for v in self.motif]
        events = self.w.detect_pattern_triggers(noisy_pattern, tolerance=0.05)
        self.assertEqual([e.index for e in events], self.planted_indices)

    def test_outside_tolerance_no_hit(self) -> None:
        far_off_pattern = [v + 5.0 for v in self.motif]
        events = self.w.detect_pattern_triggers(far_off_pattern, tolerance=1e-9)
        self.assertEqual(events, [])

    def test_pattern_longer_than_waveform_returns_empty(self) -> None:
        events = self.w.detect_pattern_triggers([0.0] * 200, tolerance=1.0)
        self.assertEqual(events, [])

    def test_empty_pattern_returns_empty(self) -> None:
        self.assertEqual(self.w.detect_pattern_triggers([], tolerance=1.0), [])


class TestDetectPatternTriggersMinimumInterval(unittest.TestCase):
    """§Gap 21 (chunk 55): ``minimum_interval`` dedup entry point 4 of 5
    (``detect_pattern_triggers``)."""

    def test_close_matches_are_deduped(self) -> None:
        motif = [1.0, 0.0]
        values = np.zeros(10)
        values[1] = 1.0
        values[3] = 1.0
        values[7] = 1.0
        w = Waveform1D(values, dt_seconds=1.0)

        no_dedup = w.detect_pattern_triggers(motif, tolerance=1e-9)
        self.assertEqual([e.index for e in no_dedup], [1, 3, 7])

        deduped = w.detect_pattern_triggers(
            motif, tolerance=1e-9, minimum_interval=PrecisionTimeInterval.from_seconds(3.0)
        )
        self.assertEqual([e.index for e in deduped], [1, 7])


class TestDetectTriggersGenericDispatch(unittest.TestCase):
    def setUp(self) -> None:
        self.square = Waveform1D(
            _square_pulses(4, samples_per_phase=10, low=-1.0, high=1.0), dt_seconds=0.1
        )

    def test_edge_kind_dispatches_with_default_both(self) -> None:
        via_trigger = self.square.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.EDGE, level=0.0)
        )
        direct = self.square.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.BOTH)
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])

    def test_edge_kind_honors_explicit_edge_field(self) -> None:
        via_trigger = self.square.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.EDGE, level=0.0, edge=WaveformEdgeType.RISING)
        )
        direct = self.square.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])

    def test_edge_kind_missing_level_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.square.detect_triggers(WaveformTrigger(kind=WaveformTriggerType.EDGE))

    def test_level_kind_dispatches_with_default_rising(self) -> None:
        via_trigger = self.square.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.LEVEL, level=0.0)
        )
        direct = self.square.detect_level_triggers(level=0.0)
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])

    def test_level_kind_missing_level_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.square.detect_triggers(WaveformTrigger(kind=WaveformTriggerType.LEVEL))

    def test_window_kind_dispatches_with_default_enter(self) -> None:
        via_trigger = self.square.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.WINDOW, lower=0.0, upper=1.5)
        )
        direct = self.square.detect_window_triggers(0.0, 1.5, WaveformWindowTriggerType.ENTER)
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])

    def test_window_kind_missing_bounds_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.square.detect_triggers(WaveformTrigger(kind=WaveformTriggerType.WINDOW))

    def test_pattern_kind_dispatches(self) -> None:
        motif = [1.0, -1.0]
        via_trigger = self.square.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.PATTERN, pattern=tuple(motif), tolerance=0.01)
        )
        direct = self.square.detect_pattern_triggers(motif, tolerance=0.01)
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])

    def test_pattern_kind_missing_fields_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.square.detect_triggers(WaveformTrigger(kind=WaveformTriggerType.PATTERN))

    def test_minimum_interval_honored_through_generic_dispatch(self) -> None:
        """§Gap 21 (chunk 55): ``minimum_interval`` dedup entry point 5 of 5
        (``detect_triggers``'s generic ``WaveformTrigger``-driven dispatch)."""
        values = [-1.0, 1.0, -1.0, 1.0, -1.0]
        w = Waveform1D(values, dt_seconds=1.0)
        min_interval = PrecisionTimeInterval.from_seconds(5.0)

        via_trigger = w.detect_triggers(
            WaveformTrigger(kind=WaveformTriggerType.EDGE, level=0.0, minimum_interval=min_interval)
        )
        direct = w.detect_edge_triggers(level=0.0, minimum_interval=min_interval)
        self.assertEqual([e.index for e in via_trigger], [1])
        self.assertEqual([e.index for e in via_trigger], [e.index for e in direct])


class TestWithEventMarkers(unittest.TestCase):
    def test_markers_built_from_events(self) -> None:
        w = Waveform1D(_square_pulses(2, samples_per_phase=10, low=-1.0, high=1.0), dt_seconds=0.1)
        events = w.detect_edge_triggers(level=0.0, edge=WaveformEdgeType.RISING)

        result = w.with_event_markers(events)

        self.assertIs(result.waveform, w)
        self.assertEqual(len(result.events), len(events))
        for marker, event in zip(result.events, events, strict=True):
            self.assertEqual(marker.index, event.index)
            self.assertEqual(marker.label, event.kind.value)

    def test_empty_events_yields_no_markers(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.1)
        result = w.with_event_markers([])
        self.assertEqual(result.events, ())


if __name__ == "__main__":
    unittest.main()
