from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from test_spice_observation_geometry import FakeSpice

from seeingbench.cli import main
from seeingbench.rendering.reference import render_telescope_matched_reference


def test_render_telescope_matched_reference_applies_diffraction_blur(
    tmp_path: Path,
) -> None:
    source = np.zeros((65, 65), dtype=np.float64)
    source[32, 32] = 1.0
    source_path = tmp_path / "surface.npy"
    np.save(source_path, source)
    surface_report = _write_surface_report(tmp_path, source_path)
    observation = _write_observation(tmp_path)

    report = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "telescope",
        role="reflectance",
    )

    output = np.load(Path(report["references"][0]["output"]))
    assert report["reference_count"] == 1
    assert output.shape == source.shape
    assert output[32, 32] < 1.0
    assert output[32, 32] > output[32, 33]
    assert report["references"][0]["diffraction_sigma_reference_px"] > 0.0
    assert report["references"][0]["label_provenance"]["logical_identifier"] == (
        "urn:nasa:pds:surface"
    )
    assert "not_spice_backed" in report["limitations"]


def test_render_telescope_matched_reference_blocks_missing_telescope_metadata(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "surface.npy"
    np.save(source_path, np.ones((8, 8), dtype=np.float64))
    surface_report = _write_surface_report(tmp_path, source_path)
    observation = tmp_path / "observation.json"
    observation.write_text(
        json.dumps(
            {
                "target": "Moon",
                "telescope": {"aperture_mm": 200.0},
                "camera": {},
                "filter": {"effective_wavelength_nm": 550.0},
            }
        ),
        encoding="utf-8",
    )

    report = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "telescope",
        role="reflectance",
    )

    assert report["reference_count"] == 0
    assert "missing_telescope.focal_length_mm" in report["blocking_reasons"]
    assert "missing_camera.pixel_size_um" in report["blocking_reasons"]
    assert (tmp_path / "telescope" / "telescope-reference-report.json").exists()


def test_render_telescope_matched_reference_uses_spice_geometry_distance(
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
    source = np.zeros((65, 65), dtype=np.float64)
    source[32, 32] = 1.0
    source_path = tmp_path / "surface.npy"
    np.save(source_path, source)
    surface_report = _write_surface_report(tmp_path, source_path)
    observation = _write_spice_observation(tmp_path)

    report = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "telescope",
        role="reflectance",
        spice_cache_root=cache_root,
    )

    reference = report["references"][0]
    assert report["reference_count"] == 1
    assert "not_spice_backed" not in report["limitations"]
    assert report["spice_geometry_report"]["ready"]
    assert reference["spice_geometry"]["reference_frame"] == "J2000"
    assert (
        reference["earth_moon_distance_m"] == reference["spice_geometry"]["earth_moon_distance_m"]
    )


def test_render_telescope_matched_reference_can_apply_terrain_illumination(
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
    reflectance = np.ones((65, 65), dtype=np.float64)
    terrain = np.tile(np.arange(65, dtype=np.float64), (65, 1)) * 100.0
    reflectance_path = tmp_path / "reflectance.npy"
    terrain_path = tmp_path / "terrain.npy"
    np.save(reflectance_path, reflectance)
    np.save(terrain_path, terrain)
    surface_report = _write_surface_report_with_terrain(
        tmp_path,
        reflectance_path,
        terrain_path,
    )
    observation = _write_spice_observation(tmp_path)

    report = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "telescope",
        role="reflectance",
        spice_cache_root=cache_root,
        apply_illumination=True,
    )

    output = np.load(Path(report["references"][0]["output"]))
    illumination = report["references"][0]["illumination"]
    assert illumination["applied"]
    assert illumination["shading_mean"] == pytest.approx(2.0**-0.5)
    assert float(np.mean(output)) < 1.0
    assert "simple_lambertian_illumination_model" in report["limitations"]
    assert "no_illumination_model" not in report["limitations"]


def test_render_telescope_matched_reference_can_apply_earth_view_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "seeingbench.rendering.reference.build_spice_observation_geometry_report",
        lambda observation_path, cache_root: _spice_geometry_report(sub_observer_lon=60.0),
    )
    source = np.tile(np.arange(65, dtype=np.float64), (65, 1)) / 64.0
    source_path = tmp_path / "reflectance.npy"
    np.save(source_path, source)
    surface_report = _write_surface_report_with_roi(tmp_path, source_path)
    observation = _write_observation(tmp_path)

    unprojected = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "unprojected",
        role="reflectance",
        spice_cache_root=tmp_path,
    )
    projected = render_telescope_matched_reference(
        surface_report,
        observation,
        tmp_path / "projected",
        role="reflectance",
        spice_cache_root=tmp_path,
        apply_earth_view_projection=True,
    )

    unprojected_output = np.load(Path(unprojected["references"][0]["output"]))
    projected_output = np.load(Path(projected["references"][0]["output"]))
    projection = projected["references"][0]["earth_view_projection"]
    assert projection["applied"]
    assert projection["incidence_cosine"] == pytest.approx(0.5)
    assert not np.allclose(projected_output, unprojected_output)
    assert "local_linear_orthographic_projection" in projected["limitations"]
    assert "not_earth_view_projected" not in projected["limitations"]


def test_cli_telescope_reference_returns_nonzero_when_metadata_is_incomplete(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "surface.npy"
    np.save(source_path, np.ones((8, 8), dtype=np.float64))
    surface_report = _write_surface_report(tmp_path, source_path)
    observation = tmp_path / "observation.json"
    observation.write_text(json.dumps({"target": "Moon"}), encoding="utf-8")

    assert (
        main(
            [
                "render",
                "telescope-reference",
                "--surface-reference-report",
                str(surface_report),
                "--observation",
                str(observation),
                "--output-root",
                str(tmp_path / "telescope"),
                "--role",
                "reflectance",
            ]
        )
        == 1
    )


def _write_surface_report(tmp_path: Path, source_path: Path) -> Path:
    report_path = tmp_path / "surface-reference-report.json"
    report_path.write_text(
        json.dumps(
            {
                "target_resolution_m_per_px": 100.0,
                "references": [
                    {
                        "role": "reflectance",
                        "output": str(source_path),
                        "shape": [65, 65],
                        "dtype": "float64",
                        "label_provenance": {
                            "logical_identifier": "urn:nasa:pds:surface",
                            "title": "Surface Reference",
                        },
                        "label_summary": {"map_scale_m_per_px": 100.0},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return report_path


def _write_surface_report_with_terrain(
    tmp_path: Path,
    reflectance_path: Path,
    terrain_path: Path,
) -> Path:
    report_path = tmp_path / "surface-reference-report.json"
    report_path.write_text(
        json.dumps(
            {
                "roi": {
                    "center_lat_deg": 0.0,
                    "center_lon_deg": 0.0,
                },
                "target_resolution_m_per_px": 100.0,
                "references": [
                    {
                        "role": "reflectance",
                        "output": str(reflectance_path),
                        "shape": [65, 65],
                        "dtype": "float64",
                        "label_provenance": {"logical_identifier": "urn:nasa:pds:reflectance"},
                        "label_summary": {"map_scale_m_per_px": 100.0},
                    },
                    {
                        "role": "terrain",
                        "output": str(terrain_path),
                        "shape": [65, 65],
                        "dtype": "float64",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return report_path


def _write_surface_report_with_roi(tmp_path: Path, source_path: Path) -> Path:
    report_path = tmp_path / "surface-reference-report.json"
    report_path.write_text(
        json.dumps(
            {
                "roi": {
                    "center_lat_deg": 0.0,
                    "center_lon_deg": 0.0,
                },
                "target_resolution_m_per_px": 100.0,
                "references": [
                    {
                        "role": "reflectance",
                        "output": str(source_path),
                        "shape": [65, 65],
                        "dtype": "float64",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return report_path


def _write_observation(tmp_path: Path) -> Path:
    observation = tmp_path / "observation.json"
    observation.write_text(
        json.dumps(
            {
                "target": "Moon",
                "utc_start": "2026-08-15T00:46:34Z",
                "telescope": {
                    "aperture_mm": 200.0,
                    "focal_length_mm": 4000.0,
                    "central_obstruction": 0.0,
                },
                "camera": {
                    "pixel_size_um": 2.9,
                    "width": 1920,
                    "height": 1080,
                },
                "filter": {
                    "name": "green",
                    "effective_wavelength_nm": 550.0,
                },
            }
        ),
        encoding="utf-8",
    )
    return observation


def _write_spice_observation(tmp_path: Path) -> Path:
    observation = tmp_path / "observation-spice.json"
    observation.write_text(
        json.dumps(
            {
                "target": "Moon",
                "utc_start": "2026-08-15T00:46:34Z",
                "earth_moon_distance_m": 1.0,
                "observer": {
                    "latitude": 51.5,
                    "longitude": -0.1,
                    "altitude_m": 45.0,
                },
                "spice": {"kernels": ["spice/test.bsp"]},
                "telescope": {
                    "aperture_mm": 200.0,
                    "focal_length_mm": 4000.0,
                    "central_obstruction": 0.0,
                },
                "camera": {
                    "pixel_size_um": 2.9,
                    "width": 1920,
                    "height": 1080,
                },
                "filter": {
                    "name": "green",
                    "effective_wavelength_nm": 550.0,
                },
            }
        ),
        encoding="utf-8",
    )
    return observation


def _spice_geometry_report(sub_observer_lon: float) -> dict[str, object]:
    geometry = {
        "utc_start": "2026-08-15T00:46:34Z",
        "reference_frame": "J2000",
        "earth_moon_distance_m": 384400000.0,
        "sub_observer_latitude_deg": 0.0,
        "sub_observer_longitude_deg_east": sub_observer_lon,
        "sub_solar_latitude_deg": 0.0,
        "sub_solar_longitude_deg_east": 0.0,
    }
    return {
        "ready": True,
        "blocking_reasons": [],
        "geometry": geometry,
    }
