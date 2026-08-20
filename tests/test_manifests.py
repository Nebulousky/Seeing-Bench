from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from urllib.request import Request

import pytest

from seeingbench.datasets.manifests import (
    DatasetManifest,
    MetadataDocument,
    fetch_manifest_metadata,
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
