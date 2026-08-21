from __future__ import annotations

import numpy as np
import pytest

from seeingbench.rendering.illumination import lambertian_shading_from_dem


def test_lambertian_shading_flat_dem_is_one_under_overhead_sun() -> None:
    terrain = np.zeros((8, 8), dtype=np.float64)

    shading = lambertian_shading_from_dem(
        terrain,
        100.0,
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_solar_latitude_deg=0.0,
        sub_solar_longitude_deg_east=0.0,
    )

    assert np.allclose(shading, 1.0)


def test_lambertian_shading_responds_to_dem_slope() -> None:
    terrain = np.tile(np.arange(8, dtype=np.float64), (8, 1)) * 100.0

    shading = lambertian_shading_from_dem(
        terrain,
        100.0,
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_solar_latitude_deg=0.0,
        sub_solar_longitude_deg_east=0.0,
    )

    assert float(np.mean(shading)) == pytest.approx(2.0**-0.5)
