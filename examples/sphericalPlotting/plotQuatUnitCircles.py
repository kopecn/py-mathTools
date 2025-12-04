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

from numpy import pi
import quaternion

from pyMathTools.spherical.constructors import (
    quat_to_unitSphericalSmallCircle,
)

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
    _ = plot_unit_spherical_multiplot(
        circles=[
            quat_to_unitSphericalSmallCircle(q=quaternion.one, radius_angle=pi / 8),
            quat_to_unitSphericalSmallCircle(q=quaternion.x, radius_angle=pi / 8),
            quat_to_unitSphericalSmallCircle(q=quaternion.y),
            quat_to_unitSphericalSmallCircle(q=quaternion.z),
        ],
        show_plot=True,
    )


if __name__ == "__main__":
    main()
