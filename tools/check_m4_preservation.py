"""Read-only M4 preservation audit against the pre-fetch snapshot and M3 evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.workflow_state import control_directory  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *args: str) -> str:
    return (
        subprocess.check_output(["git", "-C", str(root), *args])
        .decode()
        .replace("\r\n", "\n")
    )


def inventory(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}


def audit() -> dict:
    before = json.loads(
        (ROOT / "docs/workflow-migration/M4_PRESERVATION.json").read_text()
    )
    m3 = json.loads((ROOT / "docs/workflow-migration/M3_PRESERVATION.json").read_text())
    protected = {}
    for name in ("ai-template-oop", "universal-ai-project-template"):
        root, expected = ROOT.parent / name, m3[name]
        head, status = (
            git(root, "rev-parse", "HEAD").strip(),
            git(root, "status", "--porcelain=v2"),
        )
        index = Path(
            git(
                root, "rev-parse", "--path-format=absolute", "--git-path", "index"
            ).strip()
        )
        names = git(
            root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        ).split("\x00")
        files = {p: sha(root / p) for p in names if p and (root / p).is_file()}
        assert head == expected["head"] and status == expected["status"], name
        assert (
            sha(index) == expected["index_sha256"] and files == expected["file_sha256"]
        ), name
        protected[name] = {
            "head": head,
            "index_sha256": sha(index),
            "status": status,
            "files": len(files),
            "matches": True,
        }
    for p, expected in before["m3_files"].items():
        raw = (ROOT / p).read_bytes()
        if p == "scripts/feedback.py":
            # M5 adds only this explicit integration hook. Removing exactly the
            # known block must reproduce the reviewed raw M3 bytes, including
            # original line endings. No baseline hash is refreshed.
            block = (
                "    # BEGIN M5 explicit acceptance integration\n"
                "    if (\n"
                '        kind == "REVIEW"\n'
                '        and data.get("acceptance_version") == "destination-acceptance-1"\n'
                "    ):\n"
                "        from scripts.acceptance import apply_feedback\n\n"
                "        return apply_feedback(state, event)\n"
                "    # END M5 explicit acceptance integration\n"
            ).encode()
            if block in raw:
                assert raw.count(block) == 1
                raw = raw.replace(block, b"", 1)
        assert hashlib.sha256(raw).hexdigest() == expected, p + " changed"
    state = control_directory(ROOT)
    assert str(state) == before["canonical_state_path"]
    assert inventory(state) == before["canonical_inventory"], "Canonical state changed"
    assert inventory(Path(before["archive_path"])) == before["archive_inventory"], (
        "Archive changed"
    )
    allowed = {"scripts/workflow_runtime.py", "scripts/workflow_scope.py"}
    changed = [
        p
        for p, expected in before["existing_tracked_files"].items()
        if sha(ROOT / p) != expected
    ]
    assert set(changed) <= allowed, "Unrelated/frozen tracked files changed: " + repr(
        changed
    )
    refs = {
        name: tip
        for tip, name in (line.split() for line in git(ROOT, "show-ref").splitlines())
    }
    old_refs = {
        name: tip
        for tip, name in (line.split() for line in before["starting_refs"].splitlines())
    }
    assert old_refs.keys() <= refs.keys(), "A retained ref disappeared"
    for name, tip in old_refs.items():
        if (
            name.startswith("refs/heads/")
            and name != "refs/heads/feature/workflow-migration"
        ):
            assert refs[name] == tip, "Protected local branch moved"
    return {
        "protected": protected,
        "m3_files_preserved": len(before["m3_files"]),
        "m3_preservation_note": "17 byte-identical files; feedback.py reproduces original bytes after removing the exact additive M5 hook",
        "canonical_files_preserved": len(before["canonical_inventory"]),
        "archive_files_preserved": len(before["archive_inventory"]),
        "existing_tracked_changes": changed,
        "frozen_other_files_preserved": True,
        "head": git(ROOT, "rev-parse", "HEAD").strip(),
        "refs": refs,
        "branch": git(ROOT, "branch", "--show-current").strip(),
        "passed": True,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
