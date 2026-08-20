"""Synthetic atmospheric seeing model."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

import seeingbench
from seeingbench.simulation.config import SeeingSimulationConfig
from seeingbench.simulation.noise import add_gaussian_noise, apply_sensor_range
from seeingbench.simulation.psf import gaussian_blur, spatially_varying_gaussian_blur
from seeingbench.simulation.sensor import block_average_downsample
from seeingbench.simulation.telescope import telescope_metadata
from seeingbench.simulation.warp import (
    apply_warp,
    generate_multiscale_warp_fields,
    validate_grayscale_image,
)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class SimulationResult:
    """All generated observations and retained synthetic truth."""

    frames: FloatArray
    latent_truth: FloatArray
    warp_fields: FloatArray
    warp_components: dict[str, FloatArray]
    psf_information: dict[str, Any]
    noise_information: dict[str, Any]
    metadata: dict[str, Any]


class SeeingModel:
    """Generate synthetic lunar lucky-imaging sequences with retained truth."""

    algorithm_name = "smooth_multiscale_gaussian_seeing"

    def generate(
        self,
        image: FloatArray,
        config: SeeingSimulationConfig,
        rng: np.random.Generator,
    ) -> SimulationResult:
        """Generate a sequence from a finite 2-D float64 truth image in [0, 1]."""

        config.validate()
        validate_grayscale_image(image)
        if np.min(image) < config.output_min or np.max(image) > config.output_max:
            raise ValueError("input image must already be in the configured output range")

        latent = block_average_downsample(image, config.sensor_downsample_factor)
        telescope_blurred = gaussian_blur(latent, config.telescope_psf_sigma_px)
        warp_fields, components = generate_multiscale_warp_fields(
            shape=latent.shape,
            frame_count=config.frame_count,
            scales=config.warp_scales,
            temporal_correlation=config.temporal_correlation,
            rng=rng,
        )

        frames = np.empty((config.frame_count, *latent.shape), dtype=np.float64)
        low_saturated = 0
        high_saturated = 0
        for frame_index in range(config.frame_count):
            warped = apply_warp(telescope_blurred, warp_fields[frame_index])
            blurred, local_blur = spatially_varying_gaussian_blur(
                warped,
                config.seeing_blur_sigma_px,
                config.spatial_blur_variation_sigma_px,
                config.spatial_blur_correlation_px,
                rng,
            )
            noisy = add_gaussian_noise(blurred, config.gaussian_noise_sigma, rng)
            ranged = apply_sensor_range(noisy, config.output_min, config.output_max)
            frames[frame_index] = ranged.image
            low_saturated += ranged.low_saturated
            high_saturated += ranged.high_saturated

        return SimulationResult(
            frames=frames,
            latent_truth=latent,
            warp_fields=warp_fields,
            warp_components=components,
            psf_information={
                "telescope_psf": {
                    "model": "gaussian",
                    "sigma_px": config.telescope_psf_sigma_px,
                },
                "seeing_blur": {
                    "model": "gaussian",
                    "sigma_px": config.seeing_blur_sigma_px,
                },
                "spatial_blur": local_blur if config.frame_count > 0 else None,
                "telescope": telescope_metadata(config.telescope),
            },
            noise_information={
                "model": "gaussian",
                "sigma": config.gaussian_noise_sigma,
                "sensor_range": [config.output_min, config.output_max],
                "low_saturated_pixels": low_saturated,
                "high_saturated_pixels": high_saturated,
            },
            metadata={
                "benchmark_mode": "synthetic",
                "algorithm": self.algorithm_name,
                "seeingbench_version": seeingbench.__version__,
                "python": platform.python_version(),
                "numpy": np.__version__,
                "config": config.to_dict(),
                "sensor_sampling": {
                    "downsample_factor": config.sensor_downsample_factor,
                    "truth_shape_before_sensor": list(image.shape),
                    "truth_shape_after_sensor": list(latent.shape),
                },
                "validation_boundary": (
                    "truth is retained by SeeingBench and not provided to reconstruction"
                ),
            },
        )
