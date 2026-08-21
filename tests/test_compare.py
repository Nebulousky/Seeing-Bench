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
    assert comparison["rows"][0]["reconstruction_runtime_s"] == 2.0
    assert comparison["rows"][0]["git_commit"] == "abc123"
    assert comparison["rows"][0]["reference_provenance"]["logical_identifier"] == (
        "urn:nasa:pds:strong"
    )
    assert comparison["rows"][0]["reference_uncertainty"]["risk_level"] == "medium"
    assert comparison["reference_uncertainty_levels"] == ["medium"]
    assert comparison["leaders"]["best_score"]["algorithm"] == "strong"
    assert comparison["leaders"]["best_frequency_recovery"]["algorithm"] == "strong"
    assert comparison["leaders"]["least_false_detail"]["algorithm"] == "strong"


def test_comparison_markdown_contains_ranked_table(tmp_path: Path) -> None:
    first = _write_report(tmp_path / "a.json", "a", 0.8, 0.8, 0.8, 0.1)
    second = _write_report(tmp_path / "b.json", "b", 0.2, 0.2, 0.2, 0.4)

    markdown = render_comparison_markdown(compare_metric_files([first, second]))

    assert "# SeeingBench Comparison" in markdown
    assert "## Direct Answers" in markdown
    assert "## Reference Limitations" in markdown
    assert "## Reference Uncertainty" in markdown
    assert "`local_linear_orthographic_projection`" in markdown
    assert "| 1 | `a` |" in markdown
    assert "Recon Runtime" in markdown


def test_compare_score_uses_conservative_bottleneck(tmp_path: Path) -> None:
    candidate = _write_report(
        tmp_path / "candidate.json",
        "candidate",
        ssim=0.9,
        gradient=0.8,
        frequency_limit=0.4,
        false_detail=0.25,
    )

    comparison = compare_metric_files(
        [candidate, _write_report(tmp_path / "other.json", "other", 0.1, 0.1, 0.1, 0.0)]
    )

    row = next(row for row in comparison["rows"] if row["algorithm"] == "candidate")
    assert row["score"] == 0.4 * 0.75
    assert "min(global SSIM" in comparison["ranking_basis"]


def test_compare_reports_distinct_metric_leaders(tmp_path: Path) -> None:
    score = _write_report(
        tmp_path / "score.json",
        "score",
        ssim=0.9,
        gradient=0.9,
        frequency_limit=0.8,
        false_detail=0.1,
        runtime_s=3.0,
    )
    recovery = _write_report(
        tmp_path / "recovery.json",
        "recovery",
        ssim=0.6,
        gradient=0.6,
        frequency_limit=0.95,
        false_detail=0.3,
        runtime_s=2.0,
    )
    conservative = _write_report(
        tmp_path / "conservative.json",
        "conservative",
        ssim=0.5,
        gradient=0.5,
        frequency_limit=0.5,
        false_detail=0.01,
        runtime_s=1.0,
    )

    comparison = compare_metric_files([score, recovery, conservative])

    assert comparison["leaders"]["best_score"]["algorithm"] == "score"
    assert comparison["leaders"]["best_frequency_recovery"]["algorithm"] == "recovery"
    assert comparison["leaders"]["least_false_detail"]["algorithm"] == "conservative"
    assert comparison["leaders"]["fastest_reconstruction"]["algorithm"] == "conservative"


def _write_report(
    path: Path,
    algorithm: str,
    ssim: float,
    gradient: float,
    frequency_limit: float,
    false_detail: float,
    runtime_s: float | None = 2.0,
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
                "metadata": {
                    "reconstruction_runtime_s": runtime_s,
                    "evaluation_runtime_s": 0.1,
                    "reference_limitations": ["local_linear_orthographic_projection"],
                    "reference_provenance": {
                        "logical_identifier": f"urn:nasa:pds:{algorithm}",
                    },
                    "reference_uncertainty": {
                        "risk_level": "medium",
                        "factors": [
                            {
                                "source": "local_linear_orthographic_projection",
                                "level": "medium",
                                "description": "local projection approximation",
                            }
                        ],
                    },
                    "provenance": {
                        "git": {
                            "commit": "abc123",
                            "dirty": False,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path
