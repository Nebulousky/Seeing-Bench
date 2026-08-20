"""Frame-alignment helpers for reconstruction baselines."""

from __future__ import annotations

import math

import numpy as np

from seeingbench.evaluation.image_metrics import _validate_pair
from seeingbench.simulation.warp import resize_bilinear


def estimate_integer_translation(reference: np.ndarray, moving: np.ndarray) -> tuple[float, float]:
    """Estimate integer x/y translation from ``reference`` to ``moving``.

    The returned ``(u, v)`` follows the project warp convention: positive ``u`` means image
    content is displaced right, and positive ``v`` means image content is displaced down.
    """

    _validate_pair(reference, moving)
    h, w = reference.shape
    window = np.outer(_window(h), _window(w))
    ref = (reference - float(np.mean(reference))) * window
    mov = (moving - float(np.mean(moving))) * window

    cross_power = np.fft.fft2(mov) * np.conj(np.fft.fft2(ref))
    magnitude = np.abs(cross_power)
    if not np.any(magnitude > 0):
        return (0.0, 0.0)
    phase = np.divide(
        cross_power,
        magnitude,
        out=np.zeros_like(cross_power),
        where=magnitude > 0,
    )
    correlation = np.fft.ifft2(phase).real
    peak_y, peak_x = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    if peak_y > h // 2:
        peak_y -= h
    if peak_x > w // 2:
        peak_x -= w
    return (float(peak_x), float(peak_y))


def constant_displacement(
    shape: tuple[int, int],
    u_px: float,
    v_px: float,
) -> np.ndarray:
    """Create a dense constant displacement field."""

    h, w = shape
    if h <= 0 or w <= 0:
        raise ValueError("shape must be positive")
    displacement = np.empty((h, w, 2), dtype=np.float64)
    displacement[..., 0] = u_px
    displacement[..., 1] = v_px
    return displacement


def estimate_local_translation_field(
    reference: np.ndarray,
    moving: np.ndarray,
    block_size_px: int = 32,
) -> np.ndarray:
    """Estimate a dense piecewise-smooth x/y translation field.

    Each coarse cell uses the same phase-correlation convention as
    :func:`estimate_integer_translation`; the cell estimates are then bilinearly upsampled to
    the full image. The returned field maps ``reference`` to ``moving``.
    """

    _validate_pair(reference, moving)
    if block_size_px < 4:
        raise ValueError("block_size_px must be at least 4")

    h, w = reference.shape
    rows = math.ceil(h / block_size_px)
    cols = math.ceil(w / block_size_px)
    coarse_u = np.empty((rows, cols), dtype=np.float64)
    coarse_v = np.empty((rows, cols), dtype=np.float64)

    for row in range(rows):
        y0, y1 = _block_bounds(row, rows, h, block_size_px)
        for col in range(cols):
            x0, x1 = _block_bounds(col, cols, w, block_size_px)
            shift_x, shift_y = estimate_integer_translation(
                reference[y0:y1, x0:x1],
                moving[y0:y1, x0:x1],
            )
            coarse_u[row, col] = shift_x
            coarse_v[row, col] = shift_y

    field = np.empty((h, w, 2), dtype=np.float64)
    field[..., 0] = resize_bilinear(coarse_u, (h, w))
    field[..., 1] = resize_bilinear(coarse_v, (h, w))
    return field


def _block_bounds(index: int, count: int, length: int, block_size_px: int) -> tuple[int, int]:
    start = index * block_size_px
    stop = min(start + block_size_px, length)
    if stop - start >= 4 or count == 1:
        return start, stop
    return max(0, length - 4), length


def _window(length: int) -> np.ndarray:
    if length <= 1:
        return np.ones(length, dtype=np.float64)
    return np.hanning(length).astype(np.float64)
