from __future__ import annotations

from pathlib import Path

import numpy as np

from seeingbench.io.images import read_grayscale_tiff, write_grayscale_tiff


def test_grayscale_tiff_round_trip_with_quantisation_tolerance(tmp_path: Path) -> None:
    image = np.linspace(0.0, 1.0, 25, dtype=np.float64).reshape((5, 5))
    path = tmp_path / "image.tif"

    write_grayscale_tiff(path, image)
    loaded = read_grayscale_tiff(path)

    # The writer stores 16-bit integer samples, so half an LSB is the expected bound.
    np.testing.assert_allclose(loaded, image, atol=1.0 / 131070.0)
