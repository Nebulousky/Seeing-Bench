from __future__ import annotations

import json
import sys
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


def test_cli_configured_study_runs_builtin_and_external_command(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    study_dir = tmp_path / "study"
    script_path = tmp_path / "external_tool.py"
    version_script_path = tmp_path / "external_version.py"
    config_path = tmp_path / "study.json"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import shutil",
                "import sys",
                "case = Path(sys.argv[1])",
                "result = Path(sys.argv[2])",
                "result.mkdir(parents=True, exist_ok=True)",
                "shutil.copy2(case / 'input' / 'frame_000001.tif', result / 'reconstruction.tif')",
            ]
        ),
        encoding="utf-8",
    )
    version_script_path.write_text("print('external-tool 1.2.3')\n", encoding="utf-8")

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
                "23",
                "--noise-sigma",
                "0.0",
                "--warp-scale",
                "0.2",
            ]
        )
        == 0
    )
    config_path.write_text(
        json.dumps(
            {
                "case": str(case_dir),
                "frequency_bins": 6,
                "algorithms": [
                    {
                        "name": "mean_stack",
                        "kind": "builtin",
                        "builtin": "mean_stack",
                    },
                    {
                        "name": "external_echo",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            str(script_path),
                            "{case}",
                            "{result}",
                        ],
                        "version_command": [
                            sys.executable,
                            str(version_script_path),
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "study",
                "run-config",
                "--config",
                str(config_path),
                "--output",
                str(study_dir),
            ]
        )
        == 0
    )

    summary = json.loads((study_dir / "study-summary.json").read_text(encoding="utf-8"))
    comparison = json.loads((study_dir / "comparison.json").read_text(encoding="utf-8"))
    assert summary["algorithm_count"] == 2
    assert {row["algorithm"] for row in summary["algorithms"]} == {
        "mean_stack",
        "external_echo",
    }
    assert {row["kind"] for row in summary["algorithms"]} == {"builtin", "command"}
    assert len(comparison["rows"]) == 2
    assert summary["provenance"]["git"]["commit"]
    external = next(row for row in summary["algorithms"] if row["algorithm"] == "external_echo")
    metadata = json.loads((Path(external["result_dir"]) / "metadata.json").read_text())
    assert metadata["adapter"] == "external_echo"
    assert metadata["runtime_s"] > 0.0
    assert metadata["version"]["returncode"] == 0
    assert metadata["version"]["stdout"] == "external-tool 1.2.3"
    metrics = json.loads(Path(external["metrics"]).read_text(encoding="utf-8"))
    assert metrics["metadata"]["reconstruction_metadata"]["version"]["stdout"] == (
        "external-tool 1.2.3"
    )


def test_cli_configured_study_accepts_utf8_bom_config(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    study_dir = tmp_path / "study"
    config_path = tmp_path / "study.json"

    assert (
        main(
            [
                "simulate",
                "--output",
                str(case_dir),
                "--frames",
                "2",
                "--height",
                "32",
                "--width",
                "32",
                "--seed",
                "29",
                "--noise-sigma",
                "0.0",
                "--warp-scale",
                "0.1",
            ]
        )
        == 0
    )
    payload = json.dumps(
        {
            "case": str(case_dir),
            "frequency_bins": 6,
            "algorithms": [
                {"name": "mean_stack", "kind": "builtin", "builtin": "mean_stack"},
                {
                    "name": "translation_stack",
                    "kind": "builtin",
                    "builtin": "translation_stack",
                },
            ],
        }
    )
    config_path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))

    assert (
        main(
            [
                "study",
                "run-config",
                "--config",
                str(config_path),
                "--output",
                str(study_dir),
            ]
        )
        == 0
    )

    summary = json.loads((study_dir / "study-summary.json").read_text(encoding="utf-8"))
    assert summary["algorithm_count"] == 2
    assert summary["provenance"]["git"]["commit"]


def test_cli_study_tool_readiness_reports_command_availability(tmp_path: Path) -> None:
    config_path = tmp_path / "study.json"
    readiness_path = tmp_path / "tool-readiness.json"
    config_path.write_text(
        json.dumps(
            {
                "case": str(tmp_path / "case"),
                "frequency_bins": 6,
                "algorithms": [
                    {"name": "mean_stack", "kind": "builtin", "builtin": "mean_stack"},
                    {
                        "name": "python_tool",
                        "kind": "command",
                        "command": [sys.executable, "--version"],
                        "version_command": [sys.executable, "--version"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "study",
                "tool-readiness",
                "--config",
                str(config_path),
                "--output",
                str(readiness_path),
            ]
        )
        == 0
    )

    report = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert report["ready"]
    assert report["algorithm_count"] == 2
    python_tool = next(row for row in report["algorithms"] if row["algorithm"] == "python_tool")
    assert python_tool["resolved_executable"] == sys.executable
    assert python_tool["resolved_version_executable"] == sys.executable
    assert report["validation_boundary"]


def test_cli_study_tool_readiness_returns_nonzero_for_missing_command(tmp_path: Path) -> None:
    config_path = tmp_path / "study.json"
    config_path.write_text(
        json.dumps(
            {
                "case": str(tmp_path / "case"),
                "frequency_bins": 6,
                "algorithms": [
                    {"name": "mean_stack", "kind": "builtin", "builtin": "mean_stack"},
                    {
                        "name": "missing_tool",
                        "kind": "command",
                        "command": ["seeingbench-definitely-missing-tool"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "study",
                "tool-readiness",
                "--config",
                str(config_path),
            ]
        )
        == 1
    )


def test_cli_reference_configured_study_compares_against_standalone_reference(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case"
    study_dir = tmp_path / "reference-study"
    script_path = tmp_path / "external_tool.py"
    config_path = tmp_path / "reference-study.json"
    reference_metadata_path = tmp_path / "reference-report.json"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import shutil",
                "import sys",
                "case = Path(sys.argv[1])",
                "result = Path(sys.argv[2])",
                "result.mkdir(parents=True, exist_ok=True)",
                "shutil.copy2(case / 'input' / 'frame_000001.tif', result / 'reconstruction.tif')",
            ]
        ),
        encoding="utf-8",
    )

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
                "37",
                "--noise-sigma",
                "0.0",
                "--warp-scale",
                "0.2",
            ]
        )
        == 0
    )
    reference_metadata_path.write_text(
        json.dumps({"limitations": ["local_linear_orthographic_projection"]}),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "case": str(case_dir),
                "reference": str(case_dir / "truth" / "latent.tif"),
                "reference_metadata": str(reference_metadata_path),
                "frequency_bins": 6,
                "register_translation": True,
                "registration_rotation_degrees": [0.0],
                "registration_scales": [1.0],
                "algorithms": [
                    {"name": "mean_stack", "kind": "builtin", "builtin": "mean_stack"},
                    {
                        "name": "external_echo",
                        "kind": "command",
                        "command": [
                            sys.executable,
                            str(script_path),
                            "{case}",
                            "{result}",
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "study",
                "run-reference-config",
                "--config",
                str(config_path),
                "--output",
                str(study_dir),
            ]
        )
        == 0
    )

    summary = json.loads((study_dir / "study-summary.json").read_text(encoding="utf-8"))
    comparison = json.loads((study_dir / "comparison.json").read_text(encoding="utf-8"))
    assert summary["benchmark_mode"] == "standalone_reference_study"
    assert summary["register_translation"]
    assert summary["registration_rotation_degrees"] == [0.0]
    assert summary["registration_scales"] == [1.0]
    assert summary["reference_path"] == str(case_dir / "truth" / "latent.tif")
    assert summary["reference_metadata_path"] == str(reference_metadata_path)
    assert summary["provenance"]["git"]["commit"]
    assert {row["kind"] for row in summary["algorithms"]} == {"builtin", "command"}
    assert len(comparison["rows"]) == 2
    for row in summary["algorithms"]:
        metrics = json.loads(Path(row["metrics"]).read_text(encoding="utf-8"))
        assert metrics["metadata"]["benchmark_mode"] == "standalone_reference"
        assert metrics["metadata"]["registration"]["method"] == "global_similarity_grid_search"
        assert metrics["metadata"]["reference_limitations"] == [
            "local_linear_orthographic_projection"
        ]
        assert metrics["metadata"]["reconstruction_runtime_s"] is not None
        assert metrics["metadata"]["validation_boundary"]
