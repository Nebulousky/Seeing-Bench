from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from seeingbench.cli import main
from seeingbench.datasets.reproject import reproject_extracted_roi_products


def test_reproject_extracted_roi_products_preserves_equal_target_grid(tmp_path: Path) -> None:
    source = np.arange(16, dtype=np.float64).reshape((4, 4))
    source_path = tmp_path / "terrain.npy"
    np.save(source_path, source)
    report_path = _write_extraction_report(
        tmp_path,
        source_path=source_path,
        target_resolution_m_per_px=1000.0,
    )

    report = reproject_extracted_roi_products(report_path, tmp_path / "reference")

    reference_path = Path(report["references"][0]["output"])
    reference = np.load(reference_path)
    assert report["reference_count"] == 1
    assert report["target_shape"] == [4, 4]
    assert np.array_equal(reference, source)
    assert (tmp_path / "reference" / "surface-reference-report.json").exists()


def test_reproject_extracted_roi_products_resamples_to_declared_target_grid(
    tmp_path: Path,
) -> None:
    source = np.arange(16, dtype=np.float64).reshape((4, 4))
    source_path = tmp_path / "terrain.npy"
    np.save(source_path, source)
    report_path = _write_extraction_report(
        tmp_path,
        source_path=source_path,
        target_resolution_m_per_px=500.0,
    )

    report = reproject_extracted_roi_products(report_path, tmp_path / "reference")

    reference = np.load(Path(report["references"][0]["output"]))
    assert report["target_shape"] == [8, 8]
    assert reference.shape == (8, 8)
    assert np.isfinite(reference).all()
    assert reference[0, 0] == source[0, 0]
    assert reference[-1, -1] == source[-1, -1]


def test_cli_reproject_roi_returns_nonzero_when_no_references_are_built(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "empty-extraction-report.json"
    report_path.write_text(
        json.dumps(
            {
                "roi": {
                    "name": "empty",
                    "width_km": 4.0,
                    "height_km": 4.0,
                    "target_resolution_m_per_px": 1000.0,
                },
                "extracted": [],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "datasets",
                "reproject-roi",
                "--extraction-report",
                str(report_path),
                "--output-root",
                str(tmp_path / "reference"),
            ]
        )
        == 1
    )


def _write_extraction_report(
    tmp_path: Path,
    source_path: Path,
    target_resolution_m_per_px: float,
) -> Path:
    report_path = tmp_path / "extraction-report.json"
    report_path.write_text(
        json.dumps(
            {
                "roi": {
                    "name": "tiny",
                    "center_lat_deg": 5.0,
                    "center_lon_deg": 5.0,
                    "width_km": 4.0,
                    "height_km": 4.0,
                    "target_resolution_m_per_px": target_resolution_m_per_px,
                },
                "extracted": [
                    {
                        "role": "terrain",
                        "name": "tiny terrain IMG",
                        "output": str(source_path),
                        "shape": [4, 4],
                        "dtype": "float64",
                        "label_summary": {"map_scale_m_per_px": 1000.0},
                        "roi_pixel_window": {
                            "row_start": 3,
                            "row_stop": 7,
                            "col_start": 3,
                            "col_stop": 7,
                            "row_count": 4,
                            "col_count": 4,
                            "estimated_map_scale_m_per_px": 1000.0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return report_path
