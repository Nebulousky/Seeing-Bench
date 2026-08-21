"""Typed configuration for synthetic seeing simulations.

All distances with a ``_px`` suffix are expressed in pixels in the current image grid.
All telescope dimensions use SI-derived metric units stated in the field names.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WarpScaleConfig:
    """One smooth atmospheric displacement component.

    Attributes:
        name: Stable label used in saved truth component files.
        amplitude_px: Target RMS displacement amplitude in pixels.
        correlation_px: Approximate spatial correlation length in pixels.
    """

    name: str
    amplitude_px: float
    correlation_px: float

    def validate(self) -> None:
        if not self.name:
            raise ValueError("warp scale name must be non-empty")
        if self.amplitude_px < 0:
            raise ValueError(f"{self.name}: amplitude_px must be non-negative")
        if self.correlation_px <= 0:
            raise ValueError(f"{self.name}: correlation_px must be positive")


@dataclass(frozen=True)
class TelescopeConfig:
    """Telescope and camera geometry used to set physical benchmark limits."""

    aperture_mm: float = 200.0
    focal_length_mm: float = 4000.0
    central_obstruction_ratio: float = 0.0
    wavelength_nm: float = 550.0
    pixel_size_um: float = 2.9
    sensor_width_px: int | None = None
    sensor_height_px: int | None = None

    def validate(self) -> None:
        if self.aperture_mm <= 0:
            raise ValueError("aperture_mm must be positive")
        if self.focal_length_mm <= 0:
            raise ValueError("focal_length_mm must be positive")
        if not 0 <= self.central_obstruction_ratio < 1:
            raise ValueError("central_obstruction_ratio must be in [0, 1)")
        if self.wavelength_nm <= 0:
            raise ValueError("wavelength_nm must be positive")
        if self.pixel_size_um <= 0:
            raise ValueError("pixel_size_um must be positive")
        if self.sensor_width_px is not None and self.sensor_width_px <= 0:
            raise ValueError("sensor_width_px must be positive when provided")
        if self.sensor_height_px is not None and self.sensor_height_px <= 0:
            raise ValueError("sensor_height_px must be positive when provided")


@dataclass(frozen=True)
class SeeingSimulationConfig:
    """Configuration for one synthetic sequence generation run."""

    frame_count: int = 16
    random_seed: int = 0
    temporal_correlation: float = 0.85
    warp_scales: tuple[WarpScaleConfig, ...] = field(
        default_factory=lambda: (
            WarpScaleConfig("large", amplitude_px=1.5, correlation_px=64.0),
            WarpScaleConfig("medium", amplitude_px=0.7, correlation_px=24.0),
            WarpScaleConfig("fine", amplitude_px=0.25, correlation_px=8.0),
        )
    )
    telescope: TelescopeConfig = field(default_factory=TelescopeConfig)
    telescope_psf_model: str = "gaussian"
    telescope_psf_sigma_px: float = 1.656
    seeing_blur_sigma_px: float = 2.0
    spatial_blur_variation_sigma_px: float = 0.0
    spatial_blur_correlation_px: float = 32.0
    global_motion_rms_px: float = 0.75
    sensor_downsample_factor: int = 1
    gaussian_noise_sigma: float = 0.01
    output_min: float = 0.0
    output_max: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeeingSimulationConfig:
        """Construct config from a JSON-compatible dictionary."""

        known = {
            "frame_count",
            "random_seed",
            "temporal_correlation",
            "warp_scales",
            "telescope",
            "telescope_psf_model",
            "telescope_psf_sigma_px",
            "seeing_blur_sigma_px",
            "spatial_blur_variation_sigma_px",
            "spatial_blur_correlation_px",
            "global_motion_rms_px",
            "sensor_downsample_factor",
            "gaussian_noise_sigma",
            "output_min",
            "output_max",
            "description",
        }
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"unknown simulation config field(s): {', '.join(unknown)}")

        telescope_data = data.get("telescope", {})
        if not isinstance(telescope_data, dict):
            raise ValueError("telescope must be an object")
        warp_scale_data = data.get("warp_scales")
        if warp_scale_data is None:
            warp_scales = cls().warp_scales
        else:
            if not isinstance(warp_scale_data, list):
                raise ValueError("warp_scales must be a list")
            warp_scales = tuple(_warp_scale_from_dict(item) for item in warp_scale_data)

        config = cls(
            frame_count=int(data.get("frame_count", cls.frame_count)),
            random_seed=int(data.get("random_seed", cls.random_seed)),
            temporal_correlation=float(data.get("temporal_correlation", cls.temporal_correlation)),
            warp_scales=warp_scales,
            telescope=TelescopeConfig(**telescope_data),
            telescope_psf_model=str(data.get("telescope_psf_model", cls.telescope_psf_model)),
            telescope_psf_sigma_px=float(
                data.get("telescope_psf_sigma_px", cls.telescope_psf_sigma_px)
            ),
            seeing_blur_sigma_px=float(data.get("seeing_blur_sigma_px", cls.seeing_blur_sigma_px)),
            spatial_blur_variation_sigma_px=float(
                data.get(
                    "spatial_blur_variation_sigma_px",
                    cls.spatial_blur_variation_sigma_px,
                )
            ),
            spatial_blur_correlation_px=float(
                data.get("spatial_blur_correlation_px", cls.spatial_blur_correlation_px)
            ),
            global_motion_rms_px=float(data.get("global_motion_rms_px", cls.global_motion_rms_px)),
            sensor_downsample_factor=int(
                data.get("sensor_downsample_factor", cls.sensor_downsample_factor)
            ),
            gaussian_noise_sigma=float(data.get("gaussian_noise_sigma", cls.gaussian_noise_sigma)),
            output_min=float(data.get("output_min", cls.output_min)),
            output_max=float(data.get("output_max", cls.output_max)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.frame_count <= 0:
            raise ValueError("frame_count must be positive")
        if not 0 <= self.temporal_correlation < 1:
            raise ValueError("temporal_correlation must be in [0, 1)")
        if self.telescope_psf_sigma_px < 0:
            raise ValueError("telescope_psf_sigma_px must be non-negative")
        if self.telescope_psf_model not in {"gaussian", "airy"}:
            raise ValueError("telescope_psf_model must be 'gaussian' or 'airy'")
        if self.seeing_blur_sigma_px < 0:
            raise ValueError("seeing_blur_sigma_px must be non-negative")
        if self.spatial_blur_variation_sigma_px < 0:
            raise ValueError("spatial_blur_variation_sigma_px must be non-negative")
        if self.spatial_blur_correlation_px <= 0:
            raise ValueError("spatial_blur_correlation_px must be positive")
        if self.global_motion_rms_px < 0:
            raise ValueError("global_motion_rms_px must be non-negative")
        if self.sensor_downsample_factor <= 0:
            raise ValueError("sensor_downsample_factor must be positive")
        if self.gaussian_noise_sigma < 0:
            raise ValueError("gaussian_noise_sigma must be non-negative")
        if self.output_min >= self.output_max:
            raise ValueError("output_min must be less than output_max")
        self.telescope.validate()
        for scale in self.warp_scales:
            scale.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_simulation_config(path: Path) -> SeeingSimulationConfig:
    """Load a synthetic simulation config from JSON."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("simulation config must be a JSON object")
    return SeeingSimulationConfig.from_dict(data)


def _warp_scale_from_dict(data: Any) -> WarpScaleConfig:
    if not isinstance(data, dict):
        raise ValueError("each warp scale must be an object")
    return WarpScaleConfig(
        name=str(data["name"]),
        amplitude_px=float(data["amplitude_px"]),
        correlation_px=float(data["correlation_px"]),
    )
