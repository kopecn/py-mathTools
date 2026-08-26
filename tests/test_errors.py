"""Unit tests for the ``math_tools.errors`` exception hierarchy."""

import unittest

from math_tools.errors import (
    MathToolsError,
    PolynomialSolveError,
    TimestampComparisonError,
    WaveformCompatibilityError,
)


class TestMathToolsErrorHierarchy(unittest.TestCase):
    def test_math_tools_error_is_an_exception(self) -> None:
        self.assertTrue(issubclass(MathToolsError, Exception))

    def test_waveform_compatibility_error_subclasses_math_tools_error(self) -> None:
        self.assertTrue(issubclass(WaveformCompatibilityError, MathToolsError))

    def test_timestamp_comparison_error_subclasses_math_tools_error(self) -> None:
        self.assertTrue(issubclass(TimestampComparisonError, MathToolsError))

    def test_polynomial_solve_error_subclasses_math_tools_error(self) -> None:
        self.assertTrue(issubclass(PolynomialSolveError, MathToolsError))

    def test_waveform_compatibility_error_is_catchable_as_math_tools_error(self) -> None:
        with self.assertRaises(MathToolsError):
            raise WaveformCompatibilityError("dt mismatch")

    def test_timestamp_comparison_error_is_catchable_as_math_tools_error(self) -> None:
        with self.assertRaises(MathToolsError):
            raise TimestampComparisonError("timescale mismatch")

    def test_polynomial_solve_error_is_catchable_as_math_tools_error(self) -> None:
        with self.assertRaises(MathToolsError):
            raise PolynomialSolveError("ill-posed request")

    def test_math_tools_error_message_is_preserved(self) -> None:
        try:
            raise WaveformCompatibilityError("boom")
        except MathToolsError as exc:
            self.assertEqual(str(exc), "boom")


if __name__ == "__main__":
    unittest.main()
