from typing import List

from foundationTypes.mathTypes.MathTypes import UnitSphericalArcType

from math_plot_helpers import plot_unit_spherical_multiplot
from math_plot_helpers.plot_unit_spherical import (
    deg45,
    deg90,
    deg180,
    deg22_5,
)

from math_tools.spherical import arc_from_two_points, compute_spherical_arc_endpoint


def demo() -> None:
    """Demonstration of multiplot view showing spherical small circles in three different projections."""

    arc1 = UnitSphericalArcType(orient=0, azimuth=0, polar=0, arc_length=deg90)
    arc2 = UnitSphericalArcType(orient=deg90, azimuth=0, polar=deg90, arc_length=deg90)
    az, po = compute_spherical_arc_endpoint(arc2)
    arc3 = arc_from_two_points(
        azimuth1=az,
        polar1=po,
        azimuth2=arc1.azimuth,
        polar2=arc1.polar,
    )

    arcs: List[UnitSphericalArcType] = [
        arc1,
        arc2,
        arc3,
    ]

    _ = plot_unit_spherical_multiplot(
        arcs=arcs,
        show_plot=True,
    )


if __name__ == "__main__":
    demo()
