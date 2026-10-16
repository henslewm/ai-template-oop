"""B02: generate one fresh headless OOP project and prove it runs on its own."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import project_authority as authority  # noqa: E402
from tools import generate_project as generator  # noqa: E402


@pytest.fixture
def host_state(tmp_path, monkeypatch):
    """Keep host authority registrations out of the operator's real LOCALAPPDATA."""
    state = tmp_path / "host state"
    monkeypatch.setenv("LOCALAPPDATA", str(state))
    return state


def files_of(directory: Path) -> set[str]:
    return {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(directory).parts
    }


def run(cwd: Path, *argv: str, timeout: int = 300) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_refuses_unusable_destinations_without_side_effects(host_state, tmp_path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("existing work\n")
    a_file = tmp_path / "a-file"
    a_file.write_text("not a directory\n")

    for dest in (occupied, a_file, ROOT / "generated-inside-template"):
        with pytest.raises(ValueError):
            generator.generate(dest, "sample")
    assert generator.main(["--dest", str(occupied), "--slug", "sample"]) == 1
    with pytest.raises(ValueError):
        generator.generate(tmp_path / "bad-slug", "Not A Slug")

    assert files_of(occupied) == {"keep.txt"} and not (occupied / ".git").exists()
    assert not (ROOT / "generated-inside-template").exists()
    assert not (tmp_path / "bad-slug").exists()
    assert not host_state.exists()


def test_two_outputs_have_fresh_distinct_unapproved_identities(host_state, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    first = generator.generate(empty, "sample")
    second = generator.generate(tmp_path / "new" / "second", "sample")
    assert first["project"]["id"] != second["project"]["id"]

    expected = {target for _, _, target in generator.load_manifest()}
    for dest, record in ((empty, first), (tmp_path / "new" / "second", second)):
        identity = json.loads((dest / "config/project.json").read_text())
        assert identity == record["project"]
        # Nothing but manifest outputs, the fresh identity and the provenance record.
        assert files_of(dest) == expected | {"config/project.json", "GENERATION.json"}
        assert not (dest / authority.PACKAGE).exists()
        assert authority.status(dest)["state"] == "AWAITING_APPROVAL"
        assert json.loads((dest / "GENERATION.json").read_text()) == record

        for target, entry in record["files"].items():
            data = (dest / target).read_bytes()
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
            if entry["kind"] == "copy":
                assert data == (ROOT / entry["source"]).read_bytes()

    # Host records hold only registrations: no decision or receipt was issued.
    registered = sorted(p.name for p in host_state.rglob("*") if p.is_file())
    assert registered == ["identity.json", "identity.json"]


def test_generated_project_runs_cli_and_both_implementation_variants(
    host_state, tmp_path
):
    dest = tmp_path / "generated sample"
    created = run(
        ROOT,
        "-B",
        "tools/generate_project.py",
        "--dest",
        str(dest),
        "--slug",
        "sample-app",
    )
    assert created.returncode == 0, created.stdout + created.stderr
    assert json.loads(created.stdout)["state"] == "AWAITING_APPROVAL"

    cli = run(
        dest, "main.py", "--mock", "process", "demo", "demo1234", "1", "2", "3", "10"
    )
    assert cli.returncode == 0, cli.stdout + cli.stderr
    assert "count=4 total=16 mean=4 min=1 max=10" in cli.stdout

    contract_tests = ("tests/test_contract_auth.py", "tests/test_contract_data.py")
    for variant in ("mock", "sql"):
        result = run(
            dest,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-rA",
            "-k",
            variant,
            *contract_tests,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"[{variant}" in result.stdout
        assert (
            "[mock" not in result.stdout
            if variant == "sql"
            else "[sql" not in result.stdout
        )

    full = run(dest, "-m", "pytest", "-p", "no:cacheprovider")
    assert full.returncode == 0, full.stdout + full.stderr
    boundaries = run(dest, "tools/validate_boundaries.py")
    assert boundaries.returncode == 0 and "Boundaries OK." in boundaries.stdout

    # Negative fixture: the generated checker rejects shell I/O and Tk in features.
    (dest / "src/cli/leak.py").write_text("import sqlite3\n")
    (dest / "src/features/window.py").write_text("import tkinter\n")
    leaked = run(dest, "tools/validate_boundaries.py")
    assert leaked.returncode == 1
    assert "src/cli/leak.py:1: src/cli may not import sqlite3" in leaked.stdout
    assert (
        "src/features/window.py:1: src/features may not import tkinter" in leaked.stdout
    )
