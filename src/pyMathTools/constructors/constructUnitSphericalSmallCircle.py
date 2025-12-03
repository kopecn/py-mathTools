"""
Constructor functions for UnitSphericalSmallCircle objects.

This module provides utilities for creating UnitSphericalSmallCircle instances
from various representations, using ISO Physics Convention for spherical coordinates.
"""

import numpy as np
from numpy import atan2, acos, pi

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.spatial.Quaternion import Quaternion


def quat_to_unitSphericalSmallCircle(
    q: Quaternion, radius_angle: float = pi / 4
) -> UnitSphericalSmallCircle:
    """
    Convert a quaternion's vector part to a UnitSphericalSmallCircle.

    Uses ISO Physics Convention for spherical coordinates:
    - φ (azimuth): angle in xy-plane from +x axis, range [0, 2π)
    - θ (polar): angle from +z axis (colatitude), range [0, π]

    Parameters:
    -----------
    q : Quaternion
        Quaternion whose vector part (x, y, z) defines the center direction
    radius_angle : float
        Angular radius of the small circle (default: π/4)

    Returns:
    --------
    UnitSphericalSmallCircle
        Small circle centered at the direction defined by the quaternion's vector part

    Notes:
    ------
    - If vector part is zero, defaults to north pole (azimuth=0, polar=π/2)
    - Uses standard spherical-to-Cartesian formulas:
        x = r*sin(θ)*cos(φ)
        y = r*sin(θ)*sin(φ)
        z = r*cos(θ)
    """
    # Extract vector part (this represents a direction in Cartesian space)
    r = np.sqrt(q.x**2 + q.y**2 + q.z**2)

    if r == 0:
        # Default to equator at +x axis if vector part is zero
        azimuth = 0.0
        polar = pi / 2
    else:
        # Convert Cartesian (x,y,z) to spherical (azimuth, polar)
        # ISO Physics Convention:
        azimuth = atan2(q.y, q.x)  # φ = atan2(y, x) - angle in xy-plane from +x
        polar = acos(q.z / r)       # θ = acos(z/r) - angle from +z axis

    return UnitSphericalSmallCircle(
        azimuth=azimuth, polar=polar, radius_angle=radius_angle
    )
