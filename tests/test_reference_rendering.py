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
