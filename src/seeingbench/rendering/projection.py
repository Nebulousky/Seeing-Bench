"""Local Earth-view projection helpers for ROI reference grids."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.warp import sample_bilinear, validate_grayscale_image

FloatArray = NDArray[np.float64]


def local_orthographic_projection_matrix(
    *,
    center_latitude_deg: float,
    center_longitude_deg_east: float,
    sub_observer_latitude_deg: float,
    sub_observer_longitude_deg_east: float,
) -> tuple[FloatArray, float]:
    """Return a local map-grid to sky-plane projection matrix and visibility cosine."""

    surface_normal = _surface_vector(center_latitude_deg, center_longitude_deg_east)
    east = _east_vector(center_longitude_deg_east)
    north = np.cross(surface_normal, east)
    north /= np.linalg.norm(north)
    observer = _surface_vector(sub_observer_latitude_deg, sub_observer_longitude_deg_east)
    incidence_cosine = float(np.dot(surface_normal, observer))
    if incidence_cosine <= 0.0:
        raise ValueError("ROI centre is beyond the visible lunar limb")

    east_projected = east - float(np.dot(east, observer)) * observer
    north_projected = north - float(np.dot(north, observer)) * observer
    east_norm = float(np.linalg.norm(east_projected))
    if east_norm <= 0.0:
        raise ValueError("cannot construct projected east axis")
    sky_x = east_projected / east_norm
    sky_y = north_projected - float(np.dot(north_projected, sky_x)) * sky_x
    sky_y_norm = float(np.linalg.norm(sky_y))
    if sky_y_norm <= 0.0:
        raise ValueError("cannot construct projected north axis")
    sky_y /= sky_y_norm

    matrix = np.array(
        [
            [float(np.dot(east_projected, sky_x)), float(np.dot(north_projected, sky_x))],
            [float(np.dot(east_projected, sky_y)), float(np.dot(north_projected, sky_y))],
        ],
        dtype=np.float64,
    )
    return matrix, incidence_cosine


def apply_local_orthographic_projection(image: FloatArray, matrix: FloatArray) -> FloatArray:
    """Apply a centre-anchored local linear orthographic projection to an image."""

    validate_grayscale_image(image)
    if matrix.shape != (2, 2):
        raise ValueError("projection matrix must have shape (2, 2)")
    if matrix.dtype != np.float64:
        raise TypeError(f"expected float64 projection matrix, got {matrix.dtype}")
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) < 1e-12:
        raise ValueError("projection matrix is singular")

    h, w = image.shape
    center_x = (w - 1.0) / 2.0
    center_y = (h - 1.0) / 2.0
    x, y = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    output = np.stack((x - center_x, y - center_y), axis=0).reshape(2, -1)
    source = np.linalg.inv(matrix) @ output
    source_x = source[0].reshape(image.shape) + center_x
    source_y = source[1].reshape(image.shape) + center_y
    return sample_bilinear(image, source_x, source_y)


def _surface_vector(latitude_deg: float, longitude_deg_east: float) -> FloatArray:
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg_east)
    return np.array(
        [
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        ],
        dtype=np.float64,
    )


def _east_vector(longitude_deg_east: float) -> FloatArray:
    lon = math.radians(longitude_deg_east)
    return np.array([-math.sin(lon), math.cos(lon), 0.0], dtype=np.float64)
