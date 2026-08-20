"""Adapters for external reconstruction engines."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from seeingbench.benchmark.case import load_benchmark_case
from seeingbench.io.images import load_grayscale_image, write_grayscale_tiff
from seeingbench.reconstruction.alignment import constant_displacement, estimate_integer_translation
from seeingbench.simulation.warp import apply_warp


class ReconstructionAdapter(Protocol):
    """Filesystem-based contract for reconstruction engines."""

    name: str

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        """Prepare input files for execution."""

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        """Run the external reconstruction."""

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        """Ensure mandatory output files exist in ``result_dir``."""


@dataclass(frozen=True)
class ManualImportAdapter:
    """Adapter for manually supplied ``reconstruction.tif`` results."""

    name: str = "manual"

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        result_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        return None

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        reconstruction = result_dir / "reconstruction.tif"
        if not reconstruction.exists():
            raise FileNotFoundError(f"manual result is missing {reconstruction}")


@dataclass(frozen=True)
class CommandLineAdapter:
    """Adapter for command-line tools that read a case directory and write a result."""

    command: tuple[str, ...]
    name: str = "command_line"

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        result_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        if not self.command:
            raise ValueError("command must not be empty")
        started = time.perf_counter()
        completed = subprocess.run(
            [
                part.format(case=str(benchmark_case), result=str(result_dir))
                for part in self.command
            ],
            cwd=benchmark_case.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        metadata = {
            "adapter": self.name,
            "command": list(self.command),
            "returncode": completed.returncode,
            "runtime_s": time.perf_counter() - started,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"reconstruction command failed with code {completed.returncode}")

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        if not (result_dir / "reconstruction.tif").exists():
            raise FileNotFoundError("command did not produce result/reconstruction.tif")


@dataclass(frozen=True)
class BaselineStackAdapter:
    """Simple average stack baseline for synthetic cases."""

    name: str = "mean_stack"

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        result_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        frames = [
            load_grayscale_image(path)
            for path in sorted((benchmark_case / "input").glob("frame_*.tif"))
        ]
        if not frames:
            raise FileNotFoundError(f"no input frames found under {benchmark_case / 'input'}")
        shape = frames[0].shape
        if any(frame.shape != shape for frame in frames):
            raise ValueError("all input frames must have the same shape")
        reconstruction = np.mean(np.stack(frames), axis=0).astype(np.float64)
        write_grayscale_tiff(result_dir / "reconstruction.tif", reconstruction)
        (result_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "adapter": self.name,
                    "frame_count": len(frames),
                    "method": "arithmetic mean of input frames",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        if not (result_dir / "reconstruction.tif").exists():
            raise FileNotFoundError("baseline stack did not produce reconstruction.tif")


@dataclass(frozen=True)
class TranslationAlignedStackAdapter:
    """Estimate global frame translations and average aligned frames."""

    name: str = "translation_stack"

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "warp_fields").mkdir(parents=True, exist_ok=True)

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        frames = [
            load_grayscale_image(path)
            for path in sorted((benchmark_case / "input").glob("frame_*.tif"))
        ]
        if not frames:
            raise FileNotFoundError(f"no input frames found under {benchmark_case / 'input'}")
        shape = frames[0].shape
        if any(frame.shape != shape for frame in frames):
            raise ValueError("all input frames must have the same shape")

        reference = frames[0]
        shifts: list[dict[str, float | int]] = []
        estimated_fields: list[np.ndarray] = []
        aligned_frames: list[np.ndarray] = []
        for index, frame in enumerate(frames, start=1):
            shift_x, shift_y = estimate_integer_translation(reference, frame)
            shifts.append({"frame": index, "u_px": shift_x, "v_px": shift_y})
            estimated_field = constant_displacement(shape, shift_x, shift_y)
            estimated_fields.append(estimated_field)
            aligned_frames.append(apply_warp(frame, -estimated_field))

        reconstruction = np.clip(np.mean(np.stack(aligned_frames), axis=0), 0.0, 1.0).astype(
            np.float64
        )
        write_grayscale_tiff(result_dir / "reconstruction.tif", reconstruction)

        warp_dir = result_dir / "warp_fields"
        warp_dir.mkdir(parents=True, exist_ok=True)
        for index, field in enumerate(estimated_fields, start=1):
            np.save(warp_dir / f"warp_{index:06d}.npy", field)

        (result_dir / "estimated_global_translations.json").write_text(
            json.dumps(shifts, indent=2),
            encoding="utf-8",
        )
        (result_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "adapter": self.name,
                    "frame_count": len(frames),
                    "method": "phase-correlation integer global translation alignment",
                    "reference_frame": 1,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        if not (result_dir / "reconstruction.tif").exists():
            raise FileNotFoundError("translation stack did not produce reconstruction.tif")


@dataclass(frozen=True)
class OracleAlignedStackAdapter:
    """Synthetic-only upper bound that aligns frames with retained truth warps."""

    name: str = "oracle_aligned_stack"

    def prepare(self, benchmark_case: Path, result_dir: Path) -> None:
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "warp_fields").mkdir(parents=True, exist_ok=True)

    def execute(self, benchmark_case: Path, result_dir: Path) -> None:
        case = load_benchmark_case(benchmark_case)
        frames = [
            load_grayscale_image(path)
            for path in sorted((benchmark_case / "input").glob("frame_*.tif"))
        ]
        if len(frames) != len(case.warp_fields):
            raise ValueError(
                "input frame count must match retained warp truth count for oracle alignment"
            )

        aligned = np.stack(
            [apply_warp(frame, -warp) for frame, warp in zip(frames, case.warp_fields, strict=True)]
        )
        reconstruction = np.clip(np.mean(aligned, axis=0), 0.0, 1.0).astype(np.float64)
        write_grayscale_tiff(result_dir / "reconstruction.tif", reconstruction)

        warp_dir = result_dir / "warp_fields"
        warp_dir.mkdir(parents=True, exist_ok=True)
        for index, warp in enumerate(case.warp_fields, start=1):
            np.save(warp_dir / f"warp_{index:06d}.npy", warp)

        (result_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "adapter": self.name,
                    "frame_count": len(frames),
                    "method": "mean stack after applying negative retained synthetic warp fields",
                    "synthetic_oracle": True,
                    "validation_boundary": (
                        "uses SeeingBench-retained truth and must not be treated as a "
                        "deployable reconstruction algorithm"
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def collect_results(self, benchmark_case: Path, result_dir: Path) -> None:
        if not (result_dir / "reconstruction.tif").exists():
            raise FileNotFoundError("oracle stack did not produce reconstruction.tif")


def copy_manual_reconstruction(source: Path, result_dir: Path) -> None:
    """Copy a user-supplied reconstruction into the standard result contract."""

    if not source.exists():
        raise FileNotFoundError(source)
    result_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, result_dir / "reconstruction.tif")
