from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from seeingbench.cli import main
from seeingbench.datasets.manifests import DatasetManifest
from seeingbench.datasets.readiness import (
    LunarROIConfig,
    build_roi_readiness_report,
    load_roi_config,
    resolve_manifest_cache_path,
)


def test_roi_config_rejects_unsafe_manifest_path() -> None:
    data = _valid_roi_data()
    data["required_products"] = [
        {
            "role": "terrain",
            "manifest": "../outside.json",
        }
    ]

    with pytest.raises(ValueError, match="must not escape"):
        LunarROIConfig.from_dict(data)


def test_sample_copernicus_roi_loads_manifest_roles() -> None:
    roi = load_roi_config(Path("configs/rois/copernicus-100m.json"))

    assert roi.name == "copernicus-100m-reference"
    assert {product.role for product in roi.required_products} == {
        "geometry",
        "reflectance",
        "terrain",
    }


def test_roi_readiness_reports_missing_candidate_products(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(_manifest_data(checksum=None)), encoding="utf-8")

    report = build_roi_readiness_report(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    assert not report["ready"]
    assert report["blocking_reasons"] == {
        "missing_required_roles": ["terrain"],
        "checksum_mismatch_roles": [],
        "unresolved_checksum_roles": ["terrain"],
    }
    assert report["products"][0]["presence"] == "missing"
    assert report["products"][0]["checksum_status"] == "not_declared"


def test_roi_readiness_verifies_present_file_checksum(tmp_path: Path) -> None:
    payload = b"local product bytes\n"
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(_manifest_data(checksum=checksum)), encoding="utf-8")
    product_path = tmp_path / "cache" / "data" / "terrain.bin"
    product_path.parent.mkdir(parents=True)
    product_path.write_bytes(payload)

    report = build_roi_readiness_report(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    assert report["ready"]
    assert report["products"][0]["local_path"] == str(product_path)
    assert report["products"][0]["presence"] == "present"
    assert report["products"][0]["path_type"] == "file"
    assert report["products"][0]["size_bytes"] == len(payload)
    assert report["products"][0]["checksum_status"] == "ok"


def test_roi_readiness_blocks_checksum_mismatch(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(_manifest_data(checksum="sha256:00")), encoding="utf-8")
    product_path = tmp_path / "cache" / "data" / "terrain.bin"
    product_path.parent.mkdir(parents=True)
    product_path.write_bytes(b"different bytes\n")

    report = build_roi_readiness_report(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    assert not report["ready"]
    assert report["blocking_reasons"]["checksum_mismatch_roles"] == ["terrain"]
    assert report["products"][0]["checksum_status"] == "mismatch"


def test_resolve_manifest_cache_path_uses_cache_root() -> None:
    manifest = _manifest_data(checksum=None)
    resolved = resolve_manifest_cache_path(
        manifest=_import_manifest(manifest),
        cache_root=Path("cache-root"),
    )

    assert resolved == Path("cache-root") / "data" / "terrain.bin"


def test_cli_writes_roi_readiness_report_and_returns_not_ready(tmp_path: Path) -> None:
    output_path = tmp_path / "readiness.json"

    exit_code = main(
        [
            "datasets",
            "roi-readiness",
            "--roi",
            "configs/rois/copernicus-100m.json",
            "--cache-root",
            str(tmp_path / "empty-cache"),
            "--manifest-root",
            ".",
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["roi"]["name"] == "copernicus-100m-reference"
    assert not report["ready"]
    assert set(report["blocking_reasons"]["missing_required_roles"]) == {
        "geometry",
        "reflectance",
        "terrain",
    }


def _valid_roi_data() -> dict[str, object]:
    return {
        "name": "test-roi",
        "center_lat_deg": 0.0,
        "center_lon_deg": 0.0,
        "width_km": 10.0,
        "height_km": 10.0,
        "target_resolution_m_per_px": 100.0,
        "required_products": [
            {
                "role": "terrain",
                "manifest": "manifests/terrain.json",
            }
        ],
    }


def _manifest_data(checksum: str | None) -> dict[str, object]:
    return {
        "name": "Terrain",
        "source": "https://example.invalid/terrain.bin",
        "version": "1",
        "expected_size": "20 bytes",
        "checksum": checksum,
        "local_destination": "data/terrain.bin",
        "license": "public domain",
        "provenance": "test",
        "resolution": "100 m/pixel",
        "coordinate_system": "test coordinates",
    }


def _import_manifest(data: dict[str, object]) -> DatasetManifest:
    return DatasetManifest.from_dict(data)
