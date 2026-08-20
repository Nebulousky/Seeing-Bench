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
          "sensor_downsample_factor": 2,
          "spatial_blur_variation_sigma_px": 0.1,
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
    assert config.sensor_downsample_factor == 2
    assert config.spatial_blur_variation_sigma_px == 0.1
    assert config.warp_scales[0].name == "coarse"


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
    )

    result = SeeingModel().generate(image, config, np.random.default_rng(config.random_seed))

    assert result.latent_truth.shape == (16, 16)
    assert result.frames.shape == (1, 16, 16)
    assert result.metadata["sensor_sampling"]["truth_shape_before_sensor"] == [32, 32]
