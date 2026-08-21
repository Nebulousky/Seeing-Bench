"""Simple lunar illumination helpers for local ROI reference grids."""

from __future__ import annotations

import math
from typing import cast

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

    return lunar_shading_from_dem(
        terrain_m,
        resolution_m_per_px,
        center_latitude_deg=center_latitude_deg,
        center_longitude_deg_east=center_longitude_deg_east,
        sub_solar_latitude_deg=sub_solar_latitude_deg,
        sub_solar_longitude_deg_east=sub_solar_longitude_deg_east,
        model="lambertian",
    )


def lunar_shading_from_dem(
    terrain_m: FloatArray,
    resolution_m_per_px: float,
    *,
    center_latitude_deg: float,
    center_longitude_deg_east: float,
    sub_solar_latitude_deg: float,
    sub_solar_longitude_deg_east: float,
    model: str = "lambertian",
    sub_observer_latitude_deg: float | None = None,
    sub_observer_longitude_deg_east: float | None = None,
) -> FloatArray:
    """Return local terrain shading for a simple lunar photometric model."""

    validate_grayscale_image(terrain_m)
    if resolution_m_per_px <= 0.0:
        raise ValueError("resolution_m_per_px must be positive")
    if model not in {"lambertian", "lommel_seeliger"}:
        raise ValueError("illumination model must be 'lambertian' or 'lommel_seeliger'")

    dz_dy, dz_dx = np.gradient(terrain_m, resolution_m_per_px, resolution_m_per_px)
    normal_x = -dz_dx
    normal_y = -dz_dy
    normal_z = np.ones_like(terrain_m)
    normal_norm = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
    normal_x /= normal_norm
    normal_y /= normal_norm
    normal_z /= normal_norm

    sun = _local_direction_vector(
        center_latitude_deg=center_latitude_deg,
        center_longitude_deg_east=center_longitude_deg_east,
        target_latitude_deg=sub_solar_latitude_deg,
        target_longitude_deg_east=sub_solar_longitude_deg_east,
    )
    incidence = np.maximum(normal_x * sun[0] + normal_y * sun[1] + normal_z * sun[2], 0.0)
    if model == "lambertian":
        return incidence.astype(np.float64, copy=False)

    if sub_observer_latitude_deg is None or sub_observer_longitude_deg_east is None:
        raise ValueError("lommel_seeliger model requires sub-observer coordinates")
    observer = _local_direction_vector(
        center_latitude_deg=center_latitude_deg,
        center_longitude_deg_east=center_longitude_deg_east,
        target_latitude_deg=sub_observer_latitude_deg,
        target_longitude_deg_east=sub_observer_longitude_deg_east,
    )
    emission = np.maximum(
        normal_x * observer[0] + normal_y * observer[1] + normal_z * observer[2],
        0.0,
    )
    denominator = incidence + emission
    shading = np.divide(
        2.0 * incidence,
        denominator,
        out=np.zeros_like(incidence),
        where=denominator > 0.0,
    )
    return cast(FloatArray, shading.astype(np.float64, copy=False))


def _local_direction_vector(
    *,
    center_latitude_deg: float,
    center_longitude_deg_east: float,
    target_latitude_deg: float,
    target_longitude_deg_east: float,
) -> tuple[float, float, float]:
    center_lat = math.radians(center_latitude_deg)
    center_lon = math.radians(center_longitude_deg_east)
    target_lat = math.radians(target_latitude_deg)
    target_lon = math.radians(target_longitude_deg_east)
    delta_lon = target_lon - center_lon

    east = math.cos(target_lat) * math.sin(delta_lon)
    north = math.sin(target_lat) * math.cos(center_lat) - math.cos(target_lat) * math.sin(
        center_lat
    ) * math.cos(delta_lon)
    up = math.sin(center_lat) * math.sin(target_lat) + math.cos(center_lat) * math.cos(
        target_lat
    ) * math.cos(delta_lon)
    norm = math.sqrt(east * east + north * north + up * up)
    if norm <= 0.0:
        raise ValueError("computed zero-length local direction vector")
    return east / norm, north / norm, up / norm
