from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import TracebackType
from urllib.request import Request

import pytest

from seeingbench.cli import main
from seeingbench.datasets.manifests import DatasetManifest
from seeingbench.datasets.readiness import (
    LunarROIConfig,
    build_roi_download_plan,
    build_roi_readiness_report,
    load_roi_config,
    resolve_manifest_cache_path,
    resolve_product_file_cache_path,
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
    manifests_by_role = {product.role: product.manifest for product in roi.required_products}
    assert set(manifests_by_role) == {
        "geometry",
        "reflectance",
        "terrain",
    }
    assert manifests_by_role["reflectance"] == "manifests/rois/copernicus_wac_emp_643nm.json"
    assert manifests_by_role["terrain"] == "manifests/rois/copernicus_wac_gld100.json"


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
        "incompatible_metadata_roles": [],
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


def test_roi_readiness_reports_file_level_product_status(tmp_path: Path) -> None:
    payload = b"tile bytes\n"
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest = _manifest_data(checksum=None)
    manifest["local_destination"] = "data/terrain"
    manifest["product_files"] = [
        {
            "name": "terrain tile",
            "url": "https://example.invalid/terrain/tile.img",
            "local_path": "data/terrain/tile.img",
            "checksum": checksum,
            "expected_size_bytes": len(payload),
            "label_local_path": "data/metadata/terrain.lbl",
            "purpose": "ROI terrain tile",
        },
        {
            "name": "terrain label",
            "url": "https://example.invalid/terrain/tile.lbl",
            "local_path": "data/terrain/tile.lbl",
            "checksum": "sha256:00",
            "expected_size_bytes": 12,
            "purpose": "PDS label",
        },
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    product_path = tmp_path / "cache" / "data" / "terrain" / "tile.img"
    product_path.parent.mkdir(parents=True)
    product_path.write_bytes(payload)
    label_path = tmp_path / "cache" / "data" / "metadata" / "terrain.lbl"
    label_path.parent.mkdir(parents=True)
    label_path.write_text(_compatible_label_text(), encoding="utf-8")

    report = build_roi_readiness_report(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    product = report["products"][0]
    assert not report["ready"]
    assert product["presence"] == "partial"
    assert product["path_type"] == "file_set"
    assert product["file_count"] == 2
    assert product["missing_file_count"] == 1
    assert product["checksum_status"] == "missing"
    assert product["label_metadata_status"] == "ok"
    assert product["files"][0]["checksum_status"] == "ok"
    assert product["files"][0]["size_status"] == "ok"
    assert product["files"][0]["label_metadata"]["coverage_status"] == "ok"
    assert product["files"][0]["label_metadata"]["resolution_status"] == "ok"
    assert product["files"][0]["label_metadata"]["roi_pixel_window"]["status"] == "ok"
    assert product["files"][0]["label_metadata"]["roi_pixel_window"]["row_count"] > 0
    assert product["files"][1]["presence"] == "missing"


def test_roi_readiness_blocks_incompatible_label_metadata(tmp_path: Path) -> None:
    payload = b"tile bytes\n"
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest = _manifest_data(checksum=None)
    manifest["product_files"] = [
        {
            "name": "terrain tile",
            "url": "https://example.invalid/terrain/tile.img",
            "local_path": "data/terrain.bin",
            "checksum": checksum,
            "label_local_path": "data/metadata/terrain.lbl",
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    product_path = tmp_path / "cache" / "data" / "terrain.bin"
    product_path.parent.mkdir(parents=True)
    product_path.write_bytes(payload)
    label_path = tmp_path / "cache" / "data" / "metadata" / "terrain.lbl"
    label_path.parent.mkdir(parents=True)
    label_path.write_text(
        _compatible_label_text().replace("MAP_SCALE = 99.75", "MAP_SCALE = 250.0"),
        encoding="utf-8",
    )

    report = build_roi_readiness_report(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    assert not report["ready"]
    assert report["blocking_reasons"]["incompatible_metadata_roles"] == ["terrain"]
    assert report["products"][0]["label_metadata_status"] == "incompatible"
    assert report["products"][0]["files"][0]["label_metadata"]["resolution_status"] == (
        "coarser_than_target"
    )


def test_resolve_manifest_cache_path_uses_cache_root() -> None:
    manifest = _manifest_data(checksum=None)
    resolved = resolve_manifest_cache_path(
        manifest=_import_manifest(manifest),
        cache_root=Path("cache-root"),
    )

    assert resolved == Path("cache-root") / "data" / "terrain.bin"


def test_resolve_product_file_cache_path_uses_cache_root() -> None:
    product = DatasetManifest.from_dict(
        {
            **_manifest_data(checksum=None),
            "product_files": [
                {
                    "name": "tile",
                    "url": "https://example.invalid/tile.img",
                    "local_path": "data/tiles/tile.img",
                    "checksum": None,
                }
            ],
        }
    ).product_files[0]

    assert resolve_product_file_cache_path(product, Path("cache-root")) == (
        Path("cache-root") / "data" / "tiles" / "tile.img"
    )


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
    products_by_role = {product["role"]: product for product in report["products"]}
    assert products_by_role["reflectance"]["file_count"] == 2
    assert products_by_role["terrain"]["file_count"] == 2
    assert products_by_role["geometry"]["file_count"] == 0
    assert products_by_role["reflectance"]["label_metadata_status"] == "missing"
    assert products_by_role["terrain"]["label_metadata_status"] == "missing"


def test_cli_fetch_labels_writes_declared_product_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = _manifest_data(checksum=None)
    manifest["product_files"] = [
        {
            "name": "tile",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/tile.img",
            "checksum": None,
            "label_url": "https://example.invalid/tile.lbl",
            "label_local_path": "data/metadata/tile.lbl",
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class Response:
        def __init__(self) -> None:
            self.headers = {"Content-Type": "text/plain", "Content-Length": "10"}

        def __enter__(self) -> Response:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"MAP_SCALE\n"

    def fake_urlopen(request: Request, timeout: int) -> Response:
        return Response()

    monkeypatch.setattr("seeingbench.datasets.manifests.urllib.request.urlopen", fake_urlopen)

    assert (
        main(
            [
                "datasets",
                "fetch-labels",
                str(manifest_path),
                "--output-root",
                str(tmp_path / "cache"),
            ]
        )
        == 0
    )
    assert (tmp_path / "cache" / "data" / "metadata" / "tile.lbl").read_text(
        encoding="utf-8"
    ) == "MAP_SCALE\n"


def test_roi_download_plan_lists_declared_products_without_downloading(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi.json"
    roi_path.write_text(json.dumps(_valid_roi_data()), encoding="utf-8")
    manifest_path = tmp_path / "manifests" / "terrain.json"
    manifest_path.parent.mkdir()
    manifest = _manifest_data(checksum=None)
    manifest["product_files"] = [
        {
            "name": "tile",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/tile.img",
            "checksum": None,
            "label_url": "https://example.invalid/tile.xml",
            "label_local_path": "data/metadata/tile.xml",
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    plan = build_roi_download_plan(
        roi_path,
        cache_root=tmp_path / "cache",
        manifest_root=tmp_path,
    )

    assert plan["downloads_are_not_started"]
    assert plan["bulk_product_count"] == 1
    assert plan["label_count"] == 1
    assert plan["bulk_products"][0]["local_path"] == str(tmp_path / "cache" / "data" / "tile.img")
    assert plan["labels"][0]["local_path"] == str(
        tmp_path / "cache" / "data" / "metadata" / "tile.xml"
    )
    assert not (tmp_path / "cache" / "data" / "tile.img").exists()


def test_cli_writes_roi_download_plan(tmp_path: Path) -> None:
    output_path = tmp_path / "download-plan.json"

    assert (
        main(
            [
                "datasets",
                "roi-download-plan",
                "--roi",
                "configs/rois/copernicus-100m.json",
                "--cache-root",
                str(tmp_path / "cache"),
                "--manifest-root",
                ".",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["downloads_are_not_started"]
    assert plan["bulk_product_count"] == 4
    assert plan["label_count"] == 2


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


def _compatible_label_text() -> str:
    return """
    MAP_PROJECTION_TYPE = "EQUIRECTANGULAR"
    MINIMUM_LATITUDE = 0.0
    MAXIMUM_LATITUDE = 60.0
    WESTERNMOST_LONGITUDE = 270.0
    EASTERNMOST_LONGITUDE = 360.0
    MAP_SCALE = 99.75 <METERS/PIXEL>
    MAP_RESOLUTION = 304.0 <PIXELS/DEGREE>
    LINES = 18240
    LINE_SAMPLES = 27360
    SAMPLE_TYPE = LSB_INTEGER
    SAMPLE_BITS = 16
    END
    """
