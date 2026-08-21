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
    reconstruction_runtime_s: float | None
    evaluation_runtime_s: float | None
    git_commit: str | None
    git_dirty: bool | None
    reference_limitations: tuple[str, ...]
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
            "reconstruction_runtime_s": self.reconstruction_runtime_s,
            "evaluation_runtime_s": self.evaluation_runtime_s,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "reference_limitations": list(self.reference_limitations),
            "score": self.score,
        }


def compare_metric_files(paths: list[Path]) -> dict[str, Any]:
    """Return ranked comparison data for metrics JSON files or result directories."""

    if len(paths) < 2:
        raise ValueError("compare requires at least two metrics files or result directories")
    rows = [_row_from_report(_resolve_metrics_path(path)) for path in paths]
    ranked = sorted(rows, key=lambda row: row.score, reverse=True)
    ranked_dicts = [row.to_dict() for row in ranked]
    return {
        "ranking_basis": (
            "conservative diagnostic score = min(global SSIM, gradient correlation, "
            "spectral-fidelity limit) * (1 - false detail fraction)"
        ),
        "leaders": _leaders(rows),
        "reference_limitations": sorted(
            {limitation for row in rows for limitation in row.reference_limitations}
        ),
        "rows": ranked_dicts,
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
    ]
    if comparison.get("reference_limitations"):
        lines += [
            "## Reference Limitations",
            "",
            *[f"- `{limitation}`" for limitation in comparison["reference_limitations"]],
            "",
        ]
    lines += [
        "## Direct Answers",
        "",
        *[
            f"- {label}: {_leader_text(comparison['leaders'][key], value_key)}"
            for label, key, value_key in (
                ("Best conservative score", "best_score", "score"),
                (
                    "Most genuine spectral recovery",
                    "best_frequency_recovery",
                    "frequency_limit_fraction",
                ),
                (
                    "Best structural recovery",
                    "best_structural_accuracy",
                    "gradient_correlation",
                ),
                (
                    "Least unsupported fine detail",
                    "least_false_detail",
                    "false_detail_fraction",
                ),
                (
                    "Fastest reconstruction",
                    "fastest_reconstruction",
                    "reconstruction_runtime_s",
                ),
            )
        ],
        "",
        "## Ranked Table",
        "",
        (
            "| Rank | Algorithm | Score | MSE | SSIM | Gradient Corr | Spectral Limit | "
            "False Detail | Recon Runtime (s) |"
        ),
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(comparison["rows"], start=1):
        lines.append(
            "| "
            f"{rank} | `{row['algorithm']}` | {_fmt(row['score'])} | {_fmt(row['mse'])} | "
            f"{_fmt(row['ssim_global'])} | {_fmt(row['gradient_correlation'])} | "
            f"{_fmt(row['frequency_limit_fraction'])} | {_fmt(row['false_detail_fraction'])} | "
            f"{_fmt(row['reconstruction_runtime_s'])} |"
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
    metadata = report.get("metadata", {})
    provenance = metadata.get("provenance", {})
    git = provenance.get("git", {}) if isinstance(provenance, dict) else {}
    ssim = float(image["ssim_global"])
    gradient = float(structure["gradient_correlation"])
    frequency_limit = float(frequency["correlation_0_5_limit_fraction"])
    false_fraction = float(false_detail["unsupported_energy_fraction"])
    score = min(ssim, gradient, frequency_limit) * (1.0 - false_fraction)
    return ComparisonRow(
        algorithm=str(report["algorithm"]),
        metrics_path=str(metrics_path),
        mse=float(image["mse"]),
        ssim_global=ssim,
        gradient_correlation=gradient,
        frequency_limit_fraction=frequency_limit,
        false_detail_fraction=false_fraction,
        reconstruction_runtime_s=_optional_float(metadata.get("reconstruction_runtime_s")),
        evaluation_runtime_s=_optional_float(metadata.get("evaluation_runtime_s")),
        git_commit=None if not isinstance(git, dict) else _optional_str(git.get("commit")),
        git_dirty=None if not isinstance(git, dict) else _optional_bool(git.get("dirty")),
        reference_limitations=_metadata_str_tuple(metadata, "reference_limitations"),
        score=score,
    )


def _leaders(rows: list[ComparisonRow]) -> dict[str, dict[str, Any] | None]:
    finite_runtime_rows = [row for row in rows if row.reconstruction_runtime_s is not None]
    return {
        "best_score": _leader(max(rows, key=lambda row: row.score), "score"),
        "best_frequency_recovery": _leader(
            max(rows, key=lambda row: row.frequency_limit_fraction),
            "frequency_limit_fraction",
        ),
        "best_structural_accuracy": _leader(
            max(rows, key=lambda row: row.gradient_correlation),
            "gradient_correlation",
        ),
        "least_false_detail": _leader(
            min(rows, key=lambda row: row.false_detail_fraction),
            "false_detail_fraction",
        ),
        "fastest_reconstruction": (
            _leader(
                min(finite_runtime_rows, key=lambda row: row.reconstruction_runtime_s or 0.0),
                "reconstruction_runtime_s",
            )
            if finite_runtime_rows
            else None
        ),
    }


def _leader(row: ComparisonRow, metric: str) -> dict[str, Any]:
    data = row.to_dict()
    return {
        "algorithm": row.algorithm,
        "metric": metric,
        "value": data[metric],
        "metrics_path": row.metrics_path,
    }


def _leader_text(leader: dict[str, Any] | None, value_key: str) -> str:
    if leader is None:
        return "`n/a`"
    return f"`{leader['algorithm']}` ({value_key}={_fmt(_optional_float(leader['value']))})"


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def _metadata_str_tuple(metadata: dict[str, Any], key: str) -> tuple[str, ...]:
    value = metadata.get(key, [])
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"
