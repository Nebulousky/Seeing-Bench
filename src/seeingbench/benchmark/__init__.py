"""Benchmark case storage and evaluation orchestration."""

from seeingbench.benchmark.case import BenchmarkCase, save_simulation_case
from seeingbench.benchmark.compare import compare_metric_files

__all__ = ["BenchmarkCase", "compare_metric_files", "save_simulation_case"]
