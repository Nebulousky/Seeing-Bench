from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from seeingbench.cli import main
from seeingbench.geometry.spice import build_spice_readiness_report, parse_naif_checksum_table


def test_parse_naif_checksum_table_reads_md5_and_archive_paths() -> None:
    checksums = parse_naif_checksum_table(
        """
        642d40181a9c8ef88ec31c12619274a5  aareadme.htm
        11111111111111111111111111111111  data/lsk/naif0012.tls
        """
    )

    assert checksums["aareadme.htm"] == "642d40181a9c8ef88ec31c12619274a5"
    assert checksums["data/lsk/naif0012.tls"] == "11111111111111111111111111111111"


def test_spice_readiness_verifies_declared_local_kernel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = tmp_path / "cache"
    kernel_payload = b"kernel"
    kernel_path = cache_root / "spice" / "data" / "lsk" / "test.tls"
    kernel_path.parent.mkdir(parents=True)
    kernel_path.write_bytes(kernel_payload)
    checksum = hashlib.md5(kernel_payload, usedforsecurity=False).hexdigest()
    checksum_path = cache_root / "metadata" / "checksum.tab"
    checksum_path.parent.mkdir(parents=True)
    checksum_path.write_text(f"{checksum}  data/lsk/test.tls\n", encoding="utf-8")
    observation_path = _write_observation(tmp_path, kernels=["spice/data/lsk/test.tls"])
    manifest_path = _write_manifest(tmp_path)
    monkeypatch.setattr(
        "seeingbench.geometry.spice.importlib.util.find_spec",
        lambda name: object() if name == "spiceypy" else None,
    )

    report = build_spice_readiness_report(observation_path, manifest_path, cache_root)

    assert report["ready"]
    assert report["spiceypy_available"]
    assert report["checksum_table"]["kernel_type_counts"] == {"lsk": 1}
    assert report["kernels"][0]["checksum_status"] == "ok"
    assert report["kernels"][0]["kernel_type"] == "lsk"


def test_spice_readiness_blocks_missing_observer_and_kernels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps({"target": "Moon", "utc_start": "2026-08-15T00:46:34Z"}),
        encoding="utf-8",
    )
    manifest_path = _write_manifest(tmp_path)
    monkeypatch.setattr(
        "seeingbench.geometry.spice.importlib.util.find_spec",
        lambda name: None,
    )

    report = build_spice_readiness_report(observation_path, manifest_path, tmp_path / "cache")

    assert not report["ready"]
    assert "missing_observer.latitude" in report["blocking_reasons"]
    assert "missing_spice.kernels" in report["blocking_reasons"]
    assert "spiceypy_not_installed" in report["blocking_reasons"]


def test_cli_spice_readiness_writes_report(tmp_path: Path) -> None:
    observation_path = _write_observation(tmp_path, kernels=[])
    manifest_path = _write_manifest(tmp_path)
    output_path = tmp_path / "spice-readiness.json"

    assert (
        main(
            [
                "geometry",
                "spice-readiness",
                "--observation",
                str(observation_path),
                "--manifest",
                str(manifest_path),
                "--cache-root",
                str(tmp_path / "cache"),
                "--output",
                str(output_path),
            ]
        )
        == 1
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["checksum_table"]["status"] == "missing"
    assert "missing_spice.kernels" in report["blocking_reasons"]


def _write_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "spice-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "SPICE",
                "source": "https://example.invalid/spice",
                "version": "1",
                "expected_size": "small test",
                "checksum": None,
                "local_destination": "spice",
                "license": "public domain",
                "provenance": "test",
                "resolution": "N/A",
                "coordinate_system": "SPICE",
                "metadata_documents": [
                    {
                        "name": "checksum",
                        "url": "https://example.invalid/checksum.tab",
                        "local_path": "metadata/checksum.tab",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _write_observation(tmp_path: Path, kernels: list[str]) -> Path:
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps(
            {
                "target": "Moon",
                "utc_start": "2026-08-15T00:46:34Z",
                "observer": {
                    "latitude": 51.5,
                    "longitude": -0.1,
                    "altitude_m": 45.0,
                },
                "spice": {"kernels": kernels},
            }
        ),
        encoding="utf-8",
    )
    return observation_path
