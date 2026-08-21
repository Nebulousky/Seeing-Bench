"""Metadata-only readiness checks for Phase 2 lunar ROI inputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from seeingbench.datasets.labels import (
    label_coverage_status,
    label_resolution_status,
    label_summary,
    parse_pds_label_file,
    roi_pixel_window,
)
from seeingbench.datasets.manifests import DatasetManifest, ProductFile, load_manifest

SUPPORTED_CHECKSUMS = ("sha256", "sha1", "md5")


@dataclass(frozen=True)
class ROIProductRequirement:
    """One manifest-backed product role required for an ROI."""

    role: str
    manifest: str
    required: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ROIProductRequirement:
        required = {"role", "manifest"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"ROI product is missing required field(s): {', '.join(missing)}")
        requirement = cls(
            role=str(data["role"]),
            manifest=str(data["manifest"]),
            required=bool(data.get("required", True)),
            notes=str(data.get("notes", "")),
        )
        requirement.validate()
        return requirement

    def validate(self) -> None:
        if not self.role:
            raise ValueError("ROI product role must be non-empty")
        _validate_relative_path(self.manifest, "ROI product manifest")


@dataclass(frozen=True)
class LunarROIConfig:
    """Small declared lunar region and the products needed to construct it."""

    name: str
    center_lat_deg: float
    center_lon_deg: float
    width_km: float
    height_km: float
    target_resolution_m_per_px: float
    required_products: tuple[ROIProductRequirement, ...]
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LunarROIConfig:
        required = {
            "name",
            "center_lat_deg",
            "center_lon_deg",
            "width_km",
            "height_km",
            "target_resolution_m_per_px",
            "required_products",
        }
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"ROI config is missing required field(s): {', '.join(missing)}")
        product_data = data["required_products"]
        if not isinstance(product_data, list):
            raise ValueError("required_products must be a list")
        config = cls(
            name=str(data["name"]),
            center_lat_deg=float(data["center_lat_deg"]),
            center_lon_deg=float(data["center_lon_deg"]),
            width_km=float(data["width_km"]),
            height_km=float(data["height_km"]),
            target_resolution_m_per_px=float(data["target_resolution_m_per_px"]),
            required_products=tuple(_product_requirement(item) for item in product_data),
            description=str(data.get("description", "")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ROI name must be non-empty")
        if not -90.0 <= self.center_lat_deg <= 90.0:
            raise ValueError("center_lat_deg must be in [-90, 90]")
        if not -180.0 <= self.center_lon_deg <= 360.0:
            raise ValueError("center_lon_deg must be in [-180, 360]")
        if self.width_km <= 0 or self.height_km <= 0:
            raise ValueError("ROI width_km and height_km must be positive")
        if self.target_resolution_m_per_px <= 0:
            raise ValueError("target_resolution_m_per_px must be positive")
        if not self.required_products:
            raise ValueError("required_products must not be empty")
        roles = [product.role for product in self.required_products]
        duplicate_roles = sorted({role for role in roles if roles.count(role) > 1})
        if duplicate_roles:
            raise ValueError(f"duplicate ROI product role(s): {', '.join(duplicate_roles)}")


def load_roi_config(path: Path) -> LunarROIConfig:
    """Load and validate a lunar ROI config JSON file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ROI config must be a JSON object")
    return LunarROIConfig.from_dict(data)


def _product_requirement(value: Any) -> ROIProductRequirement:
    if not isinstance(value, dict):
        raise ValueError("each required_products entry must be a JSON object")
    return ROIProductRequirement.from_dict(value)


def resolve_manifest_cache_path(manifest: DatasetManifest, cache_root: Path) -> Path:
    """Resolve a manifest's repository-relative destination under ``cache_root``."""

    manifest.validate()
    _validate_relative_path(manifest.local_destination, "local_destination")
    return cache_root / manifest.local_destination


def resolve_product_file_cache_path(product: ProductFile, cache_root: Path) -> Path:
    """Resolve a product file's repository-relative destination under ``cache_root``."""

    product.validate()
    _validate_relative_path(product.local_path, "product file local_path")
    return cache_root / product.local_path


def build_roi_readiness_report(
    roi_path: Path,
    cache_root: Path,
    manifest_root: Path,
) -> dict[str, Any]:
    """Inspect whether an ROI's manifest-backed products are locally available.

    This function performs no bulk downloads. It only reads the ROI JSON, the referenced
    manifests, and any local files already present under ``cache_root``.
    """

    roi = load_roi_config(roi_path)
    products = [
        _product_status(requirement, roi, cache_root, manifest_root)
        for requirement in roi.required_products
    ]
    missing_required = [
        product["role"]
        for product in products
        if product["required"] and product["presence"] != "present"
    ]
    failed_checksums = [
        product["role"]
        for product in products
        if product["required"] and product["checksum_status"] == "mismatch"
    ]
    unresolved_checksums = [
        product["role"]
        for product in products
        if product["required"] and product["manifest_status"] != "verified"
    ]
    incompatible_metadata = [
        product["role"]
        for product in products
        if product["required"] and product["label_metadata_status"] == "incompatible"
    ]
    ready = (
        not missing_required
        and not failed_checksums
        and not unresolved_checksums
        and not incompatible_metadata
    )
    return {
        "roi": {
            "name": roi.name,
            "description": roi.description,
            "center_lat_deg": roi.center_lat_deg,
            "center_lon_deg": roi.center_lon_deg,
            "width_km": roi.width_km,
            "height_km": roi.height_km,
            "target_resolution_m_per_px": roi.target_resolution_m_per_px,
        },
        "cache_root": str(cache_root),
        "manifest_root": str(manifest_root),
        "ready": ready,
        "blocking_reasons": {
            "missing_required_roles": missing_required,
            "checksum_mismatch_roles": failed_checksums,
            "unresolved_checksum_roles": unresolved_checksums,
            "incompatible_metadata_roles": incompatible_metadata,
        },
        "products": products,
    }


def build_roi_download_plan(
    roi_path: Path,
    cache_root: Path,
    manifest_root: Path,
) -> dict[str, Any]:
    """Build an explicit no-download acquisition plan for an ROI."""

    roi = load_roi_config(roi_path)
    product_files: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    seen_labels: set[tuple[str, str]] = set()
    for requirement in roi.required_products:
        manifest_path = manifest_root / requirement.manifest
        manifest = load_manifest(manifest_path)
        for product in manifest.product_files:
            product_files.append(
                {
                    "role": requirement.role,
                    "manifest_path": str(manifest_path),
                    "name": product.name,
                    "url": product.url,
                    "local_path": str(resolve_product_file_cache_path(product, cache_root)),
                    "declared_checksum": product.checksum,
                    "expected_size_bytes": product.expected_size_bytes,
                    "purpose": product.purpose,
                }
            )
            if product.label_url is not None and product.label_local_path is not None:
                label_key = (product.label_url, str(cache_root / product.label_local_path))
                if label_key in seen_labels:
                    continue
                seen_labels.add(label_key)
                label_entry = {
                    "role": requirement.role,
                    "manifest_path": str(manifest_path),
                    "url": product.label_url,
                    "local_path": str(cache_root / product.label_local_path),
                }
                labels.append(label_entry)
    return {
        "roi": {
            "name": roi.name,
            "center_lat_deg": roi.center_lat_deg,
            "center_lon_deg": roi.center_lon_deg,
            "width_km": roi.width_km,
            "height_km": roi.height_km,
            "target_resolution_m_per_px": roi.target_resolution_m_per_px,
        },
        "cache_root": str(cache_root),
        "manifest_root": str(manifest_root),
        "downloads_are_not_started": True,
        "bulk_product_count": len(product_files),
        "label_count": len(labels),
        "bulk_products": product_files,
        "labels": labels,
    }


def _product_status(
    requirement: ROIProductRequirement,
    roi: LunarROIConfig,
    cache_root: Path,
    manifest_root: Path,
) -> dict[str, Any]:
    manifest_path = manifest_root / requirement.manifest
    manifest = load_manifest(manifest_path)
    cache_path = resolve_manifest_cache_path(manifest, cache_root)
    if manifest.product_files:
        files: list[dict[str, Any]] = []
        for product in manifest.product_files:
            files.append(_product_file_status(product, roi, cache_root))
        presence, path_type, size_bytes = _aggregate_file_presence(files)
        checksum_status = _aggregate_file_checksum_status(files)
        label_metadata_status = _aggregate_label_metadata_status(files)
        checksum_algorithm = None
        computed_checksum = None
    else:
        files = []
        presence, path_type, size_bytes = _presence(cache_path)
        label_metadata_status = "not_declared"
        checksum_status, checksum_algorithm, computed_checksum = _checksum_status(
            cache_path,
            manifest.checksum,
            presence,
            path_type,
        )
    manifest_status = _manifest_status(manifest)
    return {
        "role": requirement.role,
        "required": requirement.required,
        "notes": requirement.notes,
        "manifest_path": str(manifest_path),
        "manifest_name": manifest.name,
        "manifest_status": manifest_status,
        "source": manifest.source,
        "expected_size": manifest.expected_size,
        "resolution": manifest.resolution,
        "coordinate_system": manifest.coordinate_system,
        "local_path": str(cache_path),
        "presence": presence,
        "path_type": path_type,
        "size_bytes": size_bytes,
        "declared_checksum": manifest.checksum,
        "checksum_algorithm": checksum_algorithm,
        "computed_checksum": computed_checksum,
        "checksum_status": checksum_status,
        "label_metadata_status": label_metadata_status,
        "file_count": len(files),
        "missing_file_count": sum(1 for file in files if file["presence"] != "present"),
        "files": files,
    }


def _product_file_status(
    product: ProductFile,
    roi: LunarROIConfig,
    cache_root: Path,
) -> dict[str, Any]:
    cache_path = resolve_product_file_cache_path(product, cache_root)
    presence, path_type, size_bytes = _presence(cache_path)
    label_status = _label_status(product, roi, cache_root)
    label_checksum = _label_product_checksum(label_status)
    label_size = _label_product_size(label_status)
    checksum_status, checksum_algorithm, computed_checksum = _checksum_status(
        cache_path,
        product.checksum or label_checksum,
        presence,
        path_type,
    )
    size_status = _size_status(
        size_bytes,
        product.expected_size_bytes or label_size,
        presence,
        path_type,
    )
    return {
        "name": product.name,
        "source": product.url,
        "local_path": str(cache_path),
        "presence": presence,
        "path_type": path_type,
        "size_bytes": size_bytes,
        "expected_size_bytes": product.expected_size_bytes,
        "label_expected_size_bytes": label_size,
        "size_status": size_status,
        "declared_checksum": product.checksum,
        "label_declared_checksum": label_checksum,
        "checksum_algorithm": checksum_algorithm,
        "computed_checksum": computed_checksum,
        "checksum_status": checksum_status,
        "label_metadata": label_status,
        "purpose": product.purpose,
    }


def _presence(path: Path) -> tuple[str, str, int | None]:
    if not path.exists():
        return "missing", "missing", None
    if path.is_file():
        return "present", "file", path.stat().st_size
    if path.is_dir():
        return "present", "directory", _directory_size(path)
    return "present", "other", None


def _aggregate_file_presence(files: list[dict[str, Any]]) -> tuple[str, str, int | None]:
    if not files:
        return "missing", "missing", None
    present_count = sum(1 for file in files if file["presence"] == "present")
    size_bytes = sum(
        int(file["size_bytes"]) for file in files if isinstance(file["size_bytes"], int)
    )
    if present_count == 0:
        return "missing", "file_set", size_bytes
    if present_count == len(files):
        return "present", "file_set", size_bytes
    return "partial", "file_set", size_bytes


def _aggregate_file_checksum_status(files: list[dict[str, Any]]) -> str:
    statuses = [str(file["checksum_status"]) for file in files]
    if any(status == "mismatch" for status in statuses):
        return "mismatch"
    if any(status == "not_file" for status in statuses):
        return "not_file"
    if any(status == "not_declared" for status in statuses):
        return "not_declared"
    if any(status == "missing" for status in statuses):
        return "missing"
    if statuses and all(status == "ok" for status in statuses):
        return "ok"
    return "unknown"


def _aggregate_label_metadata_status(files: list[dict[str, Any]]) -> str:
    statuses = [str(file["label_metadata"]["status"]) for file in files]
    if any(status == "incompatible" for status in statuses):
        return "incompatible"
    if any(status == "ok" for status in statuses):
        return "ok"
    if any(status == "missing" for status in statuses):
        return "missing"
    if any(status == "not_declared" for status in statuses):
        return "not_declared"
    return "unknown"


def _label_status(
    product: ProductFile,
    roi: LunarROIConfig,
    cache_root: Path,
) -> dict[str, Any]:
    if product.label_local_path is None:
        return {
            "status": "not_declared",
            "local_path": None,
            "coverage_status": "unknown",
            "resolution_status": "unknown",
            "summary": {},
        }
    label_path = cache_root / product.label_local_path
    if not label_path.exists():
        return {
            "status": "missing",
            "local_path": str(label_path),
            "coverage_status": "unknown",
            "resolution_status": "unknown",
            "summary": {},
        }
    fields = parse_pds_label_file(label_path)
    coverage = label_coverage_status(fields, roi.center_lat_deg, roi.center_lon_deg)
    resolution = label_resolution_status(fields, roi.target_resolution_m_per_px)
    summary = label_summary(fields)
    describes_product = _label_describes_product(summary, product)
    status = "ok"
    if coverage == "outside" or resolution == "coarser_than_target":
        status = "incompatible"
    elif coverage == "unknown" and resolution == "unknown":
        status = "unknown"
    return {
        "status": status,
        "local_path": str(label_path),
        "coverage_status": coverage,
        "resolution_status": resolution,
        "describes_product": describes_product,
        "roi_pixel_window": roi_pixel_window(
            fields,
            roi.center_lat_deg,
            roi.center_lon_deg,
            roi.width_km,
            roi.height_km,
        ),
        "summary": summary,
    }


def _label_describes_product(summary: dict[str, Any], product: ProductFile) -> bool:
    file_name = summary.get("product_file_name")
    if not isinstance(file_name, str):
        return False
    return file_name.lower() == Path(product.local_path).name.lower()


def _label_product_checksum(label_status: dict[str, Any]) -> str | None:
    if not label_status.get("describes_product"):
        return None
    checksum = label_status.get("summary", {}).get("product_md5_checksum")
    if isinstance(checksum, str) and checksum:
        return f"md5:{checksum}"
    return None


def _label_product_size(label_status: dict[str, Any]) -> int | None:
    if not label_status.get("describes_product"):
        return None
    size = label_status.get("summary", {}).get("product_file_size_bytes")
    if isinstance(size, int):
        return size
    return None


def _checksum_status(
    path: Path,
    declared_checksum: str | None,
    presence: str,
    path_type: str,
) -> tuple[str, str | None, str | None]:
    if declared_checksum is None:
        return "not_declared", None, None
    algorithm, expected = _parse_checksum(declared_checksum)
    if presence != "present":
        return "missing", algorithm, None
    if path_type != "file":
        return "not_file", algorithm, None
    actual = _file_checksum(path, algorithm)
    return ("ok" if actual.lower() == expected.lower() else "mismatch", algorithm, actual)


def _size_status(
    size_bytes: int | None,
    expected_size_bytes: int | None,
    presence: str,
    path_type: str,
) -> str:
    if expected_size_bytes is None:
        return "not_declared"
    if presence != "present":
        return "missing"
    if path_type != "file":
        return "not_file"
    return "ok" if size_bytes == expected_size_bytes else "mismatch"


def _parse_checksum(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ValueError("checksum must use '<algorithm>:<hex>' format")
    algorithm, checksum = value.split(":", 1)
    algorithm = algorithm.lower()
    if algorithm not in SUPPORTED_CHECKSUMS:
        raise ValueError(
            f"unsupported checksum algorithm {algorithm!r}; expected one of {SUPPORTED_CHECKSUMS}"
        )
    if not checksum:
        raise ValueError("checksum value must be non-empty")
    return algorithm, checksum


def _file_checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _manifest_status(manifest: DatasetManifest) -> str:
    has_checksums = manifest.checksum is not None or (
        bool(manifest.product_files)
        and all(product.checksum is not None for product in manifest.product_files)
    )
    if has_checksums and "TBD" not in manifest.version and "TBD" not in manifest.license:
        return "verified"
    return "candidate"


def _validate_relative_path(path: str, field_name: str) -> None:
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute():
        raise ValueError(f"{field_name} must be repository-relative")
    destination = Path(path)
    if ".." in destination.parts:
        raise ValueError(f"{field_name} must not escape the repository")
