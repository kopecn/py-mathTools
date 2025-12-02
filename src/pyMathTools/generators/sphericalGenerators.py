from typing import Tuple
from numpy import (
    clip,
    pi,
    arctan2,
    cos,
    sin,
    array,
    cross,
    linspace,
    zeros,
    sqrt,
    arccos,
    dot,
)
from numpy.linalg import norm
from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.hints import FloatNDArray


def generate_spherical_small_circle_points(
    circle: UnitSphericalSmallCircle,
    num_points: int = 120,
) -> Tuple[FloatNDArray, FloatNDArray]:
    """
    Generate points on a true small circle on a unit sphere.

    A small circle is the set of all points at a fixed angular distance (radius_angle)
    from a center point on the sphere.

    Parameters:
    -----------
    circle.azimuth : float or NDArray
        Azimuth angle of circle center (radians, -2π to 2π)
    polar_center : float or NDArray
        Polar angle of circle center (radians, 0 to π)
    radius_angle : float or NDArray
        Angular radius of the circle (radians)
    num_points : int
        Number of points to generate around the circle

    Returns:
    --------
    azimuth_points : NDArray
        Azimuth angles of points on the circle
    polar_points : NDArray
        Polar angles of points on the circle
    """
    # Convert center to Cartesian coordinates (physics convention)
    # theta (polar) = 0 at north pole, pi at south pole
    # phi (azimuth) = rotation about Z axis
    x_center = sin(circle.polar) * cos(circle.azimuth)
    y_center = sin(circle.polar) * sin(circle.azimuth)
    z_center = cos(circle.polar)
    center = array([x_center, y_center, z_center])

    # Create orthonormal basis at the center point
    # North pole direction
    north = array([0, 0, 1])

    # Tangent vector 1 (east direction)
    if abs(z_center) < 0.999:  # Not at poles
        east = cross(north, center)
        east = east / norm(east)
    else:  # At poles, use arbitrary east direction
        east = array([1, 0, 0])

    # Tangent vector 2 (north direction in tangent plane)
    north_tangent = cross(center, east)
    north_tangent = north_tangent / norm(north_tangent)

    # Generate points around the circle
    theta = linspace(-pi, pi, num_points)

    # Points on the small circle using rotation
    # The small circle is at angular distance radius_angle from center
    azimuth_points = zeros(num_points)
    polar_points = zeros(num_points)

    for i, t in enumerate(theta):
        # Local coordinates: move radius_angle away from center in direction t
        local_direction = cos(t) * east + sin(t) * north_tangent

        # Rotate center point toward local_direction by radius_angle
        # Using Rodrigues' rotation formula
        axis = cross(center, local_direction)
        axis_norm = norm(axis)

        if axis_norm > 1e-10:
            axis = axis / axis_norm
            # Rotate center around axis by radius_angle
            cos_angle = cos(circle.radius_angle)
            sin_angle = sin(circle.radius_angle)

            point = (
                cos_angle * center
                + sin_angle * cross(axis, center)
                + (1 - cos_angle) * dot(axis, center) * axis
            )
        else:
            # If no rotation needed (shouldn't happen)
            point = center

        # Convert back to spherical coordinates (physics convention)
        x, y, z = point
        r = sqrt(x**2 + y**2 + z**2)
        x, y, z = x / r, y / r, z / r  # Normalize to unit sphere

        polar_points[i] = arccos(clip(z, -1, 1))
        azimuth_points[i] = arctan2(y, x)

    return azimuth_points, polar_points
