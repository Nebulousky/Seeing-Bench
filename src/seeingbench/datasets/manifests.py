"""Dataset manifest model for future orbital-data integration."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlparse

MAX_METADATA_BYTES = 1_000_000
TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/x-pds-label",
)
TEXT_METADATA_SUFFIXES = (
    ".asc",
    ".csv",
    ".htm",
    ".html",
    ".json",
    ".lbl",
    ".tab",
    ".txt",
    ".xml",
)
SUPPORTED_CHECKSUMS = ("sha256", "sha1", "md5")


@dataclass(frozen=True)
class MetadataDocument:
    """Small metadata/index document that may be fetched without bulk data."""

    name: str
    url: str
    local_path: str
    expected_max_bytes: int = MAX_METADATA_BYTES
    purpose: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetadataDocument:
        required = {"name", "url", "local_path"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(
                f"metadata document is missing required field(s): {', '.join(missing)}"
            )
        document = cls(
            name=str(data["name"]),
            url=str(data["url"]),
            local_path=str(data["local_path"]),
            expected_max_bytes=int(data.get("expected_max_bytes", MAX_METADATA_BYTES)),
            purpose=str(data.get("purpose", "")),
        )
        document.validate()
        return document

    def validate(self) -> None:
        if not self.name:
            raise ValueError("metadata document name must be non-empty")
        _validate_http_url(self.url, "metadata document url")
        if self.expected_max_bytes <= 0 or self.expected_max_bytes > MAX_METADATA_BYTES:
            raise ValueError(
                f"metadata document expected_max_bytes must be in (0, {MAX_METADATA_BYTES}]"
            )
        _validate_relative_path(self.local_path, "metadata document local_path")


@dataclass(frozen=True)
class ProductFile:
    """Specific bulk product expected in the local cache, but not fetched automatically."""

    name: str
    url: str
    local_path: str
    checksum: str | None
    expected_size_bytes: int | None = None
    label_url: str | None = None
    label_local_path: str | None = None
    purpose: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductFile:
        required = {"name", "url", "local_path"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"product file is missing required field(s): {', '.join(missing)}")
        product = cls(
            name=str(data["name"]),
            url=str(data["url"]),
            local_path=str(data["local_path"]),
            checksum=None if data.get("checksum") is None else str(data["checksum"]),
            expected_size_bytes=None
            if data.get("expected_size_bytes") is None
            else int(data["expected_size_bytes"]),
            label_url=None if data.get("label_url") is None else str(data["label_url"]),
            label_local_path=None
            if data.get("label_local_path") is None
            else str(data["label_local_path"]),
            purpose=str(data.get("purpose", "")),
        )
        product.validate()
        return product

    def validate(self) -> None:
        if not self.name:
            raise ValueError("product file name must be non-empty")
        _validate_http_url(self.url, "product file url")
        _validate_relative_path(self.local_path, "product file local_path")
        if self.label_url is not None:
            _validate_http_url(self.label_url, "product file label_url")
        if self.label_local_path is not None:
            _validate_relative_path(self.label_local_path, "product file label_local_path")
        if self.checksum is not None:
            _validate_checksum(self.checksum)
        if self.expected_size_bytes is not None and self.expected_size_bytes <= 0:
            raise ValueError("product file expected_size_bytes must be positive")


@dataclass(frozen=True)
class DatasetManifest:
    """Metadata needed to acquire and verify a dataset without committing it."""

    name: str
    source: str
    version: str
    expected_size: str
    checksum: str | None
    local_destination: str
    license: str
    provenance: str
    resolution: str
    coordinate_system: str
    notes: str = ""
    metadata_documents: tuple[MetadataDocument, ...] = field(default_factory=tuple)
    product_files: tuple[ProductFile, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        required = {
            "name",
            "source",
            "version",
            "expected_size",
            "local_destination",
            "license",
            "provenance",
            "resolution",
            "coordinate_system",
        }
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"manifest is missing required field(s): {', '.join(missing)}")
        document_data = data.get("metadata_documents", [])
        if not isinstance(document_data, list):
            raise ValueError("metadata_documents must be a list")
        product_data = data.get("product_files", [])
        if not isinstance(product_data, list):
            raise ValueError("product_files must be a list")
        manifest = cls(
            name=str(data["name"]),
            source=str(data["source"]),
            version=str(data["version"]),
            expected_size=str(data["expected_size"]),
            checksum=None if data.get("checksum") is None else str(data["checksum"]),
            local_destination=str(data["local_destination"]),
            license=str(data["license"]),
            provenance=str(data["provenance"]),
            resolution=str(data["resolution"]),
            coordinate_system=str(data["coordinate_system"]),
            notes=str(data.get("notes", "")),
            metadata_documents=tuple(MetadataDocument.from_dict(item) for item in document_data),
            product_files=tuple(_product_file(item) for item in product_data),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        values = {
            "name": self.name,
            "source": self.source,
            "version": self.version,
            "expected_size": self.expected_size,
            "local_destination": self.local_destination,
            "license": self.license,
            "provenance": self.provenance,
            "resolution": self.resolution,
            "coordinate_system": self.coordinate_system,
        }
        empty = sorted(name for name, value in values.items() if not value)
        if empty:
            raise ValueError(f"manifest field(s) must be non-empty: {', '.join(empty)}")
        _validate_http_url(self.source, "source")
        _validate_relative_path(self.local_destination, "local_destination")
        if self.checksum is not None:
            _validate_checksum(self.checksum)
        for document in self.metadata_documents:
            document.validate()
        for product in self.product_files:
            product.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "version": self.version,
            "expected_size": self.expected_size,
            "checksum": self.checksum,
            "local_destination": self.local_destination,
            "license": self.license,
            "provenance": self.provenance,
            "resolution": self.resolution,
            "coordinate_system": self.coordinate_system,
            "notes": self.notes,
            "metadata_documents": [
                {
                    "name": document.name,
                    "url": document.url,
                    "local_path": document.local_path,
                    "expected_max_bytes": document.expected_max_bytes,
                    "purpose": document.purpose,
                }
                for document in self.metadata_documents
            ],
            "product_files": [
                {
                    "name": product.name,
                    "url": product.url,
                    "local_path": product.local_path,
                    "checksum": product.checksum,
                    "expected_size_bytes": product.expected_size_bytes,
                    "label_url": product.label_url,
                    "label_local_path": product.label_local_path,
                    "purpose": product.purpose,
                }
                for product in self.product_files
            ],
        }


def _product_file(value: Any) -> ProductFile:
    if not isinstance(value, dict):
        raise ValueError("each product_files entry must be a JSON object")
    return ProductFile.from_dict(value)


def load_manifest(path: Path) -> DatasetManifest:
    """Load and validate a dataset manifest JSON file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dataset manifest must be a JSON object")
    return DatasetManifest.from_dict(data)


def validate_manifest_files(paths: list[Path]) -> list[dict[str, Any]]:
    """Validate manifests and return serialisable reports."""

    return [_validate_one(path) for path in paths]


def fetch_manifest_metadata(manifest_path: Path, output_root: Path) -> list[Path]:
    """Fetch only the small metadata documents listed by a manifest."""

    manifest = load_manifest(manifest_path)
    written: list[Path] = []
    for document in manifest.metadata_documents:
        destination = output_root / document.local_path
        _fetch_text_document(document, destination)
        written.append(destination)
    return written


def fetch_manifest_product_labels(manifest_path: Path, output_root: Path) -> list[Path]:
    """Fetch only small product labels explicitly declared by product file records."""

    manifest = load_manifest(manifest_path)
    written: list[Path] = []
    seen_destinations: set[Path] = set()
    for product in manifest.product_files:
        if product.label_url is None or product.label_local_path is None:
            continue
        destination = output_root / product.label_local_path
        if destination in seen_destinations:
            continue
        _fetch_text_url(
            product.label_url,
            destination,
            max_bytes=MAX_METADATA_BYTES,
            description="product label",
        )
        seen_destinations.add(destination)
        written.append(destination)
    return written


def _validate_one(path: Path) -> dict[str, Any]:
    try:
        manifest = load_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"path": str(path), "valid": False, "error": str(exc)}
    return {
        "path": str(path),
        "valid": True,
        "name": manifest.name,
        "source": manifest.source,
        "metadata_document_count": len(manifest.metadata_documents),
        "product_file_count": len(manifest.product_files),
        "status": _verification_status(manifest),
    }


def _verification_status(manifest: DatasetManifest) -> str:
    has_checksums = manifest.checksum is not None or (
        bool(manifest.product_files)
        and all(product.checksum is not None for product in manifest.product_files)
    )
    if has_checksums and "TBD" not in manifest.version and "TBD" not in manifest.license:
        return "verified"
    return "candidate"


def _fetch_text_document(document: MetadataDocument, destination: Path) -> None:
    _fetch_text_url(
        document.url,
        destination,
        max_bytes=document.expected_max_bytes,
        description="metadata document",
    )


def _fetch_text_url(
    url: str,
    destination: Path,
    max_bytes: int,
    description: str,
) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "SeeingBench/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) > max_bytes:
            raise ValueError(f"{url} exceeds {description} size limit")
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not _is_text_metadata_response(content_type, url):
            raise ValueError(f"{url} is not a text {description}: {content_type}")
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"{url} exceeds {description} size limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def _is_text_metadata_response(content_type: str, url: str) -> bool:
    if content_type.startswith(TEXT_CONTENT_TYPES):
        return True
    return urlparse(url).path.lower().endswith(TEXT_METADATA_SUFFIXES)


def _validate_http_url(url: str, field_name: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")


def _validate_relative_path(path: str, field_name: str) -> None:
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute():
        raise ValueError(f"{field_name} must be repository-relative")
    destination = Path(path)
    if ".." in destination.parts:
        raise ValueError(f"{field_name} must not escape the repository")


def _validate_checksum(value: str) -> None:
    if ":" not in value:
        raise ValueError("checksum must use '<algorithm>:<hex>' format")
    algorithm, checksum = value.split(":", 1)
    if algorithm.lower() not in SUPPORTED_CHECKSUMS:
        raise ValueError(
            f"unsupported checksum algorithm {algorithm!r}; expected one of {SUPPORTED_CHECKSUMS}"
        )
    if not checksum:
        raise ValueError("checksum value must be non-empty")
