from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from seeingbench.cli import main
from seeingbench.datasets.extract import extract_verified_roi_products


def test_extract_verified_roi_products_reads_supported_local_img_window(tmp_path: Path) -> None:
    roi_path, cache_root, manifest_root, source_array = _write_extractable_case(tmp_path)

    report = extract_verified_roi_products(
        roi_path,
        cache_root=cache_root,
        manifest_root=manifest_root,
        output_root=tmp_path / "out",
    )

    output_path = Path(report["extracted"][0]["output"])
    extracted = np.load(output_path)

    assert report["extracted_count"] == 1
    assert report["skipped_count"] == 0
    provenance = report["extracted"][0]["label_provenance"]
    assert provenance["logical_identifier"] == "urn:nasa:pds:tiny"
    assert extracted.shape == (4, 4)
    assert np.array_equal(extracted, source_array[3:7, 3:7].astype(np.float64))
    assert (tmp_path / "out" / "extraction-report.json").exists()


def test_extract_verified_roi_products_skips_unverified_local_img(tmp_path: Path) -> None:
    roi_path, cache_root, manifest_root, _source_array = _write_extractable_case(
        tmp_path,
        checksum="md5:0000",
    )

    report = extract_verified_roi_products(
        roi_path,
        cache_root=cache_root,
        manifest_root=manifest_root,
        output_root=tmp_path / "out",
    )

    assert report["extracted_count"] == 0
    assert report["skipped"][0]["reason"] == "checksum_mismatch"


def test_cli_extract_roi_returns_nonzero_when_no_products_are_extractable(tmp_path: Path) -> None:
    output_root = tmp_path / "out"

    assert (
        main(
            [
                "datasets",
                "extract-roi",
                "--roi",
                "configs/rois/copernicus-100m.json",
                "--cache-root",
                str(tmp_path / "empty-cache"),
                "--manifest-root",
                ".",
                "--output-root",
                str(output_root),
            ]
        )
        == 1
    )
    report = json.loads((output_root / "extraction-report.json").read_text(encoding="utf-8"))
    assert report["extracted_count"] == 0
    assert report["skipped_count"] > 0


def _write_extractable_case(
    tmp_path: Path,
    checksum: str | None = None,
) -> tuple[Path, Path, Path, np.ndarray]:
    cache_root = tmp_path / "cache"
    manifest_root = tmp_path
    product_path = cache_root / "data" / "tiny.img"
    label_path = cache_root / "data" / "tiny.xml"
    product_path.parent.mkdir(parents=True)
    source_array = np.arange(100, dtype="<i2").reshape((10, 10))
    product_path.write_bytes(source_array.tobytes())
    digest = hashlib.md5(product_path.read_bytes()).hexdigest()
    label_path.write_text(
        _label_text("tiny.img", product_path.stat().st_size, digest),
        encoding="utf-8",
    )

    roi_path = tmp_path / "roi.json"
    roi_path.write_text(
        json.dumps(
            {
                "name": "tiny",
                "center_lat_deg": 5.0,
                "center_lon_deg": 5.0,
                "width_km": 4.0,
                "height_km": 4.0,
                "target_resolution_m_per_px": 1000.0,
                "required_products": [
                    {
                        "role": "terrain",
                        "manifest": "manifests/tiny.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifests" / "tiny.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "name": "Tiny Terrain",
                "source": "https://example.invalid/tiny.img",
                "version": "1",
                "expected_size": "200 bytes",
                "checksum": None,
                "local_destination": "data/tiny",
                "license": "public domain",
                "provenance": "test",
                "resolution": "1000 m/pixel",
                "coordinate_system": "test equirectangular",
                "product_files": [
                    {
                        "name": "tiny terrain IMG",
                        "url": "https://example.invalid/tiny.img",
                        "local_path": "data/tiny.img",
                        "checksum": checksum,
                        "label_local_path": "data/tiny.xml",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return roi_path, cache_root, manifest_root, source_array


def _label_text(file_name: str, file_size: int, md5: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Product_Observational xmlns:cart="http://pds.nasa.gov/pds4/cart/v1">
      <Identification_Area>
        <logical_identifier>urn:nasa:pds:tiny</logical_identifier>
        <version_id>1.0</version_id>
        <title>Tiny ROI Product</title>
      </Identification_Area>
      <cart:Bounding_Coordinates>
        <cart:west_bounding_coordinate unit="deg">0.0</cart:west_bounding_coordinate>
        <cart:east_bounding_coordinate unit="deg">10.0</cart:east_bounding_coordinate>
        <cart:north_bounding_coordinate unit="deg">10.0</cart:north_bounding_coordinate>
        <cart:south_bounding_coordinate unit="deg">0.0</cart:south_bounding_coordinate>
      </cart:Bounding_Coordinates>
      <cart:map_projection_name>Equirectangular</cart:map_projection_name>
      <cart:pixel_scale_x unit="m/pixel">1000.0</cart:pixel_scale_x>
      <File><file_name>{file_name}</file_name><file_size unit="byte">{file_size}</file_size>
      <md5_checksum>{md5}</md5_checksum></File>
      <Array_2D_Image>
        <offset unit="byte">0</offset>
        <Element_Array><data_type>SignedLSB2</data_type></Element_Array>
        <Axis_Array><axis_name>Line</axis_name><elements>10</elements></Axis_Array>
        <Axis_Array><axis_name>Sample</axis_name><elements>10</elements></Axis_Array>
      </Array_2D_Image>
    </Product_Observational>
    """
