"""The PowerShell project launcher works independently of the caller's directory."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="Uses a no-op Unix editor executable")
def test_first_run_drafts_request_from_foreign_working_directory(tmp_path):
    powershell = shutil.which("pwsh")
    editor = shutil.which("true")
    if not powershell or not editor:
        pytest.skip("PowerShell 7 and the true command are required")

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-File",
            str(ROOT / "new-project.ps1"),
            "classroom-summary",
        ],
        cwd=tmp_path,
        env={**os.environ, "EDITOR": editor},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    request = tmp_path / "classroom-summary.request.json"
    assert json.loads(request.read_text(encoding="utf-8"))["slug"] == "classroom-summary"
    assert "run this command again" in result.stdout
    assert not (tmp_path / "classroom-summary").exists()
