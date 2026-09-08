from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".env",
    ".ini",
    ".cfg",
    ".sh",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
}

PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\n]{12,}['\"]"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
]

SAFE_FILENAMES = {".env.example"}


def should_scan(path: Path) -> bool:
    if any(part in IGNORED_DIRS for part in path.parts):
        return False
    if path.name in SAFE_FILENAMES:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.startswith(".env")


def main() -> int:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(p.search(line) for p in PATTERNS):
                hits.append(f"{path.relative_to(ROOT)}:{line_no}")

    if hits:
        print("Potential secret-like values found:")
        for hit in hits:
            print(f" - {hit}")
        return 1

    print("Secret scan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
