"""Small grayscale image IO helpers.

The TIFF support here intentionally covers only the uncompressed 16-bit grayscale files this
project writes. It is a benchmark exchange format, not a general image library.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]

_TIFF_SHORT = 3
_TIFF_LONG = 4
_TIFF_RATIONAL = 5


def load_grayscale_image(path: Path) -> FloatArray:
    """Load a supported grayscale image as finite ``float64`` values in [0, 1]."""

    suffix = path.suffix.lower()
    if suffix == ".npy":
        image = np.load(path).astype(np.float64, copy=False)
        validate_grayscale_image(image)
        return cast(FloatArray, image)
    if suffix in {".tif", ".tiff"}:
        return read_grayscale_tiff(path)
    raise ValueError(f"unsupported image format: {path.suffix}; supported: .npy, .tif")


def write_grayscale_tiff(path: Path, image: FloatArray) -> None:
    """Write an uncompressed 16-bit little-endian grayscale TIFF.

    The input must already be finite and in [0, 1]. Out-of-range data raises instead of
    being silently clipped or rescaled.
    """

    validate_grayscale_image(image)
    minimum = float(np.min(image))
    maximum = float(np.max(image))
    if minimum < 0.0 or maximum > 1.0:
        raise ValueError(f"cannot write TIFF: image range [{minimum}, {maximum}] is outside [0, 1]")

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.rint(image * 65535.0).astype("<u2", copy=False).tobytes()
    height, width = image.shape
    entries = 11
    ifd_offset = 8
    ifd_size = 2 + entries * 12 + 4
    x_resolution_offset = ifd_offset + ifd_size
    y_resolution_offset = x_resolution_offset + 8
    data_offset = y_resolution_offset + 8

    tags = [
        _entry(256, _TIFF_LONG, 1, width),
        _entry(257, _TIFF_LONG, 1, height),
        _entry(258, _TIFF_SHORT, 1, 16),
        _entry(259, _TIFF_SHORT, 1, 1),
        _entry(262, _TIFF_SHORT, 1, 1),
        _entry(273, _TIFF_LONG, 1, data_offset),
        _entry(277, _TIFF_SHORT, 1, 1),
        _entry(278, _TIFF_LONG, 1, height),
        _entry(279, _TIFF_LONG, 1, len(data)),
        _entry(282, _TIFF_RATIONAL, 1, x_resolution_offset),
        _entry(283, _TIFF_RATIONAL, 1, y_resolution_offset),
    ]

    with path.open("wb") as handle:
        handle.write(b"II")
        handle.write(struct.pack("<H", 42))
        handle.write(struct.pack("<I", ifd_offset))
        handle.write(struct.pack("<H", entries))
        for tag in tags:
            handle.write(tag)
        handle.write(struct.pack("<I", 0))
        handle.write(struct.pack("<II", 1, 1))
        handle.write(struct.pack("<II", 1, 1))
        handle.write(data)


def read_grayscale_tiff(path: Path) -> FloatArray:
    """Read uncompressed 8-bit or 16-bit grayscale TIFF files."""

    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path} is too small to be a TIFF")
    byte_order = data[:2]
    if byte_order == b"II":
        endian = "<"
    elif byte_order == b"MM":
        endian = ">"
    else:
        raise ValueError(f"{path} is not a TIFF file")
    magic, ifd_offset = struct.unpack_from(f"{endian}HI", data, 2)
    if magic != 42:
        raise ValueError(f"{path} has unsupported TIFF magic {magic}")

    tag_count = struct.unpack_from(f"{endian}H", data, ifd_offset)[0]
    tags: dict[int, tuple[int, int, int]] = {}
    cursor = ifd_offset + 2
    for _ in range(tag_count):
        tag, field_type, count, value = struct.unpack_from(f"{endian}HHII", data, cursor)
        tags[tag] = (field_type, count, value)
        cursor += 12

    width = _require_scalar(tags, 256, _TIFF_LONG)
    height = _require_scalar(tags, 257, _TIFF_LONG)
    bits_per_sample = _require_scalar(tags, 258, _TIFF_SHORT)
    compression = _require_scalar(tags, 259, _TIFF_SHORT)
    photometric = _require_scalar(tags, 262, _TIFF_SHORT)
    offset = _require_scalar(tags, 273, _TIFF_LONG)
    byte_count = _require_scalar(tags, 279, _TIFF_LONG)

    if compression != 1:
        raise ValueError("only uncompressed TIFF is supported")
    if photometric != 1:
        raise ValueError("only black-is-zero grayscale TIFF is supported")
    if bits_per_sample not in {8, 16}:
        raise ValueError("only 8-bit and 16-bit grayscale TIFF are supported")

    expected = width * height * (bits_per_sample // 8)
    if byte_count != expected:
        raise ValueError(
            f"unsupported TIFF strip layout: expected {expected} bytes, got {byte_count}"
        )

    raw = data[offset : offset + byte_count]
    if bits_per_sample == 8:
        image = np.frombuffer(raw, dtype=np.uint8).astype(np.float64).reshape((height, width))
        return image / 255.0
    image = np.frombuffer(raw, dtype=f"{endian}u2").astype(np.float64).reshape((height, width))
    return image / 65535.0


def _entry(tag: int, field_type: int, count: int, value: int) -> bytes:
    if field_type == _TIFF_SHORT and count == 1:
        return struct.pack("<HHI", tag, field_type, count) + struct.pack("<H", value) + b"\x00\x00"
    return struct.pack("<HHII", tag, field_type, count, value)


def _require_scalar(tags: dict[int, tuple[int, int, int]], tag: int, field_type: int) -> int:
    found = tags.get(tag)
    if found is None:
        raise ValueError(f"missing TIFF tag {tag}")
    actual_type, count, value = found
    if actual_type != field_type or count != 1:
        raise ValueError(f"unsupported TIFF tag {tag} layout")
    return value & 0xFFFF if field_type == _TIFF_SHORT else value
