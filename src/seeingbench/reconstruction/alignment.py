"""Frame-alignment helpers for reconstruction baselines."""

from __future__ import annotations

import numpy as np

from seeingbench.evaluation.image_metrics import _validate_pair


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


def _window(length: int) -> np.ndarray:
    if length <= 1:
        return np.ones(length, dtype=np.float64)
    return np.hanning(length).astype(np.float64)
