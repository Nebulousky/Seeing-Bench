from __future__ import annotations

import numpy as np
import pytest

from seeingbench.rendering.illumination import lambertian_shading_from_dem, lunar_shading_from_dem


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


def test_lommel_seeliger_shading_uses_solar_and_observer_geometry() -> None:
    terrain = np.zeros((8, 8), dtype=np.float64)

    lambertian = lunar_shading_from_dem(
        terrain,
        100.0,
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_solar_latitude_deg=0.0,
        sub_solar_longitude_deg_east=0.0,
        model="lambertian",
    )
    lommel = lunar_shading_from_dem(
        terrain,
        100.0,
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_solar_latitude_deg=0.0,
        sub_solar_longitude_deg_east=0.0,
        sub_observer_latitude_deg=0.0,
        sub_observer_longitude_deg_east=60.0,
        model="lommel_seeliger",
    )

    assert float(np.mean(lambertian)) == pytest.approx(1.0)
    assert float(np.mean(lommel)) == pytest.approx(4.0 / 3.0)


def test_lommel_seeliger_requires_observer_geometry() -> None:
    terrain = np.zeros((8, 8), dtype=np.float64)

    with pytest.raises(ValueError, match="requires sub-observer"):
        lunar_shading_from_dem(
            terrain,
            100.0,
            center_latitude_deg=0.0,
            center_longitude_deg_east=0.0,
            sub_solar_latitude_deg=0.0,
            sub_solar_longitude_deg_east=0.0,
            model="lommel_seeliger",
        )
