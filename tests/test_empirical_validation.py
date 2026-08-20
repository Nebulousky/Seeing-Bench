from __future__ import annotations

from pathlib import Path

import numpy as np

from seeingbench.benchmark.case import save_simulation_case
from seeingbench.benchmark.runner import evaluate_reconstruction
from seeingbench.evaluation.false_detail import false_detail_score
from seeingbench.evaluation.frequency import frequency_recovery_limit, radial_frequency_correlation
from seeingbench.evaluation.image_metrics import image_similarity_metrics
from seeingbench.evaluation.structure import gradient_correlation
from seeingbench.io.images import write_grayscale_tiff
from seeingbench.reconstruction.adapter import BaselineStackAdapter
from seeingbench.simulation.atmosphere import SeeingModel
from seeingbench.simulation.config import SeeingSimulationConfig, WarpScaleConfig
from seeingbench.simulation.psf import gaussian_blur
from seeingbench.simulation.source import crater_field


def test_mean_stack_empirically_beats_single_noisy_frame(tmp_path: Path) -> None:
    truth = crater_field((64, 64), crater_count=32, seed=4)
    config = SeeingSimulationConfig(
        frame_count=12,
        random_seed=11,
        temporal_correlation=0.0,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=8.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        gaussian_noise_sigma=0.05,
    )
    simulation = SeeingModel().generate(
        truth,
        config,
        np.random.default_rng(config.random_seed),
    )
    case_dir = tmp_path / "case"
    save_simulation_case(simulation, case_dir)

    single_dir = tmp_path / "single"
    single_dir.mkdir()
    write_grayscale_tiff(single_dir / "reconstruction.tif", simulation.frames[0])

    mean_dir = tmp_path / "mean"
    adapter = BaselineStackAdapter()
    adapter.prepare(case_dir, mean_dir)
    adapter.execute(case_dir, mean_dir)
    adapter.collect_results(case_dir, mean_dir)

    single = evaluate_reconstruction(case_dir, single_dir, algorithm="single_frame")
    mean = evaluate_reconstruction(case_dir, mean_dir, algorithm="mean_stack")

    assert mean.image_similarity["mse"] < single.image_similarity["mse"] * 0.2
    assert mean.image_similarity["psnr_db"] > single.image_similarity["psnr_db"] + 6.0
    assert mean.image_similarity["ssim_global"] > single.image_similarity["ssim_global"]
    assert (
        mean.structural_accuracy["gradient_correlation"]
        > single.structural_accuracy["gradient_correlation"]
    )
    assert (
        mean.frequency_recovery["correlation_0_5_limit_fraction"]
        > single.frequency_recovery["correlation_0_5_limit_fraction"]
    )
    assert (
        mean.false_detail["unsupported_energy_fraction"]
        < single.false_detail["unsupported_energy_fraction"]
    )


def test_false_detail_penalises_unsupported_checkerboard_texture() -> None:
    truth = crater_field((64, 64), crater_count=36, seed=8)
    smooth_reconstruction = gaussian_blur(truth, sigma_px=1.2)
    checkerboard = np.where(np.indices(truth.shape).sum(axis=0) % 2 == 0, 1.0, -1.0)
    hallucinated = np.clip(smooth_reconstruction + 0.07 * checkerboard, 0.0, 1.0)

    smooth_false_detail = false_detail_score(truth, smooth_reconstruction)
    hallucinated_false_detail = false_detail_score(truth, hallucinated)

    assert (
        hallucinated_false_detail["unsupported_energy_fraction"]
        > smooth_false_detail["unsupported_energy_fraction"] + 0.5
    )
    assert (
        hallucinated_false_detail["unsupported_energy"]
        > smooth_false_detail["unsupported_energy"] * 100.0
    )
    assert (
        image_similarity_metrics(truth, hallucinated)["ssim_global"]
        < image_similarity_metrics(
            truth,
            smooth_reconstruction,
        )["ssim_global"]
    )
    assert gradient_correlation(truth, hallucinated) < gradient_correlation(
        truth,
        smooth_reconstruction,
    )


def test_frequency_recovery_ranks_blur_levels() -> None:
    truth = crater_field((64, 64), crater_count=40, seed=12)
    mildly_blurred = gaussian_blur(truth, sigma_px=0.6)
    heavily_blurred = gaussian_blur(truth, sigma_px=2.0)

    mild_limit = frequency_recovery_limit(
        radial_frequency_correlation(truth, mildly_blurred, bins=12),
        threshold=0.5,
    )
    heavy_limit = frequency_recovery_limit(
        radial_frequency_correlation(truth, heavily_blurred, bins=12),
        threshold=0.5,
    )

    assert mild_limit > heavy_limit
