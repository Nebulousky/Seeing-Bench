"""Small PDS/LROC label parsing helpers for metadata-only readiness checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

PDS_FIELD_NAMES = (
    "EASTERNMOST_LONGITUDE",
    "LINE_SAMPLES",
    "LINES",
    "MAP_PROJECTION_TYPE",
    "MAP_RESOLUTION",
    "MAP_SCALE",
    "MAXIMUM_LATITUDE",
    "MINIMUM_LATITUDE",
    "SAMPLE_BITS",
    "SAMPLE_TYPE",
    "WESTERNMOST_LONGITUDE",
)


def parse_pds_label_text(text: str) -> dict[str, Any]:
    """Parse a bounded subset of flat PDS label key/value metadata."""

    stripped = text.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<Product"):
        return _parse_pds4_xml_label(stripped)

    fields: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip().upper()
        if key not in PDS_FIELD_NAMES:
            continue
        fields[key.lower()] = _parse_value(raw_value.strip())
    return fields


def _parse_pds4_xml_label(text: str) -> dict[str, Any]:
    root = ElementTree.fromstring(text)
    fields: dict[str, Any] = {}
    axis_name: str | None = None
    for element in root.iter():
        name = _local_name(element.tag)
        value = (element.text or "").strip()
        if not value:
            continue
        if name == "map_projection_name":
            fields["map_projection_type"] = value
        elif name == "south_bounding_coordinate":
            fields["minimum_latitude"] = _parse_value(value)
        elif name == "north_bounding_coordinate":
            fields["maximum_latitude"] = _parse_value(value)
        elif name == "west_bounding_coordinate":
            fields["westernmost_longitude"] = _parse_value(value)
        elif name == "east_bounding_coordinate":
            fields["easternmost_longitude"] = _parse_value(value)
        elif name == "pixel_scale_x":
            fields["map_scale"] = _parse_value(value)
        elif name == "pixel_resolution_x":
            degrees_per_pixel = _numeric_value(_parse_value(value))
            if degrees_per_pixel is not None and degrees_per_pixel > 0:
                fields["map_resolution"] = 1.0 / degrees_per_pixel
        elif name == "data_type":
            fields["sample_type"] = value
        elif name == "sample_bit_mask":
            fields["sample_bits"] = value.count("1")
        elif name == "axis_name":
            axis_name = value.lower()
        elif name == "elements" and axis_name is not None:
            if axis_name == "line":
                fields["lines"] = _parse_value(value)
            elif axis_name == "sample":
                fields["line_samples"] = _parse_value(value)
            axis_name = None
    return fields


def parse_pds_label_file(path: Path, max_bytes: int = 1_000_000) -> dict[str, Any]:
    """Parse a small local PDS label file without reading arbitrary-size products."""

    payload = path.read_bytes()
    if len(payload) > max_bytes:
        raise ValueError(f"PDS label exceeds metadata size limit: {path}")
    return parse_pds_label_text(payload.decode("utf-8", errors="replace"))


def label_coverage_status(
    fields: dict[str, Any],
    center_lat_deg: float,
    center_lon_deg: float,
) -> str:
    """Return whether parsed label bounds contain the ROI center."""

    required = (
        "minimum_latitude",
        "maximum_latitude",
        "westernmost_longitude",
        "easternmost_longitude",
    )
    if any(name not in fields for name in required):
        return "unknown"
    lat = float(center_lat_deg)
    lon = _normalise_lon_360(center_lon_deg)
    min_lat = float(fields["minimum_latitude"])
    max_lat = float(fields["maximum_latitude"])
    west = _normalise_lon_360(float(fields["westernmost_longitude"]))
    east = _normalise_lon_360(float(fields["easternmost_longitude"]))
    lat_ok = min(min_lat, max_lat) <= lat <= max(min_lat, max_lat)
    lon_ok = _longitude_in_interval(lon, west, east)
    return "ok" if lat_ok and lon_ok else "outside"


def label_resolution_status(
    fields: dict[str, Any],
    target_resolution_m_per_px: float,
) -> str:
    """Return whether parsed map scale is compatible with target sampling."""

    map_scale = _numeric_value(fields.get("map_scale"))
    if map_scale is None:
        return "unknown"
    return "ok" if map_scale <= target_resolution_m_per_px else "coarser_than_target"


def label_summary(fields: dict[str, Any]) -> dict[str, Any]:
    """Return stable report fields extracted from a parsed label."""

    return {
        "projection": fields.get("map_projection_type"),
        "minimum_latitude": fields.get("minimum_latitude"),
        "maximum_latitude": fields.get("maximum_latitude"),
        "westernmost_longitude": fields.get("westernmost_longitude"),
        "easternmost_longitude": fields.get("easternmost_longitude"),
        "map_scale_m_per_px": _numeric_value(fields.get("map_scale")),
        "map_resolution_px_per_deg": _numeric_value(fields.get("map_resolution")),
        "lines": fields.get("lines"),
        "line_samples": fields.get("line_samples"),
        "sample_type": fields.get("sample_type"),
        "sample_bits": fields.get("sample_bits"),
    }


def _strip_comment(line: str) -> str:
    return re.sub(r"/\*.*?\*/", "", line)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_value(value: str) -> Any:
    value = value.rstrip(",").strip()
    if value.startswith('"') and '"' in value[1:]:
        return value.split('"', 2)[1]
    if "<" in value:
        value = value.split("<", 1)[0].strip()
    if value.startswith("(") and value.endswith(")"):
        return [_parse_value(item.strip()) for item in value[1:-1].split(",")]
    try:
        if any(marker in value.upper() for marker in (".", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _normalise_lon_360(lon: float) -> float:
    return lon % 360.0


def _longitude_in_interval(lon: float, west: float, east: float) -> bool:
    if west <= east:
        return west <= lon <= east
    return lon >= west or lon <= east
