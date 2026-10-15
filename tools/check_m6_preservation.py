"""Read-only M6 additive-change audit of the retained original environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.check_m1_acceptance_preservation import check as prior_check  # noqa: E402
from tools.check_m4_preservation import git, sha  # noqa: E402


def check() -> dict:
    entry = json.loads(
        (ROOT / "docs/workflow-migration/M6_PRESERVATION.json").read_bytes()
    )
    prior = prior_check()
    changed = [
        p for p, digest in entry["tracked_sha256"].items() if sha(ROOT / p) != digest
    ]
    assert not changed, "M6 changed existing files: " + repr(changed)
    old = {
        name: tip for tip, name in (row.split() for row in entry["refs"].splitlines())
    }
    current = {
        name: tip
        for tip, name in (row.split() for row in git(ROOT, "show-ref").splitlines())
    }
    assert old.keys() <= current.keys(), "Retained ref disappeared"
    git(ROOT, "merge-base", "--is-ancestor", entry["entry_head"], "HEAD")
    for name, tip in old.items():
        if name.startswith("refs/heads/"):
            if name == "refs/heads/feature/workflow-migration":
                git(ROOT, "merge-base", "--is-ancestor", tip, current[name])
            else:
                assert current[name] == tip, "Protected local branch moved: " + name
    return {
        **prior,
        "m6_entry_files_checked": len(entry["tracked_sha256"]),
        "all_m6_entry_files_byte_identical": True,
        "m6_entry_refs_retained": True,
    }


if __name__ == "__main__":
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    print(json.dumps(check(), indent=2))
