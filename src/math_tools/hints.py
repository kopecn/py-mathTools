"""
Type hinting utilities for complex mathematical operations.

This module provides reusable type hints for NumPy arrays and scalars,
enabling strict and clear typing in mathematical code throughout the package.
"""

from typing import TYPE_CHECKING, Union

from numpy import float64
from numpy.typing import NDArray
from quaternion import one as q_one  # type: ignore[import-untyped]
from quaternion import quaternion as np_quaternion

if TYPE_CHECKING:
    from math_tools.spatial.quaternion import Quaternion

# Basic numeric types
FloatOrNDArray = float | NDArray[float64]
FloatNDArray = NDArray[float64]

# Quaternion types
QuaternionLike = Union["Quaternion", np_quaternion, NDArray[np_quaternion]]
FloatOrQuaternion = Union["Quaternion", float, np_quaternion]
FloatArray3 = NDArray[float64]  # Shape (..., 3)
FloatArray4 = NDArray[float64]  # Shape (..., 4)
RotationMatrix = NDArray[float64]  # Shape (..., 3, 3)


if __name__ == "__main__":
    q = q_one
    assert isinstance(q, np_quaternion)
