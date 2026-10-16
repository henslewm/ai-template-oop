"""Non-UI checks must work when the optional Tk toolkit cannot be imported."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("collect_only", [True, False], ids=["collection", "contracts"])
def test_non_ui_checks_without_tk(collect_only: bool) -> None:
    checks = (
        ["--collect-only", "--ignore=tests/test_ui.py"]
        if collect_only
        else [
            "tests/test_contract_auth.py",
            "tests/test_contract_data.py",
            "tests/test_boundaries.py",
        ]
    )
    code = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class NoTk(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "tkinter" or fullname.startswith("tkinter."):
                    raise AssertionError("Non-UI verification tried to import Tk")

        sys.meta_path.insert(0, NoTk())
        import pytest

        result = pytest.main(sys.argv[1:])
        assert not any(name == "tkinter" or name.startswith("tkinter.") for name in sys.modules)
        raise SystemExit(result)
        """
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--ignore=tests/test_workflow_approval.py",
            *checks,
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
