"""Dense displacement-field recovery metrics."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def warp_error_metrics(truth: FloatArray, estimate: FloatArray) -> dict[str, float]:
    """Return displacement-vector error statistics in pixels."""

    _validate_warp_pair(truth, estimate)
    error = np.linalg.norm(estimate - truth, axis=-1)
    return {
        "mean_px": float(np.mean(error)),
        "median_px": float(np.median(error)),
        "p95_px": float(np.percentile(error, 95.0)),
        "max_px": float(np.max(error)),
    }


def warp_error_by_component(
    truth_components: dict[str, FloatArray],
    estimate_components: dict[str, FloatArray],
) -> dict[str, dict[str, float]]:
    """Return displacement error statistics for matching named components."""

    missing = sorted(set(truth_components) - set(estimate_components))
    if missing:
        raise ValueError(f"missing estimated warp component(s): {', '.join(missing)}")
    return {
        name: warp_error_metrics(truth, estimate_components[name])
        for name, truth in truth_components.items()
    }


def _validate_warp_pair(truth: FloatArray, estimate: FloatArray) -> None:
    if truth.shape != estimate.shape:
        raise ValueError(f"shape mismatch: {truth.shape} != {estimate.shape}")
    if truth.ndim < 3 or truth.shape[-1] != 2:
        raise ValueError("warp fields must end with vector dimension 2")
    if truth.dtype != np.float64 or estimate.dtype != np.float64:
        raise TypeError("warp fields must be float64")
    if not np.isfinite(truth).all() or not np.isfinite(estimate).all():
        raise ValueError("warp fields must be finite")
