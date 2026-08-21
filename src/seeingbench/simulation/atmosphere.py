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
from seeingbench.simulation.psf import (
    airy_blur,
    airy_first_zero_radius_px,
    gaussian_blur,
    spatially_varying_gaussian_blur,
)
from seeingbench.simulation.sensor import block_average_downsample
from seeingbench.simulation.telescope import diffraction_gaussian_sigma_px, telescope_metadata
from seeingbench.simulation.warp import (
    apply_warp,
    generate_multiscale_warp_fields,
    validate_grayscale_image,
)

FloatArray = NDArray[np.float64]
SENSOR_SAMPLING_ORDER = "telescope_psf -> atmosphere_warp -> seeing_blur -> sensor_block_average"


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
        telescope_blurred = _apply_telescope_psf(image, config)
        warp_fields, components = generate_multiscale_warp_fields(
            shape=image.shape,
            frame_count=config.frame_count,
            scales=config.warp_scales,
            temporal_correlation=config.temporal_correlation,
            rng=rng,
        )
        if config.global_motion_rms_px > 0.0:
            global_motion = _generate_global_motion_fields(
                shape=image.shape,
                frame_count=config.frame_count,
                rms_px=config.global_motion_rms_px,
                temporal_correlation=config.temporal_correlation,
                rng=rng,
            )
            components = {**components, "global": global_motion}
            warp_fields = warp_fields + global_motion

        frames = np.empty((config.frame_count, *latent.shape), dtype=np.float64)
        low_saturated = 0
        high_saturated = 0
        spatial_blur_frames: list[dict[str, Any]] = []
        for frame_index in range(config.frame_count):
            warped = apply_warp(telescope_blurred, warp_fields[frame_index])
            blurred, local_blur = spatially_varying_gaussian_blur(
                warped,
                config.seeing_blur_sigma_px,
                config.spatial_blur_variation_sigma_px,
                config.spatial_blur_correlation_px,
                rng,
            )
            spatial_blur_frames.append(local_blur)
            sampled = block_average_downsample(blurred, config.sensor_downsample_factor)
            noisy = add_gaussian_noise(sampled, config.gaussian_noise_sigma, rng)
            ranged = apply_sensor_range(noisy, config.output_min, config.output_max)
            frames[frame_index] = ranged.image
            low_saturated += ranged.low_saturated
            high_saturated += ranged.high_saturated

        sensor_warp_fields = _downsample_displacement_fields(
            warp_fields,
            config.sensor_downsample_factor,
        )
        sensor_components = {
            name: _downsample_displacement_fields(component, config.sensor_downsample_factor)
            for name, component in components.items()
        }

        return SimulationResult(
            frames=frames,
            latent_truth=latent,
            warp_fields=sensor_warp_fields,
            warp_components=sensor_components,
            psf_information={
                "telescope_psf": _telescope_psf_metadata(config),
                "seeing_blur": {
                    "model": "gaussian",
                    "sigma_px": config.seeing_blur_sigma_px,
                },
                "spatial_blur": _summarise_spatial_blur(spatial_blur_frames),
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
                    "order": SENSOR_SAMPLING_ORDER,
                },
                "validation_boundary": (
                    "truth is retained by SeeingBench and not provided to reconstruction"
                ),
            },
        )


def _apply_telescope_psf(image: FloatArray, config: SeeingSimulationConfig) -> FloatArray:
    if config.telescope_psf_model == "gaussian":
        return gaussian_blur(image, config.telescope_psf_sigma_px)
    if config.telescope_psf_model == "airy":
        return airy_blur(image, config.telescope)
    raise ValueError("telescope_psf_model must be 'gaussian' or 'airy'")


def _telescope_psf_metadata(config: SeeingSimulationConfig) -> dict[str, Any]:
    if config.telescope_psf_model == "gaussian":
        diffraction_sigma = diffraction_gaussian_sigma_px(config.telescope)
        return {
            "model": "gaussian",
            "sigma_px": config.telescope_psf_sigma_px,
            "diffraction_gaussian_sigma_px": diffraction_sigma,
            "sigma_to_diffraction_gaussian_ratio": config.telescope_psf_sigma_px
            / diffraction_sigma,
        }
    if config.telescope_psf_model == "airy":
        return {
            "model": "airy",
            "first_zero_radius_px": airy_first_zero_radius_px(config.telescope),
            "central_obstruction_ratio": config.telescope.central_obstruction_ratio,
            "diffraction_gaussian_sigma_px": diffraction_gaussian_sigma_px(config.telescope),
        }
    raise ValueError("telescope_psf_model must be 'gaussian' or 'airy'")


def _generate_global_motion_fields(
    shape: tuple[int, int],
    frame_count: int,
    rms_px: float,
    temporal_correlation: float,
    rng: np.random.Generator,
) -> FloatArray:
    h, w = shape
    fields = np.empty((frame_count, h, w, 2), dtype=np.float64)
    state = rng.normal(scale=rms_px, size=2).astype(np.float64)
    innovation_weight = float(np.sqrt(1.0 - temporal_correlation * temporal_correlation))
    for index in range(frame_count):
        if index > 0:
            innovation = rng.normal(scale=rms_px, size=2).astype(np.float64)
            state = temporal_correlation * state + innovation_weight * innovation
        fields[index, ..., 0] = state[0]
        fields[index, ..., 1] = state[1]
    return fields


def _downsample_displacement_fields(fields: FloatArray, factor: int) -> FloatArray:
    if factor == 1:
        return fields.copy()
    frame_count = fields.shape[0]
    downsampled = np.empty(
        (frame_count, fields.shape[1] // factor, fields.shape[2] // factor, 2),
        dtype=np.float64,
    )
    for index in range(frame_count):
        downsampled[index, ..., 0] = (
            block_average_downsample(fields[index, ..., 0], factor) / factor
        )
        downsampled[index, ..., 1] = (
            block_average_downsample(fields[index, ..., 1], factor) / factor
        )
    return downsampled


def _summarise_spatial_blur(frames: list[dict[str, Any]]) -> dict[str, Any]:
    if not frames:
        return {"model": "none", "frame_count": 0}
    return {
        "model": "per_frame_summary",
        "frame_count": len(frames),
        "frame_model": frames[0].get("model", "unknown"),
        "base_sigma_px": frames[0].get("base_sigma_px"),
        "variation_sigma_px": frames[0].get("variation_sigma_px"),
        "correlation_px": frames[0].get("correlation_px"),
        "min_effective_sigma_px": min(
            float(frame.get("min_effective_sigma_px", frame.get("min_sigma_px", 0.0)))
            for frame in frames
        ),
        "max_effective_sigma_px": max(
            float(frame.get("max_effective_sigma_px", frame.get("max_sigma_px", 0.0)))
            for frame in frames
        ),
    }
