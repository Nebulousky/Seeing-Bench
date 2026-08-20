"""Telescope geometry helpers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from seeingbench.simulation.config import TelescopeConfig

ARCSEC_PER_RADIAN = 206_264.80624709636
MOON_MEAN_DISTANCE_M = 384_400_000.0


def effective_f_ratio(config: TelescopeConfig) -> float:
    """Return focal ratio, ``focal_length / aperture``."""

    config.validate()
    return config.focal_length_mm / config.aperture_mm


def plate_scale_arcsec_per_px(config: TelescopeConfig) -> float:
    """Return angular sampling in arcseconds per pixel."""

    config.validate()
    return ARCSEC_PER_RADIAN * (config.pixel_size_um * 1e-6) / (config.focal_length_mm * 1e-3)


def diffraction_limit_arcsec(config: TelescopeConfig) -> float:
    """Return Rayleigh angular resolution, ``1.22 lambda / aperture``."""

    config.validate()
    radians = 1.22 * (config.wavelength_nm * 1e-9) / (config.aperture_mm * 1e-3)
    return radians * ARCSEC_PER_RADIAN


def lunar_resolution_m_per_px(
    config: TelescopeConfig,
    earth_moon_distance_m: float = MOON_MEAN_DISTANCE_M,
) -> float:
    """Return approximate lunar surface sampling per pixel at the lunar distance."""

    if earth_moon_distance_m <= 0:
        raise ValueError("earth_moon_distance_m must be positive")
    radians_per_px = plate_scale_arcsec_per_px(config) / ARCSEC_PER_RADIAN
    return radians_per_px * earth_moon_distance_m


def diffraction_frequency_fraction(config: TelescopeConfig) -> float:
    """Return diffraction limit as a fraction of the Nyquist frequency.

    Values below 1 mean diffraction removes contrast before the sensor Nyquist limit. Values
    above 1 mean the sensor undersamples the diffraction-limited image.
    """

    sample = plate_scale_arcsec_per_px(config)
    diffraction = diffraction_limit_arcsec(config)
    return min(1.0, sample / (2.0 * diffraction))


def telescope_metadata(config: TelescopeConfig) -> dict[str, Any]:
    """Return serialisable telescope metadata and derived physical quantities."""

    return {
        "config": asdict(config),
        "effective_f_ratio": effective_f_ratio(config),
        "plate_scale_arcsec_per_px": plate_scale_arcsec_per_px(config),
        "diffraction_limit_arcsec": diffraction_limit_arcsec(config),
        "lunar_resolution_m_per_px_at_mean_distance": lunar_resolution_m_per_px(config),
        "diffraction_frequency_fraction_of_nyquist": diffraction_frequency_fraction(config),
        "rayleigh_formula": "1.22 * wavelength / aperture",
        "plate_scale_formula": "206264.806 * pixel_size / focal_length",
    }
