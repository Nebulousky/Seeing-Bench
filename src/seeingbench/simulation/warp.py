"""Dense atmospheric displacement fields and image warping."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.config import WarpScaleConfig

FloatArray = NDArray[np.float64]


def validate_grayscale_image(image: FloatArray) -> None:
    """Validate the internal image contract: finite 2-D ``float64`` values."""

    if image.ndim != 2:
        raise ValueError(f"expected a 2-D grayscale image, got shape {image.shape}")
    if image.dtype != np.float64:
        raise TypeError(f"expected float64 image, got {image.dtype}")
    if not np.isfinite(image).all():
        raise ValueError("image contains NaN or infinite values")


def resize_bilinear(image: FloatArray, shape: tuple[int, int]) -> FloatArray:
    """Resize a 2-D image using bilinear interpolation with edge extension."""

    validate_grayscale_image(image)
    out_h, out_w = shape
    if out_h <= 0 or out_w <= 0:
        raise ValueError("output shape must be positive")
    in_h, in_w = image.shape
    if (out_h, out_w) == (in_h, in_w):
        return image.copy()

    y = np.linspace(0.0, in_h - 1.0, out_h)
    x = np.linspace(0.0, in_w - 1.0, out_w)
    grid_x, grid_y = np.meshgrid(x, y)
    return sample_bilinear(image, grid_x, grid_y)


def sample_bilinear(image: FloatArray, x_coords: FloatArray, y_coords: FloatArray) -> FloatArray:
    """Sample ``image`` at floating point x/y coordinates using edge extension."""

    validate_grayscale_image(image)
    if x_coords.shape != y_coords.shape:
        raise ValueError("x_coords and y_coords must have the same shape")

    h, w = image.shape
    x = np.clip(x_coords, 0.0, w - 1.0)
    y = np.clip(y_coords, 0.0, h - 1.0)

    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)

    wx = x - x0
    wy = y - y0

    top = (1.0 - wx) * image[y0, x0] + wx * image[y0, x1]
    bottom = (1.0 - wx) * image[y1, x0] + wx * image[y1, x1]
    return cast(FloatArray, (1.0 - wy) * top + wy * bottom)


def apply_warp(image: FloatArray, displacement: FloatArray) -> FloatArray:
    """Apply a dense displacement field.

    ``displacement[y, x] == [u, v]`` means the image content is displaced by ``u`` pixels
    horizontally and ``v`` pixels vertically at output pixel ``(x, y)``. The implementation
    samples the source at ``(x - u, y - v)``.
    """

    validate_grayscale_image(image)
    if displacement.shape != (*image.shape, 2):
        raise ValueError(
            "displacement must have shape (height, width, 2); "
            f"got {displacement.shape} for image {image.shape}"
        )
    if displacement.dtype != np.float64:
        raise TypeError(f"expected float64 displacement, got {displacement.dtype}")
    if not np.isfinite(displacement).all():
        raise ValueError("displacement contains NaN or infinite values")

    h, w = image.shape
    x, y = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    return sample_bilinear(image, x - displacement[..., 0], y - displacement[..., 1])


def generate_multiscale_warp_fields(
    shape: tuple[int, int],
    frame_count: int,
    scales: tuple[WarpScaleConfig, ...],
    temporal_correlation: float,
    rng: np.random.Generator,
) -> tuple[FloatArray, dict[str, FloatArray]]:
    """Generate temporally correlated smooth displacement fields.

    The fields are stochastic but reproducible through the caller-owned RNG. Each scale is
    retained separately so later metrics can report scale-specific recovery error.
    """

    h, w = shape
    if h <= 0 or w <= 0:
        raise ValueError("shape must be positive")
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if not 0 <= temporal_correlation < 1:
        raise ValueError("temporal_correlation must be in [0, 1)")
    for scale in scales:
        scale.validate()

    components: dict[str, FloatArray] = {}
    for scale in scales:
        components[scale.name] = _generate_scale_fields(
            shape=shape,
            frame_count=frame_count,
            scale=scale,
            temporal_correlation=temporal_correlation,
            rng=rng,
        )

    combined = np.zeros((frame_count, h, w, 2), dtype=np.float64)
    for component in components.values():
        combined += component
    return combined, components


def _generate_scale_fields(
    shape: tuple[int, int],
    frame_count: int,
    scale: WarpScaleConfig,
    temporal_correlation: float,
    rng: np.random.Generator,
) -> FloatArray:
    h, w = shape
    coarse_h = max(2, math.ceil(h / scale.correlation_px) + 1)
    coarse_w = max(2, math.ceil(w / scale.correlation_px) + 1)
    fields = np.empty((frame_count, h, w, 2), dtype=np.float64)
    state = _normalised_random_field((coarse_h, coarse_w, 2), rng)
    innovation_weight = math.sqrt(1.0 - temporal_correlation * temporal_correlation)

    for index in range(frame_count):
        if index > 0:
            innovation = _normalised_random_field((coarse_h, coarse_w, 2), rng)
            state = temporal_correlation * state + innovation_weight * innovation
            state = _normalise_component(state)

        upsampled = np.empty((h, w, 2), dtype=np.float64)
        upsampled[..., 0] = resize_bilinear(state[..., 0], shape)
        upsampled[..., 1] = resize_bilinear(state[..., 1], shape)
        fields[index] = _normalise_component(upsampled) * scale.amplitude_px
    return fields


def _normalised_random_field(shape: tuple[int, ...], rng: np.random.Generator) -> FloatArray:
    return _normalise_component(rng.normal(size=shape).astype(np.float64))


def _normalise_component(field: FloatArray) -> FloatArray:
    centred = field - np.mean(field, axis=(0, 1), keepdims=True)
    std = np.std(centred, axis=(0, 1), keepdims=True)
    std = np.where(std > 0, std, 1.0)
    return centred / std
