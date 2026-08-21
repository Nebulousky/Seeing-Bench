"""SPICE-backed observation geometry for real lunar reference rendering."""

from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from seeingbench.observations import load_observation_metadata

MOON_MEAN_RADIUS_KM = 1737.4
EARTH_EQUATORIAL_RADIUS_KM = 6378.137
EARTH_POLAR_RADIUS_KM = 6356.752314245


def build_spice_observation_geometry_report(
    observation_path: Path,
    cache_root: Path,
) -> dict[str, Any]:
    """Compute topocentric lunar observation geometry from local SPICE kernels."""

    observation = load_observation_metadata(observation_path)
    missing_fields = _missing_geometry_fields(observation)
    kernel_paths = _local_kernel_paths(observation, cache_root)
    missing_kernels = [str(path) for path in kernel_paths if not path.is_file()]
    blocking_reasons = [f"missing_{field}" for field in missing_fields]
    if missing_kernels:
        blocking_reasons.append("kernel_file_missing")

    try:
        spice = importlib.import_module("spiceypy")
    except ImportError:
        spice = None
        blocking_reasons.append("spiceypy_not_installed")

    if blocking_reasons or spice is None:
        return _geometry_report(
            observation_path,
            cache_root,
            kernel_paths,
            ready=False,
            blocking_reasons=sorted(set(blocking_reasons)),
            geometry=None,
        )

    try:
        for path in kernel_paths:
            spice.furnsh(str(path))
        geometry = _compute_geometry(spice, observation)
    except Exception as exc:  # pragma: no cover - exercised with real kernels.
        return _geometry_report(
            observation_path,
            cache_root,
            kernel_paths,
            ready=False,
            blocking_reasons=[f"spice_geometry_error: {exc}"],
            geometry=None,
        )
    finally:
        if hasattr(spice, "kclear"):
            spice.kclear()

    return _geometry_report(
        observation_path,
        cache_root,
        kernel_paths,
        ready=True,
        blocking_reasons=[],
        geometry=geometry,
    )


def write_spice_observation_geometry_report(report: dict[str, Any], output: Path) -> None:
    """Persist a SPICE observation-geometry report as JSON."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _compute_geometry(spice: Any, observation: dict[str, Any]) -> dict[str, Any]:
    utc_start = str(observation["utc_start"])
    observer = observation["observer"]
    et = float(spice.utc2et(utc_start))

    observer_itrf_km = _observer_rectangular_km(spice, observer)
    itrf_to_j2000 = np.asarray(spice.pxform("ITRF93", "J2000", et), dtype=np.float64)
    observer_j2000_km = itrf_to_j2000 @ observer_itrf_km

    moon_from_earth_km, one_way_light_time_s = spice.spkpos(
        "MOON",
        et,
        "J2000",
        "LT+S",
        "EARTH",
    )
    observer_to_moon_km = np.asarray(moon_from_earth_km, dtype=np.float64) - observer_j2000_km
    moon_to_observer_km = -observer_to_moon_km
    distance_km = float(np.linalg.norm(observer_to_moon_km))
    if distance_km <= 0.0:
        raise ValueError("computed non-positive Earth-Moon distance")

    moon_fixed_from_j2000 = np.asarray(spice.pxform("J2000", "MOON_ME", et), dtype=np.float64)
    moon_to_observer_fixed_km = moon_fixed_from_j2000 @ moon_to_observer_km
    sub_observer = _lat_lon_degrees(spice, moon_to_observer_fixed_km)

    sun_from_moon_km, _ = spice.spkpos("SUN", et, "J2000", "LT+S", "MOON")
    sun_from_moon_j2000 = np.asarray(sun_from_moon_km, dtype=np.float64)
    sun_from_moon_fixed_km = moon_fixed_from_j2000 @ sun_from_moon_j2000
    sub_solar = _lat_lon_degrees(spice, sun_from_moon_fixed_km)
    phase_angle_deg = _angle_degrees(moon_to_observer_km, sun_from_moon_j2000)

    return {
        "utc_start": utc_start,
        "ephemeris_time_s": et,
        "reference_frame": "J2000",
        "moon_body_fixed_frame": "MOON_ME",
        "observer_body_fixed_frame": "ITRF93",
        "observer_to_moon_vector_km": observer_to_moon_km.tolist(),
        "earth_moon_distance_m": distance_km * 1000.0,
        "one_way_light_time_s": float(one_way_light_time_s),
        "moon_angular_radius_deg": math.degrees(math.asin(MOON_MEAN_RADIUS_KM / distance_km)),
        "sub_observer_latitude_deg": sub_observer["latitude_deg"],
        "sub_observer_longitude_deg_east": sub_observer["longitude_deg_east"],
        "sub_solar_latitude_deg": sub_solar["latitude_deg"],
        "sub_solar_longitude_deg_east": sub_solar["longitude_deg_east"],
        "phase_angle_deg": phase_angle_deg,
        "illuminated_fraction": (1.0 + math.cos(math.radians(phase_angle_deg))) / 2.0,
    }


def _observer_rectangular_km(spice: Any, observer: dict[str, Any]) -> np.ndarray:
    lat_rad = math.radians(float(observer["latitude"]))
    lon_rad = math.radians(float(observer["longitude"]))
    altitude_km = float(observer["altitude_m"]) / 1000.0
    earth_equatorial_km, earth_polar_km = _earth_radii_km(spice)
    flattening = (earth_equatorial_km - earth_polar_km) / earth_equatorial_km
    return np.asarray(
        spice.georec(lon_rad, lat_rad, altitude_km, earth_equatorial_km, flattening),
        dtype=np.float64,
    )


def _earth_radii_km(spice: Any) -> tuple[float, float]:
    try:
        result = spice.bodvrd("EARTH", "RADII", 3)
        radii = result[1] if isinstance(result, tuple) else result
        return float(radii[0]), float(radii[2])
    except Exception:
        return EARTH_EQUATORIAL_RADIUS_KM, EARTH_POLAR_RADIUS_KM


def _lat_lon_degrees(spice: Any, vector: np.ndarray) -> dict[str, float]:
    radius, lon_rad, lat_rad = spice.reclat(vector)
    if float(radius) <= 0.0:
        raise ValueError("cannot convert zero vector to latitude/longitude")
    lon_deg = math.degrees(float(lon_rad)) % 360.0
    if lon_deg > 180.0:
        lon_deg -= 360.0
    return {
        "latitude_deg": math.degrees(float(lat_rad)),
        "longitude_deg_east": lon_deg,
    }


def _angle_degrees(first: np.ndarray, second: np.ndarray) -> float:
    norm_product = float(np.linalg.norm(first) * np.linalg.norm(second))
    if norm_product <= 0.0:
        raise ValueError("cannot compute angle involving a zero vector")
    cosine = float(np.dot(first, second) / norm_product)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _geometry_report(
    observation_path: Path,
    cache_root: Path,
    kernel_paths: list[Path],
    *,
    ready: bool,
    blocking_reasons: list[str],
    geometry: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "observation": str(observation_path),
        "cache_root": str(cache_root),
        "ready": ready,
        "blocking_reasons": blocking_reasons,
        "kernels": [str(path) for path in kernel_paths],
        "geometry": geometry,
        "limitations": [
            "computes observation geometry only; pixel reprojection is handled separately",
            "uses the observation's listed local SPICE kernels and does not download kernels",
        ],
    }


def _missing_geometry_fields(observation: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if observation.get("utc_start") is None:
        missing.append("utc_start")
    observer = observation.get("observer", {})
    if observer is None:
        observer = {}
    if not isinstance(observer, dict):
        raise ValueError("observation observer metadata must be an object")
    for field in ("latitude", "longitude", "altitude_m"):
        if observer.get(field) is None:
            missing.append(f"observer.{field}")
    if not _observation_kernels(observation):
        missing.append("spice.kernels")
    return missing


def _local_kernel_paths(observation: dict[str, Any], cache_root: Path) -> list[Path]:
    paths: list[Path] = []
    for kernel in _observation_kernels(observation):
        path = Path(kernel)
        paths.append(path if path.is_absolute() else cache_root / path)
    return paths


def _observation_kernels(observation: dict[str, Any]) -> list[str]:
    spice = observation.get("spice", {})
    if spice is None:
        return []
    if not isinstance(spice, dict):
        raise ValueError("observation spice metadata must be an object")
    kernels = spice.get("kernels", [])
    if not isinstance(kernels, list):
        raise ValueError("observation spice.kernels must be a list")
    return [str(kernel) for kernel in kernels]
