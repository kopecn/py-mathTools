"""
Constructor functions for UnitSphericalSmallCircle objects.

This module provides utilities for creating UnitSphericalSmallCircle instances
from various representations, using ISO Physics Convention for spherical coordinates.
"""

import numpy as np
from numpy import atan2, acos, pi

from foundationTypes.mathTypes.UnitSphericalArc import UnitSphericalArc


def arc_from_two_points(
    azimuth1: float,
    polar1: float,
    azimuth2: float,
    polar2: float,
    isPositive: bool = True,
) -> UnitSphericalArc:
    """
    Create a UnitSphericalArc connecting two points on a unit sphere.

    Uses ISO Physics Convention for spherical coordinates:
    - φ (azimuth): angle in xy-plane from +x axis
    - θ (polar): angle from +z axis (colatitude), range [0, π]

    The arc follows a great circle path between the two points. The direction of
    travel is determined by the isPositive parameter.

    Parameters:
    -----------
    azimuth1 : float
        Starting point azimuth angle (φ₁) in radians
    polar1 : float
        Starting point polar angle (θ₁) in radians (colatitude from +z)
    azimuth2 : float
        Ending point azimuth angle (φ₂) in radians
    polar2 : float
        Ending point polar angle (θ₂) in radians (colatitude from +z)
    isPositive : bool, optional
        If True (default), creates arc with positive arc_length
        If False, creates arc with negative arc_length (opposite direction)

    Returns:
    --------
    UnitSphericalArc
        Arc starting at (azimuth1, polar1) that reaches toward (azimuth2, polar2)

    Notes:
    ------
    Uses spherical trigonometry formulas:
    - arc_length: Great circle distance using spherical law of cosines
    - orient: Initial bearing computed relative to north direction

    Examples:
    ---------
    >>> # Arc from north pole to equator at 0° azimuth
    >>> arc = arc_from_two_points(0, 0, 0, np.pi/2, isPositive=True)
    """
    # Great circle distance using spherical law of cosines
    # In ISO physics convention: polar = θ (colatitude from +z axis)
    # γ = arccos(cos(θ1)*cos(θ2) + sin(θ1)*sin(θ2)*cos(φ2 - φ1))

    cos_theta1 = np.cos(polar1)
    sin_theta1 = np.sin(polar1)
    cos_theta2 = np.cos(polar2)
    sin_theta2 = np.sin(polar2)

    delta_phi = azimuth2 - azimuth1
    cos_delta_phi = np.cos(delta_phi)

    # Arc length (great circle distance)
    cos_arc_length = cos_theta1 * cos_theta2 + sin_theta1 * sin_theta2 * cos_delta_phi
    arc_length = np.arccos(np.clip(cos_arc_length, -1.0, 1.0))

    # Initial bearing from point 1 to point 2 (relative to north)
    # This gives the orient parameter
    # bearing = atan2(sin(Δφ)*sin(θ2), cos(θ1)*sin(θ2) - sin(θ1)*cos(θ2)*cos(Δφ))

    sin_delta_phi = np.sin(delta_phi)

    y_component = sin_delta_phi * sin_theta2
    x_component = cos_theta1 * sin_theta2 - sin_theta1 * cos_theta2 * cos_delta_phi

    orient = atan2(y_component, x_component)

    # Apply isPositive parameter
    if not isPositive:
        arc_length = -arc_length

    return UnitSphericalArc(
        azimuth=azimuth1,
        polar=polar1,
        orient=orient,
        arc_length=arc_length,
    )
