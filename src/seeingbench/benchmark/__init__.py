"""Benchmark case storage and evaluation orchestration."""

from seeingbench.benchmark.case import BenchmarkCase, save_simulation_case
from seeingbench.benchmark.compare import compare_metric_files
from seeingbench.benchmark.experiment import SyntheticSweepConfig, run_synthetic_sweep

__all__ = [
    "BenchmarkCase",
    "SyntheticSweepConfig",
    "compare_metric_files",
    "run_synthetic_sweep",
    "save_simulation_case",
]
