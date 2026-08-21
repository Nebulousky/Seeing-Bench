"""Telescope-matched references derived from local ROI reference grids."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from seeingbench.geometry.observation import build_spice_observation_geometry_report
from seeingbench.observations import (
    earth_moon_distance_m,
    load_observation_metadata,
    telescope_config_from_observation,
)
from seeingbench.rendering.illumination import lunar_shading_from_dem
from seeingbench.rendering.projection import (
    apply_local_orthographic_projection,
    local_orthographic_projection_matrix,
)
from seeingbench.simulation.psf import airy_blur, gaussian_blur
from seeingbench.simulation.telescope import (
    diffraction_gaussian_sigma_px,
    lunar_resolution_m_per_px,
)


def render_telescope_matched_reference(
    surface_reference_report_path: Path,
    observation_path: Path,
    output_root: Path,
    role: str | None = None,
    spice_cache_root: Path | None = None,
    apply_illumination: bool = False,
    apply_earth_view_projection: bool = False,
    terrain_role: str = "terrain",
    psf_model: str = "gaussian",
    illumination_model: str = "lambertian",
) -> dict[str, Any]:
    """Blur a local surface reference to the observation telescope's diffraction limit."""

    surface_report = json.loads(surface_reference_report_path.read_text(encoding="utf-8"))
    observation = load_observation_metadata(observation_path)
    telescope, blocking_reasons = telescope_config_from_observation(observation)
    distance_m, distance_limitations = earth_moon_distance_m(observation)
    spice_geometry_report = None
    if spice_cache_root is not None:
        spice_geometry_report = build_spice_observation_geometry_report(
            observation_path,
            spice_cache_root,
        )
        geometry = spice_geometry_report.get("geometry")
        if spice_geometry_report["ready"] and isinstance(geometry, dict):
            distance_m = float(geometry["earth_moon_distance_m"])
            distance_limitations = []
        else:
            distance_limitations.extend(
                f"spice_geometry_{reason}" for reason in spice_geometry_report["blocking_reasons"]
            )
    source_reference = _select_reference(surface_report, role)
    terrain_reference = _select_reference(surface_report, terrain_role)
    output_root.mkdir(parents=True, exist_ok=True)

    if source_reference is None:
        blocking_reasons.append("missing_surface_reference")
    if telescope is None or source_reference is None:
        report = _blocked_report(
            surface_reference_report_path,
            observation_path,
            output_root,
            role,
            blocking_reasons,
            distance_limitations,
            spice_geometry_report,
        )
        _write_report(output_root, report)
        return report

    source = np.load(Path(str(source_reference["output"]))).astype(np.float64)
    reference_resolution_m_per_px = float(surface_report["target_resolution_m_per_px"])
    illumination = _illumination_report(
        source,
        source_reference,
        terrain_reference,
        surface_report,
        spice_geometry_report,
        reference_resolution_m_per_px,
        apply_illumination,
        illumination_model,
    )
    source_for_matching = source
    if illumination["applied"]:
        source_for_matching = source * illumination.pop("_shading")
    projection = _projection_report(
        source_for_matching,
        surface_report,
        spice_geometry_report,
        apply_earth_view_projection,
    )
    if projection["applied"]:
        source_for_matching = projection.pop("_projected")
    sigma_px = telescope_diffraction_sigma_in_reference_px(
        telescope,
        reference_resolution_m_per_px,
        distance_m,
    )
    matched = _apply_reference_psf(source_for_matching, telescope, sigma_px, psf_model)
    destination = output_root / f"telescope-matched-{_safe_name(str(source_reference['role']))}.npy"
    np.save(destination, matched)

    report = {
        "surface_reference_report": str(surface_reference_report_path),
        "observation_metadata": str(observation_path),
        "output_root": str(output_root),
        "reference_count": 1,
        "blocking_reasons": [],
        "references": [
            {
                "role": source_reference["role"],
                "source": source_reference["output"],
                "output": str(destination),
                "shape": list(matched.shape),
                "dtype": str(matched.dtype),
                "method": f"{psf_model} diffraction matching on local ROI map grid",
                "psf_model": psf_model,
                "label_provenance": source_reference.get("label_provenance", {}),
                "label_summary": source_reference.get("label_summary", {}),
                "reference_resolution_m_per_px": reference_resolution_m_per_px,
                "earth_moon_distance_m": distance_m,
                "diffraction_sigma_reference_px": sigma_px,
                "telescope": asdict(telescope),
                "spice_geometry": None
                if spice_geometry_report is None
                else spice_geometry_report.get("geometry"),
                "illumination": illumination,
                "earth_view_projection": projection,
            }
        ],
        "spice_geometry_report": spice_geometry_report,
        "limitations": _limitations(
            distance_limitations,
            spice_geometry_report,
            illumination,
            projection,
        ),
    }
    _write_report(output_root, report)
    return report


def _apply_reference_psf(
    source: np.ndarray,
    telescope: Any,
    sigma_px: float,
    psf_model: str,
) -> np.ndarray:
    if psf_model == "gaussian":
        return gaussian_blur(source, sigma_px)
    if psf_model == "airy":
        return airy_blur(source, telescope)
    raise ValueError("psf_model must be 'gaussian' or 'airy'")


def telescope_diffraction_sigma_in_reference_px(
    telescope: Any,
    reference_resolution_m_per_px: float,
    earth_moon_distance_m_value: float,
) -> float:
    """Return telescope diffraction blur sigma in local reference-grid pixels."""

    if reference_resolution_m_per_px <= 0.0:
        raise ValueError("reference_resolution_m_per_px must be positive")
    sensor_m_per_px = lunar_resolution_m_per_px(telescope, earth_moon_distance_m_value)
    return (
        sensor_m_per_px * diffraction_gaussian_sigma_px(telescope) / reference_resolution_m_per_px
    )


def _select_reference(surface_report: dict[str, Any], role: str | None) -> dict[str, Any] | None:
    references = surface_report.get("references", [])
    if not isinstance(references, list):
        raise ValueError("surface reference report references must be a list")
    if role is None:
        return references[0] if references else None
    for reference in references:
        if isinstance(reference, dict) and reference.get("role") == role:
            return reference
    return None


def _blocked_report(
    surface_reference_report_path: Path,
    observation_path: Path,
    output_root: Path,
    role: str | None,
    blocking_reasons: list[str],
    distance_limitations: list[str],
    spice_geometry_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "surface_reference_report": str(surface_reference_report_path),
        "observation_metadata": str(observation_path),
        "output_root": str(output_root),
        "requested_role": role,
        "reference_count": 0,
        "blocking_reasons": blocking_reasons,
        "references": [],
        "spice_geometry_report": spice_geometry_report,
        "limitations": _limitations(distance_limitations, spice_geometry_report, None, None),
    }


def _illumination_report(
    source: np.ndarray,
    source_reference: dict[str, Any],
    terrain_reference: dict[str, Any] | None,
    surface_report: dict[str, Any],
    spice_geometry_report: dict[str, Any] | None,
    reference_resolution_m_per_px: float,
    apply_illumination: bool,
    illumination_model: str,
) -> dict[str, Any]:
    if not apply_illumination:
        return {"applied": False, "reason": "not_requested"}
    if illumination_model not in {"lambertian", "lommel_seeliger"}:
        raise ValueError("illumination_model must be 'lambertian' or 'lommel_seeliger'")
    geometry = None if spice_geometry_report is None else spice_geometry_report.get("geometry")
    if not isinstance(geometry, dict):
        return {"applied": False, "reason": "missing_spice_geometry"}
    if terrain_reference is None:
        return {"applied": False, "reason": "missing_terrain_reference"}

    terrain = np.load(Path(str(terrain_reference["output"]))).astype(np.float64)
    if terrain.shape != source.shape:
        return {
            "applied": False,
            "reason": "terrain_shape_mismatch",
            "terrain_shape": list(terrain.shape),
            "source_shape": list(source.shape),
        }
    roi = surface_report.get("roi", {})
    center_latitude_deg = float(roi.get("center_lat_deg", 0.0))
    center_longitude_deg = float(roi.get("center_lon_deg", 0.0))
    shading = lunar_shading_from_dem(
        terrain,
        reference_resolution_m_per_px,
        center_latitude_deg=center_latitude_deg,
        center_longitude_deg_east=center_longitude_deg,
        sub_solar_latitude_deg=float(geometry["sub_solar_latitude_deg"]),
        sub_solar_longitude_deg_east=float(geometry["sub_solar_longitude_deg_east"]),
        sub_observer_latitude_deg=float(geometry["sub_observer_latitude_deg"]),
        sub_observer_longitude_deg_east=float(geometry["sub_observer_longitude_deg_east"]),
        model=illumination_model,
    )
    return {
        "applied": True,
        "method": f"local DEM {illumination_model} shading",
        "model": illumination_model,
        "reflectance_role": source_reference["role"],
        "terrain_role": terrain_reference["role"],
        "terrain_source": terrain_reference["output"],
        "center_latitude_deg": center_latitude_deg,
        "center_longitude_deg_east": center_longitude_deg,
        "sub_solar_latitude_deg": geometry["sub_solar_latitude_deg"],
        "sub_solar_longitude_deg_east": geometry["sub_solar_longitude_deg_east"],
        "shading_min": float(np.min(shading)),
        "shading_mean": float(np.mean(shading)),
        "shading_max": float(np.max(shading)),
        "_shading": shading,
    }


def _projection_report(
    source: np.ndarray,
    surface_report: dict[str, Any],
    spice_geometry_report: dict[str, Any] | None,
    apply_earth_view_projection: bool,
) -> dict[str, Any]:
    if not apply_earth_view_projection:
        return {"applied": False, "reason": "not_requested"}
    geometry = None if spice_geometry_report is None else spice_geometry_report.get("geometry")
    if not isinstance(geometry, dict):
        return {"applied": False, "reason": "missing_spice_geometry"}
    roi = surface_report.get("roi", {})
    center_latitude_deg = float(roi.get("center_lat_deg", 0.0))
    center_longitude_deg = float(roi.get("center_lon_deg", 0.0))
    try:
        matrix, incidence_cosine = local_orthographic_projection_matrix(
            center_latitude_deg=center_latitude_deg,
            center_longitude_deg_east=center_longitude_deg,
            sub_observer_latitude_deg=float(geometry["sub_observer_latitude_deg"]),
            sub_observer_longitude_deg_east=float(geometry["sub_observer_longitude_deg_east"]),
        )
        projected = apply_local_orthographic_projection(source, matrix)
    except ValueError as exc:
        return {"applied": False, "reason": f"projection_unavailable: {exc}"}
    return {
        "applied": True,
        "method": "local linear orthographic projection",
        "center_latitude_deg": center_latitude_deg,
        "center_longitude_deg_east": center_longitude_deg,
        "sub_observer_latitude_deg": geometry["sub_observer_latitude_deg"],
        "sub_observer_longitude_deg_east": geometry["sub_observer_longitude_deg_east"],
        "incidence_cosine": incidence_cosine,
        "matrix": matrix.tolist(),
        "_projected": projected,
    }


def _limitations(
    distance_limitations: list[str],
    spice_geometry_report: dict[str, Any] | None,
    illumination: dict[str, Any] | None,
    projection: dict[str, Any] | None,
) -> list[str]:
    illumination_applied = illumination is not None and bool(illumination.get("applied"))
    illumination_limitations = _illumination_limitations(illumination, illumination_applied)
    projection_applied = projection is not None and bool(projection.get("applied"))
    projection_limitations = (
        ["local_linear_orthographic_projection"]
        if projection_applied
        else ["not_earth_view_projected"]
    )
    if spice_geometry_report is not None and spice_geometry_report["ready"]:
        return [
            "spice_libration_and_illumination_metadata_not_yet_applied_to_pixels",
            *projection_limitations,
            *illumination_limitations,
            *distance_limitations,
        ]
    return [
        "not_spice_backed",
        "no_libration_or_orientation_solution",
        *projection_limitations,
        *illumination_limitations,
        *distance_limitations,
    ]


def _illumination_limitations(
    illumination: dict[str, Any] | None,
    illumination_applied: bool,
) -> list[str]:
    if not illumination_applied or illumination is None:
        return ["no_illumination_model"]
    if illumination.get("model") == "lommel_seeliger":
        return ["simple_lommel_seeliger_illumination_model"]
    return ["simple_lambertian_illumination_model"]


def _write_report(output_root: Path, report: dict[str, Any]) -> None:
    (output_root / "telescope-reference-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")
