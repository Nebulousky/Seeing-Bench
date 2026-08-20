from __future__ import annotations

import math

import numpy as np

from seeingbench.evaluation.false_detail import false_detail_score
from seeingbench.evaluation.frequency import frequency_recovery_limit, radial_frequency_correlation
from seeingbench.evaluation.image_metrics import image_similarity_metrics
from seeingbench.evaluation.structure import gradient_correlation
from seeingbench.evaluation.warp_metrics import warp_error_metrics


def test_identity_image_metrics_report_perfect_similarity() -> None:
    image = np.arange(64, dtype=np.float64).reshape((8, 8)) / 63.0

    metrics = image_similarity_metrics(image, image)

    assert metrics["mse"] == 0.0
    assert math.isinf(metrics["psnr_db"])
    assert metrics["ssim_global"] == 1.0
    assert gradient_correlation(image, image) == 1.0


def test_frequency_curve_reports_identity_recovery() -> None:
    image = np.arange(64, dtype=np.float64).reshape((8, 8)) / 63.0

    curve = radial_frequency_correlation(image, image, bins=4)

    assert frequency_recovery_limit(curve, threshold=0.5) > 0.0
    finite_correlations = [
        row["correlation"] for row in curve if not math.isnan(row["correlation"])
    ]
    assert all(correlation >= 0.99 for correlation in finite_correlations)


def test_warp_error_metrics_known_offset() -> None:
    truth = np.zeros((2, 4, 4, 2), dtype=np.float64)
    estimate = truth.copy()
    estimate[..., 0] = 3.0
    estimate[..., 1] = 4.0

    metrics = warp_error_metrics(truth, estimate)

    assert metrics["mean_px"] == 5.0
    assert metrics["median_px"] == 5.0
    assert metrics["p95_px"] == 5.0
    assert metrics["max_px"] == 5.0


def test_false_detail_score_is_zero_for_identical_images() -> None:
    image = np.arange(64, dtype=np.float64).reshape((8, 8)) / 63.0

    metrics = false_detail_score(image, image)

    assert metrics["unsupported_energy_fraction"] == 0.0
