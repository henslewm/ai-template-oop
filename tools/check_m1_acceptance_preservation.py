"""Read-only delivered-M5 and protected-state audit for AC-02/AC-03 closure."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.check_m5_preservation import check as m5_check  # noqa: E402
from tools.check_m4_preservation import git, sha  # noqa: E402


def check():
    prior = m5_check()
    entry = json.loads(
        (ROOT / "docs/workflow-migration/M1_ACCEPTANCE_BASELINE.json").read_text()
    )
    git(ROOT, "merge-base", "--is-ancestor", entry["head"], "HEAD")
    changes = [
        p
        for p, expected in entry["tracked_sha256"].items()
        if sha(ROOT / p) != expected
    ]
    assert set(changes) <= {"docs/workflow-migration/M6_HANDOFF.md"}, changes
    refs = {
        name: tip
        for tip, name in (row.split() for row in git(ROOT, "show-ref").splitlines())
    }
    for name, tip in entry["refs"].items():
        assert name in refs, "Retained ref disappeared: " + name
        if name.startswith("refs/heads/"):
            if name == "refs/heads/feature/workflow-migration":
                git(ROOT, "merge-base", "--is-ancestor", tip, refs[name])
            else:
                assert refs[name] == tip, "Protected branch moved: " + name
    return {
        **prior,
        "delivered_m5_head": entry["head"],
        "m5_delivered_files_checked": len(entry["tracked_sha256"]),
        "m5_delivered_changes": changes,
        "m5_production_source_config_tests_tools_byte_identical": True,
        "m1_entry_refs_retained": True,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
