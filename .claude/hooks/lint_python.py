import json
import shutil
import subprocess
import sys
from pathlib import Path

path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
if path.endswith(".py"):
    # Prefer the project's own ruff, so the hook works even when the editor's PATH has no venv.
    venv = Path(__file__).resolve().parents[2] / ".venv"
    venv_ruff = venv / "Scripts" / "ruff.exe" if sys.platform == "win32" else venv / "bin" / "ruff"
    ruff = str(venv_ruff) if venv_ruff.is_file() else shutil.which("ruff")
    if ruff is None:
        print('ruff not found in .venv or on PATH. Create .venv and run: pip install -e ".[dev]"', file=sys.stderr)
        sys.exit(2)
    result = subprocess.run([ruff, "check", "--quiet", path], capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        sys.exit(2)
