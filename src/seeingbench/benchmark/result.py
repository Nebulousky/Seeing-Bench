"""Benchmark evaluation report model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationReport:
    """Machine-readable result of evaluating one reconstruction."""

    algorithm: str
    image_similarity: dict[str, float]
    structural_accuracy: dict[str, float]
    frequency_recovery: dict[str, Any]
    false_detail: dict[str, float]
    warp_recovery: dict[str, float] | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
