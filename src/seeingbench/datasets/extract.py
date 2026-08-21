"""Local-only extraction from already cached and verified ROI products."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from seeingbench.datasets.labels import parse_pds_label_file
from seeingbench.datasets.readiness import build_roi_readiness_report

SUPPORTED_PDS_DTYPES: dict[str, np.dtype[Any]] = {
    "IEEE754LSBSingle": np.dtype("<f4"),
    "SignedLSB2": np.dtype("<i2"),
}


def extract_verified_roi_products(
    roi_path: Path,
    cache_root: Path,
    manifest_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Extract supported verified local ROI product windows into ``.npy`` files."""

    readiness = build_roi_readiness_report(roi_path, cache_root, manifest_root)
    output_root.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for product in readiness["products"]:
        for file_status in product["files"]:
            decision = _extraction_decision(file_status)
            if decision is not None:
                skipped.append(
                    {"role": product["role"], "name": file_status["name"], "reason": decision}
                )
                continue
            destination = _destination_path(
                output_root,
                str(product["role"]),
                str(file_status["name"]),
            )
            array = _read_product_window(
                Path(str(file_status["local_path"])),
                Path(str(file_status["label_metadata"]["local_path"])),
                file_status["label_metadata"]["roi_pixel_window"],
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            np.save(destination, array)
            extracted.append(
                {
                    "role": product["role"],
                    "name": file_status["name"],
                    "source": file_status["local_path"],
                    "output": str(destination),
                    "shape": list(array.shape),
                    "dtype": str(array.dtype),
                    "label_summary": file_status["label_metadata"]["summary"],
                    "roi_pixel_window": file_status["label_metadata"]["roi_pixel_window"],
                }
            )

    report = {
        "roi": readiness["roi"],
        "cache_root": str(cache_root),
        "manifest_root": str(manifest_root),
        "output_root": str(output_root),
        "extracted_count": len(extracted),
        "skipped_count": len(skipped),
        "extracted": extracted,
        "skipped": skipped,
    }
    (output_root / "extraction-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def _extraction_decision(file_status: dict[str, Any]) -> str | None:
    if Path(str(file_status["local_path"])).suffix.lower() != ".img":
        return "unsupported_file_type"
    if file_status["presence"] != "present":
        return "missing_product_file"
    if file_status["checksum_status"] != "ok":
        return f"checksum_{file_status['checksum_status']}"
    if file_status["size_status"] != "ok":
        return f"size_{file_status['size_status']}"
    label = file_status["label_metadata"]
    if label["status"] != "ok":
        return f"label_{label['status']}"
    if not label["describes_product"]:
        return "label_does_not_describe_product"
    window = label["roi_pixel_window"]
    if window["status"] != "ok":
        return f"window_{window['status']}"
    sample_type = label["summary"].get("sample_type")
    if sample_type not in SUPPORTED_PDS_DTYPES:
        return f"unsupported_sample_type_{sample_type}"
    return None


def _read_product_window(
    product_path: Path,
    label_path: Path,
    window: dict[str, Any],
) -> np.ndarray:
    fields = parse_pds_label_file(label_path)
    dtype = SUPPORTED_PDS_DTYPES[str(fields["sample_type"])]
    lines = int(fields["lines"])
    samples = int(fields["line_samples"])
    offset = int(fields["array_offset_bytes"])
    row_start = int(window["row_start"])
    row_stop = int(window["row_stop"])
    col_start = int(window["col_start"])
    col_stop = int(window["col_stop"])
    if not 0 <= row_start <= row_stop <= lines or not 0 <= col_start <= col_stop <= samples:
        raise ValueError("ROI pixel window is outside labelled array dimensions")

    row_count = row_stop - row_start
    col_count = col_stop - col_start
    row_bytes = samples * dtype.itemsize
    output = np.empty((row_count, col_count), dtype=dtype)
    with product_path.open("rb") as handle:
        for out_row, source_row in enumerate(range(row_start, row_stop)):
            handle.seek(offset + source_row * row_bytes + col_start * dtype.itemsize)
            payload = handle.read(col_count * dtype.itemsize)
            if len(payload) != col_count * dtype.itemsize:
                raise ValueError(f"could not read complete ROI row from {product_path}")
            output[out_row] = np.frombuffer(payload, dtype=dtype, count=col_count)
    return _mask_missing(output.astype(np.float64), fields)


def _mask_missing(array: np.ndarray, fields: dict[str, Any]) -> np.ndarray:
    missing = fields.get("missing_constant")
    if missing is None:
        return array
    try:
        missing_value = float(missing)
    except (TypeError, ValueError):
        return array
    return np.where(array == missing_value, np.nan, array)


def _destination_path(output_root: Path, role: str, name: str) -> Path:
    safe_role = _safe_name(role)
    safe_name = _safe_name(Path(name).stem or name)
    return output_root / safe_role / f"{safe_name}.npy"


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")
