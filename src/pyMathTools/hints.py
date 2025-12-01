"""
Type hinting utilities for complex mathematical operations.

This module provides reusable type hints for NumPy arrays and scalars,
enabling strict and clear typing in mathematical code throughout the package.
"""

from typing import Union
from numpy import float64
from numpy.typing import NDArray

FloatOrNDArray = Union[float, NDArray[float64]]

FloatNDArray = NDArray[float64]
