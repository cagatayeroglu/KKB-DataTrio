"""The make-pr checks using the caller's Python; usable from Windows PowerShell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    ("-m", "ruff", "format", "--check", "src", "tests", "scripts"),
    ("-m", "ruff", "check", "src", "tests", "scripts"),
    ("-m", "pytest", "-q", "tests/unit", "--disable-warnings", "--maxfail=1"),
    ("-m", "bandit", "-q", "-r", "src"),
    ("scripts/check_secrets.py",),
)


def main() -> int:
    for arguments in COMMANDS:
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            env={**os.environ, "PYTHONUTF8": "1"},
            check=False,
        )
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
