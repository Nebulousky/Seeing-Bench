"""Sensor sampling helpers."""

from __future__ import annotations

from typing import cast

import numpy as np

from seeingbench.simulation.warp import FloatArray, validate_grayscale_image


def block_average_downsample(image: FloatArray, factor: int) -> FloatArray:
    """Downsample by integer block averaging.

    The image dimensions must be divisible by ``factor`` so no border pixels are silently
    discarded.
    """

    validate_grayscale_image(image)
    if factor <= 0:
        raise ValueError("factor must be positive")
    if factor == 1:
        return image.copy()
    height, width = image.shape
    if height % factor != 0 or width % factor != 0:
        raise ValueError(
            f"image shape {image.shape} is not divisible by downsample factor {factor}"
        )
    reshaped = image.reshape(height // factor, factor, width // factor, factor)
    return cast(FloatArray, np.mean(reshaped, axis=(1, 3), dtype=np.float64))
