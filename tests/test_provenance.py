from __future__ import annotations

from pathlib import Path

from seeingbench.benchmark.provenance import runtime_provenance


def test_runtime_provenance_records_git_and_python_details() -> None:
    provenance = runtime_provenance(Path(__file__).resolve().parents[1])

    assert provenance["seeingbench_version"]
    assert provenance["python_version"]
    assert provenance["numpy_version"]
    assert provenance["python_executable"]
    assert isinstance(provenance["git"]["available"], bool)
    assert isinstance(provenance["git"]["dirty"], bool)
    assert isinstance(provenance["git"]["status_short"], list)
