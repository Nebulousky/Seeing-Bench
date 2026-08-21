from __future__ import annotations

import json
from pathlib import Path

from seeingbench.cli import main


def test_cli_builtin_baseline_study_runs_and_compares_all_baselines(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    study_dir = tmp_path / "study"

    assert (
        main(
            [
                "simulate",
                "--output",
                str(case_dir),
                "--frames",
                "3",
                "--height",
                "32",
                "--width",
                "32",
                "--seed",
                "11",
                "--noise-sigma",
                "0.0",
                "--warp-scale",
                "0.2",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "study",
                "builtin-baselines",
                "--case",
                str(case_dir),
                "--output",
                str(study_dir),
                "--frequency-bins",
                "6",
                "--local-block-size",
                "16",
            ]
        )
        == 0
    )

    summary = json.loads((study_dir / "study-summary.json").read_text(encoding="utf-8"))
    comparison = json.loads((study_dir / "comparison.json").read_text(encoding="utf-8"))
    assert summary["algorithm_count"] == 3
    assert {row["algorithm"] for row in summary["algorithms"]} == {
        "mean_stack",
        "translation_stack",
        "local_block_stack",
    }
    assert len(comparison["rows"]) == 3
    assert "validation_boundary" in summary
    assert (study_dir / "comparison.md").exists()
    for row in summary["algorithms"]:
        metrics_path = Path(row["metrics"])
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert metrics["algorithm"] == row["algorithm"]
        assert metrics["metadata"]["reconstruction_runtime_s"] is not None
        assert metrics["metadata"]["evaluation_runtime_s"] > 0.0
        assert (Path(row["result_dir"]) / "reconstruction.tif").exists()
