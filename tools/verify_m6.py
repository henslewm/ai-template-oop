"""Record one final M6 split verification, exact source hashes and actual output."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
SOURCE = [
    "scripts/workflow_handoff.py",
    "scripts/workflow_closeout.py",
    "tests/test_workflow_handoff.py",
    "tests/test_workflow_closeout.py",
    "tools/check_m6_preservation.py",
    "tools/verify_m6.py",
]
IMAGE = "sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e"


def hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE
    }


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    output = ROOT / "docs/workflow-migration/M6_VERIFICATION.json"
    if output.exists():
        raise ValueError(
            "Retain prior verification; choose a separately named follow-up recorder"
        )
    environment = {
        **os.environ,
        "WORKFLOW_TEST_IMAGE": IMAGE,
        "GIT_OPTIONAL_LOCKS": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    py = [sys.executable, "-B"]
    commands = [
        [
            *py,
            "-m",
            "pytest",
            "-q",
            "-rs",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--ignore=tests/test_workflow_approval.py",
        ],
        [*py, "tools/check_workflow_approval.py"],
        [
            *py,
            "scripts/validate_workflow_approval.py",
            "--fingerprint",
            "--check-source",
            "--require-active",
        ],
        [*py, "scripts/workflow_state.py", "verify"],
        [*py, "tools/validate_boundaries.py"],
        *[
            [*py, "tools/check_" + milestone + "_preservation.py"]
            for milestone in ("m4", "m5", "m1_acceptance", "m6")
        ],
        ["ruff", "check", *SOURCE],
        ["ruff", "format", "--check", *SOURCE],
        ["uvx", "--offline", "ty", "check", *SOURCE],
        [
            "uvx",
            "--offline",
            "basedpyright",
            "--pythonpath",
            sys.executable,
            "--outputjson",
            *SOURCE,
        ],
        ["git", "diff", "--check"],
    ]
    directory = Path(tempfile.mkdtemp(prefix="m6-final-verification-"))
    record = {
        "scope": "M6 AC-10, integration/readiness AC-11 and AC-12 only",
        "started_at": now(),
        "image": IMAGE,
        "source_sha256": hashes(),
        "logs": str(directory),
        "checks": [],
    }
    for index, command in enumerate(commands):
        diagnostic = "basedpyright" in command
        print(f"START {index + 1}/{len(commands)}: {' '.join(command)}", flush=True)
        started = time.monotonic()
        before = hashes()
        log = directory / f"{index + 1:02d}.log"
        with log.open("wb") as stream:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        text = log.read_text(encoding="utf-8", errors="replace")
        check = {
            "argv": command,
            "exit_code": result.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "output": text,
            "diagnostic_only": diagnostic,
            "source_sha256_before": before,
            "source_sha256_after": hashes(),
        }
        if diagnostic:
            try:
                data = json.loads(text)
                check["summary"] = data["summary"]
            except (ValueError, KeyError):
                check["diagnostic_unavailable"] = True
        record["checks"].append(check)
        record["source_hashes_unchanged"] = (
            record.get("source_hashes_unchanged", True)
            and before == record["source_sha256"]
            and check["source_sha256_after"] == record["source_sha256"]
        )
        output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(
            f"END {index + 1}: exit={result.returncode}, {check['seconds']}s",
            flush=True,
        )
    record["finished_at"] = now()
    record["required_gates_passed"] = record["source_hashes_unchanged"] and all(
        c["exit_code"] == 0 for c in record["checks"] if not c["diagnostic_only"]
    )
    record["basedpyright_green"] = all(
        c["exit_code"] == 0 for c in record["checks"] if c["diagnostic_only"]
    )
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if record["required_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
