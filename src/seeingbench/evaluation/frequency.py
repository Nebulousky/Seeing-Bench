"""Spatial-frequency recovery metrics."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.image_metrics import _validate_pair

FloatArray = NDArray[np.float64]


def radial_frequency_correlation(
    reference: FloatArray,
    reconstruction: FloatArray,
    bins: int = 24,
) -> list[dict[str, float | int]]:
    """Return radial Fourier-magnitude correlation by frequency bin.

    Frequencies are reported as fractions of the image Nyquist frequency, so 1.0 is the
    largest radial frequency represented by the sampled image.
    """

    _validate_pair(reference, reconstruction)
    if bins <= 0:
        raise ValueError("bins must be positive")

    ref_fft = np.fft.fftshift(np.fft.fft2(reference))
    rec_fft = np.fft.fftshift(np.fft.fft2(reconstruction))
    ref_mag = np.abs(ref_fft)
    rec_mag = np.abs(rec_fft)
    radius = _normalised_radius(reference.shape)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float | int]] = []

    for index in range(bins):
        low = edges[index]
        high = edges[index + 1]
        mask = (radius >= low) & (radius < high if index < bins - 1 else radius <= high)
        count = int(np.count_nonzero(mask))
        if count < 2:
            correlation = float("nan")
        else:
            correlation = _pearson(ref_mag[mask], rec_mag[mask])
        rows.append(
            {
                "bin": index,
                "frequency_min_fraction": float(low),
                "frequency_max_fraction": float(high),
                "frequency_mid_fraction": float((low + high) / 2.0),
                "sample_count": count,
                "correlation": correlation,
            }
        )
    return rows


def frequency_recovery_limit(
    curve: list[dict[str, float | int]],
    threshold: float = 0.5,
) -> float:
    """Return highest frequency-bin midpoint whose correlation reaches ``threshold``."""

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    passed = [
        float(row["frequency_mid_fraction"])
        for row in curve
        if float(row["correlation"]) >= threshold
    ]
    return max(passed) if passed else 0.0


def _normalised_radius(shape: tuple[int, int]) -> FloatArray:
    h, w = shape
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    grid_x, grid_y = np.meshgrid(fx, fy)
    radius = np.hypot(grid_x, grid_y)
    peak = float(np.max(radius))
    if peak == 0:
        raise ValueError("cannot compute frequency radius for a degenerate image")
    return radius / peak


def _pearson(left: FloatArray, right: FloatArray) -> float:
    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denominator == 0:
        return 1.0 if np.array_equal(left, right) else 0.0
    return float(np.dot(left_centered, right_centered) / denominator)
