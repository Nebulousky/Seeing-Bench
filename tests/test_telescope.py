from __future__ import annotations

import pytest

from seeingbench.simulation.config import TelescopeConfig
from seeingbench.simulation.telescope import diffraction_frequency_fraction


def test_default_diffraction_cutoff_is_sensor_nyquist_fraction() -> None:
    assert diffraction_frequency_fraction(TelescopeConfig()) == pytest.approx(0.5272727272727272)


def test_diffraction_cutoff_can_exceed_nyquist_when_sensor_undersamples() -> None:
    config = TelescopeConfig(pixel_size_um=10.0)

    assert diffraction_frequency_fraction(config) > 1.0
