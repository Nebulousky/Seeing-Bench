"""Compare multiple SeeingBench evaluation reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ComparisonRow:
    """One algorithm's metrics extracted for comparison."""

    algorithm: str
    metrics_path: str
    mse: float
    ssim_global: float
    gradient_correlation: float
    frequency_limit_fraction: float
    false_detail_fraction: float
    runtime_s: float | None
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "metrics_path": self.metrics_path,
            "mse": self.mse,
            "ssim_global": self.ssim_global,
            "gradient_correlation": self.gradient_correlation,
            "frequency_limit_fraction": self.frequency_limit_fraction,
            "false_detail_fraction": self.false_detail_fraction,
            "runtime_s": self.runtime_s,
            "score": self.score,
        }


def compare_metric_files(paths: list[Path]) -> dict[str, Any]:
    """Return ranked comparison data for metrics JSON files or result directories."""

    if len(paths) < 2:
        raise ValueError("compare requires at least two metrics files or result directories")
    rows = [_row_from_report(_resolve_metrics_path(path)) for path in paths]
    ranked = sorted(rows, key=lambda row: row.score, reverse=True)
    return {
        "ranking_basis": (
            "diagnostic score = mean(global SSIM, gradient correlation, spectral-fidelity "
            "limit) - false detail fraction"
        ),
        "rows": [row.to_dict() for row in ranked],
    }


def write_comparison_json(paths: list[Path], output_path: Path) -> None:
    """Write comparison data as JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(compare_metric_files(paths), indent=2), encoding="utf-8")


def write_comparison_markdown(paths: list[Path], output_path: Path) -> None:
    """Write comparison data as a Markdown table."""

    comparison = compare_metric_files(paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_comparison_markdown(comparison), encoding="utf-8")


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    """Render comparison data as Markdown."""

    lines = [
        "# SeeingBench Comparison",
        "",
        f"Ranking basis: {comparison['ranking_basis']}",
        "",
        "| Rank | Algorithm | Score | MSE | SSIM | Gradient Corr | Spectral Limit | False Detail |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(comparison["rows"], start=1):
        lines.append(
            "| "
            f"{rank} | `{row['algorithm']}` | {_fmt(row['score'])} | {_fmt(row['mse'])} | "
            f"{_fmt(row['ssim_global'])} | {_fmt(row['gradient_correlation'])} | "
            f"{_fmt(row['frequency_limit_fraction'])} | {_fmt(row['false_detail_fraction'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _resolve_metrics_path(path: Path) -> Path:
    if path.is_dir():
        path = path / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _row_from_report(metrics_path: Path) -> ComparisonRow:
    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    image = report["image_similarity"]
    structure = report["structural_accuracy"]
    frequency = report["frequency_recovery"]
    false_detail = report["false_detail"]
    ssim = float(image["ssim_global"])
    gradient = float(structure["gradient_correlation"])
    frequency_limit = float(frequency["correlation_0_5_limit_fraction"])
    false_fraction = float(false_detail["unsupported_energy_fraction"])
    score = ((ssim + gradient + frequency_limit) / 3.0) - false_fraction
    return ComparisonRow(
        algorithm=str(report["algorithm"]),
        metrics_path=str(metrics_path),
        mse=float(image["mse"]),
        ssim_global=ssim,
        gradient_correlation=gradient,
        frequency_limit_fraction=frequency_limit,
        false_detail_fraction=false_fraction,
        runtime_s=_optional_float(report.get("metadata", {}).get("runtime_s")),
        score=score,
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _fmt(value: float) -> str:
    return f"{value:.6g}"
