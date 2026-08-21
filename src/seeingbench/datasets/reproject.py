"""Basic local map-window reprojection for extracted lunar ROI products."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


def reproject_extracted_roi_products(
    extraction_report_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Resample extracted map windows onto the ROI's declared target grid."""

    extraction_report = json.loads(extraction_report_path.read_text(encoding="utf-8"))
    roi = extraction_report["roi"]
    target_shape = _target_shape(roi)
    output_root.mkdir(parents=True, exist_ok=True)
    references: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for extracted in extraction_report.get("extracted", []):
        reason = _reprojection_decision(extracted)
        if reason is not None:
            skipped.append(
                {
                    "role": extracted.get("role"),
                    "name": extracted.get("name"),
                    "reason": reason,
                }
            )
            continue
        source_path = Path(str(extracted["output"]))
        source = np.load(source_path)
        if source.ndim != 2:
            skipped.append(
                {
                    "role": extracted.get("role"),
                    "name": extracted.get("name"),
                    "reason": "source_array_not_2d",
                }
            )
            continue
        reference = _resize_bilinear(source.astype(np.float64), target_shape)
        destination = _destination_path(output_root, str(extracted["role"]), str(extracted["name"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.save(destination, reference)
        references.append(
            {
                "role": extracted["role"],
                "name": extracted["name"],
                "source": str(source_path),
                "output": str(destination),
                "shape": list(reference.shape),
                "dtype": str(reference.dtype),
                "source_shape": list(source.shape),
                "source_map_scale_m_per_px": _source_map_scale(extracted),
                "method": "label-window bilinear resampling",
            }
        )

    report = {
        "roi": roi,
        "extraction_report": str(extraction_report_path),
        "output_root": str(output_root),
        "target_shape": list(target_shape),
        "target_resolution_m_per_px": roi["target_resolution_m_per_px"],
        "reference_count": len(references),
        "skipped_count": len(skipped),
        "references": references,
        "skipped": skipped,
        "limitations": [
            "basic north-up map-window reprojection; not an Earth-view renderer",
            (
                "illumination, libration, local registration, and telescope PSF matching "
                "are not applied"
            ),
        ],
    }
    (output_root / "surface-reference-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def _target_shape(roi: dict[str, Any]) -> tuple[int, int]:
    resolution = float(roi["target_resolution_m_per_px"])
    if resolution <= 0.0:
        raise ValueError("ROI target_resolution_m_per_px must be positive")
    height_px = max(1, round(float(roi["height_km"]) * 1000.0 / resolution))
    width_px = max(1, round(float(roi["width_km"]) * 1000.0 / resolution))
    return height_px, width_px


def _reprojection_decision(extracted: dict[str, Any]) -> str | None:
    if "output" not in extracted:
        return "missing_extracted_output_path"
    if not Path(str(extracted["output"])).exists():
        return "missing_extracted_array"
    if "roi_pixel_window" not in extracted:
        return "missing_roi_pixel_window"
    if _source_map_scale(extracted) is None:
        return "missing_source_map_scale"
    return None


def _source_map_scale(extracted: dict[str, Any]) -> float | None:
    window = extracted.get("roi_pixel_window", {})
    if isinstance(window, dict) and isinstance(
        window.get("estimated_map_scale_m_per_px"), int | float
    ):
        return float(window["estimated_map_scale_m_per_px"])
    summary = extracted.get("label_summary", {})
    if isinstance(summary, dict) and isinstance(summary.get("map_scale_m_per_px"), int | float):
        return float(summary["map_scale_m_per_px"])
    return None


def _resize_bilinear(
    source: NDArray[np.float64],
    target_shape: tuple[int, int],
) -> NDArray[np.float64]:
    source_height, source_width = source.shape
    target_height, target_width = target_shape
    if source_height <= 0 or source_width <= 0:
        raise ValueError("cannot reproject an empty source array")
    if source.shape == target_shape:
        return source.copy()

    y = (np.arange(target_height, dtype=np.float64) + 0.5) * source_height / target_height - 0.5
    x = (np.arange(target_width, dtype=np.float64) + 0.5) * source_width / target_width - 0.5
    y_grid, x_grid = np.meshgrid(y, x, indexing="ij")
    y0 = np.floor(y_grid).astype(np.int64)
    x0 = np.floor(x_grid).astype(np.int64)
    y1 = y0 + 1
    x1 = x0 + 1
    wy = y_grid - y0
    wx = x_grid - x0

    y0_clip = np.clip(y0, 0, source_height - 1)
    y1_clip = np.clip(y1, 0, source_height - 1)
    x0_clip = np.clip(x0, 0, source_width - 1)
    x1_clip = np.clip(x1, 0, source_width - 1)

    samples = [
        (source[y0_clip, x0_clip], (1.0 - wy) * (1.0 - wx)),
        (source[y0_clip, x1_clip], (1.0 - wy) * wx),
        (source[y1_clip, x0_clip], wy * (1.0 - wx)),
        (source[y1_clip, x1_clip], wy * wx),
    ]
    numerator = np.zeros(target_shape, dtype=np.float64)
    denominator = np.zeros(target_shape, dtype=np.float64)
    for values, weights in samples:
        finite = np.isfinite(values)
        numerator += np.where(finite, values * weights, 0.0)
        denominator += np.where(finite, weights, 0.0)
    return np.divide(
        numerator,
        denominator,
        out=np.full(target_shape, np.nan, dtype=np.float64),
        where=denominator > 0.0,
    )


def _destination_path(output_root: Path, role: str, name: str) -> Path:
    safe_role = _safe_name(role)
    safe_name = _safe_name(Path(name).stem or name)
    return output_root / safe_role / f"{safe_name}.npy"


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")
