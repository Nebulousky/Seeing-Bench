from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from seeingbench.cli import main
from seeingbench.geometry.observation import build_spice_observation_geometry_report


def test_spice_observation_geometry_computes_topocentric_distance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_spice = FakeSpice()
    monkeypatch.setattr(
        "seeingbench.geometry.observation.importlib.import_module",
        lambda name: fake_spice if name == "spiceypy" else None,
    )
    cache_root = tmp_path / "cache"
    kernel_path = cache_root / "spice" / "test.bsp"
    kernel_path.parent.mkdir(parents=True)
    kernel_path.write_bytes(b"kernel")
    observation_path = _write_observation(tmp_path, kernels=["spice/test.bsp"])

    report = build_spice_observation_geometry_report(observation_path, cache_root)

    geometry = report["geometry"]
    assert report["ready"]
    assert fake_spice.furnished == [str(kernel_path)]
    assert fake_spice.cleared
    assert geometry["earth_moon_distance_m"] == pytest.approx(
        np.linalg.norm(np.array([384400.0, 0.0, 0.0]) - fake_spice.observer_itrf_km) * 1000.0
    )
    assert geometry["moon_angular_radius_deg"] > 0.0
    assert -90.0 <= geometry["sub_observer_latitude_deg"] <= 90.0
    assert -180.0 <= geometry["sub_solar_longitude_deg_east"] <= 180.0
    assert 0.0 <= geometry["illuminated_fraction"] <= 1.0


def test_cli_spice_observation_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_spice = FakeSpice()
    monkeypatch.setattr(
        "seeingbench.geometry.observation.importlib.import_module",
        lambda name: fake_spice if name == "spiceypy" else None,
    )
    cache_root = tmp_path / "cache"
    kernel_path = cache_root / "spice" / "test.bsp"
    kernel_path.parent.mkdir(parents=True)
    kernel_path.write_bytes(b"kernel")
    observation_path = _write_observation(tmp_path, kernels=["spice/test.bsp"])
    output_path = tmp_path / "geometry.json"

    assert (
        main(
            [
                "geometry",
                "spice-observation",
                "--observation",
                str(observation_path),
                "--cache-root",
                str(cache_root),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["ready"]
    assert report["geometry"]["reference_frame"] == "J2000"


def _write_observation(tmp_path: Path, kernels: list[str]) -> Path:
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps(
            {
                "target": "Moon",
                "utc_start": "2026-08-15T00:46:34Z",
                "observer": {
                    "latitude": 51.5,
                    "longitude": -0.1,
                    "altitude_m": 45.0,
                },
                "spice": {"kernels": kernels},
            }
        ),
        encoding="utf-8",
    )
    return observation_path


class FakeSpice:
    def __init__(self) -> None:
        self.furnished: list[str] = []
        self.cleared = False
        self.observer_itrf_km = np.zeros(3, dtype=np.float64)

    def furnsh(self, path: str) -> None:
        self.furnished.append(path)

    def kclear(self) -> None:
        self.cleared = True

    def utc2et(self, utc: str) -> float:
        assert utc == "2026-08-15T00:46:34Z"
        return 123.0

    def bodvrd(self, body: str, item: str, maxn: int) -> tuple[int, np.ndarray]:
        assert (body, item, maxn) == ("EARTH", "RADII", 3)
        return 3, np.array([6378.137, 6378.137, 6356.752314245], dtype=np.float64)

    def georec(
        self,
        lon_rad: float,
        lat_rad: float,
        altitude_km: float,
        equatorial_radius_km: float,
        flattening: float,
    ) -> np.ndarray:
        eccentricity_squared = 2.0 * flattening - flattening * flattening
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)
        normal = equatorial_radius_km / math.sqrt(1.0 - eccentricity_squared * sin_lat**2)
        self.observer_itrf_km = np.array(
            [
                (normal + altitude_km) * cos_lat * math.cos(lon_rad),
                (normal + altitude_km) * cos_lat * math.sin(lon_rad),
                (normal * (1.0 - eccentricity_squared) + altitude_km) * sin_lat,
            ],
            dtype=np.float64,
        )
        return self.observer_itrf_km

    def pxform(self, from_frame: str, to_frame: str, et: float) -> np.ndarray:
        assert et == 123.0
        assert (from_frame, to_frame) in {("ITRF93", "J2000"), ("J2000", "MOON_ME")}
        return np.eye(3, dtype=np.float64)

    def spkpos(
        self,
        target: str,
        et: float,
        reference_frame: str,
        aberration_correction: str,
        observer: str,
    ) -> tuple[np.ndarray, float]:
        assert et == 123.0
        assert reference_frame == "J2000"
        assert aberration_correction == "LT+S"
        if (target, observer) == ("MOON", "EARTH"):
            return np.array([384400.0, 0.0, 0.0], dtype=np.float64), 1.28
        if (target, observer) == ("SUN", "MOON"):
            return np.array([150000000.0, 0.0, 0.0], dtype=np.float64), 500.0
        raise AssertionError((target, observer))

    def reclat(self, vector: np.ndarray) -> tuple[float, float, float]:
        radius = float(np.linalg.norm(vector))
        lon_rad = math.atan2(float(vector[1]), float(vector[0]))
        lat_rad = math.asin(float(vector[2]) / radius)
        return radius, lon_rad, lat_rad
