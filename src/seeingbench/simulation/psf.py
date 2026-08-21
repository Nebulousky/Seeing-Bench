"""Simple point-spread-function operations for synthetic benchmarks."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
from numpy.typing import NDArray

from seeingbench.simulation.config import TelescopeConfig
from seeingbench.simulation.telescope import diffraction_limit_arcsec, plate_scale_arcsec_per_px
from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]
J1_FIRST_ZERO = 3.8317059702075125


def gaussian_kernel1d(sigma_px: float, truncate: float = 4.0) -> FloatArray:
    """Return a unit-sum 1-D Gaussian kernel."""

    if sigma_px < 0:
        raise ValueError("sigma_px must be non-negative")
    if truncate <= 0:
        raise ValueError("truncate must be positive")
    if sigma_px == 0:
        return np.array([1.0], dtype=np.float64)

    radius = max(1, math.ceil(truncate * sigma_px))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2.0 * sigma_px * sigma_px))
    kernel_sum = float(np.sum(kernel))
    if kernel_sum <= 0:
        raise ValueError("gaussian kernel underflowed to zero")
    return kernel / kernel_sum


def gaussian_blur(image: FloatArray, sigma_px: float) -> FloatArray:
    """Blur a 2-D image with a separable Gaussian kernel."""

    validate_grayscale_image(image)
    kernel = gaussian_kernel1d(sigma_px)
    if kernel.size == 1:
        return image.copy()

    horizontal = _convolve_axis_reflect(image, kernel, axis=1)
    return _convolve_axis_reflect(horizontal, kernel, axis=0)


def airy_first_zero_radius_px(config: TelescopeConfig) -> float:
    """Return the Rayleigh/Airy first-zero radius in sensor pixels."""

    return diffraction_limit_arcsec(config) / plate_scale_arcsec_per_px(config)


def airy_kernel2d(
    first_zero_radius_px: float,
    *,
    central_obstruction_ratio: float = 0.0,
    truncate: float = 8.0,
) -> FloatArray:
    """Return a unit-sum Airy diffraction kernel sampled on the image grid.

    ``first_zero_radius_px`` is the unobstructed Rayleigh radius. A non-zero central
    obstruction uses the standard annular-aperture amplitude model.
    """

    first_zero_radius_px = float(first_zero_radius_px)
    central_obstruction_ratio = float(central_obstruction_ratio)
    truncate = float(truncate)
    if first_zero_radius_px <= 0.0:
        raise ValueError("first_zero_radius_px must be positive")
    if not 0.0 <= central_obstruction_ratio < 1.0:
        raise ValueError("central_obstruction_ratio must be in [0, 1)")
    if truncate <= 0.0:
        raise ValueError("truncate must be positive")

    radius = max(1, math.ceil(truncate * first_zero_radius_px))
    y, x = np.mgrid[-radius : radius + 1, -radius : radius + 1].astype(np.float64)
    rho = np.hypot(x, y)
    argument = J1_FIRST_ZERO * rho / first_zero_radius_px
    amplitude = _annular_airy_amplitude(argument, central_obstruction_ratio)
    kernel = amplitude * amplitude
    kernel_sum = float(np.sum(kernel))
    if kernel_sum <= 0.0:
        raise ValueError("Airy kernel underflowed to zero")
    return (kernel / kernel_sum).astype(np.float64, copy=False)


def airy_blur(image: FloatArray, config: TelescopeConfig, *, truncate: float = 8.0) -> FloatArray:
    """Blur a 2-D image with the diffraction PSF implied by a telescope config."""

    validate_grayscale_image(image)
    kernel = airy_kernel2d(
        airy_first_zero_radius_px(config),
        central_obstruction_ratio=config.central_obstruction_ratio,
        truncate=truncate,
    )
    return _convolve2d_reflect(image, kernel)


def spatially_varying_gaussian_blur(
    image: FloatArray,
    base_sigma_px: float,
    variation_sigma_px: float,
    correlation_px: float,
    rng: np.random.Generator,
) -> tuple[FloatArray, dict[str, str | float]]:
    """Approximate local seeing blur with a smooth blend between two Gaussian blurs."""

    validate_grayscale_image(image)
    if base_sigma_px < 0:
        raise ValueError("base_sigma_px must be non-negative")
    if variation_sigma_px < 0:
        raise ValueError("variation_sigma_px must be non-negative")
    if correlation_px <= 0:
        raise ValueError("correlation_px must be positive")
    if variation_sigma_px == 0:
        return gaussian_blur(image, base_sigma_px), {
            "model": "constant_gaussian",
            "base_sigma_px": base_sigma_px,
            "variation_sigma_px": variation_sigma_px,
            "correlation_px": correlation_px,
            "min_sigma_px": base_sigma_px,
            "max_sigma_px": base_sigma_px,
            "min_effective_sigma_px": base_sigma_px,
            "max_effective_sigma_px": base_sigma_px,
        }

    low_sigma = max(0.0, base_sigma_px - variation_sigma_px)
    high_sigma = base_sigma_px + variation_sigma_px
    low = gaussian_blur(image, low_sigma)
    high = gaussian_blur(image, high_sigma)
    weights = _smooth_weight_field(image.shape, correlation_px, rng)
    blended = (1.0 - weights) * low + weights * high
    effective_sigma_map = np.sqrt(
        (1.0 - weights) * low_sigma * low_sigma + weights * high_sigma * high_sigma
    )
    return blended.astype(np.float64), {
        "model": "smooth_two_kernel_blend",
        "base_sigma_px": base_sigma_px,
        "variation_sigma_px": variation_sigma_px,
        "correlation_px": correlation_px,
        "low_kernel_sigma_px": low_sigma,
        "high_kernel_sigma_px": high_sigma,
        "min_blend_weight": float(np.min(weights)),
        "max_blend_weight": float(np.max(weights)),
        "min_effective_sigma_px": float(np.min(effective_sigma_map)),
        "max_effective_sigma_px": float(np.max(effective_sigma_map)),
    }


def _convolve_axis_reflect(image: FloatArray, kernel: FloatArray, axis: int) -> FloatArray:
    pad = kernel.size // 2
    if axis == 1:
        padded = np.pad(image, ((0, 0), (pad, pad)), mode="reflect")
        out = np.empty_like(image)
        for col in range(image.shape[1]):
            out[:, col] = np.sum(padded[:, col : col + kernel.size] * kernel, axis=1)
        return out

    padded = np.pad(image, ((pad, pad), (0, 0)), mode="reflect")
    out = np.empty_like(image)
    for row in range(image.shape[0]):
        out[row, :] = np.sum(padded[row : row + kernel.size, :] * kernel[:, None], axis=0)
    return out


def _convolve2d_reflect(image: FloatArray, kernel: FloatArray) -> FloatArray:
    pad_y = kernel.shape[0] // 2
    pad_x = kernel.shape[1] // 2
    padded = np.pad(image, ((pad_y, pad_y), (pad_x, pad_x)), mode="reflect")
    out = np.empty_like(image)
    for row in range(image.shape[0]):
        for col in range(image.shape[1]):
            window = padded[row : row + kernel.shape[0], col : col + kernel.shape[1]]
            out[row, col] = float(np.sum(window * kernel))
    return out


def _annular_airy_amplitude(argument: FloatArray, obstruction: float) -> FloatArray:
    amplitude = np.ones_like(argument)
    nonzero = argument != 0.0
    x = argument[nonzero]
    if obstruction == 0.0:
        amplitude[nonzero] = 2.0 * _bessel_j1(x) / x
        return amplitude

    denominator = x * (1.0 - obstruction * obstruction)
    amplitude[nonzero] = 2.0 * (_bessel_j1(x) - obstruction * _bessel_j1(obstruction * x))
    amplitude[nonzero] /= denominator
    return amplitude


def _bessel_j1(values: FloatArray) -> FloatArray:
    """Numerically evaluate J1 with fixed Gauss-Legendre quadrature.

    The integral representation keeps this dependency-free while remaining accurate enough
    for deterministic PSF kernels.
    """

    nodes, weights = np.polynomial.legendre.leggauss(64)
    theta = 0.5 * math.pi * (nodes + 1.0)
    theta_weights = 0.5 * weights
    integrand = np.cos(theta[None, :] - values.reshape(-1, 1) * np.sin(theta)[None, :])
    result = integrand @ theta_weights
    return (result.reshape(values.shape)).astype(np.float64, copy=False)


def _smooth_weight_field(
    shape: tuple[int, int],
    correlation_px: float,
    rng: np.random.Generator,
) -> FloatArray:
    height, width = shape
    coarse_h = max(2, math.ceil(height / correlation_px) + 1)
    coarse_w = max(2, math.ceil(width / correlation_px) + 1)
    coarse = rng.uniform(size=(coarse_h, coarse_w)).astype(np.float64)
    y = np.linspace(0.0, coarse_h - 1.0, height)
    x = np.linspace(0.0, coarse_w - 1.0, width)
    grid_x, grid_y = np.meshgrid(x, y)
    return _sample_bilinear_unit(coarse, grid_x, grid_y)


def _sample_bilinear_unit(
    image: FloatArray, x_coords: FloatArray, y_coords: FloatArray
) -> FloatArray:
    height, width = image.shape
    x0 = np.floor(x_coords).astype(np.int64)
    y0 = np.floor(y_coords).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = x_coords - x0
    wy = y_coords - y0
    top = (1.0 - wx) * image[y0, x0] + wx * image[y0, x1]
    bottom = (1.0 - wx) * image[y1, x0] + wx * image[y1, x1]
    return cast(FloatArray, ((1.0 - wy) * top + wy * bottom).astype(np.float64))
