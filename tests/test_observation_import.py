from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from seeingbench.cli import main


def test_cli_import_observation_supports_reference_study_path(tmp_path: Path) -> None:
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    reference = np.full((16, 16), 0.5, dtype=np.float64)
    np.save(frame_dir / "frame_a.npy", reference)
    np.save(frame_dir / "frame_b.npy", reference + 0.01)
    metadata_path = tmp_path / "observation.json"
    metadata_path.write_text(
        json.dumps(
            {
                "target": "Moon",
                "utc_start": "2026-08-15T00:46:34Z",
                "observer": {
                    "latitude": 51.5,
                    "longitude": -0.1,
                    "altitude_m": 45.0,
                },
            }
        ),
        encoding="utf-8",
    )
    case_dir = tmp_path / "observation-case"
    result_dir = tmp_path / "result"
    metrics_path = tmp_path / "metrics.json"
    reference_path = tmp_path / "reference.npy"
    np.save(reference_path, reference)

    assert (
        main(
            [
                "import-observation",
                "--output",
                str(case_dir),
                "--metadata",
                str(metadata_path),
                str(frame_dir / "*.npy"),
            ]
        )
        == 0
    )
    assert main(["baseline-stack", "--case", str(case_dir), "--output", str(result_dir)]) == 0
    assert (
        main(
            [
                "evaluate-reference",
                "--reference",
                str(reference_path),
                "--reconstruction",
                str(result_dir / "reconstruction.tif"),
                "--algorithm",
                "mean_stack",
                "--output",
                str(metrics_path),
                "--frequency-bins",
                "6",
            ]
        )
        == 0
    )

    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metadata["benchmark_mode"] == "real_observation"
    assert metadata["frame_count"] == 2
    assert metadata["observation"]["target"] == "Moon"
    assert not (case_dir / "truth").exists()
    assert (case_dir / "input" / "frame_000001.tif").exists()
    assert metrics["metadata"]["benchmark_mode"] == "standalone_reference"


def test_cli_import_observation_rejects_mismatched_frame_shapes(tmp_path: Path) -> None:
    first = tmp_path / "first.npy"
    second = tmp_path / "second.npy"
    np.save(first, np.ones((8, 8), dtype=np.float64))
    np.save(second, np.ones((9, 8), dtype=np.float64))

    try:
        main(
            [
                "import-observation",
                "--output",
                str(tmp_path / "case"),
                str(first),
                str(second),
            ]
        )
    except ValueError as exc:
        assert "same shape" in str(exc)
    else:
        raise AssertionError("import-observation accepted mismatched frame shapes")
