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
    lines = [
        f"# SeeingBench Report: {report['algorithm']}",
        "",
        "## Summary",
        "",
        f"- Algorithm: `{report['algorithm']}`",
        f"- Benchmark mode: `{case_metadata.get('benchmark_mode', 'unknown')}`",
        f"- Runtime: {_format_float(metadata.get('runtime_s'))} s",
        f"- Frame count: `{config.get('frame_count', 'unknown')}`",
        f"- Random seed: `{config.get('random_seed', 'unknown')}`",
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
