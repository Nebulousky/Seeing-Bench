"""Filesystem contract for synthetic benchmark cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from seeingbench.io.images import load_grayscale_image, write_grayscale_tiff
from seeingbench.simulation.atmosphere import SimulationResult

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class BenchmarkCase:
    """A benchmark case loaded from disk."""

    root: Path
    metadata: dict[str, Any]
    latent_truth: FloatArray
    warp_fields: FloatArray


def save_simulation_case(result: SimulationResult, root: Path) -> None:
    """Save a synthetic case using the external reconstruction filesystem contract."""

    input_dir = root / "input"
    truth_dir = root / "truth"
    input_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)

    for index, frame in enumerate(result.frames, start=1):
        write_grayscale_tiff(input_dir / f"frame_{index:06d}.tif", frame)
    write_grayscale_tiff(truth_dir / "latent.tif", result.latent_truth)

    for index, warp in enumerate(result.warp_fields, start=1):
        np.save(truth_dir / f"warp_{index:06d}.npy", warp)
    component_arrays: dict[str, Any] = dict(result.warp_components)
    np.savez_compressed(truth_dir / "warp_components.npz", **component_arrays)

    metadata = {
        **result.metadata,
        "psf_information": result.psf_information,
        "noise_information": result.noise_information,
        "files": {
            "input_pattern": "input/frame_000001.tif",
            "truth_latent": "truth/latent.tif",
            "truth_warp_pattern": "truth/warp_000001.npy",
            "truth_warp_components": "truth/warp_components.npz",
        },
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def load_benchmark_case(root: Path) -> BenchmarkCase:
    """Load the mandatory truth files for a synthetic benchmark case."""

    metadata_path = root / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing benchmark metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    latent = load_grayscale_image(root / "truth" / "latent.tif")
    warp_paths = sorted((root / "truth").glob("warp_*.npy"))
    if not warp_paths:
        raise FileNotFoundError(f"no warp truth fields found under {root / 'truth'}")
    warp_fields = np.stack([np.load(path).astype(np.float64, copy=False) for path in warp_paths])
    return BenchmarkCase(
        root=root,
        metadata=metadata,
        latent_truth=latent,
        warp_fields=warp_fields,
    )
