"""Constrained global registration helpers for standalone-reference evaluation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.image_metrics import _validate_pair
from seeingbench.reconstruction.alignment import (
    constant_displacement,
    estimate_integer_translation,
)
from seeingbench.simulation.warp import apply_warp, sample_bilinear, validate_grayscale_image

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class GlobalSimilarityRegistration:
    """Registered image and the selected global transform metadata."""

    image: FloatArray
    metadata: dict[str, Any]


def apply_global_similarity_transform(
    image: FloatArray,
    rotation_degrees: float = 0.0,
    scale: float = 1.0,
) -> FloatArray:
    """Apply a global centre-anchored rotation/scale transform with edge extension."""

    validate_grayscale_image(image)
    rotation_degrees = float(rotation_degrees)
    scale = float(scale)
    if not math.isfinite(rotation_degrees):
        raise ValueError("rotation_degrees must be finite")
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale must be a finite positive value")

    h, w = image.shape
    center_x = (w - 1.0) / 2.0
    center_y = (h - 1.0) / 2.0
    x, y = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    x_rel = x - center_x
    y_rel = y - center_y

    theta = math.radians(rotation_degrees)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    src_x = (cos_theta * x_rel + sin_theta * y_rel) / scale + center_x
    src_y = (-sin_theta * x_rel + cos_theta * y_rel) / scale + center_y
    return sample_bilinear(image, src_x, src_y)


def register_global_similarity(
    reference: FloatArray,
    moving: FloatArray,
    *,
    rotation_degrees: Sequence[float],
    scales: Sequence[float],
    register_translation: bool,
) -> GlobalSimilarityRegistration:
    """Select the best constrained global similarity transform by reference MSE."""

    _validate_pair(reference, moving)
    rotations = _normalise_rotation_candidates(rotation_degrees)
    scale_values = _normalise_scale_candidates(scales)
    best_image: FloatArray | None = None
    best_metadata: dict[str, Any] | None = None
    best_mse = math.inf

    for rotation in rotations:
        for scale in scale_values:
            candidate = apply_global_similarity_transform(moving, rotation, scale)
            shift_x = 0.0
            shift_y = 0.0
            if register_translation:
                shift_x, shift_y = estimate_integer_translation(reference, candidate)
                candidate = apply_warp(
                    candidate,
                    -constant_displacement(reference.shape, shift_x, shift_y),
                )
            mse = float(np.mean((reference - candidate) ** 2))
            if mse < best_mse:
                best_mse = mse
                best_image = candidate
                best_metadata = {
                    "method": "global_similarity_grid_search",
                    "constraint": (
                        "global centre-anchored rotation/scale grid search"
                        + (" plus global integer translation" if register_translation else "")
                    ),
                    "selected_rotation_degrees": rotation,
                    "selected_scale": scale,
                    "selected_shift_x_px": shift_x,
                    "selected_shift_y_px": shift_y,
                    "selected_mse": mse,
                    "candidate_count": len(rotations) * len(scale_values),
                    "rotation_degrees": list(rotations),
                    "scales": list(scale_values),
                    "translation_registered": register_translation,
                }

    if best_image is None or best_metadata is None:
        raise RuntimeError("registration candidate search produced no candidates")
    return GlobalSimilarityRegistration(image=best_image, metadata=best_metadata)


def _normalise_rotation_candidates(values: Sequence[float]) -> tuple[float, ...]:
    rotations = tuple(float(value) for value in values) or (0.0,)
    if not all(math.isfinite(value) for value in rotations):
        raise ValueError("registration rotation candidates must be finite")
    return rotations


def _normalise_scale_candidates(values: Sequence[float]) -> tuple[float, ...]:
    scales = tuple(float(value) for value in values) or (1.0,)
    if not all(math.isfinite(value) and value > 0.0 for value in scales):
        raise ValueError("registration scale candidates must be finite positive values")
    return scales
