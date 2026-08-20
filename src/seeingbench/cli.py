"""Command-line interface for SeeingBench."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from glob import glob
from pathlib import Path
from typing import Any

import numpy as np

from seeingbench.benchmark.case import load_benchmark_case, load_input_frame, save_simulation_case
from seeingbench.benchmark.compare import write_comparison_json, write_comparison_markdown
from seeingbench.benchmark.experiment import load_synthetic_sweep_config, run_synthetic_sweep
from seeingbench.benchmark.report import write_markdown_report
from seeingbench.benchmark.runner import evaluate_reconstruction, save_evaluation_report
from seeingbench.datasets.manifests import fetch_manifest_metadata, validate_manifest_files
from seeingbench.datasets.readiness import build_roi_readiness_report
from seeingbench.io.images import load_grayscale_image
from seeingbench.reconstruction.adapter import (
    BaselineStackAdapter,
    LocalBlockAlignedStackAdapter,
    OracleAlignedStackAdapter,
    TranslationAlignedStackAdapter,
    copy_manual_reconstruction,
)
from seeingbench.simulation.atmosphere import SeeingModel
from seeingbench.simulation.config import (
    SeeingSimulationConfig,
    WarpScaleConfig,
    load_simulation_config,
)
from seeingbench.simulation.source import crater_field
from seeingbench.visualization.diagnostics import write_diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seeingbench")
    subparsers = parser.add_subparsers(required=True)

    simulate = subparsers.add_parser("simulate", help="generate a synthetic benchmark case")
    simulate.add_argument("--output", required=True, type=Path)
    simulate.add_argument("--config", type=Path)
    simulate.add_argument("--truth", type=Path)
    simulate.add_argument("--frames", type=int)
    simulate.add_argument("--seed", type=int)
    simulate.add_argument("--height", type=int, default=256)
    simulate.add_argument("--width", type=int, default=256)
    simulate.add_argument("--noise-sigma", type=float)
    simulate.add_argument("--warp-scale", type=float)
    simulate.add_argument("--sensor-downsample", type=int)
    simulate.set_defaults(func=_simulate)

    baseline = subparsers.add_parser("baseline-stack", help="create a mean-stack baseline result")
    baseline.add_argument("--case", required=True, type=Path)
    baseline.add_argument("--output", required=True, type=Path)
    baseline.set_defaults(func=_baseline_stack)

    translation = subparsers.add_parser(
        "translation-stack",
        help="create a global-translation aligned stack baseline",
    )
    translation.add_argument("--case", required=True, type=Path)
    translation.add_argument("--output", required=True, type=Path)
    translation.set_defaults(func=_translation_stack)

    local_block = subparsers.add_parser(
        "local-block-stack",
        help="create a local block-translation aligned stack baseline",
    )
    local_block.add_argument("--case", required=True, type=Path)
    local_block.add_argument("--output", required=True, type=Path)
    local_block.add_argument("--block-size", type=int, default=32)
    local_block.set_defaults(func=_local_block_stack)

    oracle = subparsers.add_parser(
        "oracle-stack",
        help="create a synthetic-only truth-aligned stack upper bound",
    )
    oracle.add_argument("--case", required=True, type=Path)
    oracle.add_argument("--output", required=True, type=Path)
    oracle.set_defaults(func=_oracle_stack)

    import_result = subparsers.add_parser(
        "import-result", help="copy a reconstruction into result/"
    )
    import_result.add_argument("--source", required=True, type=Path)
    import_result.add_argument("--output", required=True, type=Path)
    import_result.set_defaults(func=_import_result)

    evaluate = subparsers.add_parser("evaluate", help="evaluate result/reconstruction.tif")
    evaluate.add_argument("--case", required=True, type=Path)
    evaluate.add_argument("--result", required=True, type=Path)
    evaluate.add_argument("--algorithm", default="manual")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--diagnostics", type=Path)
    evaluate.add_argument("--frequency-bins", type=int, default=24)
    evaluate.set_defaults(func=_evaluate)

    report = subparsers.add_parser("report", help="render metrics.json as Markdown")
    report.add_argument("--metrics", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)
    report.set_defaults(func=_report)

    compare = subparsers.add_parser("compare", help="compare two or more metrics reports")
    compare.add_argument("inputs", nargs="+", type=Path)
    compare.add_argument("--output", required=True, type=Path)
    compare.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare.set_defaults(func=_compare)

    experiment = subparsers.add_parser("experiment", help="experiment orchestration")
    experiment_subparsers = experiment.add_subparsers(required=True)

    synthetic_sweep = experiment_subparsers.add_parser(
        "synthetic-sweep",
        help="run a small synthetic parameter sweep",
    )
    synthetic_sweep.add_argument("--config", required=True, type=Path)
    synthetic_sweep.add_argument("--output", required=True, type=Path)
    synthetic_sweep.set_defaults(func=_experiment_synthetic_sweep)

    datasets = subparsers.add_parser("datasets", help="dataset manifest utilities")
    dataset_subparsers = datasets.add_subparsers(required=True)

    validate_manifests = dataset_subparsers.add_parser(
        "validate-manifest",
        help="validate dataset manifest JSON files",
    )
    validate_manifests.add_argument("manifests", nargs="+", type=Path)
    validate_manifests.add_argument("--output", type=Path)
    validate_manifests.set_defaults(func=_datasets_validate_manifest)

    fetch_metadata = dataset_subparsers.add_parser(
        "fetch-metadata",
        help="fetch only small metadata documents listed by a manifest",
    )
    fetch_metadata.add_argument("manifest", type=Path)
    fetch_metadata.add_argument("--output-root", required=True, type=Path)
    fetch_metadata.set_defaults(func=_datasets_fetch_metadata)

    roi_readiness = dataset_subparsers.add_parser(
        "roi-readiness",
        help="inspect local cache readiness for a documented lunar ROI without downloading data",
    )
    roi_readiness.add_argument("--roi", required=True, type=Path)
    roi_readiness.add_argument("--cache-root", type=Path, default=Path("."))
    roi_readiness.add_argument("--manifest-root", type=Path, default=Path("."))
    roi_readiness.add_argument("--output", type=Path)
    roi_readiness.set_defaults(func=_datasets_roi_readiness)
    return parser


def _simulate(args: argparse.Namespace) -> int:
    config = (
        load_simulation_config(args.config) if args.config is not None else SeeingSimulationConfig()
    )
    config = _apply_simulation_overrides(config, args)

    if args.truth is None:
        truth = crater_field(shape=(args.height, args.width), seed=config.random_seed)
        source_metadata = {
            "source": "seeingbench synthetic crater_field",
            "not_orbital_truth": True,
        }
    else:
        truth = load_grayscale_image(args.truth)
        source_metadata = {"source": str(args.truth), "not_orbital_truth": False}

    sensor_width = truth.shape[1] // config.sensor_downsample_factor
    sensor_height = truth.shape[0] // config.sensor_downsample_factor
    config = replace(
        config,
        telescope=replace(
            config.telescope,
            sensor_width_px=config.telescope.sensor_width_px or sensor_width,
            sensor_height_px=config.telescope.sensor_height_px or sensor_height,
        ),
    )
    config.validate()
    rng = np.random.default_rng(config.random_seed)
    result = SeeingModel().generate(truth, config, rng)
    result.metadata["source_image"] = source_metadata
    if args.config is not None:
        result.metadata["config_source"] = str(args.config)
    save_simulation_case(result, args.output)
    return 0


def _apply_simulation_overrides(
    config: SeeingSimulationConfig,
    args: argparse.Namespace,
) -> SeeingSimulationConfig:
    if args.frames is not None:
        config = replace(config, frame_count=args.frames)
    if args.seed is not None:
        config = replace(config, random_seed=args.seed)
    if args.noise_sigma is not None:
        config = replace(config, gaussian_noise_sigma=args.noise_sigma)
    if args.sensor_downsample is not None:
        config = replace(config, sensor_downsample_factor=args.sensor_downsample)
    if args.warp_scale is not None:
        config = replace(
            config,
            warp_scales=tuple(
                WarpScaleConfig(
                    scale.name,
                    amplitude_px=scale.amplitude_px * args.warp_scale,
                    correlation_px=scale.correlation_px,
                )
                for scale in config.warp_scales
            ),
        )
    config.validate()
    return config


def _baseline_stack(args: argparse.Namespace) -> int:
    adapter = BaselineStackAdapter()
    adapter.prepare(args.case, args.output)
    adapter.execute(args.case, args.output)
    adapter.collect_results(args.case, args.output)
    return 0


def _translation_stack(args: argparse.Namespace) -> int:
    adapter = TranslationAlignedStackAdapter()
    adapter.prepare(args.case, args.output)
    adapter.execute(args.case, args.output)
    adapter.collect_results(args.case, args.output)
    return 0


def _local_block_stack(args: argparse.Namespace) -> int:
    adapter = LocalBlockAlignedStackAdapter(block_size_px=args.block_size)
    adapter.prepare(args.case, args.output)
    adapter.execute(args.case, args.output)
    adapter.collect_results(args.case, args.output)
    return 0


def _oracle_stack(args: argparse.Namespace) -> int:
    adapter = OracleAlignedStackAdapter()
    adapter.prepare(args.case, args.output)
    adapter.execute(args.case, args.output)
    adapter.collect_results(args.case, args.output)
    return 0


def _import_result(args: argparse.Namespace) -> int:
    copy_manual_reconstruction(args.source, args.output)
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    report = evaluate_reconstruction(
        case_dir=args.case,
        result_dir=args.result,
        algorithm=args.algorithm,
        frequency_bins=args.frequency_bins,
    )
    output = args.output or args.result / "metrics.json"
    save_evaluation_report(report, output)
    if args.diagnostics is not None:
        case = load_benchmark_case(args.case)
        reconstruction = load_grayscale_image(args.result / "reconstruction.tif")
        diagnostics = write_diagnostics(
            args.diagnostics,
            case.latent_truth,
            reconstruction,
            report.frequency_recovery["bins"],
            degraded_frame=load_input_frame(args.case, index=1),
            warp_fields=case.warp_fields,
            warp_components=case.warp_components,
        )
        _append_diagnostics(output, diagnostics)
    return 0


def _report(args: argparse.Namespace) -> int:
    write_markdown_report(args.metrics, args.output)
    return 0


def _compare(args: argparse.Namespace) -> int:
    if args.format == "json":
        write_comparison_json(args.inputs, args.output)
    else:
        write_comparison_markdown(args.inputs, args.output)
    return 0


def _experiment_synthetic_sweep(args: argparse.Namespace) -> int:
    config = load_synthetic_sweep_config(args.config)
    run_synthetic_sweep(config, args.output)
    sys.stdout.write(f"{args.output / 'summary.md'}\n")
    return 0


def _datasets_validate_manifest(args: argparse.Namespace) -> int:
    reports = validate_manifest_files(_expand_path_patterns(args.manifests))
    payload = json.dumps(reports, indent=2)
    if args.output is None:
        sys.stdout.write(f"{payload}\n")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 1 if any(not report["valid"] for report in reports) else 0


def _datasets_fetch_metadata(args: argparse.Namespace) -> int:
    written = fetch_manifest_metadata(args.manifest, args.output_root)
    sys.stdout.write(f"{json.dumps([str(path) for path in written], indent=2)}\n")
    return 0


def _datasets_roi_readiness(args: argparse.Namespace) -> int:
    report = build_roi_readiness_report(args.roi, args.cache_root, args.manifest_root)
    payload = json.dumps(report, indent=2)
    if args.output is None:
        sys.stdout.write(f"{payload}\n")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0 if report["ready"] else 1


def _expand_path_patterns(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        path_text = str(path)
        if any(marker in path_text for marker in "*?["):
            matches = [Path(match) for match in sorted(glob(path_text))]
            expanded.extend(matches or [path])
        else:
            expanded.append(path)
    return expanded


def _append_diagnostics(report_path: Path, diagnostics: dict[str, Any]) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["diagnostics"] = diagnostics
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
