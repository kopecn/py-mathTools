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
from foundationTypes.mathTypes.UnitSphericalArc import UnitSphericalArc

from pyMathTools.hints import FloatNDArray, FloatArray3


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
    circle.polar : float or NDArray
        Polar angle of circle center (radians, physics convention: 0 to π)
        where 0 = north pole, π/2 = equator, π = south pole
    circle.radius_angle : float or NDArray
        Angular radius of the circle (radians)
    num_points : int
        Number of points to generate around the circle

    Returns:
    --------
    azimuth_points : NDArray
        Azimuth angles of points on the circle (radians)
    polar_points : NDArray
        Polar angles of points on the circle (physics convention: 0 to π, colatitude)
    """
    # Use physics convention directly: polar ∈ [0, π], where 0 = north pole, π/2 = equator
    # Convert center to Cartesian coordinates (physics convention)
    # theta (polar/colatitude) = 0 at north pole, π at south pole
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

        # Output in physics convention for compatibility with downstream code
        polar_points[i] = arccos(clip(z, -1, 1))  # colatitude (0 to π)
        azimuth_points[i] = arctan2(y, x)  # azimuth

    return azimuth_points, polar_points


def generate_spherical_arc_points(
    arc: UnitSphericalArc,
    num_points: int = 120,
) -> Tuple[FloatNDArray, FloatNDArray]:
    """
    Generate points along an arc on a unit sphere.

    The arc starts at the point (azimuth, polar) and extends along a great circle
    in the direction determined by the orient parameter for the specified arc_length.

    The orientation follows the right-hand rule: point your right thumb along the radial
    vector (from origin through the start point), and your fingers curl in the positive
    direction of rotation (positive orient).

    Parameters:
    -----------
    arc : UnitSphericalArc
        Arc specification with:
        - azimuth: starting point longitude (radians)
        - polar: starting point colatitude in physics convention (0 to π, 0 = north pole)
        - orient: rotation angle about the radial vector (radians, -π to π)
                  Following right-hand rule: thumb along radial, fingers curl in +orient direction
        - arc_length: extension along great circle (radians, can be negative)
    num_points : int
        Number of points to generate along the arc

    Returns:
    --------
    azimuth_points : NDArray
        Azimuth angles of points along the arc (radians)
    polar_points : NDArray
        Polar angles of points along the arc (physics convention: 0 to π, colatitude)
    """
    # Use physics convention directly: polar ∈ [0, π], where 0 = north pole, π/2 = equator
    # Convert starting point to Cartesian coordinates (physics convention)
    x_start = sin(arc.polar) * cos(arc.azimuth)
    y_start = sin(arc.polar) * sin(arc.azimuth)
    z_start = cos(arc.polar)
    start_point = array([x_start, y_start, z_start])

    # Create tangent direction based on the orient parameter
    # The orient defines the rotation angle about the radial vector (right-hand rule)
    # We need to create an orthonormal basis in the tangent plane and rotate by orient
    # Convention: orient=0 points towards the north pole in the tangent plane

    north = array([0, 0, 1])

    # Create an orthonormal basis in the tangent plane
    # Following right-hand rule: thumb along radial, fingers curl in positive orient direction
    if abs(z_start) < 0.999:  # Not at poles
        # East direction: perpendicular to both north and radial
        east = cross(north, start_point)
        east = east / norm(east)

        # North direction in tangent plane: completes right-handed system
        # cross(north_tangent, east) = start_point (outward radial)
        north_tangent = cross(east, start_point)
        north_tangent = north_tangent / norm(north_tangent)

        ref_tangent = north_tangent
        second_tangent = east
    else:  # At poles, use arbitrary reference
        ref_tangent = array([1, 0, 0])
        second_tangent = array([0, 1, 0])

    # Rotate by the orient angle about the radial vector (right-hand rule)
    # orient=0 points north, positive orient rotates towards east
    initial_direction = cos(arc.orient) * ref_tangent + sin(arc.orient) * second_tangent
    initial_direction = initial_direction / norm(initial_direction)

    # The rotation axis for the arc is perpendicular to the initial direction and radial
    rotation_axis = cross(start_point, initial_direction)
    rotation_axis = rotation_axis / norm(rotation_axis)

    # Generate points along the arc
    # Arc length parameter: 0 to arc_length
    t = linspace(0, arc.arc_length, num_points)

    azimuth_points = zeros(num_points)
    polar_points = zeros(num_points)

    for i, arc_dist in enumerate(t):
        # Move along great circle in the direction determined by orient
        # Using Rodrigues' rotation formula
        # Rotation axis is perpendicular to initial direction (follows from right-hand rule)
        axis = rotation_axis

        # Rotate start_point around axis by arc_dist
        cos_angle = cos(arc_dist)
        sin_angle = sin(arc_dist)

        point = (
            cos_angle * start_point
            + sin_angle * cross(axis, start_point)
            + (1 - cos_angle) * dot(axis, start_point) * axis
        )

        # Convert back to spherical coordinates (physics convention)
        x, y, z = point
        r = sqrt(x**2 + y**2 + z**2)
        x, y, z = x / r, y / r, z / r  # Normalize to unit sphere

        # Output in physics convention for compatibility with downstream code
        polar_points[i] = arccos(clip(z, -1, 1))  # colatitude (0 to π)
        azimuth_points[i] = arctan2(y, x)  # azimuth

    return azimuth_points, polar_points


def quaternion_to_spherical_vector(quaternion) -> Tuple[FloatArray3, float, float]:
    """
    Convert a quaternion to a unit vector in spherical coordinates.

    The quaternion is applied to a reference direction (positive Z-axis)
    to get the pointing direction, which is then converted to spherical coordinates.

    Parameters:
    -----------
    quaternion : Quaternion
        A quaternion object representing a rotation

    Returns:
    --------
    cartesian_point : FloatArray3
        The Cartesian coordinates [x, y, z] of the rotated unit vector
    azimuth : float
        Azimuth angle in radians (-π to π)
    polar : float
        Polar angle in radians (0 to π, physics convention: 0 = north pole)
    """
    # Reference direction: positive Z-axis (north pole)
    reference_direction = array([0.0, 0.0, 1.0])

    # Apply quaternion rotation to the reference direction
    rotated_vector = quaternion.rotate_vector(reference_direction)

    # Normalize to ensure it's a unit vector
    x, y, z = rotated_vector
    r = sqrt(x**2 + y**2 + z**2)
    if r > 1e-10:
        x, y, z = x / r, y / r, z / r

    # Convert to spherical coordinates (physics convention)
    polar = arccos(clip(z, -1, 1))  # colatitude (0 to π)
    azimuth = arctan2(y, x)  # azimuth (-π to π)

    cartesian_point = array([x, y, z])

    return cartesian_point, azimuth, polar
