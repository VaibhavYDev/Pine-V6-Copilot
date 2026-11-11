import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_golden.py"


def guard_exit_code(command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True).returncode


@pytest.mark.parametrize(
    "command",
    [
        "rm eval/golden/t-001.toml",
        "rm eval//golden/t-001.toml",
        "cat labels//pine_editor.csv",
        "rm eval/./golden/t-001.toml",
        "rm eval/.//./golden/t-001.toml",
        "Remove-Item EVAL\\GOLDEN\\t-001.toml",
        "del .\\eval\\.\\golden\\t-001.toml",
        'cat "labels\\\\pine_editor.csv"',
        "python -m eval.freeze",
    ],
)
def test_guard_blocks_ground_truth_paths_and_refreeze(command: str) -> None:
    assert guard_exit_code(command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "python -m eval.freeze --check",
        ".venv/Scripts/python -m eval.freeze --check",
        "git diff eval/freeze.py",
        "pytest -q",
        "ruff check .",
        "git status",
        "docker compose ps",
    ],
)
def test_guard_allows_ordinary_commands(command: str) -> None:
    assert guard_exit_code(command) == 0
