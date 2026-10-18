"""Separate, host-local live authority; the historical ACTIVE receipt is read-only."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_workflow_approval as approval

PROFILE = "run-live-pilot-approval/approval.json"
PROJECT = "live-pilot-2026-10"
OBJECTIVE = "Improve the operator start/resume experience"
IMAGE = "sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e"
WRITE_PATHS = [
    "README.md",
    "scripts/operator_cli.py",
    "start.ps1",
    "tests/test_operator_cli.py",
]
READ_PATHS = sorted(
    WRITE_PATHS
    + [
        "contracts/operator.py",
        "scripts/operator_service.py",
        "config/pilot-onboarding.json",
        "tests/pilot_shell_checks.py",
    ]
)
LIMITS = {
    "task_usd": 1,
    "project_usd": 5,
    "worker_attempts": 2,
    "reviewer_attempts": 2,
    "context_chars": 40000,
    "output_tokens": 8192,
}
PROVIDER = {
    "name": "openai",
    "endpoint": "https://api.openai.com/v1/responses",
    "worker": "gpt-6-luna",
    "escalation": "gpt-6.1-sol",
    "reviewer": "gpt-6.1-sol",
    "effort": "medium",
}


def inventory(root: Path, commit: str | None = None) -> dict[str, str]:
    """Bind the complete executing Python/config/runtime closure, excluding the shell."""
    if commit is None:
        extra = (
            approval.git(root, "ls-files", "--others", "--exclude-standard")
            .decode()
            .splitlines()
        )
        approval.require(
            not extra,
            "Unreviewed untracked pilot input; preserve and reconcile it before activation",
        )
    names = (
        approval.git(root, "ls-tree", "-r", "--name-only", commit or "HEAD")
        .decode()
        .splitlines()
    )
    if commit is None:
        # Ignored output files are still inputs to the scoped Docker export.
        # Every existing input must belong to the delivery base, even when the
        # worker leaves it unchanged and it never appears in the replacement bundle.
        approval.require(
            all(p in names or not (root / p).exists() for p in READ_PATHS),
            "Untracked pilot scope input; preserve and reconcile it before activation",
        )
    names = [
        p
        for p in names
        if p not in WRITE_PATHS
        and (
            p.startswith(("scripts/", "contracts/", "config/", "runtime/", "tools/"))
            or p == "tests/pilot_shell_checks.py"
        )
    ]
    return {
        p: approval.content_digest(
            approval.git(root, "show", f"{commit}:{p}")
            if commit
            else approval.safe_file(root, p).read_bytes()
        )
        for p in names
    }


def load_profile(root: Path) -> dict:
    from scripts import workflow_state as ws

    root = Path(root).resolve()
    journal = ws.Journal(root)
    path = journal.directory / PROFILE
    approval.require(
        path.is_file(),
        "Live pilot approval missing; offline restrictions remain effective",
    )
    profile = approval.read_json(approval.safe_file(journal.directory, PROFILE))
    approval.exact(
        profile,
        {
            "version",
            "approved_by",
            "approved_at",
            "foundation",
            "identity",
            "implementation_commit",
            "implementation",
            "review",
            "image",
            "read_paths",
            "write_paths",
            "provider",
            "limits",
            "project",
            "objective",
            "delivery",
            "fingerprint",
        },
        "live pilot approval",
    )
    body = {k: v for k, v in profile.items() if k != "fingerprint"}
    approval.require(
        profile["fingerprint"] == ws._digest(approval.canonical(body)),
        "Pilot fingerprint differs",
    )
    approval.require(
        profile["version"] == "live-pilot-1" and profile["approved_by"] == "Winston",
        "Invalid pilot approval",
    )
    ws._instant(profile["approved_at"])
    approval.require(
        profile["foundation"] == ws.active_anchor(root), "Pilot foundation changed"
    )
    approval.require(
        profile["identity"] == journal.identity, "Pilot belongs to a different checkout"
    )
    approval.require(
        Path(journal.identity) == root / ".git",
        "Pilot requires an independent checkout",
    )
    origin = approval.git(root, "remote", "get-url", "origin").decode().strip()
    approval.require(
        origin
        in {
            "https://github.com/henslewm/ai-template-oop.git",
            "git@github.com:henslewm/ai-template-oop.git",
        },
        "Pilot origin is not the approved delivery repository",
    )
    approval.require(
        profile["image"] == IMAGE
        and profile["read_paths"] == READ_PATHS
        and profile["write_paths"] == WRITE_PATHS
        and profile["provider"] == PROVIDER
        and profile["limits"] == LIMITS
        and profile["project"] == PROJECT
        and profile["objective"] == OBJECTIVE,
        "Pilot authority changed",
    )
    approval.require(
        profile["delivery"]
        == {
            "repository": "henslewm/ai-template-oop",
            "base": "main",
            "publish": True,
            "merge_after_gates": True,
            "retain_branches": True,
        },
        "Pilot delivery authority differs",
    )
    commit = profile["implementation_commit"]
    approval.require(approval.hex_digest(commit, 40), "Invalid reviewed implementation")
    approval.git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    approval.require(
        profile["implementation"] == inventory(root, commit) == inventory(root),
        "Executing implementation differs from reviewed pilot",
    )
    review = profile["review"]
    approval.exact(
        review, {"head", "actor", "verdict", "report_sha256", "pr"}, "pilot review"
    )
    approval.require(
        approval.hex_digest(review["head"], 40)
        and inventory(root, review["head"]) == profile["implementation"]
        and review["verdict"] == "APPROVE"
        and review["actor"] != "Bootstrap implementer"
        and approval.hex_digest(review["report_sha256"], 64)
        and type(review["pr"]) is int
        and review["pr"] > 0,
        "Independent bootstrap review required",
    )
    return profile


def profile_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
