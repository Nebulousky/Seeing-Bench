"""Comparative study orchestration for reconstruction adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seeingbench.benchmark.compare import write_comparison_json, write_comparison_markdown
from seeingbench.benchmark.reference_runner import (
    evaluate_reference_reconstruction,
    save_reference_evaluation_report,
)
from seeingbench.benchmark.runner import evaluate_reconstruction, save_evaluation_report
from seeingbench.reconstruction.adapter import (
    BaselineStackAdapter,
    CommandLineAdapter,
    LocalBlockAlignedStackAdapter,
    TranslationAlignedStackAdapter,
)

BUILTIN_BASELINE_ALGORITHMS = (
    "mean_stack",
    "translation_stack",
    "local_block_stack",
)


@dataclass(frozen=True)
class StudyAlgorithmConfig:
    """One reconstruction algorithm entry in a comparative study config."""

    name: str
    kind: str
    builtin: str | None = None
    command: tuple[str, ...] = ()
    local_block_size_px: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StudyAlgorithmConfig:
        required = {"name", "kind"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"study algorithm is missing field(s): {', '.join(missing)}")
        command = data.get("command", [])
        if not isinstance(command, list):
            raise ValueError("study algorithm command must be a list")
        config = cls(
            name=str(data["name"]),
            kind=str(data["kind"]),
            builtin=None if data.get("builtin") is None else str(data["builtin"]),
            command=tuple(str(part) for part in command),
            local_block_size_px=None
            if data.get("local_block_size_px") is None
            else int(data["local_block_size_px"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.name:
            raise ValueError("study algorithm name must be non-empty")
        if self.kind not in {"builtin", "command"}:
            raise ValueError("study algorithm kind must be 'builtin' or 'command'")
        if self.kind == "builtin":
            if self.builtin not in BUILTIN_BASELINE_ALGORITHMS:
                raise ValueError(f"unknown built-in study algorithm: {self.builtin}")
            if self.command:
                raise ValueError("built-in study algorithms must not declare command")
        if self.kind == "command":
            if self.builtin is not None:
                raise ValueError("command study algorithms must not declare builtin")
            if not self.command:
                raise ValueError("command study algorithms must declare a non-empty command")
        if self.local_block_size_px is not None and self.local_block_size_px <= 0:
            raise ValueError("local_block_size_px must be positive when provided")


@dataclass(frozen=True)
class ComparativeStudyConfig:
    """Config for running multiple reconstruction adapters against the same case."""

    case_dir: Path
    algorithms: tuple[StudyAlgorithmConfig, ...]
    frequency_bins: int = 24
    local_block_size_px: int = 32

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: Path) -> ComparativeStudyConfig:
        required = {"case", "algorithms"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"study config is missing field(s): {', '.join(missing)}")
        algorithm_data = data["algorithms"]
        if not isinstance(algorithm_data, list):
            raise ValueError("study config algorithms must be a list")
        config = cls(
            case_dir=_resolve_config_path(base_dir, str(data["case"])),
            algorithms=tuple(
                StudyAlgorithmConfig.from_dict(_algorithm_dict(item)) for item in algorithm_data
            ),
            frequency_bins=int(data.get("frequency_bins", 24)),
            local_block_size_px=int(data.get("local_block_size_px", 32)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.frequency_bins <= 0:
            raise ValueError("frequency_bins must be positive")
        if self.local_block_size_px <= 0:
            raise ValueError("local_block_size_px must be positive")
        if len(self.algorithms) < 2:
            raise ValueError("comparative studies require at least two algorithms")
        names = [algorithm.name for algorithm in self.algorithms]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate study algorithm name(s): {', '.join(duplicates)}")


@dataclass(frozen=True)
class ReferenceComparativeStudyConfig:
    """Config for comparing reconstructed observations against a standalone reference."""

    case_dir: Path
    reference_path: Path
    algorithms: tuple[StudyAlgorithmConfig, ...]
    frequency_bins: int = 24
    local_block_size_px: int = 32
    register_translation: bool = False

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        base_dir: Path,
    ) -> ReferenceComparativeStudyConfig:
        required = {"case", "reference", "algorithms"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"reference study config is missing field(s): {', '.join(missing)}")
        algorithm_data = data["algorithms"]
        if not isinstance(algorithm_data, list):
            raise ValueError("reference study config algorithms must be a list")
        config = cls(
            case_dir=_resolve_config_path(base_dir, str(data["case"])),
            reference_path=_resolve_config_path(base_dir, str(data["reference"])),
            algorithms=tuple(
                StudyAlgorithmConfig.from_dict(_algorithm_dict(item)) for item in algorithm_data
            ),
            frequency_bins=int(data.get("frequency_bins", 24)),
            local_block_size_px=int(data.get("local_block_size_px", 32)),
            register_translation=bool(data.get("register_translation", False)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.frequency_bins <= 0:
            raise ValueError("frequency_bins must be positive")
        if self.local_block_size_px <= 0:
            raise ValueError("local_block_size_px must be positive")
        if len(self.algorithms) < 2:
            raise ValueError("reference comparative studies require at least two algorithms")
        names = [algorithm.name for algorithm in self.algorithms]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate study algorithm name(s): {', '.join(duplicates)}")


def load_comparative_study_config(path: Path) -> ComparativeStudyConfig:
    """Load a JSON comparative study config."""

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("study config must be a JSON object")
    return ComparativeStudyConfig.from_dict(data, path.parent)


def load_reference_comparative_study_config(path: Path) -> ReferenceComparativeStudyConfig:
    """Load a JSON standalone-reference comparative study config."""

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("reference study config must be a JSON object")
    return ReferenceComparativeStudyConfig.from_dict(data, path.parent)


def run_builtin_baseline_study(
    case_dir: Path,
    output_root: Path,
    frequency_bins: int = 24,
    local_block_size_px: int = 32,
) -> dict[str, Any]:
    """Run built-in baselines against the same case and compare their metrics."""

    if frequency_bins <= 0:
        raise ValueError("frequency_bins must be positive")
    if local_block_size_px <= 0:
        raise ValueError("local_block_size_px must be positive")

    config = ComparativeStudyConfig(
        case_dir=case_dir,
        algorithms=tuple(
            StudyAlgorithmConfig(
                name=algorithm,
                kind="builtin",
                builtin=algorithm,
                local_block_size_px=local_block_size_px,
            )
            for algorithm in BUILTIN_BASELINE_ALGORITHMS
        ),
        frequency_bins=frequency_bins,
        local_block_size_px=local_block_size_px,
    )
    return run_comparative_study(config, output_root)


def run_comparative_study(
    config: ComparativeStudyConfig,
    output_root: Path,
) -> dict[str, Any]:
    """Run a configured comparative study and write metrics/comparison artifacts."""

    config.validate()
    output_root.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    metrics_paths: list[Path] = []
    for algorithm in config.algorithms:
        result_dir = output_root / "results" / _safe_name(algorithm.name)
        adapter = _configured_adapter(algorithm, config.local_block_size_px)
        adapter.prepare(config.case_dir, result_dir)
        adapter.execute(config.case_dir, result_dir)
        adapter.collect_results(config.case_dir, result_dir)
        metrics_path = result_dir / "metrics.json"
        report = evaluate_reconstruction(
            case_dir=config.case_dir,
            result_dir=result_dir,
            algorithm=algorithm.name,
            frequency_bins=config.frequency_bins,
        )
        save_evaluation_report(report, metrics_path)
        metrics_paths.append(metrics_path)
        result_rows.append(
            {
                "algorithm": algorithm.name,
                "kind": algorithm.kind,
                "result_dir": str(result_dir),
                "metrics": str(metrics_path),
            }
        )

    comparison_json = output_root / "comparison.json"
    comparison_markdown = output_root / "comparison.md"
    write_comparison_json(metrics_paths, comparison_json)
    write_comparison_markdown(metrics_paths, comparison_markdown)
    summary = {
        "case_dir": str(config.case_dir),
        "output_root": str(output_root),
        "algorithm_count": len(result_rows),
        "algorithms": result_rows,
        "comparison_json": str(comparison_json),
        "comparison_markdown": str(comparison_markdown),
        "frequency_bins": config.frequency_bins,
        "local_block_size_px": config.local_block_size_px,
        "validation_boundary": (
            "study adapters consume only benchmark input frames; evaluation consumes retained "
            "truth after reconstruction outputs are written"
        ),
    }
    (output_root / "study-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def run_reference_comparative_study(
    config: ReferenceComparativeStudyConfig,
    output_root: Path,
) -> dict[str, Any]:
    """Run adapters and compare reconstructions against a standalone reference."""

    config.validate()
    output_root.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    metrics_paths: list[Path] = []
    for algorithm in config.algorithms:
        result_dir = output_root / "results" / _safe_name(algorithm.name)
        adapter = _configured_adapter(algorithm, config.local_block_size_px)
        adapter.prepare(config.case_dir, result_dir)
        adapter.execute(config.case_dir, result_dir)
        adapter.collect_results(config.case_dir, result_dir)
        metrics_path = result_dir / "metrics.json"
        report = evaluate_reference_reconstruction(
            reference_path=config.reference_path,
            reconstruction_path=result_dir / "reconstruction.tif",
            algorithm=algorithm.name,
            frequency_bins=config.frequency_bins,
            register_translation=config.register_translation,
            reconstruction_metadata_path=result_dir / "metadata.json",
        )
        save_reference_evaluation_report(report, metrics_path)
        metrics_paths.append(metrics_path)
        result_rows.append(
            {
                "algorithm": algorithm.name,
                "kind": algorithm.kind,
                "result_dir": str(result_dir),
                "metrics": str(metrics_path),
            }
        )

    comparison_json = output_root / "comparison.json"
    comparison_markdown = output_root / "comparison.md"
    write_comparison_json(metrics_paths, comparison_json)
    write_comparison_markdown(metrics_paths, comparison_markdown)
    summary = {
        "case_dir": str(config.case_dir),
        "reference_path": str(config.reference_path),
        "output_root": str(output_root),
        "benchmark_mode": "standalone_reference_study",
        "algorithm_count": len(result_rows),
        "algorithms": result_rows,
        "comparison_json": str(comparison_json),
        "comparison_markdown": str(comparison_markdown),
        "frequency_bins": config.frequency_bins,
        "local_block_size_px": config.local_block_size_px,
        "register_translation": config.register_translation,
        "validation_boundary": (
            "study adapters consume only observation input frames; the standalone reference "
            "is loaded only by the evaluator after reconstruction outputs are written"
        ),
    }
    (output_root / "study-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def _configured_adapter(
    algorithm: StudyAlgorithmConfig,
    default_local_block_size_px: int,
) -> (
    BaselineStackAdapter
    | TranslationAlignedStackAdapter
    | LocalBlockAlignedStackAdapter
    | CommandLineAdapter
):
    if algorithm.kind == "command":
        return CommandLineAdapter(command=algorithm.command, name=algorithm.name)
    if algorithm.builtin is None:
        raise ValueError("built-in study algorithm is missing builtin")
    return _builtin_adapter(
        algorithm.builtin,
        algorithm.local_block_size_px or default_local_block_size_px,
    )


def _builtin_adapter(
    algorithm: str,
    local_block_size_px: int,
) -> BaselineStackAdapter | TranslationAlignedStackAdapter | LocalBlockAlignedStackAdapter:
    if algorithm == "mean_stack":
        return BaselineStackAdapter()
    if algorithm == "translation_stack":
        return TranslationAlignedStackAdapter()
    if algorithm == "local_block_stack":
        return LocalBlockAlignedStackAdapter(block_size_px=local_block_size_px)
    raise ValueError(f"unknown built-in baseline algorithm: {algorithm}")


def _algorithm_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each study algorithm must be a JSON object")
    return value


def _resolve_config_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")
