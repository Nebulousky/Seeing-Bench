"""Synthetic experiment sweeps for empirical benchmark validation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from seeingbench.benchmark.case import save_simulation_case
from seeingbench.benchmark.result import EvaluationReport
from seeingbench.benchmark.runner import evaluate_reconstruction, save_evaluation_report
from seeingbench.io.images import load_grayscale_image, write_grayscale_tiff
from seeingbench.reconstruction.adapter import BaselineStackAdapter, OracleAlignedStackAdapter
from seeingbench.simulation.atmosphere import SeeingModel
from seeingbench.simulation.config import SeeingSimulationConfig, WarpScaleConfig
from seeingbench.simulation.source import crater_field


@dataclass(frozen=True)
class SyntheticSweepConfig:
    """Configuration for a compact synthetic parameter sweep."""

    name: str = "phase1-smoke"
    height: int = 64
    width: int = 64
    crater_count: int = 40
    source_seed: int = 0
    frame_count: int = 12
    random_seed: int = 0
    temporal_correlation: float = 0.85
    warp_strengths: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)
    noise_sigmas: tuple[float, ...] = (0.0, 0.01, 0.03, 0.05)
    frequency_bins: int = 12
    base_warp_scales: tuple[WarpScaleConfig, ...] = (
        WarpScaleConfig("large", amplitude_px=1.5, correlation_px=64.0),
        WarpScaleConfig("medium", amplitude_px=0.7, correlation_px=24.0),
        WarpScaleConfig("fine", amplitude_px=0.25, correlation_px=8.0),
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyntheticSweepConfig:
        known = {
            "name",
            "height",
            "width",
            "crater_count",
            "source_seed",
            "frame_count",
            "random_seed",
            "temporal_correlation",
            "warp_strengths",
            "noise_sigmas",
            "frequency_bins",
            "base_warp_scales",
        }
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"unknown synthetic sweep config field(s): {', '.join(unknown)}")
        config = cls(
            name=str(data.get("name", cls.name)),
            height=int(data.get("height", cls.height)),
            width=int(data.get("width", cls.width)),
            crater_count=int(data.get("crater_count", cls.crater_count)),
            source_seed=int(data.get("source_seed", cls.source_seed)),
            frame_count=int(data.get("frame_count", cls.frame_count)),
            random_seed=int(data.get("random_seed", cls.random_seed)),
            temporal_correlation=float(data.get("temporal_correlation", cls.temporal_correlation)),
            warp_strengths=_float_tuple(data.get("warp_strengths", cls.warp_strengths)),
            noise_sigmas=_float_tuple(data.get("noise_sigmas", cls.noise_sigmas)),
            frequency_bins=int(data.get("frequency_bins", cls.frequency_bins)),
            base_warp_scales=_warp_scales(data.get("base_warp_scales", cls.base_warp_scales)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.height <= 0 or self.width <= 0:
            raise ValueError("height and width must be positive")
        if self.crater_count < 0:
            raise ValueError("crater_count must be non-negative")
        if self.frame_count <= 0:
            raise ValueError("frame_count must be positive")
        if not 0 <= self.temporal_correlation < 1:
            raise ValueError("temporal_correlation must be in [0, 1)")
        if not self.warp_strengths:
            raise ValueError("warp_strengths must not be empty")
        if any(strength < 0 for strength in self.warp_strengths):
            raise ValueError("warp_strengths must be non-negative")
        if not self.noise_sigmas:
            raise ValueError("noise_sigmas must not be empty")
        if any(sigma < 0 for sigma in self.noise_sigmas):
            raise ValueError("noise_sigmas must be non-negative")
        if self.frequency_bins <= 0:
            raise ValueError("frequency_bins must be positive")
        if not self.base_warp_scales:
            raise ValueError("base_warp_scales must not be empty")
        for scale in self.base_warp_scales:
            scale.validate()


def load_synthetic_sweep_config(path: Path) -> SyntheticSweepConfig:
    """Load a synthetic sweep config from JSON."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("synthetic sweep config must be a JSON object")
    return SyntheticSweepConfig.from_dict(data)


def run_synthetic_sweep(config: SyntheticSweepConfig, output_dir: Path) -> dict[str, Any]:
    """Run a compact synthetic parameter sweep and write metrics plus summaries."""

    output_dir.mkdir(parents=True, exist_ok=True)
    truth = crater_field(
        (config.height, config.width),
        crater_count=config.crater_count,
        seed=config.source_seed,
    )

    rows: list[dict[str, Any]] = []
    for case_index, warp_strength in enumerate(config.warp_strengths):
        for noise_sigma in config.noise_sigmas:
            scenario = _scenario_name(warp_strength, noise_sigma)
            case_dir = output_dir / "cases" / scenario
            _recreate_dir(case_dir)
            simulation_config = _simulation_config(config, warp_strength, noise_sigma, case_index)
            simulation = SeeingModel().generate(
                truth,
                simulation_config,
                np.random.default_rng(simulation_config.random_seed),
            )
            save_simulation_case(simulation, case_dir)

            result_root = output_dir / "results" / scenario
            _recreate_dir(result_root)
            reports = _evaluate_scenario(case_dir, result_root, config.frequency_bins)
            rows.extend(
                _summary_row(scenario, warp_strength, noise_sigma, report, metrics_path)
                for report, metrics_path in reports
            )

    comparison = {
        "name": config.name,
        "config": _config_to_dict(config),
        "ranking_basis": (
            "score = mean(global SSIM, gradient correlation, frequency recovery limit) "
            "- false detail fraction"
        ),
        "rows": sorted(rows, key=lambda row: row["score"], reverse=True),
    }
    (output_dir / "comparison.json").write_text(
        json.dumps(_json_safe(comparison), indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_sweep_markdown(comparison), encoding="utf-8")
    return comparison


def render_sweep_markdown(comparison: dict[str, Any]) -> str:
    """Render a synthetic sweep summary as Markdown."""

    lines = [
        f"# Synthetic Sweep: {comparison['name']}",
        "",
        f"Ranking basis: {comparison['ranking_basis']}",
        "",
        "| Rank | Scenario | Algorithm | Score | MSE | SSIM | Gradient Corr | "
        "Freq Limit | False Detail |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(comparison["rows"], start=1):
        lines.append(
            "| "
            f"{rank} | `{row['scenario']}` | `{row['algorithm']}` | {_fmt(row['score'])} | "
            f"{_fmt(row['mse'])} | {_fmt(row['ssim_global'])} | "
            f"{_fmt(row['gradient_correlation'])} | "
            f"{_fmt(row['frequency_limit_fraction'])} | "
            f"{_fmt(row['false_detail_fraction'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _evaluate_scenario(
    case_dir: Path,
    result_root: Path,
    frequency_bins: int,
) -> list[tuple[EvaluationReport, Path]]:
    result_root.mkdir(parents=True, exist_ok=True)

    single_dir = result_root / "single_frame"
    single_dir.mkdir(parents=True, exist_ok=True)
    first_frame = next(iter(sorted((case_dir / "input").glob("frame_*.tif"))), None)
    if first_frame is None:
        raise FileNotFoundError(f"no input frames found under {case_dir / 'input'}")
    write_grayscale_tiff(
        single_dir / "reconstruction.tif",
        load_grayscale_image(first_frame),
    )
    (single_dir / "metadata.json").write_text(
        json.dumps(
            {
                "adapter": "single_frame",
                "method": "first input frame copied as reconstruction",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    mean_dir = result_root / "mean_stack"
    mean_adapter = BaselineStackAdapter()
    mean_adapter.prepare(case_dir, mean_dir)
    mean_adapter.execute(case_dir, mean_dir)
    mean_adapter.collect_results(case_dir, mean_dir)

    oracle_dir = result_root / "oracle_aligned_stack"
    oracle_adapter = OracleAlignedStackAdapter()
    oracle_adapter.prepare(case_dir, oracle_dir)
    oracle_adapter.execute(case_dir, oracle_dir)
    oracle_adapter.collect_results(case_dir, oracle_dir)

    reports: list[tuple[EvaluationReport, Path]] = []
    for algorithm, result_dir in (
        ("single_frame", single_dir),
        ("mean_stack", mean_dir),
        ("oracle_aligned_stack", oracle_dir),
    ):
        report = evaluate_reconstruction(
            case_dir,
            result_dir,
            algorithm=algorithm,
            frequency_bins=frequency_bins,
        )
        metrics_path = result_dir / "metrics.json"
        save_evaluation_report(report, metrics_path)
        reports.append((report, metrics_path))
    return reports


def _simulation_config(
    config: SyntheticSweepConfig,
    warp_strength: float,
    noise_sigma: float,
    case_index: int,
) -> SeeingSimulationConfig:
    return SeeingSimulationConfig(
        frame_count=config.frame_count,
        random_seed=config.random_seed + case_index,
        temporal_correlation=config.temporal_correlation,
        warp_scales=tuple(
            WarpScaleConfig(
                scale.name,
                amplitude_px=scale.amplitude_px * warp_strength,
                correlation_px=scale.correlation_px,
            )
            for scale in config.base_warp_scales
        ),
        telescope_psf_sigma_px=0.0,
        seeing_blur_sigma_px=0.0,
        gaussian_noise_sigma=noise_sigma,
    )


def _summary_row(
    scenario: str,
    warp_strength: float,
    noise_sigma: float,
    report: EvaluationReport,
    metrics_path: Path,
) -> dict[str, Any]:
    image = report.image_similarity
    structure = report.structural_accuracy
    frequency = report.frequency_recovery
    false_detail = report.false_detail
    ssim = float(image["ssim_global"])
    gradient = float(structure["gradient_correlation"])
    frequency_limit = float(frequency["correlation_0_5_limit_fraction"])
    false_fraction = float(false_detail["unsupported_energy_fraction"])
    return {
        "scenario": scenario,
        "warp_strength": warp_strength,
        "noise_sigma": noise_sigma,
        "algorithm": report.algorithm,
        "metrics_path": str(metrics_path),
        "mse": float(image["mse"]),
        "psnr_db": float(image["psnr_db"]),
        "ssim_global": ssim,
        "gradient_correlation": gradient,
        "frequency_limit_fraction": frequency_limit,
        "false_detail_fraction": false_fraction,
        "warp_mean_px": None
        if report.warp_recovery is None
        else float(report.warp_recovery["mean_px"]),
        "score": ((ssim + gradient + frequency_limit) / 3.0) - false_fraction,
    }


def _config_to_dict(config: SyntheticSweepConfig) -> dict[str, Any]:
    return {
        "name": config.name,
        "height": config.height,
        "width": config.width,
        "crater_count": config.crater_count,
        "source_seed": config.source_seed,
        "frame_count": config.frame_count,
        "random_seed": config.random_seed,
        "temporal_correlation": config.temporal_correlation,
        "warp_strengths": list(config.warp_strengths),
        "noise_sigmas": list(config.noise_sigmas),
        "frequency_bins": config.frequency_bins,
        "base_warp_scales": [
            {
                "name": scale.name,
                "amplitude_px": scale.amplitude_px,
                "correlation_px": scale.correlation_px,
            }
            for scale in config.base_warp_scales
        ],
    }


def _float_tuple(value: Any) -> tuple[float, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("expected a list of numbers")
    return tuple(float(item) for item in value)


def _warp_scales(value: Any) -> tuple[WarpScaleConfig, ...]:
    if isinstance(value, tuple) and all(isinstance(item, WarpScaleConfig) for item in value):
        return value
    if not isinstance(value, list):
        raise ValueError("base_warp_scales must be a list")
    return tuple(
        WarpScaleConfig(
            name=str(item["name"]),
            amplitude_px=float(item["amplitude_px"]),
            correlation_px=float(item["correlation_px"]),
        )
        for item in value
    )


def _scenario_name(warp_strength: float, noise_sigma: float) -> str:
    return f"warp_{_slug_float(warp_strength)}__noise_{_slug_float(noise_sigma)}"


def _recreate_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _slug_float(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"
