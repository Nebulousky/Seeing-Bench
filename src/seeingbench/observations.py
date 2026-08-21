"""Real lunar observation metadata parsing for reference generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seeingbench.simulation.config import TelescopeConfig
from seeingbench.simulation.telescope import MOON_MEAN_DISTANCE_M


def load_observation_metadata(path: Path) -> dict[str, Any]:
    """Load a real-observation metadata JSON object."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("observation metadata must be a JSON object")
    if data.get("target", "Moon") != "Moon":
        raise ValueError("only Moon observation metadata is currently supported")
    return data


def telescope_config_from_observation(
    metadata: dict[str, Any],
) -> tuple[TelescopeConfig | None, list[str]]:
    """Build a telescope config from partial real-observation metadata."""

    telescope = _section(metadata, "telescope")
    camera = _section(metadata, "camera")
    filter_data = _section(metadata, "filter")
    missing = _missing_required_fields(telescope, camera, filter_data)
    if missing:
        return None, [f"missing_{field}" for field in missing]

    try:
        config = TelescopeConfig(
            aperture_mm=float(telescope["aperture_mm"]),
            focal_length_mm=float(telescope["focal_length_mm"]),
            central_obstruction_ratio=float(telescope.get("central_obstruction", 0.0)),
            wavelength_nm=float(filter_data["effective_wavelength_nm"]),
            pixel_size_um=float(camera["pixel_size_um"]),
            sensor_width_px=_optional_int(camera.get("width")),
            sensor_height_px=_optional_int(camera.get("height")),
        )
        config.validate()
    except (TypeError, ValueError) as exc:
        return None, [f"invalid_telescope_metadata: {exc}"]
    return config, []


def earth_moon_distance_m(metadata: dict[str, Any]) -> tuple[float, list[str]]:
    """Return Earth-Moon distance from metadata, or the documented mean-distance fallback."""

    value = metadata.get("earth_moon_distance_m")
    if value is None:
        return MOON_MEAN_DISTANCE_M, ["using_mean_earth_moon_distance"]
    distance = float(value)
    if distance <= 0.0:
        raise ValueError("earth_moon_distance_m must be positive when provided")
    return distance, []


def _section(metadata: dict[str, Any], name: str) -> dict[str, Any]:
    section = metadata.get(name, {})
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ValueError(f"{name} metadata must be an object")
    return section


def _missing_required_fields(
    telescope: dict[str, Any],
    camera: dict[str, Any],
    filter_data: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    if telescope.get("aperture_mm") is None:
        missing.append("telescope.aperture_mm")
    if telescope.get("focal_length_mm") is None:
        missing.append("telescope.focal_length_mm")
    if camera.get("pixel_size_um") is None:
        missing.append("camera.pixel_size_um")
    if filter_data.get("effective_wavelength_nm") is None:
        missing.append("filter.effective_wavelength_nm")
    return missing


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
