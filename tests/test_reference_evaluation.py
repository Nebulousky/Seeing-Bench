from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from seeingbench.benchmark.reference_runner import evaluate_reference_reconstruction
from seeingbench.cli import main
from seeingbench.reconstruction.alignment import constant_displacement
from seeingbench.simulation.source import crater_field
from seeingbench.simulation.warp import apply_warp


def test_reference_evaluation_translation_registration_improves_mse(tmp_path: Path) -> None:
    reference = crater_field((64, 64), seed=17)
    reconstruction = apply_warp(reference, constant_displacement(reference.shape, 2.0, -1.0))
    reference_path = tmp_path / "reference.npy"
    reconstruction_path = tmp_path / "reconstruction.npy"
    np.save(reference_path, reference)
    np.save(reconstruction_path, reconstruction)

    raw = evaluate_reference_reconstruction(
        reference_path,
        reconstruction_path,
        algorithm="shifted",
        frequency_bins=8,
        register_translation=False,
    )
    registered = evaluate_reference_reconstruction(
        reference_path,
        reconstruction_path,
        algorithm="shifted",
        frequency_bins=8,
        register_translation=True,
    )

    assert registered.image_similarity["mse"] < raw.image_similarity["mse"]
    assert registered.metadata["registration"]["method"] == "integer_phase_correlation_translation"
    assert registered.metadata["benchmark_mode"] == "standalone_reference"


def test_cli_evaluate_reference_writes_metrics_json(tmp_path: Path) -> None:
    reference = crater_field((32, 32), seed=19)
    reference_path = tmp_path / "reference.npy"
    reconstruction_path = tmp_path / "reconstruction.npy"
    metrics_path = tmp_path / "metrics.json"
    np.save(reference_path, reference)
    np.save(reconstruction_path, reference.copy())

    assert (
        main(
            [
                "evaluate-reference",
                "--reference",
                str(reference_path),
                "--reconstruction",
                str(reconstruction_path),
                "--algorithm",
                "perfect",
                "--output",
                str(metrics_path),
                "--frequency-bins",
                "6",
            ]
        )
        == 0
    )

    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert report["algorithm"] == "perfect"
    assert report["metadata"]["benchmark_mode"] == "standalone_reference"
    assert report["image_similarity"]["mse"] == 0.0
