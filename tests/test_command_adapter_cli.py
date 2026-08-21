from __future__ import annotations

import json
import sys
from pathlib import Path

from seeingbench.cli import main


def test_cli_run_command_executes_external_result_contract(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    result_dir = tmp_path / "external-result"
    script_path = tmp_path / "external_tool.py"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import shutil",
                "import sys",
                "case = Path(sys.argv[1])",
                "result = Path(sys.argv[2])",
                "result.mkdir(parents=True, exist_ok=True)",
                "shutil.copy2(case / 'input' / 'frame_000001.tif', result / 'reconstruction.tif')",
                "print('wrote reconstruction')",
            ]
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "simulate",
                "--output",
                str(case_dir),
                "--frames",
                "2",
                "--height",
                "32",
                "--width",
                "32",
                "--seed",
                "5",
                "--noise-sigma",
                "0.0",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "run-command",
                "--case",
                str(case_dir),
                "--output",
                str(result_dir),
                "--name",
                "external_echo",
                "--",
                sys.executable,
                str(script_path),
                "{case}",
                "{result}",
            ]
        )
        == 0
    )

    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    assert (result_dir / "reconstruction.tif").exists()
    assert metadata["adapter"] == "external_echo"
    assert metadata["returncode"] == 0
    assert "wrote reconstruction" in metadata["stdout"]
