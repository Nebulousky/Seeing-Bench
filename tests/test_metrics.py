from __future__ import annotations

import math
from typing import cast

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


def test_frequency_recovery_is_phase_sensitive() -> None:
    image = _structured_image()
    surrogate = _phase_scrambled_surrogate(image, seed=3)

    perfect_limit = frequency_recovery_limit(radial_frequency_correlation(image, image, bins=12))
    surrogate_limit = frequency_recovery_limit(
        radial_frequency_correlation(image, surrogate, bins=12)
    )

    assert perfect_limit > 0.9
    assert surrogate_limit < 0.25
    assert image_similarity_metrics(image, surrogate)["mse"] > 0.05


def test_frequency_recovery_declines_with_strong_blur() -> None:
    from seeingbench.simulation.psf import gaussian_blur

    image = _structured_image()
    mild = gaussian_blur(image, sigma_px=0.5)
    moderate = gaussian_blur(image, sigma_px=1.0)
    severe = gaussian_blur(image, sigma_px=3.0)
    extreme = gaussian_blur(image, sigma_px=8.0)

    limits = [
        frequency_recovery_limit(radial_frequency_correlation(image, candidate, bins=24))
        for candidate in (mild, moderate, severe, extreme)
    ]

    assert limits[0] > limits[1] > limits[2] >= limits[3]


def test_frequency_sample_count_tracks_independent_samples() -> None:
    image = _structured_image()

    rows = radial_frequency_correlation(image, image, bins=4)

    assert any(row["fourier_sample_count"] > row["sample_count"] for row in rows)


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


def test_false_detail_penalises_high_frequency_sign_flip() -> None:
    image = _structured_image()
    low_pass = _low_pass(image, cutoff_fraction=0.6)
    high_pass = image - low_pass
    sign_flipped = low_pass - high_pass

    metrics = false_detail_score(image, sign_flipped, cutoff_fraction=0.6)

    assert metrics["unsupported_energy_fraction"] > 0.6
    assert metrics["signed_residual_energy"] > 0.0


def test_gradient_correlation_detects_nyquist_checkerboard_difference() -> None:
    image = np.zeros((8, 8), dtype=np.float64)
    checkerboard = np.where(np.indices(image.shape).sum(axis=0) % 2 == 0, 1.0, 0.0)

    assert gradient_correlation(image, checkerboard.astype(np.float64)) < 1.0


def _structured_image() -> np.ndarray:
    y, x = np.mgrid[0:64, 0:64].astype(np.float64)
    image = (
        0.5
        + 0.18 * np.sin(2.0 * np.pi * x / 13.0)
        + 0.14 * np.cos(2.0 * np.pi * y / 9.0)
        + 0.08 * np.sin(2.0 * np.pi * (x + y) / 5.0)
    )
    image -= float(np.min(image))
    return cast(np.ndarray, (image / float(np.max(image))).astype(np.float64))


def _phase_scrambled_surrogate(image: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spectrum = np.fft.rfft2(image)
    phases = np.asarray(rng.uniform(-np.pi, np.pi, size=spectrum.shape), dtype=np.float64)
    phases[0, 0] = 0.0
    surrogate = np.fft.irfft2(np.abs(spectrum) * np.exp(1j * phases), s=image.shape).real
    surrogate -= float(np.min(surrogate))
    return (surrogate / float(np.max(surrogate))).astype(np.float64)


def _low_pass(image: np.ndarray, cutoff_fraction: float) -> np.ndarray:
    from seeingbench.evaluation.frequency import _normalised_radius

    transform = np.fft.fftshift(np.fft.fft2(image))
    transform[_normalised_radius(image.shape) >= cutoff_fraction] = 0.0
    return cast(np.ndarray, np.fft.ifft2(np.fft.ifftshift(transform)).real.astype(np.float64))
