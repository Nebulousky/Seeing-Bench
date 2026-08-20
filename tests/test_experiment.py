from __future__ import annotations

import json
from pathlib import Path

from seeingbench.benchmark.experiment import (
    SyntheticSweepConfig,
    load_synthetic_sweep_config,
    run_synthetic_sweep,
)


def test_synthetic_sweep_config_loads_from_json(tmp_path: Path) -> None:
    config_path = tmp_path / "sweep.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "tiny",
                "height": 24,
                "width": 24,
                "crater_count": 8,
                "frame_count": 3,
                "warp_strengths": [0.0, 1.0],
                "noise_sigmas": [0.0, 0.02],
                "telescope_psf_sigma_px": 0.7,
                "seeing_blur_sigma_px": 0.2,
                "global_motion_rms_px": 0.4,
                "frequency_bins": 4,
                "base_warp_scales": [
                    {
                        "name": "test",
                        "amplitude_px": 1.0,
                        "correlation_px": 12.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_synthetic_sweep_config(config_path)

    assert config.name == "tiny"
    assert config.warp_strengths == (0.0, 1.0)
    assert config.noise_sigmas == (0.0, 0.02)
    assert config.telescope_psf_sigma_px == 0.7
    assert config.seeing_blur_sigma_px == 0.2
    assert config.global_motion_rms_px == 0.4
    assert config.base_warp_scales[0].name == "test"


def test_synthetic_sweep_writes_metrics_and_summary(tmp_path: Path) -> None:
    config = SyntheticSweepConfig(
        name="tiny",
        height=24,
        width=24,
        crater_count=8,
        frame_count=3,
        random_seed=5,
        warp_strengths=(0.0, 1.0),
        noise_sigmas=(0.0,),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
        frequency_bins=4,
    )

    comparison = run_synthetic_sweep(config, tmp_path / "sweep")

    assert len(comparison["rows"]) == 8
    assert (tmp_path / "sweep" / "comparison.json").exists()
    assert (tmp_path / "sweep" / "summary.md").exists()
    assert (
        tmp_path / "sweep" / "results" / "warp_1__noise_0" / "oracle_aligned_stack" / "metrics.json"
    ).exists()
    assert {row["algorithm"] for row in comparison["rows"]} == {
        "single_frame",
        "mean_stack",
        "translation_stack",
        "oracle_aligned_stack",
    }
