"""Pin the ``math_tools.spherical`` and ``math_plot_helpers`` public surface.

Per mathToolsArchitecture.md §Shared conventions (Public surface), every
package/subpackage ``__init__.py`` re-exports its public API with
``__all__``, and consumers import from the subpackage level, never deep
module paths. This test pins each subpackage's ``__all__`` and asserts every
name resolves to the module-defined function by identity (no shadow copies),
mirroring ``tests/test_public_surface.py``'s identity-check shape.
"""

import unittest

import math_plot_helpers
import math_plot_helpers.plot_unit_spherical
import math_tools.spherical
import math_tools.spherical.constructors
import math_tools.spherical.spherical_generators
import math_tools.spherical.spherical_transforms


class TestSphericalPublicSurface(unittest.TestCase):
    def test_all_pins_exact_function_set(self) -> None:
        expected = {
            "arc_from_two_points",
            "generate_spherical_arc_points",
            "generate_spherical_small_circle_points",
            "cartesian_to_spherical",
            "compute_spherical_arc_endpoint",
            "plate_carree_transform",
            "spherical_to_cartesian",
        }
        self.assertEqual(set(math_tools.spherical.__all__), expected)
        self.assertEqual(len(math_tools.spherical.__all__), len(expected))

    def test_every_public_name_resolves_by_identity(self) -> None:
        identity_sources = {
            "arc_from_two_points": (
                math_tools.spherical.constructors.arc_from_two_points
            ),
            "generate_spherical_arc_points": (
                math_tools.spherical.spherical_generators.generate_spherical_arc_points
            ),
            "generate_spherical_small_circle_points": (
                math_tools.spherical.spherical_generators.generate_spherical_small_circle_points
            ),
            "cartesian_to_spherical": (
                math_tools.spherical.spherical_transforms.cartesian_to_spherical
            ),
            "compute_spherical_arc_endpoint": (
                math_tools.spherical.spherical_transforms.compute_spherical_arc_endpoint
            ),
            "plate_carree_transform": (
                math_tools.spherical.spherical_transforms.plate_carree_transform
            ),
            "spherical_to_cartesian": (
                math_tools.spherical.spherical_transforms.spherical_to_cartesian
            ),
        }
        for name, source in identity_sources.items():
            with self.subTest(name=name):
                self.assertIs(getattr(math_tools.spherical, name), source)


class TestMathPlotHelpersPublicSurface(unittest.TestCase):
    def test_all_pins_exact_function_set(self) -> None:
        expected = {
            "plot_unit_spherical_advanced",
            "plot_unit_spherical_polar",
            "plot_unit_spherical_3d",
            "plot_unit_spherical_multiplot",
        }
        self.assertEqual(set(math_plot_helpers.__all__), expected)
        self.assertEqual(len(math_plot_helpers.__all__), len(expected))

    def test_every_public_name_resolves_by_identity(self) -> None:
        identity_sources = {
            "plot_unit_spherical_advanced": (
                math_plot_helpers.plot_unit_spherical.plot_unit_spherical_advanced
            ),
            "plot_unit_spherical_polar": (
                math_plot_helpers.plot_unit_spherical.plot_unit_spherical_polar
            ),
            "plot_unit_spherical_3d": (
                math_plot_helpers.plot_unit_spherical.plot_unit_spherical_3d
            ),
            "plot_unit_spherical_multiplot": (
                math_plot_helpers.plot_unit_spherical.plot_unit_spherical_multiplot
            ),
        }
        for name, source in identity_sources.items():
            with self.subTest(name=name):
                self.assertIs(getattr(math_plot_helpers, name), source)


if __name__ == "__main__":
    unittest.main()
