"""Generated frontend examples must not hide authored sources from secret scanning."""

import runpy
from pathlib import Path

import pytest


@pytest.fixture
def scanner(tmp_path):
    module = runpy.run_path(str(Path(__file__).parents[2] / "scripts/check_secrets.py"))
    main = module["main"]
    main.__globals__["ROOT"] = tmp_path
    return main


def write_candidate(root, relative):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('api_key = "' + "test-only-" * 3 + '"', encoding="utf-8")


def test_generated_libraries_and_build_are_excluded(scanner, tmp_path, capsys):
    for relative in ("web/node_modules/library/index.js", "web/.next/server/chunk.js"):
        write_candidate(tmp_path, relative)
    assert scanner() == 0
    assert "clean" in capsys.readouterr().out


@pytest.mark.parametrize(
    "relative",
    [
        "web/app/page.tsx",
        "web/lib/config.ts",
        "web/package.json",
        "web/package-lock.json",
        "web/next.config.mjs",
        "web/config.cjs",
        "web/.env.local",
        "web/node_modules-extra/example.js",
        "web/.next-extra/example.js",
    ],
)
def test_authored_and_similarly_named_paths_still_fail(scanner, tmp_path, capsys, relative):
    write_candidate(tmp_path, relative)
    assert scanner() == 1
    output = capsys.readouterr().out
    assert str(Path(relative)) in output
    assert "test-only-" not in output
