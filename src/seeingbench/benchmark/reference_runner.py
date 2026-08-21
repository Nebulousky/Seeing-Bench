"""Evaluate reconstructions against a standalone reference image."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any, cast

import numpy as np

import seeingbench
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

    registration: dict[str, Any] = {"method": "none"}
    if register_translation:
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
    reconstruction_metadata = _load_reconstruction_metadata(reconstruction_metadata_path)
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
            "reconstruction_path": str(reconstruction_path),
            "benchmark_mode": "standalone_reference",
            "registration": registration,
            "reconstruction_metadata": reconstruction_metadata,
            "reconstruction_runtime_s": _optional_float(reconstruction_metadata.get("runtime_s")),
            "evaluation_runtime_s": elapsed_s,
            "seeingbench_version": seeingbench.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
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


def _load_reconstruction_metadata(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"reconstruction metadata must be a JSON object: {path}")
    return data


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
