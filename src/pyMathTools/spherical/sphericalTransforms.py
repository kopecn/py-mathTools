"""
Transforms for spherical coordinate systems.

This module provides functions for converting to and from spherical coordinates,
including projections and other mathematical transformations commonly used in
geometry, mapping, and scientific computing.

ISO Physics Convention
-----------------------
All functions use the ISO physics convention for spherical coordinates:
- θ (theta/polar): angle from +z axis (colatitude), range [0, π]
- φ (phi/azimuth): angle in xy-plane from +x axis, range [0, 2π)

See pyMathTools.generators.sphericalGenerators module docstring for complete details.
"""

from foundationTypes.mathTypes.unitSphericalArcABC import UnitSphericalArcABC
from numpy import (
    arccos,
    arctan2,
    clip,
    cos,
    float64,
    pi,
    sin,
)
from numpy.linalg import norm
from numpy.typing import NDArray

from pyMathTools.hints import FloatOrNDArray


def plate_carree_transform(
    azimuth: FloatOrNDArray, polar: FloatOrNDArray
) -> tuple[FloatOrNDArray, FloatOrNDArray]:
    """
    Apply plate carrée (equirectangular) projection to spherical coordinates.

    This is a simple cylindrical projection that preserves angular measurements,
    making it suitable for applications where actual angles in radians are needed.

    Uses ISO Physics Convention (see module docstring for details).

    Parameters:
    -----------
    azimuth : float or ndarray
        Azimuth angle(s) φ in radians
        Angle in xy-plane from +x axis, range [0, 2π)
    polar : float or ndarray
        Polar angle(s) θ in radians
        Angle from +z axis (colatitude), range [0, π]
        - θ = 0: north pole (+z)
        - θ = π/2: equator
        - θ = π: south pole (-z)

    Returns:
    --------
    x : float or ndarray
        Projected x-coordinate = azimuth (φ) in radians [0, 2π)
    y : float or ndarray
        Projected y-coordinate = latitude in radians [-π/2, π/2]
        - y = π/2: north pole
        - y = 0: equator
        - y = -π/2: south pole

    Notes:
    ------
    Conversion formula: latitude = π/2 - polar
    """
    x = azimuth
    # Convert physics polar angle (θ, 0 to π) to latitude (-π/2 to π/2)
    # latitude = π/2 - θ
    y = pi / 2 - polar
    return x, y


def spherical_to_cartesian(azimuth: float, polar: float) -> tuple[float, float, float]:
    """
    Convert spherical coordinates to Cartesian coordinates on the unit sphere.

    Uses ISO physics convention:
    - polar (theta): angle from +z axis (colatitude), range [0, π]
    - azimuth (phi): angle in xy-plane from +x axis, range (-π, π] or [0, 2π)

    Args:
        azimuth: Azimuth angle (φ) in radians - angle in xy-plane from +x axis
        polar: Polar angle (θ) in radians - angle from +z axis (colatitude)

    Returns:
        Tuple with Cartesian coordinates [x, y, z] on unit sphere

    Notes:
        Conversion formulas (ISO physics convention):
        - x = sin(θ) * cos(φ)
        - y = sin(θ) * sin(φ)
        - z = cos(θ)
    """
    x = sin(polar) * cos(azimuth)
    y = sin(polar) * sin(azimuth)
    z = cos(polar)

    return (x, y, z)


def cartesian_to_spherical(point: NDArray[float64]) -> tuple:
    """
    Convert Cartesian coordinates to spherical coordinates.

    Uses ISO physics convention:
    - polar (theta): angle from +z axis (colatitude), range [0, π]
    - azimuth (phi): angle in xy-plane from +x axis, range (-π, π]

    Args:
        point: Cartesian coordinates [x, y, z]

    Returns:
        Tuple of (azimuth, polar) in radians
    """
    point = point / norm(point)
    x, y, z = point

    # Azimuth: angle in xy-plane from +x axis
    azimuth = arctan2(y, x)

    # Polar: angle from +z axis (colatitude)
    polar = arccos(clip(z, -1.0, 1.0))

    return azimuth, polar


def compute_spherical_arc_endpoint(
    arc: UnitSphericalArcABC,
) -> tuple[float, float]:
    """
    Compute the endpoint of a UnitSphericalArcABC on a unit sphere.

    Parameters
    ----------
    arc : UnitSphericalArcABC
        The spherical arc containing:
        - azimuth: Starting azimuth angle in radians (0 to 2π)
        - polar: Starting polar angle in radians (colatitude/zenith angle)
                 measured from vertical +Z axis (0 at north pole,
                 π/2 at equator, π at south pole)
        - arc_length: Length of the arc in radians (angular distance to travel)
        - orient: Orientation/bearing of the arc in radians (-π to π)
                  This is the direction to travel from the start point

    Returns
    -------
    Tuple[float, float]
        (azimuth_end, polar_end) - endpoint in spherical coordinates
        polar_end uses the same colatitude convention

    Notes
    -----
    This uses spherical trigonometry to compute great circle navigation.
    The polar angle uses colatitude convention (angle from +Z axis):
    - polar = 0 at north pole (+z axis)
    - polar = π/2 at equator
    - polar = π at south pole (-z axis)

    Examples
    --------
    >>> arc = UnitSphericalArcABC(
    ...     arc_length=deg2rad(45),
    ...     azimuth=0.0,
    ...     orient=0.0,
    ...     polar=deg2rad(90)  # Starting at equator
    ... )
    >>> azimuth_end, polar_end = compute_spherical_arc_endpoint(arc)
    """
    # polar is already in colatitude convention (angle from +Z axis)
    theta_start = arc.polar

    # Using spherical trigonometry formulas for great circle navigation:
    # cos(theta_end) = cos(theta_start)*cos(arc_length) +
    #                  sin(theta_start)*sin(arc_length)*cos(orient)
    cos_theta_end = cos(theta_start) * cos(arc.arc_length) + sin(theta_start) * sin(
        arc.arc_length
    ) * cos(arc.orient)
    theta_end = arccos(clip(cos_theta_end, -1.0, 1.0))

    # Compute the change in azimuth using:
    # sin(Δazimuth) = sin(arc_length)*sin(orient) / sin(theta_end)
    # cos(Δazimuth) = (cos(arc_length) - cos(theta_start)*cos(theta_end)) /
    #                 (sin(theta_start)*sin(theta_end))

    if abs(sin(theta_start)) < 1e-10:
        # Special case: starting point at pole
        # When starting from a pole, the ending azimuth is simply the bearing direction
        azimuth_end = arc.orient
    elif abs(sin(theta_end)) < 1e-10:
        # Special case: endpoint at pole
        azimuth_end = arc.azimuth
    else:
        sin_delta_az = sin(arc.arc_length) * sin(arc.orient) / sin(theta_end)
        cos_delta_az = (cos(arc.arc_length) - cos(theta_start) * cos(theta_end)) / (
            sin(theta_start) * sin(theta_end)
        )
        delta_azimuth = arctan2(sin_delta_az, cos_delta_az)
        azimuth_end = arc.azimuth + delta_azimuth

    # Normalize azimuth to [0, 2π)
    azimuth_end = azimuth_end % (2 * pi)

    polar_end = theta_end

    return azimuth_end, polar_end
