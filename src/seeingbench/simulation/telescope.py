"""Telescope geometry helpers."""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from seeingbench.simulation.config import TelescopeConfig

ARCSEC_PER_RADIAN = 206_264.80624709636
MOON_MEAN_DISTANCE_M = 384_400_000.0
GAUSSIAN_FWHM_TO_SIGMA = 1.0 / 2.3548200450309493


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


def airy_fwhm_arcsec(config: TelescopeConfig) -> float:
    """Return the approximate unobstructed Airy FWHM, ``1.028 lambda / aperture``."""

    config.validate()
    radians = 1.028 * (config.wavelength_nm * 1e-9) / (config.aperture_mm * 1e-3)
    return radians * ARCSEC_PER_RADIAN


def diffraction_gaussian_sigma_px(config: TelescopeConfig) -> float:
    """Return Gaussian sigma whose FWHM approximates the Airy core FWHM."""

    return airy_fwhm_arcsec(config) / plate_scale_arcsec_per_px(config) * GAUSSIAN_FWHM_TO_SIGMA


def central_obstruction_area_fraction(config: TelescopeConfig) -> float:
    """Return aperture area blocked by the central obstruction."""

    config.validate()
    return config.central_obstruction_ratio * config.central_obstruction_ratio


def clear_aperture_area_mm2(config: TelescopeConfig) -> float:
    """Return geometric light-collecting area after central obstruction."""

    config.validate()
    radius_mm = config.aperture_mm / 2.0
    return math.pi * radius_mm * radius_mm * (1.0 - central_obstruction_area_fraction(config))


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
    """Return incoherent diffraction cutoff as a fraction of sensor Nyquist frequency.

    Values below 1 mean diffraction removes contrast before the sensor Nyquist limit. Values
    above 1 mean the sensor undersamples the diffraction-limited image.
    """

    config.validate()
    sample_radians = plate_scale_arcsec_per_px(config) / ARCSEC_PER_RADIAN
    aperture_m = config.aperture_mm * 1e-3
    wavelength_m = config.wavelength_nm * 1e-9
    diffraction_cutoff_cycles_per_rad = aperture_m / wavelength_m
    sensor_nyquist_cycles_per_rad = 1.0 / (2.0 * sample_radians)
    return diffraction_cutoff_cycles_per_rad / sensor_nyquist_cycles_per_rad


def telescope_metadata(config: TelescopeConfig) -> dict[str, Any]:
    """Return serialisable telescope metadata and derived physical quantities."""

    return {
        "config": asdict(config),
        "effective_f_ratio": effective_f_ratio(config),
        "plate_scale_arcsec_per_px": plate_scale_arcsec_per_px(config),
        "diffraction_limit_arcsec": diffraction_limit_arcsec(config),
        "airy_fwhm_arcsec": airy_fwhm_arcsec(config),
        "diffraction_gaussian_sigma_px": diffraction_gaussian_sigma_px(config),
        "lunar_resolution_m_per_px_at_mean_distance": lunar_resolution_m_per_px(config),
        "diffraction_frequency_fraction_of_nyquist": diffraction_frequency_fraction(config),
        "central_obstruction_area_fraction": central_obstruction_area_fraction(config),
        "clear_aperture_area_mm2": clear_aperture_area_mm2(config),
        "rayleigh_formula": "1.22 * wavelength / aperture",
        "airy_fwhm_formula": "1.028 * wavelength / aperture",
        "diffraction_cutoff_formula": "(aperture / wavelength) / sensor_nyquist",
        "plate_scale_formula": "206264.806 * pixel_size / focal_length",
    }
