"""Unit tests for ``waveforms/support.py`` and ``dsp/_protocol.py``.

Covers waveformDsp.md §Support descriptor types and §Compliance 3: every
spec-listed enum member exists, every descriptor dataclass is frozen
(mutation raises), every ndarray-bearing descriptor has ``eq=False`` (``==``
on two equal-content instances must not raise), and ``Waveform1D``
structurally satisfies ``WaveformProtocol`` both at runtime
(``isinstance``, via ``@runtime_checkable``) and under mypy strict (a
protocol-typed assignment).
"""

import dataclasses
import unittest
from typing import Any

import numpy as np

from math_tools.waveforms import support as sup
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.waveform1d import Waveform1D


class TestEnumMembers(unittest.TestCase):
    """Every enum member listed in waveformDsp.md §Support descriptor types exists."""

    def _assert_members(self, enum_cls: type, expected: list[str]) -> None:
        for name in expected:
            self.assertTrue(
                hasattr(enum_cls, name), f"{enum_cls.__name__} is missing member {name}"
            )

    def test_waveform_filter_type(self) -> None:
        self._assert_members(
            sup.WaveformFilterType, ["LOW_PASS", "HIGH_PASS", "BAND_PASS", "BAND_STOP"]
        )

    def test_waveform_window_type(self) -> None:
        self._assert_members(
            sup.WaveformWindowType,
            ["HANN", "HAMMING", "BLACKMAN", "BARTLETT", "KAISER", "RECTANGULAR"],
        )

    def test_waveform_interpolation_method(self) -> None:
        self._assert_members(
            sup.WaveformInterpolationMethod, ["LINEAR", "CUBIC", "NEAREST", "FOURIER"]
        )

    def test_waveform_instantaneous_method(self) -> None:
        self._assert_members(sup.WaveformInstantaneousMethod, ["HILBERT", "RMS", "PEAK"])

    def test_waveform_edge_type(self) -> None:
        self._assert_members(sup.WaveformEdgeType, ["RISING", "FALLING", "BOTH"])

    def test_waveform_window_trigger_type(self) -> None:
        self._assert_members(sup.WaveformWindowTriggerType, ["ENTER", "EXIT"])

    def test_waveform_alignment_method(self) -> None:
        self._assert_members(sup.WaveformAlignmentMethod, ["CORRELATION", "START_TIME"])

    def test_waveform_zero_crossing_direction(self) -> None:
        self._assert_members(sup.WaveformZeroCrossingDirection, ["POSITIVE", "NEGATIVE", "BOTH"])

    def test_waveform_padding_strategy(self) -> None:
        self._assert_members(sup.WaveformPaddingStrategy, ["ZERO", "EDGE", "REFLECT", "WRAP"])

    def test_waveform_psd_scaling(self) -> None:
        self._assert_members(sup.WaveformPSDScaling, ["DENSITY", "SPECTRUM"])

    def test_waveform_spectrogram_scaling(self) -> None:
        self._assert_members(sup.WaveformSpectrogramScaling, ["LINEAR", "DB", "MEL"])

    def test_waveform_trigger_type(self) -> None:
        self._assert_members(sup.WaveformTriggerType, ["EDGE", "LEVEL", "WINDOW", "PATTERN"])

    def test_enum_values_are_snake_case_strings(self) -> None:
        for enum_cls in (
            sup.WaveformFilterType,
            sup.WaveformWindowType,
            sup.WaveformInterpolationMethod,
            sup.WaveformInstantaneousMethod,
            sup.WaveformEdgeType,
            sup.WaveformWindowTriggerType,
            sup.WaveformAlignmentMethod,
            sup.WaveformZeroCrossingDirection,
            sup.WaveformPaddingStrategy,
            sup.WaveformPSDScaling,
            sup.WaveformSpectrogramScaling,
            sup.WaveformTriggerType,
        ):
            for member in enum_cls:
                self.assertIsInstance(member.value, str)
                self.assertEqual(member.value, member.value.lower())
                self.assertNotIn(" ", member.value)


def _sample_instances() -> list[Any]:
    """One instance of every descriptor dataclass in support.py."""
    freq = np.array([1.0, 2.0, 3.0])
    mag = np.array([4.0, 5.0, 6.0])
    phases = np.array([0.1, 0.2, 0.3])
    peak = sup.WaveformPeak(index=1, time_seconds=0.1, value=2.0)
    waveform = Waveform1D([1.0, 2.0, 3.0])
    return [
        sup.WaveformSpectrum(frequencies=freq, magnitudes=mag, phases=phases),
        sup.WaveformSpectrogram(times=freq, frequencies=freq, magnitudes=mag),
        sup.WaveformMelSpectrogram(times=freq, mel_frequencies=freq, magnitudes=mag),
        sup.WaveformSpectralFeatures(centroid=1.0, spread=2.0, rolloff=3.0, flatness=0.5),
        peak,
        sup.WaveformPeakWithProminence(peak=peak, prominence=0.5),
        sup.WaveformTimeLag(lag_samples=3, lag_seconds=0.03, correlation=0.9),
        sup.WaveformTrigger(kind=sup.WaveformTriggerType.LEVEL, level=1.0),
        sup.WaveformTriggerEvent(
            index=1, time_seconds=0.1, value=2.0, kind=sup.WaveformTriggerType.EDGE
        ),
        sup.WaveformEventMarker(index=1, label="peak"),
        sup.WaveformWithEvents(
            waveform=waveform, events=(sup.WaveformEventMarker(index=0, label="a"),)
        ),
        sup.WaveformZeroCrossing(
            index=1, time_seconds=0.1, direction=sup.WaveformZeroCrossingDirection.POSITIVE
        ),
        sup.WaveformInstantaneousFrequency(frequencies_hz=freq, times_seconds=freq),
        sup.WaveformFrequencyRange(low_hz=1.0, high_hz=10.0),
        sup.WaveformFilterCoefficients(numerator=freq, denominator=mag),
    ]


_NDARRAY_BEARING_TYPES: tuple[type, ...] = (
    sup.WaveformSpectrum,
    sup.WaveformSpectrogram,
    sup.WaveformMelSpectrogram,
    sup.WaveformInstantaneousFrequency,
    sup.WaveformFilterCoefficients,
)


class TestDataclassesAreFrozen(unittest.TestCase):
    """Every descriptor dataclass raises on mutation (frozen=True)."""

    def test_mutation_raises(self) -> None:
        for instance in _sample_instances():
            field = dataclasses.fields(instance)[0]
            with self.assertRaises(
                dataclasses.FrozenInstanceError,
                msg=f"{type(instance).__name__} did not raise on mutation",
            ):
                setattr(instance, field.name, getattr(instance, field.name))

    def test_all_dataclasses_are_slots(self) -> None:
        for instance in _sample_instances():
            self.assertFalse(
                hasattr(instance, "__dict__"),
                f"{type(instance).__name__} is missing slots=True (has __dict__)",
            )


class TestNdarrayDescriptorsHaveSafeEquality(unittest.TestCase):
    """waveformDsp.md §Compliance 3: eq=False on ndarray descriptors -- '==' must not raise."""

    def test_equal_content_instances_compare_without_raising(self) -> None:
        for cls in _NDARRAY_BEARING_TYPES:
            with self.subTest(cls=cls.__name__):
                all_instances = _sample_instances() + _sample_instances()
                instances = [inst for inst in all_instances if type(inst) is cls]
                a, b = instances[0], instances[1]
                try:
                    result = a == b
                except Exception as exc:  # pragma: no cover - failure path
                    self.fail(f"{cls.__name__}.__eq__ raised: {exc!r}")
                self.assertIsInstance(result, bool)

    def test_ndarray_descriptors_use_identity_eq(self) -> None:
        # eq=False means no dataclass-generated __eq__: object identity applies, so two
        # distinct equal-content instances are unequal (never raise, per the test above).
        freq = np.array([1.0, 2.0, 3.0])
        a = sup.WaveformFilterCoefficients(numerator=freq, denominator=freq)
        b = sup.WaveformFilterCoefficients(numerator=freq, denominator=freq)
        self.assertFalse(a == b)
        self.assertEqual(a, a)


class TestWaveformProtocol(unittest.TestCase):
    """``Waveform1D`` structurally satisfies ``WaveformProtocol``."""

    def test_isinstance_via_runtime_checkable(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0])
        self.assertIsInstance(w, WaveformProtocol)

    def test_protocol_typed_assignment(self) -> None:
        # Exercises the mypy-strict-checkable surface: a Waveform1D is assignable to a
        # WaveformProtocol-typed variable without a cast/ignore.
        w: WaveformProtocol = Waveform1D([1.0, 2.0, 3.0])
        self.assertEqual(list(w.values), [1.0, 2.0, 3.0])
        self.assertEqual(w.sampling_frequency_hz, 1.0)
        new_w = w._with_values(np.array([4.0, 5.0, 6.0]))
        self.assertEqual(list(new_w.values), [4.0, 5.0, 6.0])
        self.assertEqual(new_w.dt, w.dt)
        self.assertEqual(new_w.t0, w.t0)


class TestWithValues(unittest.TestCase):
    """``Waveform1D._with_values`` returns a new instance sharing dt/t0."""

    def test_new_instance_shares_dt_and_t0(self) -> None:
        w = Waveform1D([1.0, 2.0, 3.0], dt_seconds=0.5, t0_seconds=10.0)
        new_w = w._with_values(np.array([9.0, 8.0, 7.0]))
        self.assertIsNot(new_w, w)
        self.assertEqual(new_w.dt, w.dt)
        self.assertEqual(new_w.t0, w.t0)
        self.assertEqual(list(new_w.values), [9.0, 8.0, 7.0])
        # original is untouched
        self.assertEqual(list(w.values), [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
