"""``math_tools.spherical``: spherical arc/small-circle utilities.

Curated subpackage re-exports so consumers import
``from math_tools.spherical import arc_from_two_points`` rather than reaching
into the individual ``constructors`` / ``spherical_generators`` /
``spherical_transforms`` modules. See
``.claude/specs/mathToolsArchitecture.md`` §Shared conventions (Public
surface). ISO physics spherical convention is documented canonically in
``spherical_generators``. This module contains re-exports only -- no logic.
"""

from math_tools.spherical.constructors import arc_from_two_points
from math_tools.spherical.spherical_generators import (
    generate_spherical_arc_points,
    generate_spherical_small_circle_points,
)
from math_tools.spherical.spherical_transforms import (
    cartesian_to_spherical,
    compute_spherical_arc_endpoint,
    plate_carree_transform,
    spherical_to_cartesian,
)

__all__ = [
    "arc_from_two_points",
    "generate_spherical_arc_points",
    "generate_spherical_small_circle_points",
    "cartesian_to_spherical",
    "compute_spherical_arc_endpoint",
    "plate_carree_transform",
    "spherical_to_cartesian",
]
