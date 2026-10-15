"""Record actual scoped or complete AC-02/AC-03 verification, without API calls."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e"
OWNED = [
    "tests/test_m1_acceptance.py",
    "tests/ac02_ac03_process.py",
    "tools/check_m1_acceptance_preservation.py",
    "tools/verify_m1_acceptance.py",
]
M5 = [
    "scripts/acceptance.py",
    "scripts/acceptance_runtime.py",
    "scripts/acceptance_report.py",
    "scripts/feedback.py",
    "scripts/workflow_runtime.py",
    "tools/check_m4_preservation.py",
    "tools/check_m5_preservation.py",
]


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in OWNED + M5}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--focused", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    env = dict(os.environ)
    env["WORKFLOW_TEST_IMAGE"] = IMAGE
    env["M1_EVIDENCE_DIR"] = str(
        Path(os.environ["TEMP"]) / ("ai-template-m1-evidence-" + uuid.uuid4().hex)
    )
    before = hashes()
    record: dict[str, Any] = {
        "scope": "M1 AC-02/AC-03 acceptance only; M6 not implemented",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": before,
        "image": IMAGE,
        "commands": [],
        "docker_evidence_directory": env["M1_EVIDENCE_DIR"],
    }

    def save():
        output.write_text(json.dumps(record, indent=2), encoding="utf-8")

    tests = (
        ["tests/test_m1_acceptance.py"]
        if args.focused
        else ["--ignore=tests/test_workflow_approval.py"]
    )
    commands = [
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
            *tests,
        ],
    ]
    if not args.focused:
        commands += [
            [sys.executable, "-B", "tools/check_workflow_approval.py"],
            [
                sys.executable,
                "-B",
                "scripts/validate_workflow_approval.py",
                "--fingerprint",
                "--check-source",
                "--require-active",
            ],
            [sys.executable, "-B", "scripts/workflow_state.py", "verify"],
            [sys.executable, "-B", "tools/validate_boundaries.py"],
            *[
                [sys.executable, "-B", "tools/check_" + suffix + "_preservation.py"]
                for suffix in ("m4", "m5", "m1_acceptance")
            ],
            ["ruff", "check", *OWNED, *M5],
            ["ruff", "format", "--check", *OWNED, *M5],
            [
                "uvx",
                "--offline",
                "ty",
                "check",
                "--python",
                sys.executable,
                *OWNED,
                *M5,
            ],
            ["uvx", "--offline", "basedpyright", "--outputjson", *M5[:3]],
            [
                "uvx",
                "--offline",
                "basedpyright",
                "--pythonpath",
                sys.executable,
                "--outputjson",
                *OWNED,
            ],
            ["git", "diff", "--check"],
        ]
    save()
    failed = False
    for command in commands:
        print("Running " + subprocess.list2cmdline(command), flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True
        )
        item: dict[str, Any] = {
            "argv": command,
            "exit_code": result.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if "basedpyright" in command:
            data = json.loads(result.stdout)
            item["summary"] = data["summary"]
            item["errors"] = [
                d for d in data["generalDiagnostics"] if d["severity"] == "error"
            ]
            item["warning_rules"] = dict(
                Counter(
                    d.get("rule", "other")
                    for d in data["generalDiagnostics"]
                    if d["severity"] == "warning"
                )
            )
            item["stdout_sha256"] = hashlib.sha256(result.stdout.encode()).hexdigest()
            item.pop("stdout")
            print(json.dumps(item["summary"]), flush=True)
        else:
            print(result.stdout[-2000:], flush=True)
            failed |= result.returncode != 0
        record["commands"].append(item)
        save()
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["source_hashes_unchanged"] = hashes() == before
    record["non_typing_gates_passed"] = not failed and record["source_hashes_unchanged"]
    directory = Path(env["M1_EVIDENCE_DIR"])
    record["docker_case_count"] = len(list(directory.glob("*.json")))
    record["non_typing_gates_passed"] &= record["docker_case_count"] == 13
    bundle = {
        p.stem: json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))
    }
    bundle_path = output.with_name(output.stem + "_DOCKER.json")
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    record["docker_bundle"] = {
        "path": str(bundle_path),
        "sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
    }
    save()
    return 0 if record["non_typing_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
