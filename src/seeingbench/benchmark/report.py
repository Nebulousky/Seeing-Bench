"""Human-readable benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_markdown_report(metrics_path: Path, output_path: Path) -> None:
    """Create a concise Markdown report from a machine-readable metrics JSON file."""

    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a benchmark report dictionary as Markdown."""

    image = report["image_similarity"]
    structure = report["structural_accuracy"]
    frequency = report["frequency_recovery"]
    false_detail = report["false_detail"]
    metadata = report.get("metadata", {})
    case_metadata = metadata.get("case_metadata", {})
    config = case_metadata.get("config", {})
    provenance = metadata.get("provenance", {})
    git = provenance.get("git", {}) if isinstance(provenance, dict) else {}
    reference_limitations = metadata.get("reference_limitations", [])
    reference_provenance = metadata.get("reference_provenance", {})
    reference_generation = metadata.get("reference_generation", {})
    photometry = metadata.get("photometric_normalization", {})
    lines = [
        f"# SeeingBench Report: {report['algorithm']}",
        "",
        "## Summary",
        "",
        f"- Algorithm: `{report['algorithm']}`",
        f"- Benchmark mode: `{case_metadata.get('benchmark_mode', 'unknown')}`",
        f"- Reconstruction runtime: {_format_float(metadata.get('reconstruction_runtime_s'))} s",
        f"- Evaluation runtime: {_format_float(metadata.get('evaluation_runtime_s'))} s",
        f"- Frame count: `{config.get('frame_count', 'unknown')}`",
        f"- Random seed: `{config.get('random_seed', 'unknown')}`",
        f"- Git commit: `{git.get('commit', 'unknown')}`",
        f"- Git dirty: `{git.get('dirty', 'unknown')}`",
        f"- Photometric normalization: `{_photometry_summary(photometry)}`",
        "",
        "## Image Similarity",
        "",
        f"- MSE: {_format_float(image.get('mse'))}",
        f"- PSNR: {_format_float(image.get('psnr_db'))} dB",
        f"- Global SSIM: {_format_float(image.get('ssim_global'))}",
        "",
        "## Structural Accuracy",
        "",
        f"- Gradient correlation: {_format_float(structure.get('gradient_correlation'))}",
        "",
        "## Frequency Recovery",
        "",
        (
            "- 0.5 spectral-fidelity limit: "
            f"{_format_float(frequency.get('correlation_0_5_limit_fraction'))} axial Nyquist"
        ),
        (
            "- Diffraction frequency: "
            f"{_format_float(frequency.get('diffraction_frequency_fraction_of_nyquist'))} "
            "axial Nyquist"
        ),
        (
            "- Limit relative to diffraction: "
            f"{_format_float(frequency.get('correlation_0_5_limit_relative_to_diffraction'))}"
        ),
        (
            "- Mean spectral fidelity beyond diffraction: "
            f"{_format_float(frequency.get('mean_correlation_beyond_diffraction'))}"
        ),
        "",
        "## False Detail",
        "",
        (
            "- Unsupported high-frequency energy fraction: "
            f"{_format_float(false_detail.get('unsupported_energy_fraction'))}"
        ),
        f"- Cutoff fraction: {_format_float(false_detail.get('cutoff_fraction'))} axial Nyquist",
        "",
        "## Warp Recovery",
        "",
        _render_warp(report.get("warp_recovery")),
        "",
    ]
    if reference_limitations:
        lines += [
            "## Reference Limitations",
            "",
            *[f"- `{limitation}`" for limitation in reference_limitations],
            "",
        ]
    if reference_provenance or reference_generation:
        lines += [
            "## Reference Provenance",
            "",
            *[
                f"- {label}: `{value}`"
                for label, value in (
                    ("PDS identifier", reference_provenance.get("logical_identifier")),
                    ("Title", reference_provenance.get("title")),
                    ("Generation method", reference_generation.get("method")),
                    ("Reference source", reference_generation.get("source")),
                )
                if value is not None
            ],
            "",
        ]
    diagnostics = report.get("diagnostics")
    if diagnostics:
        lines += [
            "## Diagnostics",
            "",
            *[f"- {key}: {_format_diagnostic(value)}" for key, value in diagnostics.items()],
            "",
        ]
    return "\n".join(lines)


def _render_warp(warp: Any) -> str:
    if warp is None:
        return "- No estimated warp fields were supplied."
    return "\n".join(
        [
            f"- Mean error: {_format_float(warp.get('mean_px'))} px",
            f"- Median error: {_format_float(warp.get('median_px'))} px",
            f"- 95th percentile: {_format_float(warp.get('p95_px'))} px",
            f"- Max error: {_format_float(warp.get('max_px'))} px",
        ]
    )


def _format_float(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return f"{float(value):.6g}"


def _photometry_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return "unknown"
    method = str(value.get("method", "unknown"))
    if not value.get("applied", False):
        reason = value.get("reason")
        return method if reason is None else f"{method} skipped: {reason}"
    scale = _format_float(value.get("scale"))
    offset = _format_float(value.get("offset"))
    return f"{method}; scale={scale}; offset={offset}"


def _format_diagnostic(value: Any) -> str:
    if isinstance(value, dict) and "path" in value:
        suffix = ""
        if "source_min" in value and "source_max" in value:
            suffix = (
                f" (source range {_format_float(value['source_min'])}"
                f" to {_format_float(value['source_max'])})"
            )
        return f"`{value['path']}`{suffix}"
    return f"`{value}`"
