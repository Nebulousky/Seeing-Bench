"""Benchmark case storage and evaluation orchestration."""

from seeingbench.benchmark.case import BenchmarkCase, save_simulation_case
from seeingbench.benchmark.compare import compare_metric_files

__all__ = [
    "BenchmarkCase",
    "SyntheticSweepConfig",
    "compare_metric_files",
    "run_synthetic_sweep",
    "save_simulation_case",
]


def __getattr__(name: str) -> object:
    if name == "SyntheticSweepConfig":
        from seeingbench.benchmark.experiment import SyntheticSweepConfig

        return SyntheticSweepConfig
    if name == "run_synthetic_sweep":
        from seeingbench.benchmark.experiment import run_synthetic_sweep

        return run_synthetic_sweep
    raise AttributeError(f"module 'seeingbench.benchmark' has no attribute {name!r}")
