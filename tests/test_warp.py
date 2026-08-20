from __future__ import annotations

import numpy as np

from seeingbench.simulation.config import WarpScaleConfig
from seeingbench.simulation.warp import apply_warp, generate_multiscale_warp_fields


def test_apply_warp_identity_preserves_image() -> None:
    image = np.arange(25, dtype=np.float64).reshape((5, 5)) / 24.0
    displacement = np.zeros((5, 5, 2), dtype=np.float64)

    warped = apply_warp(image, displacement)

    np.testing.assert_allclose(warped, image)


def test_constant_horizontal_warp_uses_documented_sign() -> None:
    image = np.tile(np.arange(5, dtype=np.float64), (5, 1))
    displacement = np.zeros((5, 5, 2), dtype=np.float64)
    displacement[..., 0] = 1.0

    warped = apply_warp(image, displacement)

    np.testing.assert_allclose(warped[:, 2:], image[:, 1:-1])


def test_multiscale_fields_are_reproducible_and_components_sum() -> None:
    scales = (
        WarpScaleConfig("coarse", amplitude_px=0.5, correlation_px=8.0),
        WarpScaleConfig("fine", amplitude_px=0.2, correlation_px=4.0),
    )
    first_rng = np.random.default_rng(123)
    second_rng = np.random.default_rng(123)

    first, first_components = generate_multiscale_warp_fields(
        shape=(16, 16),
        frame_count=3,
        scales=scales,
        temporal_correlation=0.5,
        rng=first_rng,
    )
    second, _ = generate_multiscale_warp_fields(
        shape=(16, 16),
        frame_count=3,
        scales=scales,
        temporal_correlation=0.5,
        rng=second_rng,
    )

    np.testing.assert_allclose(first, second)
    component_sum = np.zeros_like(first)
    for component in first_components.values():
        component_sum += component
    np.testing.assert_allclose(first, component_sum)
