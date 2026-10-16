"""The sample is headless: its CLI and non-UI checks run when Tk cannot be imported."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parent.parent

_NO_TK = textwrap.dedent(
    """
    import importlib.abc
    import runpy
    import sys

    class NoTk(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "tkinter" or fullname.startswith("tkinter."):
                raise AssertionError("Headless sample tried to import Tk")

    sys.meta_path.insert(0, NoTk())
    target, sys.argv = sys.argv[1], sys.argv[1:]
    if target == "pytest":
        import pytest
        code = pytest.main(sys.argv[1:])
    else:
        try:
            runpy.run_path(target, run_name="__main__")
            code = 0
        except SystemExit as exc:
            code = exc.code
    assert not any(n == "tkinter" or n.startswith("tkinter.") for n in sys.modules)
    raise SystemExit(code)
    """
)


@pytest.mark.parametrize(
    "argv",
    [
        ["main.py", "--mock", "process", "demo", "demo1234", "1", "2", "3"],
        [
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "tests/test_contract_auth.py",
            "tests/test_contract_data.py",
            "tests/test_boundaries.py",
            "tests/test_cli.py",
        ],
    ],
    ids=["cli", "checks"],
)
def test_runs_without_tk(argv):
    result = subprocess.run(
        [sys.executable, "-B", "-c", _NO_TK, *argv],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
