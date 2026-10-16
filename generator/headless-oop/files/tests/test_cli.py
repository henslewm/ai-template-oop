"""CLI tests: parsing, rendering, error translation and the documented commands."""

from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.cli import CommandLine, build_parser, parse_numbers
from src.container import build_mock, build_production

ROOT = Path(__file__).resolve().parent.parent


def run(services, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    shell = CommandLine(services.authenticator, services.processor, out, err)
    code = shell.execute(build_parser().parse_args(list(argv)))
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1, 2.5, 3", [1.0, 2.5, 3.0]),
        ("1 2 3", [1.0, 2.0, 3.0]),
        ("", []),
        ("-1e3", [-1000.0]),
    ],
)
def test_parse_numbers(text, expected):
    assert parse_numbers(text) == expected


def test_mock_process_renders_statistics():
    code, out, err = run(
        build_mock(), "process", "demo", "demo1234", "1", "2", "3", "10"
    )
    assert (code, err) == (0, "")
    assert "count=4 total=16 mean=4 min=1 max=10" in out


@pytest.mark.parametrize(
    "argv,message",
    [
        (
            ("process", "demo", "wrong-password", "1"),
            "Username or password is incorrect.",
        ),
        (("process", "demo", "demo1234"), "Enter at least one number to process."),
        (
            ("process", "demo", "demo1234", "1", "two"),
            "Enter numbers separated by commas",
        ),
        (("register", "demo", "another-password"), "That username is already taken."),
        (("register", "bob", "short"), "Password is too weak."),
    ],
)
def test_errors_are_rendered_not_raised(argv, message):
    code, out, err = run(build_mock(), *argv)
    assert code == 1
    assert out == ""
    assert err.startswith(message)


def test_sqlite_register_process_history(tmp_path):
    services = build_production(tmp_path / "app.db")
    assert run(services, "register", "alice", "correct horse")[0] == 0
    run(services, "process", "alice", "correct horse", "1", "2")
    run(services, "process", "alice", "correct horse", "3")
    code, out, _ = run(services, "history", "alice", "correct horse", "--limit", "1")
    assert code == 0
    assert out.count("record ") == 1 and "total=3" in out


def test_documented_mock_command_runs_from_project_directory():
    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            "--mock",
            "process",
            "demo",
            "demo1234",
            "1",
            "2",
            "3",
            "10",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "count=4 total=16 mean=4 min=1 max=10" in result.stdout
