from __future__ import annotations

import pytest

from seeingbench.datasets.manifests import DatasetManifest


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
