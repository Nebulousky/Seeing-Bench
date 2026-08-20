from __future__ import annotations

import json
from pathlib import Path

from seeingbench.benchmark.compare import compare_metric_files, render_comparison_markdown


def test_compare_ranks_higher_recovery_and_lower_false_detail(tmp_path: Path) -> None:
    weak = _write_report(tmp_path / "weak" / "metrics.json", "weak", 0.5, 0.4, 0.2, 0.3)
    strong = _write_report(tmp_path / "strong" / "metrics.json", "strong", 0.8, 0.7, 0.5, 0.1)

    comparison = compare_metric_files([weak.parent, strong.parent])

    assert comparison["rows"][0]["algorithm"] == "strong"
    assert "false detail" in comparison["ranking_basis"]


def test_comparison_markdown_contains_ranked_table(tmp_path: Path) -> None:
    first = _write_report(tmp_path / "a.json", "a", 0.8, 0.8, 0.8, 0.1)
    second = _write_report(tmp_path / "b.json", "b", 0.2, 0.2, 0.2, 0.4)

    markdown = render_comparison_markdown(compare_metric_files([first, second]))

    assert "# SeeingBench Comparison" in markdown
    assert "| 1 | `a` |" in markdown


def _write_report(
    path: Path,
    algorithm: str,
    ssim: float,
    gradient: float,
    frequency_limit: float,
    false_detail: float,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "algorithm": algorithm,
                "image_similarity": {"mse": 0.01, "psnr_db": 20.0, "ssim_global": ssim},
                "structural_accuracy": {"gradient_correlation": gradient},
                "frequency_recovery": {"correlation_0_5_limit_fraction": frequency_limit},
                "false_detail": {"unsupported_energy_fraction": false_detail},
                "metadata": {"runtime_s": 1.0},
            }
        ),
        encoding="utf-8",
    )
    return path
