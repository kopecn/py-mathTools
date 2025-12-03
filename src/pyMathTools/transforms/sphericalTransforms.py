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

from numpy import pi
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
