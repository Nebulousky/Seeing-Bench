"""Dataset manifest model for future orbital-data integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


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
        if _is_absolute_on_supported_platform(self.local_destination):
            raise ValueError("local_destination must be repository-relative")
        destination = Path(self.local_destination)
        if ".." in destination.parts:
            raise ValueError("local_destination must not escape the repository")


def load_manifest(path: Path) -> DatasetManifest:
    """Load and validate a dataset manifest JSON file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dataset manifest must be a JSON object")
    return DatasetManifest.from_dict(data)


def _is_absolute_on_supported_platform(path: str) -> bool:
    return PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()
