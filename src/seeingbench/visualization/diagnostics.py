"""Lightweight diagnostic outputs that avoid plotting dependencies."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from seeingbench.evaluation.false_detail import false_detail_map
from seeingbench.evaluation.structure import edge_residual_map
from seeingbench.io.images import write_grayscale_tiff
from seeingbench.simulation.warp import validate_grayscale_image

FloatArray = NDArray[np.float64]


def write_diagnostics(
    output_dir: Path,
    reference: FloatArray,
    reconstruction: FloatArray,
    frequency_curve: list[dict[str, float | int]],
) -> dict[str, Any]:
    """Write residual images and a frequency-recovery CSV."""

    validate_grayscale_image(reference)
    validate_grayscale_image(reconstruction)
    output_dir.mkdir(parents=True, exist_ok=True)

    residual = np.abs(reconstruction - reference)
    edge_residual = edge_residual_map(reference, reconstruction)
    false_map = false_detail_map(reference, reconstruction)

    written = {
        "absolute_residual": _write_scaled(output_dir / "absolute_residual.tif", residual),
        "edge_residual": _write_scaled(output_dir / "edge_residual.tif", edge_residual),
        "false_detail_map": _write_scaled(output_dir / "false_detail_map.tif", false_map),
        "frequency_curve_csv": str(output_dir / "frequency_recovery.csv"),
    }

    with (output_dir / "frequency_recovery.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bin",
                "frequency_min_fraction",
                "frequency_max_fraction",
                "frequency_mid_fraction",
                "sample_count",
                "correlation",
            ],
        )
        writer.writeheader()
        writer.writerows(frequency_curve)
    return written


def _write_scaled(path: Path, image: FloatArray) -> dict[str, Any]:
    scaled, metadata = _scale_to_unit(image)
    write_grayscale_tiff(path, scaled)
    return {"path": str(path), **metadata}


def _scale_to_unit(image: FloatArray) -> tuple[FloatArray, dict[str, float]]:
    validate_grayscale_image(image)
    minimum = float(np.min(image))
    maximum = float(np.max(image))
    if maximum == minimum:
        return np.zeros_like(image), {"source_min": minimum, "source_max": maximum}
    scaled = (image - minimum) / (maximum - minimum)
    return scaled.astype(np.float64), {"source_min": minimum, "source_max": maximum}
