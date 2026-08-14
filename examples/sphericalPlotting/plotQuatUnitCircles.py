"""
Example: Visualizing Quaternion-Derived Small Circles on the Unit Sphere

This script demonstrates how to convert quaternions to spherical small circles
and visualize them using multiple projections. It serves as a validation and
walkthrough for the quaternion-to-spherical conversion and plotting utilities.

Steps:
------
1. Import required modules and functions.
2. Convert several canonical quaternions (identity and axis-aligned) to
   UnitSphericalSmallCircle objects.
3. Plot these circles using the multiplot function, which shows flat projection,
   polar, and 3D views.

Usage:
------
Run this script directly to see the resulting plots and validate the conversion.

Expected Output:
----------------
- The identity quaternion (`quaternion.one`) should map to the north pole.
- `quaternion.x`, `quaternion.y`, and `quaternion.z` should map to circles
  centered on the X, Y, and Z axes, respectively.

"""

from typing import List
from numpy import pi

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.spatial.Quaternion import Quaternion

from pyMathToolsPlotHelpers.plotUnitSpherical import (
    plot_unit_spherical_multiplot,
)


def main():
    """
    Convert canonical quaternions to spherical small circles and plot them.

    - quaternion.one: Identity quaternion (should map to north pole)
    - quaternion.x: X-axis quaternion
    - quaternion.y: Y-axis quaternion
    - quaternion.z: Z-axis quaternion

    All circles use a radius angle of pi/8 except y and z, which use the default.
    """

    quat4 = Quaternion.from_unit_x_to_vector([1, 0, 0])
    quat5 = Quaternion.from_unit_x_to_vector([0, 1, 0])
    quat6 = Quaternion.from_unit_x_to_vector([0, 0, 1])

    quat1 = Quaternion.from_components(0, 1, 0, 0)
    quat2 = Quaternion.from_components(0, 0, 1, 0)
    quat3 = Quaternion.from_components(0, 0, 0, 1)

    circles: List[UnitSphericalSmallCircle] = [
        quat1.to_unitSphericalSmallCircle(radius_angle=pi / 8),
        quat2.to_unitSphericalSmallCircle(radius_angle=pi / 8),
        quat3.to_unitSphericalSmallCircle(),
        quat4.to_unitSphericalSmallCircle(radius_angle=pi / 16),
        quat5.to_unitSphericalSmallCircle(radius_angle=pi / 16),
        quat6.to_unitSphericalSmallCircle(radius_angle=pi / 16),
    ]

    quats: List[Quaternion] = [quat1, quat2, quat3, quat4, quat5, quat6]

    # from_vector_part
    _ = plot_unit_spherical_multiplot(
        circles=circles,
        quaternions=quats,
        show_plot=True,
    )


if __name__ == "__main__":
    main()
