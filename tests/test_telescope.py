from __future__ import annotations

import pytest

from seeingbench.simulation.config import TelescopeConfig
from seeingbench.simulation.telescope import (
    diffraction_frequency_fraction,
    diffraction_gaussian_sigma_px,
    telescope_metadata,
)


def test_default_diffraction_cutoff_is_sensor_nyquist_fraction() -> None:
    assert diffraction_frequency_fraction(TelescopeConfig()) == pytest.approx(0.5272727272727272)


def test_default_diffraction_gaussian_sigma_matches_default_config() -> None:
    assert diffraction_gaussian_sigma_px(TelescopeConfig()) == pytest.approx(1.65597, rel=1e-4)


def test_diffraction_cutoff_can_exceed_nyquist_when_sensor_undersamples() -> None:
    config = TelescopeConfig(pixel_size_um=10.0)

    assert diffraction_frequency_fraction(config) > 1.0


def test_central_obstruction_changes_derived_telescope_metadata() -> None:
    unobstructed = telescope_metadata(TelescopeConfig(central_obstruction_ratio=0.0))
    obstructed = telescope_metadata(TelescopeConfig(central_obstruction_ratio=0.35))

    assert obstructed["central_obstruction_area_fraction"] == pytest.approx(0.1225)
    assert obstructed["clear_aperture_area_mm2"] < unobstructed["clear_aperture_area_mm2"]
