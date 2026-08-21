"""SPICE kernel readiness checks for real lunar observation geometry."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from seeingbench.datasets.manifests import load_manifest
from seeingbench.observations import load_observation_metadata

SPICE_KERNEL_SUFFIXES = (".bc", ".bsp", ".tf", ".ti", ".tls", ".tpc", ".tsc")


def build_spice_readiness_report(
    observation_path: Path,
    manifest_path: Path,
    cache_root: Path,
) -> dict[str, Any]:
    """Report whether local SPICE inputs are ready for Earth-view geometry."""

    observation = load_observation_metadata(observation_path)
    manifest = load_manifest(manifest_path)
    checksum_path = _checksum_table_path(manifest_path, cache_root)
    checksums = _load_checksum_table(checksum_path)
    kernels = _kernel_statuses(observation, manifest.local_destination, cache_root, checksums)
    missing_metadata = _missing_observation_geometry_fields(observation)
    blocking_reasons = _blocking_reasons(kernels, missing_metadata, checksum_path, checksums)
    spiceypy_available = importlib.util.find_spec("spiceypy") is not None
    if not spiceypy_available:
        blocking_reasons.append("spiceypy_not_installed")
    return {
        "observation": str(observation_path),
        "manifest": str(manifest_path),
        "cache_root": str(cache_root),
        "spiceypy_available": spiceypy_available,
        "ready": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "missing_observation_fields": missing_metadata,
        "checksum_table": {
            "path": str(checksum_path) if checksum_path is not None else None,
            "status": _checksum_table_status(checksum_path, checksums),
            "entry_count": len(checksums),
            "kernel_entry_count": _kernel_entry_count(checksums),
            "kernel_type_counts": _kernel_type_counts(checksums),
        },
        "kernels": kernels,
        "limitations": [
            "readiness only; no SPICE geometry is computed by this command",
            "observation metadata must explicitly list local kernels to furnish",
        ],
    }


def parse_naif_checksum_table(text: str) -> dict[str, str]:
    """Parse NAIF checksum.tab rows as ``archive/path -> md5``."""

    checksums: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"invalid checksum row {line_number}: {raw_line!r}")
        checksum, archive_path = parts
        if len(checksum) != 32 or any(char not in "0123456789abcdefABCDEF" for char in checksum):
            raise ValueError(f"invalid md5 value on checksum row {line_number}")
        checksums[_normalise_archive_path(archive_path)] = checksum.lower()
    return checksums


def _checksum_table_path(manifest_path: Path, cache_root: Path) -> Path | None:
    manifest = load_manifest(manifest_path)
    for document in manifest.metadata_documents:
        if Path(document.local_path).name.lower() == "checksum.tab":
            return cache_root / document.local_path
    for document in manifest.metadata_documents:
        if "checksum" in Path(document.local_path).name.lower():
            return cache_root / document.local_path
    return None


def _load_checksum_table(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    return parse_naif_checksum_table(path.read_text(encoding="utf-8"))


def _kernel_statuses(
    observation: dict[str, Any],
    manifest_destination: str,
    cache_root: Path,
    checksums: dict[str, str],
) -> list[dict[str, Any]]:
    kernels = _declared_observation_kernels(observation)
    return [
        _kernel_status(kernel, manifest_destination, cache_root, checksums) for kernel in kernels
    ]


def _kernel_status(
    kernel_path: str,
    manifest_destination: str,
    cache_root: Path,
    checksums: dict[str, str],
) -> dict[str, Any]:
    local_path = Path(kernel_path)
    path = cache_root / local_path
    archive_path = _archive_relative_kernel_path(kernel_path, manifest_destination)
    expected_md5 = checksums.get(archive_path)
    presence = "present" if path.is_file() else "missing"
    checksum_status = "missing"
    computed_md5 = None
    if presence == "present":
        computed_md5 = _md5(path)
        if expected_md5 is None:
            checksum_status = "not_in_checksum_table"
        else:
            checksum_status = "ok" if computed_md5 == expected_md5 else "mismatch"
    elif expected_md5 is None:
        checksum_status = "not_in_checksum_table"
    return {
        "local_path": str(path),
        "archive_path": archive_path,
        "kernel_type": _kernel_type(local_path.suffix),
        "presence": presence,
        "checksum_status": checksum_status,
        "expected_md5": expected_md5,
        "computed_md5": computed_md5,
    }


def _declared_observation_kernels(observation: dict[str, Any]) -> list[str]:
    spice = observation.get("spice", {})
    if spice is None:
        return []
    if not isinstance(spice, dict):
        raise ValueError("observation spice metadata must be an object")
    kernels = spice.get("kernels", [])
    if not isinstance(kernels, list):
        raise ValueError("observation spice.kernels must be a list")
    return [str(kernel) for kernel in kernels]


def _missing_observation_geometry_fields(observation: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if observation.get("utc_start") is None:
        missing.append("utc_start")
    observer = observation.get("observer", {})
    if observer is None:
        observer = {}
    if not isinstance(observer, dict):
        raise ValueError("observation observer metadata must be an object")
    for field in ("latitude", "longitude", "altitude_m"):
        if observer.get(field) is None:
            missing.append(f"observer.{field}")
    if not _declared_observation_kernels(observation):
        missing.append("spice.kernels")
    return missing


def _blocking_reasons(
    kernels: list[dict[str, Any]],
    missing_metadata: list[str],
    checksum_path: Path | None,
    checksums: dict[str, str],
) -> list[str]:
    reasons = [f"missing_{field}" for field in missing_metadata]
    if checksum_path is None:
        reasons.append("checksum_table_not_declared")
    elif not checksum_path.exists():
        reasons.append("checksum_table_missing")
    elif not checksums:
        reasons.append("checksum_table_empty")
    if any(kernel["presence"] != "present" for kernel in kernels):
        reasons.append("kernel_file_missing")
    if any(kernel["checksum_status"] == "mismatch" for kernel in kernels):
        reasons.append("kernel_checksum_mismatch")
    if any(kernel["checksum_status"] == "not_in_checksum_table" for kernel in kernels):
        reasons.append("kernel_not_in_checksum_table")
    return sorted(set(reasons))


def _checksum_table_status(path: Path | None, checksums: dict[str, str]) -> str:
    if path is None:
        return "not_declared"
    if not path.exists():
        return "missing"
    return "ok" if checksums else "empty"


def _kernel_entry_count(checksums: dict[str, str]) -> int:
    return sum(
        1
        for archive_path in checksums
        if Path(archive_path).suffix.lower() in SPICE_KERNEL_SUFFIXES
    )


def _kernel_type_counts(checksums: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for archive_path in checksums:
        suffix = Path(archive_path).suffix.lower()
        if suffix not in SPICE_KERNEL_SUFFIXES:
            continue
        kernel_type = _kernel_type(suffix)
        counts[kernel_type] = counts.get(kernel_type, 0) + 1
    return dict(sorted(counts.items()))


def _archive_relative_kernel_path(kernel_path: str, manifest_destination: str) -> str:
    normalised_kernel = _normalise_archive_path(kernel_path)
    normalised_destination = _normalise_archive_path(manifest_destination)
    if normalised_kernel.startswith(f"{normalised_destination}/"):
        return normalised_kernel[len(normalised_destination) + 1 :]
    return normalised_kernel


def _normalise_archive_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _kernel_type(suffix: str) -> str:
    return {
        ".bc": "ck",
        ".bsp": "spk",
        ".tf": "fk",
        ".ti": "ik",
        ".tls": "lsk",
        ".tpc": "pck",
        ".tsc": "sclk",
    }.get(suffix.lower(), "unknown")


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_spice_readiness_report(report: dict[str, Any], output: Path) -> None:
    """Persist a SPICE readiness report as JSON."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
