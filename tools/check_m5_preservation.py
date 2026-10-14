"""Read-only M5 entry preservation audit; no baseline refresh or state writes."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.check_m4_preservation import audit, git, sha  # noqa: E402


def check():
    result = audit()
    entry = json.loads(
        (ROOT / "docs/workflow-migration/M5_PRESERVATION.json").read_text()
    )
    changed = [
        p
        for p, expected in entry["tracked_sha256"].items()
        if sha(ROOT / p) != expected
    ]
    assert set(changed) <= {
        "scripts/feedback.py",
        "scripts/workflow_runtime.py",
        "tools/check_m4_preservation.py",
    }, changed
    refs = {
        name: tip
        for tip, name in (row.split() for row in git(ROOT, "show-ref").splitlines())
    }
    old = {
        name: tip for tip, name in (row.split() for row in entry["refs"].splitlines())
    }
    assert old.keys() <= refs.keys(), "Retained ref disappeared"
    for name, tip in old.items():
        if name.startswith("refs/heads/"):
            if name != "refs/heads/feature/workflow-migration":
                assert refs[name] == tip, "Protected branch moved"
            else:
                git(ROOT, "merge-base", "--is-ancestor", tip, refs[name])
    return {
        **result,
        "m5_entry_tracked_changes": changed,
        "m5_other_entry_files_byte_identical": True,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
