"""Evaluate reconstructions against a standalone reference image."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

import seeingbench
from seeingbench.benchmark.provenance import runtime_provenance
from seeingbench.benchmark.registration import register_global_similarity
from seeingbench.benchmark.result import EvaluationReport
from seeingbench.evaluation.false_detail import false_detail_score
from seeingbench.evaluation.frequency import frequency_recovery_limit, radial_frequency_correlation
from seeingbench.evaluation.image_metrics import image_similarity_metrics
from seeingbench.evaluation.structure import gradient_correlation
from seeingbench.io.images import load_grayscale_image
from seeingbench.reconstruction.alignment import (
    constant_displacement,
    estimate_integer_translation,
)
from seeingbench.simulation.warp import apply_warp, validate_grayscale_image


def evaluate_reference_reconstruction(
    reference_path: Path,
    reconstruction_path: Path,
    algorithm: str,
    frequency_bins: int = 24,
    register_translation: bool = False,
    registration_rotation_degrees: Sequence[float] | None = None,
    registration_scales: Sequence[float] | None = None,
    reference_metadata_path: Path | None = None,
    reconstruction_metadata_path: Path | None = None,
) -> EvaluationReport:
    """Evaluate a reconstruction directly against a standalone reference image."""

    if frequency_bins <= 0:
        raise ValueError("frequency_bins must be positive")
    started = time.perf_counter()
    reference = _load_reference_array(reference_path)
    reconstruction = _load_reference_array(reconstruction_path)
    if reference.shape != reconstruction.shape:
        raise ValueError(f"shape mismatch: {reference.shape} != {reconstruction.shape}")

    similarity_registration_requested = (
        registration_rotation_degrees is not None or registration_scales is not None
    )
    registration: dict[str, Any] = {"method": "none"}
    if similarity_registration_requested:
        registered = register_global_similarity(
            reference,
            reconstruction,
            rotation_degrees=registration_rotation_degrees or (0.0,),
            scales=registration_scales or (1.0,),
            register_translation=register_translation,
        )
        reconstruction = registered.image
        registration = registered.metadata
    elif register_translation:
        shift_x, shift_y = estimate_integer_translation(reference, reconstruction)
        reconstruction = apply_warp(
            reconstruction,
            -constant_displacement(reference.shape, shift_x, shift_y),
        )
        registration = {
            "method": "integer_phase_correlation_translation",
            "shift_x_px": shift_x,
            "shift_y_px": shift_y,
            "constraint": "global translation only",
        }

    frequency_curve = radial_frequency_correlation(reference, reconstruction, bins=frequency_bins)
    recovery_limit = frequency_recovery_limit(frequency_curve, threshold=0.5)
    reference_metadata = _load_optional_json_metadata(reference_metadata_path, "reference metadata")
    reconstruction_metadata = _load_optional_json_metadata(
        reconstruction_metadata_path,
        "reconstruction metadata",
    )
    provenance = runtime_provenance()
    elapsed_s = time.perf_counter() - started
    return EvaluationReport(
        algorithm=algorithm,
        image_similarity=image_similarity_metrics(reference, reconstruction),
        structural_accuracy={
            "gradient_correlation": gradient_correlation(reference, reconstruction)
        },
        frequency_recovery={
            "bins": frequency_curve,
            "correlation_0_5_limit_fraction": recovery_limit,
            "diffraction_frequency_fraction_of_nyquist": None,
            "correlation_0_5_limit_relative_to_diffraction": None,
            "mean_correlation_beyond_diffraction": None,
        },
        false_detail=false_detail_score(reference, reconstruction),
        warp_recovery=None,
        metadata={
            "reference_path": str(reference_path),
            "reference_metadata_path": None
            if reference_metadata_path is None
            else str(reference_metadata_path),
            "reference_metadata": reference_metadata,
            "reference_limitations": _metadata_list(reference_metadata, "limitations"),
            "reference_provenance": _reference_provenance(reference_metadata, reference_path),
            "reference_generation": _reference_generation(reference_metadata, reference_path),
            "reconstruction_path": str(reconstruction_path),
            "benchmark_mode": "standalone_reference",
            "registration": registration,
            "reconstruction_metadata": reconstruction_metadata,
            "reconstruction_runtime_s": _optional_float(reconstruction_metadata.get("runtime_s")),
            "evaluation_runtime_s": elapsed_s,
            "seeingbench_version": seeingbench.__version__,
            "python": provenance["python_version"],
            "numpy": np.__version__,
            "provenance": provenance,
            "runtime_s": elapsed_s,
            "validation_boundary": (
                "standalone reference is loaded only by the evaluator after reconstruction"
            ),
        },
    )


def save_reference_evaluation_report(report: EvaluationReport, path: Path) -> None:
    """Save a standalone-reference evaluation report as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(report.to_dict()), indent=2), encoding="utf-8")


def _load_reference_array(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        array = np.load(path).astype(np.float64, copy=False)
    else:
        array = load_grayscale_image(path)
    validate_grayscale_image(array)
    return cast(np.ndarray, array)


def _load_optional_json_metadata(path: Path | None, label: str) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def _metadata_list(metadata: dict[str, Any], key: str) -> list[Any]:
    value = metadata.get(key, [])
    return value if isinstance(value, list) else []


def _reference_provenance(metadata: dict[str, Any], reference_path: Path) -> dict[str, Any]:
    reference = _reference_metadata_row(metadata, reference_path)
    if reference is None:
        return {}
    provenance = reference.get("label_provenance", {})
    return provenance if isinstance(provenance, dict) else {}


def _reference_generation(metadata: dict[str, Any], reference_path: Path) -> dict[str, Any]:
    reference = _reference_metadata_row(metadata, reference_path)
    if reference is None:
        return {}
    return {
        key: reference[key]
        for key in (
            "role",
            "source",
            "output",
            "method",
            "reference_resolution_m_per_px",
            "earth_moon_distance_m",
            "diffraction_sigma_reference_px",
        )
        if key in reference
    }


def _reference_metadata_row(
    metadata: dict[str, Any],
    reference_path: Path,
) -> dict[str, Any] | None:
    references = metadata.get("references", [])
    if not isinstance(references, list):
        return None
    candidates = [reference for reference in references if isinstance(reference, dict)]
    reference_path_text = str(reference_path)
    for reference in candidates:
        if str(reference.get("output")) == reference_path_text:
            return reference
    return candidates[0] if len(candidates) == 1 else None


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
