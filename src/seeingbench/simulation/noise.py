"""Noise and sensor-range modelling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class SensorRangeResult:
    """Image after explicit sensor saturation and the number of saturated pixels."""

    image: FloatArray
    low_saturated: int
    high_saturated: int


def add_gaussian_noise(
    image: FloatArray,
    sigma: float,
    rng: np.random.Generator,
) -> FloatArray:
    """Add zero-mean Gaussian noise without changing range or dtype silently."""

    validate_grayscale_image(image)
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    if sigma == 0:
        return image.copy()
    return image + rng.normal(loc=0.0, scale=sigma, size=image.shape).astype(np.float64)


def apply_sensor_range(image: FloatArray, minimum: float, maximum: float) -> SensorRangeResult:
    """Apply explicit sensor saturation to the configured numeric range."""

    validate_grayscale_image(image)
    if minimum >= maximum:
        raise ValueError("minimum must be less than maximum")
    low = int(np.count_nonzero(image < minimum))
    high = int(np.count_nonzero(image > maximum))
    return SensorRangeResult(
        image=np.clip(image, minimum, maximum),
        low_saturated=low,
        high_saturated=high,
    )
