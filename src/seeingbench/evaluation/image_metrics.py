"""Image similarity metrics."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]


def image_similarity_metrics(
    reference: FloatArray,
    reconstruction: FloatArray,
    data_range: float = 1.0,
) -> dict[str, float]:
    """Return MSE, PSNR and global SSIM for two aligned images."""

    _validate_pair(reference, reconstruction)
    if data_range <= 0:
        raise ValueError("data_range must be positive")
    mse_value = mse(reference, reconstruction)
    return {
        "mse": mse_value,
        "psnr_db": psnr(mse_value, data_range=data_range),
        "ssim_global": ssim_global(reference, reconstruction, data_range=data_range),
    }


def mse(reference: FloatArray, reconstruction: FloatArray) -> float:
    """Return mean squared error."""

    _validate_pair(reference, reconstruction)
    diff = reconstruction - reference
    return float(np.mean(diff * diff))


def psnr(mse_value: float, data_range: float = 1.0) -> float:
    """Return peak signal-to-noise ratio in dB."""

    if mse_value < 0:
        raise ValueError("mse_value must be non-negative")
    if data_range <= 0:
        raise ValueError("data_range must be positive")
    if mse_value == 0:
        return math.inf
    return 10.0 * math.log10((data_range * data_range) / mse_value)


def ssim_global(
    reference: FloatArray, reconstruction: FloatArray, data_range: float = 1.0
) -> float:
    """Return a whole-image SSIM score.

    This is not windowed SSIM. It is intentionally small and deterministic for Phase 1, and
    can be replaced by a windowed implementation once that dependency decision is made.
    """

    _validate_pair(reference, reconstruction)
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    ref_mean = float(np.mean(reference))
    rec_mean = float(np.mean(reconstruction))
    ref_var = float(np.var(reference))
    rec_var = float(np.var(reconstruction))
    covariance = float(np.mean((reference - ref_mean) * (reconstruction - rec_mean)))
    numerator = (2.0 * ref_mean * rec_mean + c1) * (2.0 * covariance + c2)
    denominator = (ref_mean * ref_mean + rec_mean * rec_mean + c1) * (ref_var + rec_var + c2)
    if denominator == 0:
        raise ValueError("SSIM denominator is zero")
    return numerator / denominator


def _validate_pair(reference: FloatArray, reconstruction: FloatArray) -> None:
    validate_grayscale_image(reference)
    validate_grayscale_image(reconstruction)
    if reference.shape != reconstruction.shape:
        raise ValueError(f"shape mismatch: {reference.shape} != {reconstruction.shape}")
