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
from seeingbench.visualization.diagnostics import write_diagnostics


def evaluate_reference_reconstruction(
    reference_path: Path,
    reconstruction_path: Path,
    algorithm: str,
    frequency_bins: int = 24,
    register_translation: bool = False,
    registration_rotation_degrees: Sequence[float] | None = None,
    registration_scales: Sequence[float] | None = None,
    registration_shear_x: Sequence[float] | None = None,
    registration_shear_y: Sequence[float] | None = None,
    reference_metadata_path: Path | None = None,
    reconstruction_metadata_path: Path | None = None,
    photometric_normalization: str = "none",
    diagnostics_output_dir: Path | None = None,
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
        registration_rotation_degrees is not None
        or registration_scales is not None
        or registration_shear_x is not None
        or registration_shear_y is not None
    )
    registration: dict[str, Any] = {"method": "none"}
    if similarity_registration_requested:
        registered = register_global_similarity(
            reference,
            reconstruction,
            rotation_degrees=registration_rotation_degrees or (0.0,),
            scales=registration_scales or (1.0,),
            register_translation=register_translation,
            shear_x=registration_shear_x or (0.0,),
            shear_y=registration_shear_y or (0.0,),
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

    reconstruction, photometry = _apply_photometric_normalization(
        reference,
        reconstruction,
        photometric_normalization,
    )
    frequency_curve = radial_frequency_correlation(reference, reconstruction, bins=frequency_bins)
    recovery_limit = frequency_recovery_limit(frequency_curve, threshold=0.5)
    diagnostics = (
        None
        if diagnostics_output_dir is None
        else write_diagnostics(
            diagnostics_output_dir,
            reference,
            reconstruction,
            frequency_curve,
            scale_primary_images=True,
        )
    )
    reference_metadata = _load_optional_json_metadata(reference_metadata_path, "reference metadata")
    reconstruction_metadata = _load_optional_json_metadata(
        reconstruction_metadata_path,
        "reconstruction metadata",
    )
    reference_limitations = _metadata_list(reference_metadata, "limitations")
    reference_provenance = _reference_provenance(reference_metadata, reference_path)
    reference_generation = _reference_generation(reference_metadata, reference_path)
    reference_uncertainty = _reference_uncertainty(
        reference_metadata=reference_metadata,
        reference_limitations=reference_limitations,
        reference_provenance=reference_provenance,
        reference_generation=reference_generation,
        registration=registration,
        photometry=photometry,
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
            "reference_limitations": reference_limitations,
            "reference_provenance": reference_provenance,
            "reference_generation": reference_generation,
            "reference_uncertainty": reference_uncertainty,
            "reconstruction_path": str(reconstruction_path),
            "benchmark_mode": "standalone_reference",
            "registration": registration,
            "photometric_normalization": photometry,
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
        diagnostics=diagnostics,
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


def _apply_photometric_normalization(
    reference: np.ndarray,
    reconstruction: np.ndarray,
    mode: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    if mode == "none":
        return reconstruction, {"method": "none", "applied": False}
    if mode != "linear":
        raise ValueError("photometric_normalization must be 'none' or 'linear'")

    reference_flat = reference.ravel()
    reconstruction_flat = reconstruction.ravel()
    mse_before = _mean_squared_error(reference_flat, reconstruction_flat)
    reference_mean = float(np.mean(reference_flat))
    reconstruction_mean = float(np.mean(reconstruction_flat))
    reconstruction_centered = reconstruction_flat - reconstruction_mean
    reference_centered = reference_flat - reference_mean
    denominator = float(np.dot(reconstruction_centered, reconstruction_centered))
    if denominator <= np.finfo(np.float64).eps * reconstruction_flat.size:
        return reconstruction, {
            "method": "linear_least_squares",
            "applied": False,
            "reason": "degenerate_reconstruction_contrast",
            "mse_before": mse_before,
            "mse_after": mse_before,
            "validation_boundary": (
                "requested photometric normalization was skipped because the "
                "reconstruction has effectively constant intensity"
            ),
        }

    scale = float(np.dot(reconstruction_centered, reference_centered) / denominator)
    offset = float(reference_mean - scale * reconstruction_mean)
    normalised = scale * reconstruction + offset
    return normalised, {
        "method": "linear_least_squares",
        "applied": True,
        "scale": scale,
        "offset": offset,
        "reference_mean": reference_mean,
        "reconstruction_mean": reconstruction_mean,
        "mse_before": mse_before,
        "mse_after": _mean_squared_error(reference_flat, normalised.ravel()),
        "validation_boundary": (
            "global linear brightness/contrast fit is applied after geometric "
            "registration and before metrics; values are not clipped"
        ),
    }


def _mean_squared_error(reference: np.ndarray, reconstruction: np.ndarray) -> float:
    difference = reference - reconstruction
    return float(np.mean(difference * difference))


def _reference_uncertainty(
    reference_metadata: dict[str, Any],
    reference_limitations: list[Any],
    reference_provenance: dict[str, Any],
    reference_generation: dict[str, Any],
    registration: dict[str, Any],
    photometry: dict[str, Any],
) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []
    if not reference_metadata:
        factors.append(
            _uncertainty_factor(
                "reference_metadata_missing",
                "high",
                "no reference-generation metadata was supplied to the evaluator",
            )
        )
    if not reference_provenance:
        factors.append(
            _uncertainty_factor(
                "reference_provenance_missing",
                "medium",
                "reference source provenance is not present in the metrics metadata",
            )
        )
    if not reference_generation:
        factors.append(
            _uncertainty_factor(
                "reference_generation_missing",
                "medium",
                "reference-generation method metadata is not present",
            )
        )

    for limitation in reference_limitations:
        factors.append(_limitation_uncertainty(str(limitation)))
    if reference_metadata and not reference_limitations:
        factors.append(
            _uncertainty_factor(
                "no_reference_limitations_reported",
                "low",
                "reference metadata did not report known limitations",
            )
        )

    factors.append(_registration_uncertainty(registration))
    factors.append(_photometry_uncertainty(photometry))
    level = _max_uncertainty_level(factors)
    return {
        "assessment": "categorical_reference_uncertainty",
        "risk_level": level,
        "factor_count": len(factors),
        "factors": factors,
        "validation_boundary": (
            "categorical quality flags are derived only from reference metadata, "
            "registration settings, and photometric normalization metadata; they are not "
            "a calibrated statistical confidence interval"
        ),
    }


def _limitation_uncertainty(limitation: str) -> dict[str, Any]:
    high = {
        "not_spice_backed": (
            "reference uses fallback geometry instead of SPICE-backed observation geometry"
        ),
        "no_libration_or_orientation_solution": "lunar orientation and libration are not solved",
        "not_earth_view_projected": "reference pixels remain in the local map projection",
    }
    medium = {
        "spice_libration_and_illumination_metadata_not_yet_applied_to_pixels": (
            "SPICE metadata exists, but the renderer still uses an approximate pixel model"
        ),
        "local_linear_orthographic_projection": (
            "Earth-view geometry is represented by a local linear projection"
        ),
        "no_illumination_model": "illumination differences are not modelled",
        "simple_lambertian_illumination_model": (
            "illumination uses a simple Lambertian terrain model"
        ),
        "simple_lommel_seeliger_illumination_model": (
            "illumination uses a simple Lommel-Seeliger terrain model"
        ),
        "default_earth_moon_distance": "diffraction matching used a default Earth-Moon distance",
    }
    if limitation in high:
        return _uncertainty_factor(limitation, "high", high[limitation])
    if limitation in medium:
        return _uncertainty_factor(limitation, "medium", medium[limitation])
    return _uncertainty_factor(limitation, "medium", "reference report declares this limitation")


def _registration_uncertainty(registration: dict[str, Any]) -> dict[str, Any]:
    method = str(registration.get("method", "unknown"))
    if method == "none":
        return _uncertainty_factor(
            "geometric_registration_not_applied",
            "medium",
            "reference and reconstruction were scored without geometric registration",
        )
    if method == "global_similarity_grid_search":
        return _uncertainty_factor(
            "global_similarity_registration",
            "low",
            "registration was constrained to the declared global similarity candidate grid",
            candidate_count=registration.get("candidate_count"),
        )
    if method == "global_affine_grid_search":
        return _uncertainty_factor(
            "global_affine_registration",
            "low",
            "registration was constrained to the declared global affine candidate grid",
            candidate_count=registration.get("candidate_count"),
        )
    if method == "integer_phase_correlation_translation":
        return _uncertainty_factor(
            "global_translation_registration",
            "low",
            "registration was constrained to a single global integer translation",
        )
    return _uncertainty_factor(
        f"registration_{method}",
        "medium",
        "registration method is not recognised by the uncertainty classifier",
    )


def _photometry_uncertainty(photometry: dict[str, Any]) -> dict[str, Any]:
    method = str(photometry.get("method", "unknown"))
    if method == "none":
        return _uncertainty_factor(
            "photometric_normalization_not_applied",
            "low",
            "metrics use raw reconstruction/reference intensity scaling",
        )
    if photometry.get("applied", False):
        return _uncertainty_factor(
            "global_linear_photometric_normalization",
            "low",
            "one global linear brightness/contrast fit was applied before scoring",
        )
    return _uncertainty_factor(
        "photometric_normalization_skipped",
        "medium",
        str(photometry.get("reason", "requested normalization was not applied")),
    )


def _uncertainty_factor(
    source: str,
    level: str,
    description: str,
    **extra: Any,
) -> dict[str, Any]:
    factor = {"source": source, "level": level, "description": description}
    factor.update({key: value for key, value in extra.items() if value is not None})
    return factor


def _max_uncertainty_level(factors: list[dict[str, Any]]) -> str:
    levels = {"low": 1, "medium": 2, "high": 3}
    inverse = {value: key for key, value in levels.items()}
    return inverse[max(levels.get(str(factor.get("level")), 2) for factor in factors)]


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
            "psf_model",
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
