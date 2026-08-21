"""Comparative study orchestration for built-in reconstruction baselines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seeingbench.benchmark.compare import write_comparison_json, write_comparison_markdown
from seeingbench.benchmark.runner import evaluate_reconstruction, save_evaluation_report
from seeingbench.reconstruction.adapter import (
    BaselineStackAdapter,
    LocalBlockAlignedStackAdapter,
    TranslationAlignedStackAdapter,
)

BUILTIN_BASELINE_ALGORITHMS = (
    "mean_stack",
    "translation_stack",
    "local_block_stack",
)


def run_builtin_baseline_study(
    case_dir: Path,
    output_root: Path,
    frequency_bins: int = 24,
    local_block_size_px: int = 32,
) -> dict[str, Any]:
    """Run built-in baselines against the same case and compare their metrics."""

    if frequency_bins <= 0:
        raise ValueError("frequency_bins must be positive")
    if local_block_size_px <= 0:
        raise ValueError("local_block_size_px must be positive")

    output_root.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    metrics_paths: list[Path] = []
    for algorithm in BUILTIN_BASELINE_ALGORITHMS:
        result_dir = output_root / "results" / algorithm
        adapter = _adapter_for(algorithm, local_block_size_px)
        adapter.prepare(case_dir, result_dir)
        adapter.execute(case_dir, result_dir)
        adapter.collect_results(case_dir, result_dir)
        metrics_path = result_dir / "metrics.json"
        report = evaluate_reconstruction(
            case_dir=case_dir,
            result_dir=result_dir,
            algorithm=algorithm,
            frequency_bins=frequency_bins,
        )
        save_evaluation_report(report, metrics_path)
        metrics_paths.append(metrics_path)
        result_rows.append(
            {
                "algorithm": algorithm,
                "result_dir": str(result_dir),
                "metrics": str(metrics_path),
            }
        )

    comparison_json = output_root / "comparison.json"
    comparison_markdown = output_root / "comparison.md"
    write_comparison_json(metrics_paths, comparison_json)
    write_comparison_markdown(metrics_paths, comparison_markdown)
    summary = {
        "case_dir": str(case_dir),
        "output_root": str(output_root),
        "algorithm_count": len(result_rows),
        "algorithms": result_rows,
        "comparison_json": str(comparison_json),
        "comparison_markdown": str(comparison_markdown),
        "frequency_bins": frequency_bins,
        "local_block_size_px": local_block_size_px,
        "validation_boundary": (
            "study adapters consume only benchmark input frames; evaluation consumes retained "
            "truth after reconstruction outputs are written"
        ),
    }
    (output_root / "study-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def _adapter_for(
    algorithm: str,
    local_block_size_px: int,
) -> BaselineStackAdapter | TranslationAlignedStackAdapter | LocalBlockAlignedStackAdapter:
    if algorithm == "mean_stack":
        return BaselineStackAdapter()
    if algorithm == "translation_stack":
        return TranslationAlignedStackAdapter()
    if algorithm == "local_block_stack":
        return LocalBlockAlignedStackAdapter(block_size_px=local_block_size_px)
    raise ValueError(f"unknown built-in baseline algorithm: {algorithm}")
