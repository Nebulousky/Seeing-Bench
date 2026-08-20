"""False-detail metrics for unsupported high-frequency structure."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.frequency import _normalised_radius
from seeingbench.evaluation.image_metrics import _validate_pair

FloatArray = NDArray[np.float64]


def false_detail_score(
    reference: FloatArray,
    reconstruction: FloatArray,
    cutoff_fraction: float = 0.6,
    support_multiplier: float = 1.5,
) -> dict[str, float]:
    """Estimate signed high-frequency reconstruction residual unsupported by the reference.

    High-frequency reconstruction energy is unsupported when it has the wrong sign relative
    to the reference or exceeds the configured reference amplitude envelope.
    """

    _validate_pair(reference, reconstruction)
    if not 0 <= cutoff_fraction <= 1:
        raise ValueError("cutoff_fraction must be in [0, 1]")
    if support_multiplier < 0:
        raise ValueError("support_multiplier must be non-negative")

    ref_high = _high_pass(reference, cutoff_fraction)
    rec_high = _high_pass(reconstruction, cutoff_fraction)
    rec_energy = rec_high * rec_high
    signed_residual = rec_high - ref_high
    unsupported = (rec_high * ref_high < 0.0) | (
        np.abs(rec_high) > support_multiplier * np.abs(ref_high)
    )
    total_energy = float(np.sum(rec_energy))
    unsupported_energy = float(np.sum(rec_energy[unsupported]))
    fraction = unsupported_energy / total_energy if total_energy > 0 else 0.0
    return {
        "cutoff_fraction": cutoff_fraction,
        "support_multiplier": support_multiplier,
        "unsupported_energy": unsupported_energy,
        "signed_residual_energy": float(np.sum(signed_residual * signed_residual)),
        "total_high_frequency_energy": total_energy,
        "unsupported_energy_fraction": fraction,
    }


def false_detail_map(
    reference: FloatArray,
    reconstruction: FloatArray,
    cutoff_fraction: float = 0.6,
    support_multiplier: float = 1.5,
) -> FloatArray:
    """Return a map of unsupported high-frequency residual amplitude."""

    _validate_pair(reference, reconstruction)
    ref_high = _high_pass(reference, cutoff_fraction)
    rec_high = _high_pass(reconstruction, cutoff_fraction)
    wrong_sign = rec_high * ref_high < 0.0
    excess = np.abs(rec_high) - support_multiplier * np.abs(ref_high)
    return np.where(wrong_sign, np.abs(rec_high), np.maximum(excess, 0.0))


def _high_pass(image: FloatArray, cutoff_fraction: float) -> FloatArray:
    radius = _normalised_radius(image.shape)
    transform = np.fft.fftshift(np.fft.fft2(image))
    transform[radius < cutoff_fraction] = 0.0
    return np.fft.ifft2(np.fft.ifftshift(transform)).real.astype(np.float64)
