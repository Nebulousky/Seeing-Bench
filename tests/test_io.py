from __future__ import annotations

import struct
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


def test_big_endian_tiff_short_tags_are_read_from_high_word(tmp_path: Path) -> None:
    path = tmp_path / "big-endian.tif"
    image_bytes = bytes([0, 85, 170, 255])
    entries = [
        _be_entry(256, 4, 1, 2),
        _be_entry(257, 4, 1, 2),
        _be_entry(258, 3, 1, 8 << 16),
        _be_entry(259, 3, 1, 1 << 16),
        _be_entry(262, 3, 1, 1 << 16),
        _be_entry(273, 4, 1, 98),
        _be_entry(279, 4, 1, len(image_bytes)),
    ]
    payload = b"MM" + struct.pack(">HIH", 42, 8, len(entries))
    payload += b"".join(entries) + struct.pack(">I", 0) + image_bytes
    path.write_bytes(payload)

    loaded = read_grayscale_tiff(path)

    np.testing.assert_allclose(
        loaded,
        np.array([[0, 85], [170, 255]], dtype=np.float64) / 255.0,
    )


def _be_entry(tag: int, field_type: int, count: int, value: int) -> bytes:
    return struct.pack(">HHII", tag, field_type, count, value)
