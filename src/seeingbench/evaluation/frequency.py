"""Spatial-frequency recovery metrics."""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.image_metrics import _validate_pair

FloatArray = NDArray[np.float64]


def radial_frequency_correlation(
    reference: FloatArray,
    reconstruction: FloatArray,
    bins: int = 24,
) -> list[dict[str, float | int]]:
    """Return phase-sensitive spectral fidelity by frequency bin.

    Frequencies are reported as fractions of the axial sampled-image Nyquist frequency.
    Diagonal Fourier samples above axial Nyquist are outside the reported radial range.
    Each bin score is Fourier ring correlation multiplied by an energy-recovery factor, so
    phase-scrambled and strongly attenuated frequencies are both penalized.
    """

    _validate_pair(reference, reconstruction)
    if bins <= 0:
        raise ValueError("bins must be positive")

    ref_fft = np.fft.fftshift(np.fft.fft2(reference))
    rec_fft = np.fft.fftshift(np.fft.fft2(reconstruction))
    radius = _normalised_radius(reference.shape)
    independent = _independent_frequency_mask(reference.shape)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float | int]] = []

    for index in range(bins):
        low = edges[index]
        high = edges[index + 1]
        mask = (radius >= low) & (radius < high if index < bins - 1 else radius <= high)
        fourier_sample_count = int(np.count_nonzero(mask))
        independent_sample_count = int(np.count_nonzero(mask & independent))
        if fourier_sample_count < 1:
            correlation = float("nan")
            phase_correlation = float("nan")
            amplitude_recovery = float("nan")
        else:
            phase_correlation = _fourier_ring_correlation(ref_fft[mask], rec_fft[mask])
            amplitude_recovery = _amplitude_recovery(ref_fft[mask], rec_fft[mask])
            correlation = phase_correlation * amplitude_recovery
        rows.append(
            {
                "bin": index,
                "frequency_min_fraction": float(low),
                "frequency_max_fraction": float(high),
                "frequency_mid_fraction": float((low + high) / 2.0),
                "sample_count": independent_sample_count,
                "fourier_sample_count": fourier_sample_count,
                "correlation": correlation,
                "phase_correlation": phase_correlation,
                "amplitude_recovery": amplitude_recovery,
            }
        )
    return rows


def frequency_recovery_limit(
    curve: list[dict[str, float | int]],
    threshold: float = 0.5,
) -> float:
    """Return the highest contiguous low-to-high frequency passing ``threshold``."""

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    limit = 0.0
    saw_passing_bin = False
    for row in curve:
        correlation = float(row["correlation"])
        if not np.isfinite(correlation):
            continue
        if correlation < threshold:
            if saw_passing_bin:
                break
            continue
        saw_passing_bin = True
        limit = float(row["frequency_mid_fraction"])
    return limit


def _normalised_radius(shape: tuple[int, int]) -> FloatArray:
    h, w = shape
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    grid_x, grid_y = np.meshgrid(fx, fy)
    radius = np.hypot(grid_x, grid_y)
    nyquist = 0.5
    if h <= 1 and w <= 1:
        raise ValueError("cannot compute frequency radius for a degenerate image")
    return radius / nyquist


def _independent_frequency_mask(shape: tuple[int, int]) -> NDArray[np.bool_]:
    h, w = shape
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    grid_x, grid_y = np.meshgrid(fx, fy)
    return cast(NDArray[np.bool_], (grid_y > 0.0) | ((grid_y == 0.0) & (grid_x >= 0.0)))


def _fourier_ring_correlation(reference: np.ndarray, reconstruction: np.ndarray) -> float:
    numerator = float(np.real(np.sum(reference * np.conj(reconstruction))))
    denominator = float(
        np.sqrt(np.sum(np.abs(reference) ** 2) * np.sum(np.abs(reconstruction) ** 2))
    )
    if denominator == 0:
        return 1.0 if np.array_equal(reference, reconstruction) else 0.0
    return numerator / denominator


def _amplitude_recovery(reference: np.ndarray, reconstruction: np.ndarray) -> float:
    reference_energy = float(np.sum(np.abs(reference) ** 2))
    reconstruction_energy = float(np.sum(np.abs(reconstruction) ** 2))
    if reference_energy == 0.0 and reconstruction_energy == 0.0:
        return 1.0
    if reference_energy == 0.0 or reconstruction_energy == 0.0:
        return 0.0
    ratio = np.sqrt(reconstruction_energy / reference_energy)
    return float(min(ratio, 1.0 / ratio))
