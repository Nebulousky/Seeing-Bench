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
from seeingbench.simulation.psf import gaussian_blur
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
    sigma_px = telescope_diffraction_sigma_in_reference_px(
        telescope,
        reference_resolution_m_per_px,
        distance_m,
    )
    matched = gaussian_blur(source, sigma_px)
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
                "method": "gaussian diffraction matching on local ROI map grid",
                "reference_resolution_m_per_px": reference_resolution_m_per_px,
                "earth_moon_distance_m": distance_m,
                "diffraction_sigma_reference_px": sigma_px,
                "telescope": asdict(telescope),
                "spice_geometry": None
                if spice_geometry_report is None
                else spice_geometry_report.get("geometry"),
            }
        ],
        "spice_geometry_report": spice_geometry_report,
        "limitations": _limitations(distance_limitations, spice_geometry_report),
    }
    _write_report(output_root, report)
    return report


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
        "limitations": _limitations(distance_limitations, spice_geometry_report),
    }


def _limitations(
    distance_limitations: list[str],
    spice_geometry_report: dict[str, Any] | None,
) -> list[str]:
    if spice_geometry_report is not None and spice_geometry_report["ready"]:
        return [
            "not_earth_view_projected",
            "spice_libration_and_illumination_metadata_not_yet_applied_to_pixels",
            "no_illumination_model",
            *distance_limitations,
        ]
    return [
        "not_spice_backed",
        "not_earth_view_projected",
        "no_libration_or_orientation_solution",
        "no_illumination_model",
        *distance_limitations,
    ]


def _write_report(output_root: Path, report: dict[str, Any]) -> None:
    (output_root / "telescope-reference-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")
