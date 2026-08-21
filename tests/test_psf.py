from __future__ import annotations

import numpy as np
import pytest

from seeingbench.simulation.config import TelescopeConfig
from seeingbench.simulation.psf import airy_first_zero_radius_px, airy_kernel2d


def test_airy_kernel_is_normalised_symmetric_and_centrally_peaked() -> None:
    kernel = airy_kernel2d(4.0, truncate=4.0)
    center = kernel.shape[0] // 2

    assert float(np.sum(kernel)) == pytest.approx(1.0)
    np.testing.assert_allclose(kernel, np.flipud(kernel))
    np.testing.assert_allclose(kernel, np.fliplr(kernel))
    assert kernel[center, center] == np.max(kernel)
    assert kernel[center, center] > kernel[center, center + 1]


def test_airy_kernel_changes_with_central_obstruction() -> None:
    unobstructed = airy_kernel2d(4.0, central_obstruction_ratio=0.0, truncate=4.0)
    obstructed = airy_kernel2d(4.0, central_obstruction_ratio=0.35, truncate=4.0)

    assert not np.allclose(obstructed, unobstructed)
    assert float(np.sum(obstructed)) == pytest.approx(1.0)


def test_default_airy_first_zero_radius_matches_rayleigh_sampling() -> None:
    assert airy_first_zero_radius_px(TelescopeConfig()) == pytest.approx(4.627586206896552)
