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

from seeingbench.io.images import load_grayscale_image, write_grayscale_tiff


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


def copy_manual_reconstruction(source: Path, result_dir: Path) -> None:
    """Copy a user-supplied reconstruction into the standard result contract."""

    if not source.exists():
        raise FileNotFoundError(source)
    result_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, result_dir / "reconstruction.tif")
