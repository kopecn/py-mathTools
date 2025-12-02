"""
Transforms for spherical coordinate systems.

This module provides functions for converting to and from spherical coordinates,
including projections and other mathematical transformations commonly used in
geometry, mapping, and scientific computing.
"""

from numpy import pi
from pyMathTools.hints import FloatOrNDArray


def plate_carree_transform(
    azimuth: FloatOrNDArray, polar: FloatOrNDArray
) -> tuple[FloatOrNDArray, FloatOrNDArray]:
    """
    Apply plate carrée (equirectangular) projection to spherical coordinates (physics convention).

    This is a simple cylindrical projection that preserves angular measurements,
    making it suitable for robot positioning where actual angles in radians are needed.

    Parameters:
    -----------
    azimuth : float or ndarray
        Azimuth angle(s) in radians (0 to 2π), rotation about Z axis
    polar : float or ndarray
        Polar angle(s) in radians (0 to π), angle from north pole

    Returns:
    --------
    - x : float or ndarray
        Azimuth in radians (0 to 2π)
    - y : float or ndarray
        Latitude in radians (-π/2 to π/2), where:
        - π/2 = north pole
        - 0 = equator
        - -π/2 = south pole
    """
    x = azimuth
    # Convert physics polar angle (theta, 0 to π) to latitude (-π/2 to π/2)
    # lat = π/2 - theta
    y = pi / 2 - polar
    return x, y
