"""Lightweight diagnostic outputs that avoid plotting dependencies."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.false_detail import false_detail_map
from seeingbench.evaluation.structure import edge_residual_map
from seeingbench.io.images import load_grayscale_image, write_grayscale_tiff
from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]


def write_diagnostics(
    output_dir: Path,
    reference: FloatArray,
    reconstruction: FloatArray,
    frequency_curve: list[dict[str, float | int]],
    degraded_frame: FloatArray | None = None,
    warp_fields: FloatArray | None = None,
    warp_components: dict[str, FloatArray] | None = None,
    scale_primary_images: bool = False,
) -> dict[str, Any]:
    """Write residual images and a frequency-recovery CSV."""

    validate_grayscale_image(reference)
    validate_grayscale_image(reconstruction)
    output_dir.mkdir(parents=True, exist_ok=True)

    residual = np.abs(reconstruction - reference)
    edge_residual = edge_residual_map(reference, reconstruction)
    false_map = false_detail_map(reference, reconstruction)
    write_primary = _write_scaled if scale_primary_images else _write_unit

    written = {
        "truth": write_primary(output_dir / "truth.tif", reference),
        "reconstruction": write_primary(output_dir / "reconstruction.tif", reconstruction),
        "absolute_residual": _write_scaled(output_dir / "absolute_residual.tif", residual),
        "edge_residual": _write_scaled(output_dir / "edge_residual.tif", edge_residual),
        "false_detail_map": _write_scaled(output_dir / "false_detail_map.tif", false_map),
        "frequency_curve_csv": str(output_dir / "frequency_recovery.csv"),
    }
    if degraded_frame is not None:
        written["degraded_frame_000001"] = _write_unit(
            output_dir / "degraded_frame_000001.tif",
            degraded_frame,
        )
        written["blink_pair_npz"] = _write_blink_pair(
            output_dir / "blink_pair.npz",
            degraded_frame,
            reconstruction,
        )
    if warp_fields is not None:
        written["warp_magnitude_frame_000001"] = _write_scaled(
            output_dir / "warp_magnitude_frame_000001.tif",
            np.linalg.norm(warp_fields[0], axis=-1),
        )
        written["warp_summary_json"] = _write_warp_summary(
            output_dir / "warp_summary.json",
            warp_fields,
            warp_components or {},
        )

    with (output_dir / "frequency_recovery.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bin",
                "frequency_min_fraction",
                "frequency_max_fraction",
                "frequency_mid_fraction",
                "sample_count",
                "fourier_sample_count",
                "correlation",
                "phase_correlation",
                "amplitude_recovery",
            ],
        )
        writer.writeheader()
        writer.writerows(frequency_curve)
    return written


def load_diagnostic_image(path: Path) -> FloatArray:
    """Load a diagnostic TIFF."""

    return load_grayscale_image(path)


def _write_scaled(path: Path, image: FloatArray) -> dict[str, Any]:
    scaled, metadata = _scale_to_unit(image)
    write_grayscale_tiff(path, scaled)
    return {"path": str(path), **metadata}


def _write_unit(path: Path, image: FloatArray) -> dict[str, Any]:
    write_grayscale_tiff(path, image)
    return {"path": str(path)}


def _write_blink_pair(path: Path, degraded_frame: FloatArray, reconstruction: FloatArray) -> str:
    np.savez_compressed(path, degraded_frame=degraded_frame, reconstruction=reconstruction)
    return str(path)


def _write_warp_summary(
    path: Path,
    warp_fields: FloatArray,
    warp_components: dict[str, FloatArray],
) -> str:
    summary: dict[str, Any] = {"combined": _warp_stats(warp_fields)}
    summary["components"] = {
        name: _warp_stats(component) for name, component in sorted(warp_components.items())
    }
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return str(path)


def _warp_stats(warp: FloatArray) -> dict[str, float]:
    magnitude = np.linalg.norm(warp, axis=-1)
    return {
        "mean_px": float(np.mean(magnitude)),
        "median_px": float(np.median(magnitude)),
        "p95_px": float(np.percentile(magnitude, 95.0)),
        "max_px": float(np.max(magnitude)),
    }


def _scale_to_unit(image: FloatArray) -> tuple[FloatArray, dict[str, float]]:
    validate_grayscale_image(image)
    minimum = float(np.min(image))
    maximum = float(np.max(image))
    if maximum == minimum:
        return np.zeros_like(image), {"source_min": minimum, "source_max": maximum}
    scaled = (image - minimum) / (maximum - minimum)
    return scaled.astype(np.float64), {"source_min": minimum, "source_max": maximum}
