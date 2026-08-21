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

from seeingbench.benchmark.case import (
    load_benchmark_case,
    load_input_frame,
    save_observation_case,
    save_simulation_case,
)
from seeingbench.benchmark.compare import write_comparison_json, write_comparison_markdown
from seeingbench.benchmark.experiment import load_synthetic_sweep_config, run_synthetic_sweep
from seeingbench.benchmark.reference_runner import (
    evaluate_reference_reconstruction,
    save_reference_evaluation_report,
)
from seeingbench.benchmark.report import write_markdown_report
from seeingbench.benchmark.runner import evaluate_reconstruction, save_evaluation_report
from seeingbench.benchmark.study import (
    load_comparative_study_config,
    load_reference_comparative_study_config,
    run_builtin_baseline_study,
    run_comparative_study,
    run_reference_comparative_study,
)
from seeingbench.datasets.extract import extract_verified_roi_products
from seeingbench.datasets.manifests import (
    fetch_manifest_metadata,
    fetch_manifest_product_files,
    fetch_manifest_product_labels,
    validate_manifest_files,
)
from seeingbench.datasets.readiness import build_roi_download_plan, build_roi_readiness_report
from seeingbench.datasets.reproject import reproject_extracted_roi_products
from seeingbench.geometry.observation import (
    build_spice_observation_geometry_report,
    write_spice_observation_geometry_report,
)
from seeingbench.geometry.spice import build_spice_readiness_report, write_spice_readiness_report
from seeingbench.io.images import load_grayscale_image
from seeingbench.observations import load_observation_metadata
from seeingbench.reconstruction.adapter import (
    BaselineStackAdapter,
    CommandLineAdapter,
    LocalBlockAlignedStackAdapter,
    OracleAlignedStackAdapter,
    TranslationAlignedStackAdapter,
    copy_manual_reconstruction,
)
from seeingbench.rendering.reference import render_telescope_matched_reference
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

    import_observation = subparsers.add_parser(
        "import-observation",
        help="import local observation frames into the reconstruction input contract",
    )
    import_observation.add_argument("--output", required=True, type=Path)
    import_observation.add_argument("--metadata", type=Path)
    import_observation.add_argument("frames", nargs="+", type=Path)
    import_observation.set_defaults(func=_import_observation)

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

    command_result = subparsers.add_parser(
        "run-command",
        help="run an external reconstruction command under the result contract",
    )
    command_result.add_argument("--case", required=True, type=Path)
    command_result.add_argument("--output", required=True, type=Path)
    command_result.add_argument("--name", default="command_line")
    command_result.add_argument("command", nargs=argparse.REMAINDER)
    command_result.set_defaults(func=_run_command_result)

    evaluate = subparsers.add_parser("evaluate", help="evaluate result/reconstruction.tif")
    evaluate.add_argument("--case", required=True, type=Path)
    evaluate.add_argument("--result", required=True, type=Path)
    evaluate.add_argument("--algorithm", default="manual")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--diagnostics", type=Path)
    evaluate.add_argument("--frequency-bins", type=int, default=24)
    evaluate.set_defaults(func=_evaluate)

    evaluate_reference = subparsers.add_parser(
        "evaluate-reference",
        help="evaluate a reconstruction against a standalone reference image",
    )
    evaluate_reference.add_argument("--reference", required=True, type=Path)
    evaluate_reference.add_argument("--reconstruction", required=True, type=Path)
    evaluate_reference.add_argument("--algorithm", default="manual")
    evaluate_reference.add_argument("--output", required=True, type=Path)
    evaluate_reference.add_argument("--frequency-bins", type=int, default=24)
    evaluate_reference.add_argument("--register-translation", action="store_true")
    evaluate_reference.add_argument(
        "--registration-rotation-deg",
        action="append",
        type=float,
        dest="registration_rotation_degrees",
        help="global rotation candidate in degrees; may be repeated",
    )
    evaluate_reference.add_argument(
        "--registration-scale",
        action="append",
        type=float,
        dest="registration_scales",
        help="global scale candidate; may be repeated",
    )
    evaluate_reference.set_defaults(func=_evaluate_reference)

    report = subparsers.add_parser("report", help="render metrics.json as Markdown")
    report.add_argument("--metrics", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)
    report.set_defaults(func=_report)

    compare = subparsers.add_parser("compare", help="compare two or more metrics reports")
    compare.add_argument("inputs", nargs="+", type=Path)
    compare.add_argument("--output", required=True, type=Path)
    compare.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare.set_defaults(func=_compare)

    study = subparsers.add_parser("study", help="comparative study orchestration")
    study_subparsers = study.add_subparsers(required=True)

    builtin_baselines = study_subparsers.add_parser(
        "builtin-baselines",
        help="run and compare built-in baselines on the same benchmark case",
    )
    builtin_baselines.add_argument("--case", required=True, type=Path)
    builtin_baselines.add_argument("--output", required=True, type=Path)
    builtin_baselines.add_argument("--frequency-bins", type=int, default=24)
    builtin_baselines.add_argument("--local-block-size", type=int, default=32)
    builtin_baselines.set_defaults(func=_study_builtin_baselines)

    run_study_config = study_subparsers.add_parser(
        "run-config",
        help="run a JSON-configured comparative reconstruction study",
    )
    run_study_config.add_argument("--config", required=True, type=Path)
    run_study_config.add_argument("--output", required=True, type=Path)
    run_study_config.set_defaults(func=_study_run_config)

    run_reference_study_config = study_subparsers.add_parser(
        "run-reference-config",
        help="run a JSON-configured study against a standalone reference image",
    )
    run_reference_study_config.add_argument("--config", required=True, type=Path)
    run_reference_study_config.add_argument("--output", required=True, type=Path)
    run_reference_study_config.set_defaults(func=_study_run_reference_config)

    experiment = subparsers.add_parser("experiment", help="experiment orchestration")
    experiment_subparsers = experiment.add_subparsers(required=True)

    synthetic_sweep = experiment_subparsers.add_parser(
        "synthetic-sweep",
        help="run a small synthetic parameter sweep",
    )
    synthetic_sweep.add_argument("--config", required=True, type=Path)
    synthetic_sweep.add_argument("--output", required=True, type=Path)
    synthetic_sweep.set_defaults(func=_experiment_synthetic_sweep)

    render = subparsers.add_parser("render", help="reference rendering utilities")
    render_subparsers = render.add_subparsers(required=True)

    telescope_reference = render_subparsers.add_parser(
        "telescope-reference",
        help="blur a local ROI reference to a real observation telescope limit",
    )
    telescope_reference.add_argument("--surface-reference-report", required=True, type=Path)
    telescope_reference.add_argument("--observation", required=True, type=Path)
    telescope_reference.add_argument("--output-root", required=True, type=Path)
    telescope_reference.add_argument("--role")
    telescope_reference.add_argument("--spice-cache-root", type=Path)
    telescope_reference.set_defaults(func=_render_telescope_reference)

    geometry = subparsers.add_parser("geometry", help="geometry readiness utilities")
    geometry_subparsers = geometry.add_subparsers(required=True)

    spice_readiness = geometry_subparsers.add_parser(
        "spice-readiness",
        help="inspect local SPICE kernel readiness for an observation",
    )
    spice_readiness.add_argument("--observation", required=True, type=Path)
    spice_readiness.add_argument("--manifest", required=True, type=Path)
    spice_readiness.add_argument("--cache-root", type=Path, default=Path("."))
    spice_readiness.add_argument("--output", type=Path)
    spice_readiness.set_defaults(func=_geometry_spice_readiness)

    spice_observation = geometry_subparsers.add_parser(
        "spice-observation",
        help="compute SPICE-backed topocentric Moon geometry for an observation",
    )
    spice_observation.add_argument("--observation", required=True, type=Path)
    spice_observation.add_argument("--cache-root", type=Path, default=Path("."))
    spice_observation.add_argument("--output", type=Path)
    spice_observation.set_defaults(func=_geometry_spice_observation)

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

    fetch_labels = dataset_subparsers.add_parser(
        "fetch-labels",
        help="fetch only small product labels declared by a manifest",
    )
    fetch_labels.add_argument("manifest", type=Path)
    fetch_labels.add_argument("--output-root", required=True, type=Path)
    fetch_labels.set_defaults(func=_datasets_fetch_labels)

    fetch_products = dataset_subparsers.add_parser(
        "fetch-products",
        help="fetch declared bulk product files within an explicit byte budget",
    )
    fetch_products.add_argument("manifest", type=Path)
    fetch_products.add_argument("--output-root", required=True, type=Path)
    fetch_products.add_argument("--max-total-bytes", required=True, type=int)
    fetch_products.add_argument("--product-name", action="append")
    fetch_products.set_defaults(func=_datasets_fetch_products)

    roi_readiness = dataset_subparsers.add_parser(
        "roi-readiness",
        help="inspect local cache readiness for a documented lunar ROI without downloading data",
    )
    roi_readiness.add_argument("--roi", required=True, type=Path)
    roi_readiness.add_argument("--cache-root", type=Path, default=Path("."))
    roi_readiness.add_argument("--manifest-root", type=Path, default=Path("."))
    roi_readiness.add_argument("--output", type=Path)
    roi_readiness.set_defaults(func=_datasets_roi_readiness)

    roi_download_plan = dataset_subparsers.add_parser(
        "roi-download-plan",
        help="write declared ROI product URLs and cache destinations without downloading data",
    )
    roi_download_plan.add_argument("--roi", required=True, type=Path)
    roi_download_plan.add_argument("--cache-root", type=Path, default=Path("."))
    roi_download_plan.add_argument("--manifest-root", type=Path, default=Path("."))
    roi_download_plan.add_argument("--output", type=Path)
    roi_download_plan.set_defaults(func=_datasets_roi_download_plan)

    extract_roi = dataset_subparsers.add_parser(
        "extract-roi",
        help="extract supported ROI windows from already-local verified products",
    )
    extract_roi.add_argument("--roi", required=True, type=Path)
    extract_roi.add_argument("--cache-root", type=Path, default=Path("."))
    extract_roi.add_argument("--manifest-root", type=Path, default=Path("."))
    extract_roi.add_argument("--output-root", required=True, type=Path)
    extract_roi.set_defaults(func=_datasets_extract_roi)

    reproject_roi = dataset_subparsers.add_parser(
        "reproject-roi",
        help="resample extracted ROI products onto the declared target grid",
    )
    reproject_roi.add_argument("--extraction-report", required=True, type=Path)
    reproject_roi.add_argument("--output-root", required=True, type=Path)
    reproject_roi.set_defaults(func=_datasets_reproject_roi)
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


def _import_observation(args: argparse.Namespace) -> int:
    frame_paths = _expand_path_patterns(args.frames)
    metadata = load_observation_metadata(args.metadata) if args.metadata is not None else None
    report = save_observation_case(frame_paths, args.output, metadata)
    sys.stdout.write(f"{json.dumps(report, indent=2)}\n")
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


def _run_command_result(args: argparse.Namespace) -> int:
    command = _command_remainder(args.command)
    adapter = CommandLineAdapter(command=command, name=args.name)
    adapter.prepare(args.case, args.output)
    adapter.execute(args.case, args.output)
    adapter.collect_results(args.case, args.output)
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


def _evaluate_reference(args: argparse.Namespace) -> int:
    report = evaluate_reference_reconstruction(
        args.reference,
        args.reconstruction,
        algorithm=args.algorithm,
        frequency_bins=args.frequency_bins,
        register_translation=args.register_translation,
        registration_rotation_degrees=args.registration_rotation_degrees,
        registration_scales=args.registration_scales,
    )
    save_reference_evaluation_report(report, args.output)
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


def _study_builtin_baselines(args: argparse.Namespace) -> int:
    summary = run_builtin_baseline_study(
        args.case,
        args.output,
        frequency_bins=args.frequency_bins,
        local_block_size_px=args.local_block_size,
    )
    sys.stdout.write(f"{json.dumps(summary, indent=2)}\n")
    return 0


def _study_run_config(args: argparse.Namespace) -> int:
    config = load_comparative_study_config(args.config)
    summary = run_comparative_study(config, args.output)
    sys.stdout.write(f"{json.dumps(summary, indent=2)}\n")
    return 0


def _study_run_reference_config(args: argparse.Namespace) -> int:
    config = load_reference_comparative_study_config(args.config)
    summary = run_reference_comparative_study(config, args.output)
    sys.stdout.write(f"{json.dumps(summary, indent=2)}\n")
    return 0


def _experiment_synthetic_sweep(args: argparse.Namespace) -> int:
    config = load_synthetic_sweep_config(args.config)
    run_synthetic_sweep(config, args.output)
    sys.stdout.write(f"{args.output / 'summary.md'}\n")
    return 0


def _render_telescope_reference(args: argparse.Namespace) -> int:
    report = render_telescope_matched_reference(
        args.surface_reference_report,
        args.observation,
        args.output_root,
        role=args.role,
        spice_cache_root=args.spice_cache_root,
    )
    sys.stdout.write(f"{json.dumps(report, indent=2)}\n")
    return 0 if report["reference_count"] > 0 else 1


def _geometry_spice_readiness(args: argparse.Namespace) -> int:
    report = build_spice_readiness_report(args.observation, args.manifest, args.cache_root)
    payload = json.dumps(report, indent=2)
    if args.output is None:
        sys.stdout.write(f"{payload}\n")
    else:
        write_spice_readiness_report(report, args.output)
    return 0 if report["ready"] else 1


def _geometry_spice_observation(args: argparse.Namespace) -> int:
    report = build_spice_observation_geometry_report(args.observation, args.cache_root)
    payload = json.dumps(report, indent=2)
    if args.output is None:
        sys.stdout.write(f"{payload}\n")
    else:
        write_spice_observation_geometry_report(report, args.output)
    return 0 if report["ready"] else 1


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


def _datasets_fetch_labels(args: argparse.Namespace) -> int:
    written = fetch_manifest_product_labels(args.manifest, args.output_root)
    sys.stdout.write(f"{json.dumps([str(path) for path in written], indent=2)}\n")
    return 0


def _datasets_fetch_products(args: argparse.Namespace) -> int:
    written = fetch_manifest_product_files(
        args.manifest,
        args.output_root,
        max_total_bytes=args.max_total_bytes,
        product_names=args.product_name,
    )
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


def _datasets_roi_download_plan(args: argparse.Namespace) -> int:
    plan = build_roi_download_plan(args.roi, args.cache_root, args.manifest_root)
    payload = json.dumps(plan, indent=2)
    if args.output is None:
        sys.stdout.write(f"{payload}\n")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


def _datasets_extract_roi(args: argparse.Namespace) -> int:
    report = extract_verified_roi_products(
        args.roi,
        args.cache_root,
        args.manifest_root,
        args.output_root,
    )
    sys.stdout.write(f"{json.dumps(report, indent=2)}\n")
    return 0 if report["extracted_count"] > 0 else 1


def _datasets_reproject_roi(args: argparse.Namespace) -> int:
    report = reproject_extracted_roi_products(args.extraction_report, args.output_root)
    sys.stdout.write(f"{json.dumps(report, indent=2)}\n")
    return 0 if report["reference_count"] > 0 else 1


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


def _command_remainder(command: list[str]) -> tuple[str, ...]:
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("run-command requires a command after '--'")
    return tuple(command)


if __name__ == "__main__":
    raise SystemExit(main())
