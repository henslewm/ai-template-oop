"""Run the frozen approval tests on an inactive disposable projection.

The actual ACTIVE package and its approval-bound files are never rewritten.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import validate_workflow_approval as approval  # noqa: E402 -- repository script entry point


def main() -> int:
    package_path = ROOT / approval.PACKAGE
    original = package_path.read_bytes()
    package = approval.read_json(package_path)
    digest = approval.validate(package, ROOT, require_active=True)
    with tempfile.TemporaryDirectory(
        prefix="workflow-approval-regression-"
    ) as directory:
        snapshot = Path(directory)
        # Include the new exported ABC without changing the frozen receipt.
        for relative in (
            set(package["bound_files"])
            | set(package["baseline_files"])
            | {"contracts/operator.py"}
        ):
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        package.update(state="AWAITING_APPROVAL", autonomy_enabled=False)
        package["approval"] = {
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "architecture_fingerprint": None,
            "decision": None,
        }
        (snapshot / approval.PACKAGE).write_bytes(approval.canonical(package))
        if approval.fingerprint(package) != digest:
            raise ValueError("Inactive projection changed foundation fingerprint")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-rs",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "tests/test_workflow_approval.py",
            ],
            cwd=snapshot,
            check=False,
        )
    if package_path.read_bytes() != original:
        raise ValueError("Actual approval receipt changed during regression")
    print("Actual ACTIVE receipt preserved: " + hashlib.sha256(original).hexdigest())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
