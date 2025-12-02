"""
Type hinting utilities for complex mathematical operations.

This module provides reusable type hints for NumPy arrays and scalars,
enabling strict and clear typing in mathematical code throughout the package.
"""

from typing import Union, TYPE_CHECKING
import numpy as np
from numpy import float64
from numpy.typing import NDArray
import quaternion

if TYPE_CHECKING:
    from pyMathTools.spatial.quaternion import Quaternion

# Basic numeric types
FloatOrNDArray = Union[float, NDArray[float64]]
FloatNDArray = NDArray[float64]

# Quaternion types
QuaternionLike = Union["Quaternion", np.quaternion, NDArray[np.quaternion]]
FloatOrQuaternion = Union["Quaternion", float, np.quaternion]
FloatArray3 = NDArray[float64]  # Shape (..., 3)
FloatArray4 = NDArray[float64]  # Shape (..., 4)
RotationMatrix = NDArray[float64]  # Shape (..., 3, 3)


if __name__ == "__main__":
    q = quaternion.one
    assert isinstance(q, np.quaternion)
