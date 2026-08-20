"""Benchmark evaluation orchestration."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np

import seeingbench
from seeingbench.benchmark.case import load_benchmark_case
from seeingbench.benchmark.result import EvaluationReport
from seeingbench.evaluation.false_detail import false_detail_score
from seeingbench.evaluation.frequency import frequency_recovery_limit, radial_frequency_correlation
from seeingbench.evaluation.image_metrics import image_similarity_metrics
from seeingbench.evaluation.structure import gradient_correlation
from seeingbench.evaluation.warp_metrics import warp_error_metrics
from seeingbench.io.images import load_grayscale_image


def evaluate_reconstruction(
    case_dir: Path,
    result_dir: Path,
    algorithm: str = "manual",
    frequency_bins: int = 24,
) -> EvaluationReport:
    """Evaluate ``result/reconstruction.tif`` against the saved synthetic truth."""

    started = time.perf_counter()
    case = load_benchmark_case(case_dir)
    reconstruction = load_grayscale_image(result_dir / "reconstruction.tif")
    frequency_curve = radial_frequency_correlation(
        case.latent_truth,
        reconstruction,
        bins=frequency_bins,
    )
    recovery_limit = frequency_recovery_limit(frequency_curve, threshold=0.5)
    diffraction_fraction = _diffraction_frequency_fraction(case.metadata)
    warp_report = _load_warp_report(case.warp_fields, result_dir)
    elapsed_s = time.perf_counter() - started

    return EvaluationReport(
        algorithm=algorithm,
        image_similarity=image_similarity_metrics(case.latent_truth, reconstruction),
        structural_accuracy={
            "gradient_correlation": gradient_correlation(case.latent_truth, reconstruction)
        },
        frequency_recovery={
            "bins": frequency_curve,
            "correlation_0_5_limit_fraction": recovery_limit,
            "diffraction_frequency_fraction_of_nyquist": diffraction_fraction,
            "correlation_0_5_limit_relative_to_diffraction": (
                recovery_limit / diffraction_fraction if diffraction_fraction else None
            ),
            "mean_correlation_beyond_diffraction": _mean_correlation_above(
                frequency_curve,
                diffraction_fraction,
            ),
        },
        false_detail=false_detail_score(case.latent_truth, reconstruction),
        warp_recovery=warp_report,
        metadata={
            "case_dir": str(case_dir),
            "result_dir": str(result_dir),
            "case_metadata": case.metadata,
            "seeingbench_version": seeingbench.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "runtime_s": elapsed_s,
        },
    )


def save_evaluation_report(report: EvaluationReport, path: Path) -> None:
    """Save a report as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(report.to_dict()), indent=2), encoding="utf-8")


def _load_warp_report(truth: np.ndarray, result_dir: Path) -> dict[str, float] | None:
    warp_dir = result_dir / "warp_fields"
    if not warp_dir.exists():
        return None
    paths = sorted(warp_dir.glob("warp_*.npy"))
    if not paths:
        return None
    estimate = np.stack([np.load(path).astype(np.float64, copy=False) for path in paths])
    return warp_error_metrics(truth, estimate)


def _diffraction_frequency_fraction(metadata: dict[str, Any]) -> float | None:
    try:
        value = metadata["psf_information"]["telescope"][
            "diffraction_frequency_fraction_of_nyquist"
        ]
    except KeyError:
        return None
    return float(value)


def _mean_correlation_above(
    curve: list[dict[str, float | int]],
    threshold_frequency: float | None,
) -> float | None:
    if threshold_frequency is None:
        return None
    values = [
        float(row["correlation"])
        for row in curve
        if float(row["frequency_mid_fraction"]) > threshold_frequency
        and np.isfinite(float(row["correlation"]))
    ]
    return float(np.mean(values)) if values else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
