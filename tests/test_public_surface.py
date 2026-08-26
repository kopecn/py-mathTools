"""Pin the curated root ``math_tools`` public surface.

Per mathToolsArchitecture.md §Shared conventions (Public surface), the root
``math_tools/__init__.py`` re-exports a flat working set so
``import math_tools as mt`` is coherent. This test pins ``__all__`` to the
umbrella spec's literal list, imports every name, and asserts each resolves
to the subpackage-defined class/object by identity (no shadow copies).
"""

import unittest

import math_tools
import math_tools.functional
import math_tools.otg
import math_tools.precision_time
import math_tools.spatial
import math_tools.waveforms


class TestPublicSurface(unittest.TestCase):
    def test_all_pins_exact_umbrella_spec_list(self) -> None:
        expected = {
            "Position",
            "Quaternion",
            "SpatialPose",
            "PrecisionTimeInterval",
            "PrecisionTimestamp",
            "Waveform1D",
            "WaveformPosition",
            "WaveformQuaternion",
            "WaveformSpatialPose",
            "UnivariatePolynomial",
            "Otg",
            "InputParameter",
            "OutputParameter",
            "Trajectory",
            "Result",
            "MathToolsError",
            "WaveformCompatibilityError",
            "TimestampComparisonError",
            "PolynomialSolveError",
        }
        self.assertEqual(set(math_tools.__all__), expected)
        self.assertEqual(len(math_tools.__all__), len(expected))

    def test_every_public_name_resolves_by_identity(self) -> None:
        identity_sources = {
            "Position": math_tools.spatial.Position,
            "Quaternion": math_tools.spatial.Quaternion,
            "SpatialPose": math_tools.spatial.SpatialPose,
            "PrecisionTimeInterval": math_tools.precision_time.PrecisionTimeInterval,
            "PrecisionTimestamp": math_tools.precision_time.PrecisionTimestamp,
            "Waveform1D": math_tools.waveforms.Waveform1D,
            "WaveformPosition": math_tools.waveforms.WaveformPosition,
            "WaveformQuaternion": math_tools.waveforms.WaveformQuaternion,
            "WaveformSpatialPose": math_tools.waveforms.WaveformSpatialPose,
            "UnivariatePolynomial": math_tools.functional.UnivariatePolynomial,
            "Otg": math_tools.otg.Otg,
            "InputParameter": math_tools.otg.InputParameter,
            "OutputParameter": math_tools.otg.OutputParameter,
            "Trajectory": math_tools.otg.Trajectory,
            "Result": math_tools.otg.Result,
            "MathToolsError": math_tools.errors.MathToolsError,
            "WaveformCompatibilityError": math_tools.errors.WaveformCompatibilityError,
            "TimestampComparisonError": math_tools.errors.TimestampComparisonError,
            "PolynomialSolveError": math_tools.errors.PolynomialSolveError,
        }
        for name, source in identity_sources.items():
            with self.subTest(name=name):
                self.assertIs(getattr(math_tools, name), source)

    def test_waveform1d_sine_smoke(self) -> None:
        waveform = math_tools.Waveform1D.sine(n=8)
        self.assertEqual(len(waveform), 8)


if __name__ == "__main__":
    unittest.main()
