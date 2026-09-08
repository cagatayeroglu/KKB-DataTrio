"""Exercise repository ignore rules with synthetic files in an isolated Git repo."""

import os
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Developer Git configuration/index overrides must not affect this fixture
    # or send its synthetic files to the caller's repository index.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def isolated_repository(tmp_path: Path) -> Path:
    result = git(tmp_path, "init", "-q", "-b", "hygiene-check")
    assert result.returncode == 0, result.stderr
    (tmp_path / ".gitignore").write_bytes((REPOSITORY_ROOT / ".gitignore").read_bytes())
    (tmp_path / ".env.example").write_bytes((REPOSITORY_ROOT / ".env.example").read_bytes())
    return tmp_path


@pytest.mark.parametrize(
    "relative_path",
    [
        ".env",
        ".env.local",
        ".env.production",
        ".env.example.local",
        ".envrc",
        "nested/.env",
        "nested/.env.local",
        "nested/.env.example",
        ".secrets/key.txt",
        "secrets/key.txt",
        "credentials/local.json",
        "private/input.csv",
        "data/private/input.xlsx",
        "data/raw/input.csv",
        "data/processed/derived.csv",
        "data/cache/response.json",
        "uploads/input.pdf",
        "artifacts/evidence.json",
        "outputs/result.csv",
        "logs/session.log",
        "cache/response.json",
        ".cache/response.json",
        ".venv/pyvenv.cfg",
        "venv/pyvenv.cfg",
        "src/kkb_agent/__pycache__/module.pyc",
        ".pytest_cache/results",
        ".ruff_cache/results",
        ".mypy_cache/results",
        ".coverage",
        "coverage.xml",
        "htmlcov/index.html",
        "build/package.py",
        "dist/package.whl",
        "src/package.egg-info/PKG-INFO",
        ".DS_Store",
    ],
)
def test_local_files_are_not_staged(isolated_repository: Path, relative_path: str) -> None:
    candidate = isolated_repository / relative_path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("synthetic sentinel\n")

    assert git(isolated_repository, "check-ignore", "-q", "--", relative_path).returncode == 0
    result = git(isolated_repository, "add", "--all")
    assert result.returncode == 0, result.stderr
    staged = git(isolated_repository, "diff", "--cached", "--name-only").stdout.splitlines()
    assert relative_path not in staged
    assert ".env.example" in staged


@pytest.mark.parametrize(
    "relative_path",
    [
        ".env.example",
        ".gitignore",
        "src/kkb_agent/example.py",
        "tests/unit/test_example.py",
        "tests/fixtures/synthetic.csv",
        "tests/fixtures/synthetic.xlsx",
        "tests/fixtures/credentials/example.json",
        "benchmarks/cases/synthetic.json",
        "data/public/example.csv",
        "docs/README.md",
    ],
)
def test_shared_files_remain_trackable(isolated_repository: Path, relative_path: str) -> None:
    candidate = isolated_repository / relative_path
    if not candidate.exists():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("synthetic fixture\n")

    assert git(isolated_repository, "check-ignore", "-q", "--", relative_path).returncode == 1
    result = git(isolated_repository, "add", "--", relative_path)
    assert result.returncode == 0, result.stderr
    assert relative_path in git(isolated_repository, "ls-files").stdout.splitlines()


def test_environment_template_has_only_blank_values() -> None:
    assignments = [
        line
        for line in (REPOSITORY_ROOT / ".env.example").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert assignments, "The template must expose local configuration placeholders."
    for line in assignments:
        name, separator, value = line.partition("=")
        assert separator and name.isidentifier(), "Expected a simple NAME= placeholder."
        assert not value.strip(), "Environment example values must remain blank."
