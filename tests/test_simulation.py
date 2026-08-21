from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from seeingbench.simulation.atmosphere import SeeingModel
from seeingbench.simulation.config import (
    SeeingSimulationConfig,
    WarpScaleConfig,
    load_simulation_config,
)
from seeingbench.simulation.sensor import block_average_downsample
from seeingbench.simulation.source import crater_field


def test_simulation_retains_truth_and_is_reproducible() -> None:
    image = crater_field(shape=(32, 32), crater_count=5, seed=9)
    config = SeeingSimulationConfig(
        frame_count=4,
        random_seed=42,
        warp_scales=(WarpScaleConfig("test", amplitude_px=0.4, correlation_px=8.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
        gaussian_noise_sigma=0.0,
    )

    first = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))
    second = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))

    np.testing.assert_allclose(first.frames, second.frames)
    np.testing.assert_allclose(first.latent_truth, image)
    assert first.frames.shape == (4, 32, 32)
    assert first.warp_fields.shape == (4, 32, 32, 2)
    assert set(first.warp_components) == {"test"}
    assert first.metadata["validation_boundary"]


def test_simulation_records_sensor_saturation() -> None:
    image = np.full((8, 8), 0.99, dtype=np.float64)
    config = SeeingSimulationConfig(
        frame_count=1,
        random_seed=1,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=4.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        gaussian_noise_sigma=0.5,
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))

    assert result.noise_information["high_saturated_pixels"] > 0
    assert np.max(result.frames) <= 1.0


def test_simulation_config_loads_from_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        """
        {
          "frame_count": 2,
          "random_seed": 5,
          "telescope_psf_model": "airy",
          "sensor_downsample_factor": 2,
          "spatial_blur_variation_sigma_px": 0.1,
          "global_motion_rms_px": 0.2,
          "warp_scales": [
            {"name": "coarse", "amplitude_px": 0.3, "correlation_px": 8.0}
          ]
        }
        """,
        encoding="utf-8",
    )

    config = load_simulation_config(path)

    assert config.frame_count == 2
    assert config.random_seed == 5
    assert config.telescope_psf_model == "airy"
    assert config.sensor_downsample_factor == 2
    assert config.spatial_blur_variation_sigma_px == 0.1
    assert config.global_motion_rms_px == 0.2
    assert config.warp_scales[0].name == "coarse"


def test_default_psf_and_seeing_values_are_physically_conservative() -> None:
    config = SeeingSimulationConfig()

    assert config.telescope_psf_sigma_px == pytest.approx(1.656)
    assert config.seeing_blur_sigma_px == pytest.approx(2.0)


def test_simulation_can_use_airy_telescope_psf() -> None:
    image = np.zeros((33, 33), dtype=np.float64)
    image[16, 16] = 1.0
    config = SeeingSimulationConfig(
        frame_count=1,
        random_seed=10,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=8.0),),
        telescope_psf_model="airy",
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
        gaussian_noise_sigma=0.0,
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))
    psf = result.psf_information["telescope_psf"]

    assert psf["model"] == "airy"
    assert psf["first_zero_radius_px"] > 0.0
    assert result.frames[0, 16, 16] < 1.0
    assert result.frames[0, 16, 16] > result.frames[0, 16, 17]


def test_block_average_downsample_rejects_implicit_crop() -> None:
    image = np.ones((5, 4), dtype=np.float64)

    with pytest.raises(ValueError, match="not divisible"):
        block_average_downsample(image, factor=2)


def test_sensor_downsample_changes_retained_truth_grid() -> None:
    image = crater_field(shape=(32, 32), crater_count=3, seed=1)
    config = SeeingSimulationConfig(
        frame_count=1,
        random_seed=2,
        sensor_downsample_factor=2,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=4.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))

    assert result.latent_truth.shape == (16, 16)
    assert result.frames.shape == (1, 16, 16)
    assert result.metadata["sensor_sampling"]["truth_shape_before_sensor"] == [32, 32]
    assert result.metadata["sensor_sampling"]["order"].endswith("sensor_block_average")


def test_default_simulation_includes_global_motion_component() -> None:
    image = crater_field(shape=(32, 32), crater_count=3, seed=3)
    config = SeeingSimulationConfig(
        frame_count=3,
        random_seed=4,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=8.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        gaussian_noise_sigma=0.0,
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))

    assert "global" in result.warp_components
    assert abs(float(np.mean(result.warp_fields[0, ..., 0]))) > 0.0


def test_spatial_blur_metadata_summarises_all_frames() -> None:
    image = crater_field(shape=(32, 32), crater_count=3, seed=7)
    config = SeeingSimulationConfig(
        frame_count=3,
        random_seed=8,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=8.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=1.0,
        spatial_blur_variation_sigma_px=0.25,
        global_motion_rms_px=0.0,
        gaussian_noise_sigma=0.0,
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))
    spatial_blur = result.psf_information["spatial_blur"]

    assert spatial_blur["frame_count"] == 3
    assert spatial_blur["frame_model"] == "smooth_two_kernel_blend"
    assert "min_effective_sigma_px" in spatial_blur
    assert "max_effective_sigma_px" in spatial_blur


def test_sensor_downsample_happens_after_warp() -> None:
    image = crater_field(shape=(32, 32), crater_count=4, seed=5)
    with_warp = SeeingSimulationConfig(
        frame_count=1,
        random_seed=6,
        sensor_downsample_factor=2,
        warp_scales=(WarpScaleConfig("globalish", amplitude_px=1.0, correlation_px=64.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
        gaussian_noise_sigma=0.0,
    )
    no_warp = SeeingSimulationConfig(
        frame_count=1,
        random_seed=6,
        sensor_downsample_factor=2,
        warp_scales=(WarpScaleConfig("none", amplitude_px=0.0, correlation_px=64.0),),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        global_motion_rms_px=0.0,
        gaussian_noise_sigma=0.0,
    )

    warped = SeeingModel().generate(image, with_warp, np.random.default_rng(with_warp.random_seed))
    unwarped = SeeingModel().generate(image, no_warp, np.random.default_rng(no_warp.random_seed))

    assert warped.frames.shape == (1, 16, 16)
    assert not np.allclose(warped.frames, unwarped.frames)
