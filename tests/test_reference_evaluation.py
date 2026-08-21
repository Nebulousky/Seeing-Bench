from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from seeingbench.benchmark.reference_runner import evaluate_reference_reconstruction
from seeingbench.benchmark.registration import apply_global_similarity_transform
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
    assert registered.metadata["reconstruction_runtime_s"] is None
    assert registered.metadata["evaluation_runtime_s"] > 0.0


def test_reference_evaluation_similarity_registration_improves_mse(tmp_path: Path) -> None:
    reference = crater_field((64, 64), seed=44)
    reconstruction = apply_global_similarity_transform(
        reference,
        rotation_degrees=4.0,
        scale=1.04,
    )
    reference_path = tmp_path / "reference.npy"
    reconstruction_path = tmp_path / "reconstruction.npy"
    np.save(reference_path, reference)
    np.save(reconstruction_path, reconstruction)

    raw = evaluate_reference_reconstruction(
        reference_path,
        reconstruction_path,
        algorithm="rotated",
        frequency_bins=8,
    )
    registered = evaluate_reference_reconstruction(
        reference_path,
        reconstruction_path,
        algorithm="rotated",
        frequency_bins=8,
        registration_rotation_degrees=(0.0, -4.0, 4.0),
        registration_scales=(1.0, 1.04, 1.0 / 1.04),
    )

    registration = registered.metadata["registration"]
    assert registered.image_similarity["mse"] < raw.image_similarity["mse"]
    assert registration["method"] == "global_similarity_grid_search"
    assert registration["selected_rotation_degrees"] == -4.0
    assert registration["selected_scale"] == 1.0 / 1.04
    assert registration["candidate_count"] == 9


def test_reference_evaluation_uses_reconstruction_metadata_runtime(tmp_path: Path) -> None:
    reference = crater_field((32, 32), seed=18)
    reference_path = tmp_path / "reference.npy"
    reconstruction_path = tmp_path / "reconstruction.npy"
    reference_metadata_path = tmp_path / "reference-report.json"
    metadata_path = tmp_path / "metadata.json"
    np.save(reference_path, reference)
    np.save(reconstruction_path, reference.copy())
    reference_metadata_path.write_text(
        json.dumps(
            {
                "reference_count": 1,
                "limitations": ["local_linear_orthographic_projection"],
            }
        ),
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps({"adapter": "external", "runtime_s": 1.25}),
        encoding="utf-8",
    )

    report = evaluate_reference_reconstruction(
        reference_path,
        reconstruction_path,
        algorithm="external",
        frequency_bins=6,
        reference_metadata_path=reference_metadata_path,
        reconstruction_metadata_path=metadata_path,
    )

    assert report.metadata["reconstruction_runtime_s"] == 1.25
    assert report.metadata["reconstruction_metadata"]["adapter"] == "external"
    assert report.metadata["reference_metadata"]["reference_count"] == 1
    assert report.metadata["reference_limitations"] == ["local_linear_orthographic_projection"]
    assert report.metadata["provenance"]["git"]["commit"]
    assert isinstance(report.metadata["provenance"]["git"]["dirty"], bool)


def test_cli_evaluate_reference_writes_metrics_json(tmp_path: Path) -> None:
    reference = crater_field((32, 32), seed=19)
    reference_path = tmp_path / "reference.npy"
    reconstruction_path = tmp_path / "reconstruction.npy"
    reference_metadata_path = tmp_path / "reference-report.json"
    metrics_path = tmp_path / "metrics.json"
    np.save(reference_path, reference)
    np.save(reconstruction_path, reference.copy())
    reference_metadata_path.write_text(
        json.dumps({"limitations": ["simple_lambertian_illumination_model"]}),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "evaluate-reference",
                "--reference",
                str(reference_path),
                "--reference-metadata",
                str(reference_metadata_path),
                "--reconstruction",
                str(reconstruction_path),
                "--algorithm",
                "perfect",
                "--output",
                str(metrics_path),
                "--frequency-bins",
                "6",
                "--registration-rotation-deg",
                "0",
                "--registration-scale",
                "1",
            ]
        )
        == 0
    )

    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert report["algorithm"] == "perfect"
    assert report["metadata"]["benchmark_mode"] == "standalone_reference"
    assert report["metadata"]["registration"]["method"] == "global_similarity_grid_search"
    assert report["metadata"]["reference_limitations"] == ["simple_lambertian_illumination_model"]
    assert report["image_similarity"]["mse"] == 0.0
