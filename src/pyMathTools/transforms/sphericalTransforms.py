"""
Transforms for spherical coordinate systems.

This module provides functions for converting to and from spherical coordinates,
including projections and other mathematical transformations commonly used in
geometry, mapping, and scientific computing.
"""

from numpy import log, clip, pi, tan, arctan2, cos, sin, arctanh
from pyMathTools.hints import FloatOrNDArray


def mercator_transform(
    azimuth: FloatOrNDArray, polar: FloatOrNDArray
) -> tuple[FloatOrNDArray, FloatOrNDArray]:
    """
    Apply Mercator projection to spherical coordinates.

    Parameters:
    -----------
    azimuth : float or ndarray
        Azimuth angle(s) in radians (0 to 2π)
    polar : float or ndarray
        Polar angle(s) in radians (-π/2 to π/2)

    Returns:
    --------
    - x : float or ndarray
        Mercator x coordinate (longitude)
    - y : float or ndarray
        Polar (radians) coordinate (latitude projection)
    """
    x = azimuth
    # Mercator projection: y = ln(tan(π/4 + lat/2))
    # Clamp polar to avoid infinities at poles
    polar_clamped = clip(polar, -pi / 2 + 0.001, pi / 2 - 0.001)
    y = log(tan(pi / 4 + polar_clamped / 2))
    return x, y


def gauss_kruger_transform(
    azimuth: FloatOrNDArray,
    polar: FloatOrNDArray,
    central_meridian: float = pi,
) -> tuple[FloatOrNDArray, FloatOrNDArray]:
    """
    Apply Gauss-Krüger (Transverse Mercator) projection to spherical coordinates.

    Parameters:
    -----------
    azimuth : float or ndarray
        Azimuth angle(s) in radians (0 to 2π)
    polar : float or ndarray
        Polar angle(s) in radians (-π/2 to π/2)
    central_meridian : float, optional
        Central meridian in radians (default: π)

    Returns:
    --------
    easting : float or ndarray
        Gauss-Krüger easting coordinate
    northing : float or ndarray
        Gauss-Krüger northing coordinate
    """
    # Adjust azimuth relative to central meridian
    lambda_rel = azimuth - central_meridian

    # Normalize to [-π, π]
    lambda_rel = arctan2(sin(lambda_rel), cos(lambda_rel))

    # Clamp polar to avoid numerical issues
    polar_clamped = clip(polar, -pi / 2 + 0.001, pi / 2 - 0.001)

    # Transverse Mercator formulas for a sphere
    # Easting
    easting = arctanh(cos(polar_clamped) * sin(lambda_rel))

    # Northing
    northing = arctan2(sin(polar_clamped), cos(polar_clamped) * cos(lambda_rel))

    return easting, northing
