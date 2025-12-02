import numpy as np
from numpy import atan2, acos, pi

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.spatial.Quaternion import Quaternion


def quat_to_unitSphericalSmallCircle(
    q: Quaternion, radius_angle: float = pi / 4
) -> UnitSphericalSmallCircle:
    # Extract vector part

    r = np.sqrt(q.x**2 + q.y**2 + q.z**2)

    if r == 0:
        # Default to north pole if vector part is zero
        azimuth = 0.0
        polar = pi / 2
    else:
        polar = atan2(q.y, q.x)
        azimuth = acos(q.z / r)
    return UnitSphericalSmallCircle(
        azimuth=polar, polar=azimuth, radius_angle=radius_angle
    )
