from __future__ import annotations

import json
from pathlib import Path

from seeingbench.observations import load_observation_metadata


def test_load_observation_metadata_accepts_utf8_bom(tmp_path: Path) -> None:
    observation_path = tmp_path / "observation.json"
    payload = json.dumps({"target": "Moon", "utc_start": "2026-08-15T00:46:34Z"})
    observation_path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))

    metadata = load_observation_metadata(observation_path)

    assert metadata["target"] == "Moon"
    assert metadata["utc_start"] == "2026-08-15T00:46:34Z"
