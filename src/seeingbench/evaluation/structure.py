"""Structural image agreement metrics."""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.image_metrics import _validate_pair

FloatArray = NDArray[np.float64]


def gradient_correlation(reference: FloatArray, reconstruction: FloatArray) -> float:
    """Return Pearson correlation of gradient magnitudes."""

    _validate_pair(reference, reconstruction)
    ref_grad = _gradient_magnitude(reference)
    rec_grad = _gradient_magnitude(reconstruction)
    return _pearson(ref_grad.ravel(), rec_grad.ravel())


def edge_residual_map(reference: FloatArray, reconstruction: FloatArray) -> FloatArray:
    """Return absolute difference between gradient-magnitude maps."""

    _validate_pair(reference, reconstruction)
    return np.abs(_gradient_magnitude(reconstruction) - _gradient_magnitude(reference))


def _gradient_magnitude(image: FloatArray) -> FloatArray:
    gy, gx = np.gradient(image)
    return cast(FloatArray, np.hypot(gx, gy))


def _pearson(left: FloatArray, right: FloatArray) -> float:
    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denominator == 0:
        return 1.0 if np.array_equal(left, right) else 0.0
    return float(np.dot(left_centered, right_centered) / denominator)
