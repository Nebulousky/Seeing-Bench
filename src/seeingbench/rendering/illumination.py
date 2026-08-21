"""Simple lunar illumination helpers for local ROI reference grids."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]


def lambertian_shading_from_dem(
    terrain_m: FloatArray,
    resolution_m_per_px: float,
    *,
    center_latitude_deg: float,
    center_longitude_deg_east: float,
    sub_solar_latitude_deg: float,
    sub_solar_longitude_deg_east: float,
) -> FloatArray:
    """Return local Lambertian shading from a north-up DEM and sub-solar point."""

    validate_grayscale_image(terrain_m)
    if resolution_m_per_px <= 0.0:
        raise ValueError("resolution_m_per_px must be positive")

    dz_dy, dz_dx = np.gradient(terrain_m, resolution_m_per_px, resolution_m_per_px)
    normal_x = -dz_dx
    normal_y = -dz_dy
    normal_z = np.ones_like(terrain_m)
    normal_norm = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
    normal_x /= normal_norm
    normal_y /= normal_norm
    normal_z /= normal_norm

    sun = _local_sun_vector(
        center_latitude_deg=center_latitude_deg,
        center_longitude_deg_east=center_longitude_deg_east,
        sub_solar_latitude_deg=sub_solar_latitude_deg,
        sub_solar_longitude_deg_east=sub_solar_longitude_deg_east,
    )
    shading = normal_x * sun[0] + normal_y * sun[1] + normal_z * sun[2]
    return np.maximum(shading, 0.0).astype(np.float64, copy=False)


def _local_sun_vector(
    *,
    center_latitude_deg: float,
    center_longitude_deg_east: float,
    sub_solar_latitude_deg: float,
    sub_solar_longitude_deg_east: float,
) -> tuple[float, float, float]:
    center_lat = math.radians(center_latitude_deg)
    center_lon = math.radians(center_longitude_deg_east)
    sun_lat = math.radians(sub_solar_latitude_deg)
    sun_lon = math.radians(sub_solar_longitude_deg_east)
    delta_lon = sun_lon - center_lon

    east = math.cos(sun_lat) * math.sin(delta_lon)
    north = math.sin(sun_lat) * math.cos(center_lat) - math.cos(sun_lat) * math.sin(
        center_lat
    ) * math.cos(delta_lon)
    up = math.sin(center_lat) * math.sin(sun_lat) + math.cos(center_lat) * math.cos(
        sun_lat
    ) * math.cos(delta_lon)
    norm = math.sqrt(east * east + north * north + up * up)
    if norm <= 0.0:
        raise ValueError("computed zero-length sun vector")
    return east / norm, north / norm, up / norm
