"""The boundary linter is part of the test suite so CI fails on a leak."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_layer_boundaries_hold():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_boundaries.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
