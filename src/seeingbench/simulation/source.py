"""Small deterministic source images for offline examples and tests."""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def crater_field(
    shape: tuple[int, int] = (256, 256),
    crater_count: int = 48,
    seed: int = 0,
) -> FloatArray:
    """Generate a deterministic crater-like grayscale target.

    This is not orbital truth and is labelled as synthetic in metadata. It exists so the
    benchmark can be exercised without downloading external lunar data.
    """

    h, w = shape
    if h <= 0 or w <= 0:
        raise ValueError("shape must be positive")
    if crater_count < 0:
        raise ValueError("crater_count must be non-negative")

    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    base = 0.45 + 0.22 * (x / max(w - 1, 1)) + 0.08 * np.sin(y / 11.0)
    image = base.copy()

    for _ in range(crater_count):
        cx = rng.uniform(0, w - 1)
        cy = rng.uniform(0, h - 1)
        radius = rng.uniform(max(3.0, min(h, w) * 0.015), max(4.0, min(h, w) * 0.08))
        distance = np.hypot(x - cx, y - cy)
        rim = np.exp(-((distance - radius) ** 2) / (2.0 * (0.12 * radius) ** 2))
        bowl = np.exp(-(distance**2) / (2.0 * (0.62 * radius) ** 2))
        highlight = ((x - cx) * -0.7 + (y - cy) * -0.3) / max(radius, 1.0)
        image += 0.16 * rim
        image -= 0.12 * bowl
        image += 0.035 * rim * np.clip(highlight, -1.0, 1.0)

    image -= float(np.min(image))
    peak = float(np.max(image))
    if peak == 0:
        raise ValueError("generated blank source image")
    return cast(FloatArray, (image / peak).astype(np.float64))
