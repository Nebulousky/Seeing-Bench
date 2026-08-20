from __future__ import annotations

import json
from pathlib import Path

from seeingbench.cli import main


def test_cli_generates_baseline_and_evaluates_case(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    result_dir = tmp_path / "result"
    diagnostics_dir = tmp_path / "diagnostics"
    metrics_path = result_dir / "metrics.json"
    report_path = result_dir / "report.md"

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
                "7",
                "--noise-sigma",
                "0.0",
            ]
        )
        == 0
    )
    assert main(["baseline-stack", "--case", str(case_dir), "--output", str(result_dir)]) == 0
    assert (
        main(
            [
                "evaluate",
                "--case",
                str(case_dir),
                "--result",
                str(result_dir),
                "--algorithm",
                "mean_stack",
                "--output",
                str(metrics_path),
                "--diagnostics",
                str(diagnostics_dir),
                "--frequency-bins",
                "6",
            ]
        )
        == 0
    )

    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert report["algorithm"] == "mean_stack"
    assert "image_similarity" in report
    assert "frequency_recovery" in report
    assert (diagnostics_dir / "frequency_recovery.csv").exists()
    assert (diagnostics_dir / "truth.tif").exists()
    assert (diagnostics_dir / "reconstruction.tif").exists()
    assert (diagnostics_dir / "degraded_frame_000001.tif").exists()
    assert (diagnostics_dir / "blink_pair.npz").exists()
    assert (diagnostics_dir / "warp_magnitude_frame_000001.tif").exists()
    assert (diagnostics_dir / "warp_summary.json").exists()

    assert (
        main(
            [
                "report",
                "--metrics",
                str(metrics_path),
                "--output",
                str(report_path),
            ]
        )
        == 0
    )
    assert "SeeingBench Report: mean_stack" in report_path.read_text(encoding="utf-8")

    comparison_path = tmp_path / "comparison.md"
    assert (
        main(
            [
                "compare",
                str(result_dir),
                str(metrics_path),
                "--output",
                str(comparison_path),
            ]
        )
        == 0
    )
    assert "SeeingBench Comparison" in comparison_path.read_text(encoding="utf-8")
