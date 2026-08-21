from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import TracebackType
from urllib.request import Request

import pytest

from seeingbench.datasets.manifests import (
    DatasetManifest,
    MetadataDocument,
    ProductFile,
    fetch_manifest_metadata,
    fetch_manifest_product_files,
    fetch_manifest_product_labels,
    validate_manifest_files,
)


def test_dataset_manifest_rejects_absolute_destination() -> None:
    data = {
        "name": "Example",
        "source": "https://example.invalid/data",
        "version": "1",
        "expected_size": "1 MB",
        "checksum": None,
        "local_destination": "C:/unsafe",
        "license": "public domain",
        "provenance": "example",
        "resolution": "100 m/pixel",
        "coordinate_system": "example coordinates",
    }

    with pytest.raises(ValueError, match="repository-relative"):
        DatasetManifest.from_dict(data)


def test_dataset_manifest_accepts_relative_destination() -> None:
    manifest = DatasetManifest.from_dict(
        {
            "name": "Example",
            "source": "https://example.invalid/data",
            "version": "1",
            "expected_size": "1 MB",
            "checksum": None,
            "local_destination": "data/example",
            "license": "public domain",
            "provenance": "example",
            "resolution": "100 m/pixel",
            "coordinate_system": "example coordinates",
        }
    )

    assert manifest.local_destination == "data/example"


def test_dataset_manifest_rejects_non_http_source() -> None:
    data = _valid_manifest_data()
    data["source"] = "ftp://example.invalid/data"

    with pytest.raises(ValueError, match="HTTP"):
        DatasetManifest.from_dict(data)


def test_metadata_document_rejects_large_limit() -> None:
    with pytest.raises(ValueError, match="expected_max_bytes"):
        MetadataDocument.from_dict(
            {
                "name": "too large",
                "url": "https://example.invalid/meta.txt",
                "local_path": "data/metadata/meta.txt",
                "expected_max_bytes": 2_000_000,
            }
        )


def test_product_file_rejects_unsafe_local_path() -> None:
    with pytest.raises(ValueError, match="must not escape"):
        ProductFile.from_dict(
            {
                "name": "unsafe",
                "url": "https://example.invalid/product.img",
                "local_path": "../data/product.img",
                "checksum": "sha256:abcd",
            }
        )


def test_dataset_manifest_accepts_product_files() -> None:
    data = _valid_manifest_data()
    data["checksum"] = None
    data["product_files"] = [
        {
            "name": "tile",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/example/tile.img",
            "checksum": "sha256:abcd",
            "expected_size_bytes": 4,
            "label_url": "https://example.invalid/tile.lbl",
            "label_local_path": "data/metadata/example/tile.lbl",
            "purpose": "test tile",
        }
    ]

    manifest = DatasetManifest.from_dict(data)

    assert manifest.product_files[0].name == "tile"
    assert manifest.product_files[0].checksum == "sha256:abcd"
    assert manifest.product_files[0].label_url == "https://example.invalid/tile.lbl"
    assert manifest.product_files[0].label_local_path == "data/metadata/example/tile.lbl"
    assert manifest.to_dict()["product_files"][0]["expected_size_bytes"] == 4


def test_dataset_manifest_rejects_malformed_checksum() -> None:
    data = _valid_manifest_data()
    data["checksum"] = "sha512:abcd"

    with pytest.raises(ValueError, match="unsupported checksum"):
        DatasetManifest.from_dict(data)


def test_validate_manifest_files_reports_candidate_status(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_valid_manifest_data()), encoding="utf-8")

    reports = validate_manifest_files([manifest_path])

    assert reports == [
        {
            "path": str(manifest_path),
            "valid": True,
            "name": "Example",
            "source": "https://example.invalid/data",
            "metadata_document_count": 0,
            "product_file_count": 0,
            "status": "candidate",
        }
    ]


def test_fetch_manifest_metadata_writes_only_declared_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _valid_manifest_data()
    manifest["metadata_documents"] = [
        {
            "name": "readme",
            "url": "https://example.invalid/readme.txt",
            "local_path": "data/metadata/readme.txt",
            "expected_max_bytes": 100,
        }
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class Response:
        def __init__(self) -> None:
            self.headers = {"Content-Type": "text/plain", "Content-Length": "12"}

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
            return b"hello world\n"

    def fake_urlopen(request: Request, timeout: int) -> Response:
        return Response()

    monkeypatch.setattr("seeingbench.datasets.manifests.urllib.request.urlopen", fake_urlopen)

    written = fetch_manifest_metadata(manifest_path, tmp_path / "cache")

    assert written == [tmp_path / "cache" / "data" / "metadata" / "readme.txt"]
    assert written[0].read_text(encoding="utf-8") == "hello world\n"


def test_fetch_manifest_product_labels_writes_declared_labels_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _valid_manifest_data()
    manifest["product_files"] = [
        {
            "name": "tile img",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/tile.img",
            "checksum": None,
            "label_url": "https://example.invalid/tile.lbl",
            "label_local_path": "data/metadata/tile.lbl",
        },
        {
            "name": "tile tif",
            "url": "https://example.invalid/tile.tif",
            "local_path": "data/tile.tif",
            "checksum": None,
            "label_url": "https://example.invalid/tile.lbl",
            "label_local_path": "data/metadata/tile.lbl",
        },
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    requests: list[str] = []

    class Response:
        def __init__(self) -> None:
            self.headers = {"Content-Type": "application/octet-stream", "Content-Length": "12"}

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
            return b"PDS_VERSION\n"

    def fake_urlopen(request: Request, timeout: int) -> Response:
        requests.append(request.full_url)
        return Response()

    monkeypatch.setattr("seeingbench.datasets.manifests.urllib.request.urlopen", fake_urlopen)

    written = fetch_manifest_product_labels(manifest_path, tmp_path / "cache")

    assert written == [tmp_path / "cache" / "data" / "metadata" / "tile.lbl"]
    assert written[0].read_text(encoding="utf-8") == "PDS_VERSION\n"
    assert requests == ["https://example.invalid/tile.lbl"]


def test_fetch_manifest_product_files_requires_explicit_budget(tmp_path: Path) -> None:
    manifest = _valid_manifest_data()
    manifest["product_files"] = [
        {
            "name": "tile img",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/tile.img",
            "checksum": None,
            "expected_size_bytes": 12,
        }
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="exceeds max_total_bytes"):
        fetch_manifest_product_files(
            manifest_path,
            tmp_path / "cache",
            max_total_bytes=11,
        )


def test_fetch_manifest_product_files_streams_and_verifies_products(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"product-data"
    checksum = hashlib.sha256(payload).hexdigest()
    manifest = _valid_manifest_data()
    manifest["product_files"] = [
        {
            "name": "tile img",
            "url": "https://example.invalid/tile.img",
            "local_path": "data/tile.img",
            "checksum": f"sha256:{checksum}",
            "expected_size_bytes": len(payload),
        }
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    requests: list[str] = []

    class Response:
        def __init__(self) -> None:
            self.headers = {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(payload)),
            }
            self._remaining = payload

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
            chunk = self._remaining[:size]
            self._remaining = self._remaining[size:]
            return chunk

    def fake_urlopen(request: Request, timeout: int) -> Response:
        requests.append(request.full_url)
        return Response()

    monkeypatch.setattr("seeingbench.datasets.manifests.urllib.request.urlopen", fake_urlopen)

    written = fetch_manifest_product_files(
        manifest_path,
        tmp_path / "cache",
        max_total_bytes=100,
    )

    assert written == [tmp_path / "cache" / "data" / "tile.img"]
    assert written[0].read_bytes() == payload
    assert not (tmp_path / "cache" / "data" / "tile.img.part").exists()
    assert requests == ["https://example.invalid/tile.img"]


def _valid_manifest_data() -> dict[str, object]:
    return {
        "name": "Example",
        "source": "https://example.invalid/data",
        "version": "TBD",
        "expected_size": "1 MB",
        "checksum": None,
        "local_destination": "data/example",
        "license": "TBD",
        "provenance": "example",
        "resolution": "100 m/pixel",
        "coordinate_system": "example coordinates",
    }
