"""``math_plot_helpers``: matplotlib plotting helpers for spherical math types.

Curated subpackage re-exports so consumers import
``from math_plot_helpers import plot_unit_spherical_multiplot`` rather than
reaching into ``plot_unit_spherical`` directly. See
``.claude/specs/mathToolsArchitecture.md`` §Shared conventions (Public
surface). This is the only package permitted to import ``matplotlib``
(enforced by ``tests/test_package_layering.py``). This module contains
re-exports only -- no logic.
"""

from math_plot_helpers.plot_unit_spherical import (
    plot_unit_spherical_3d,
    plot_unit_spherical_advanced,
    plot_unit_spherical_multiplot,
    plot_unit_spherical_polar,
)

__all__ = [
    "plot_unit_spherical_advanced",
    "plot_unit_spherical_polar",
    "plot_unit_spherical_3d",
    "plot_unit_spherical_multiplot",
]
