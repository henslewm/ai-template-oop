"""Read-only retained-branch integration readiness; no apply, merge or deployment."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import acceptance as a
from scripts import feedback as f
from scripts import workflow_handoff as handoff
from scripts import workflow_state as ws

Json = dict[str, Any]
require = handoff.require
sha = handoff.sha
REPO = "henslewm/ai-template-oop"
REVIEW_CAP = 4
BOTS = {"chatgpt-codex-connector[bot]", "coderabbitai[bot]"}


def tree(root: Path, commit: str) -> dict[str, tuple[str, str]]:
    require(
        isinstance(commit, str) and re.fullmatch(r"[a-f0-9]{40}", commit),
        "Exact commit required",
    )
    require(
        handoff.git(root, "cat-file", "-t", commit).strip() == b"commit",
        "Missing commit",
    )
    result = {}
    for row in handoff.git(root, "ls-tree", "-rz", commit).split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            require(
                kind == "blob" and mode in {"100644", "100755"},
                "Linked or non-file candidate tree",
            )
            name = path.decode("utf-8")
            a.h.checked_path(name)
            result[name] = (mode, oid)
    require(len(result) <= 10000, "Candidate tree exceeds bound")
    return result


def candidate_tree(journal: ws.Journal, submission: Json, commit: str) -> Json:
    expected = tree(journal.root, submission["commits"]["base"])
    for change in submission["bundle"]["changes"]:
        payload = base64.b64decode(change["content_base64"], validate=True)
        # Git object identity, distinct from the preserved raw SHA256 evidence.
        oid = hashlib.sha1(
            b"blob " + str(len(payload)).encode() + b"\0" + payload
        ).hexdigest()
        path = change["path"]
        expected[path] = (expected.get(path, ("100644", ""))[0], oid)
    actual = tree(journal.root, commit)
    require(
        actual == expected, "Integration tree differs from exact accepted replacement"
    )
    for input_commit in submission["commits"].values():
        handoff.git(journal.root, "merge-base", "--is-ancestor", input_commit, commit)
    return {
        "commit": commit,
        "tree_sha256": sha(actual),
        "accepted_commits": submission["commits"],
        "submission_sha256": sha(submission),
    }


def _reference(journal: ws.Journal, value: Json) -> ws.Evidence:
    f.exact(value, {"path", "sha256", "size"})
    ref = ws.Evidence(**value)
    require(
        journal.evidence(ref.path) == ref and ref.size > 0,
        "Check/review evidence changed or empty",
    )
    return ref


def record_validation(
    journal: ws.Journal, task_stream: str, candidate_commit: str, manifest_path: str
) -> Json:
    """Register coordinator-observed evidence; never execute declared commands.

    Actors and PASS observations are trusted coordinator declarations, just as
    M5's host-side observations. Workers cannot write this Journal or evidence.
    """
    accepted, _, native, _ = a.current(journal, task_stream)
    require(
        accepted["anchor"] == native["anchor"] == ws.active_anchor(journal.root),
        "Current approval differs from accepted task",
    )
    s = accepted["submission"]
    require(
        accepted["accepted"] is not None
        and accepted["synced"] is not None
        and native["status"] == "ACCEPTED",
        "Independent synchronized acceptance required",
    )
    binding = candidate_tree(journal, s, candidate_commit)
    ref = journal.evidence(manifest_path)
    manifest = a.h.parse(a.h.read_file(journal.directory / ref.path), ws.MAX_EVENT)
    require(manifest["binding"] == binding, "Validation manifest candidate differs")
    refs = [ref]
    for check in manifest["checks"]:
        refs.append(_reference(journal, check["log"]))
    refs.append(_reference(journal, manifest["review"]["report"]))
    if manifest["interface_change"] is not None:
        refs.append(_reference(journal, manifest["interface_change"]["approval"]))
    require(len(refs) == len({r.path for r in refs}), "Duplicate validation evidence")
    data = {
        "version": "destination-integration-validation-1",
        "task_stream": task_stream,
        "binding": binding,
        "manifest": asdict(ref),
    }
    stream = "integration:" + sha(data)
    if stream not in journal.verify():
        journal.create(
            stream, family="project", binding=binding, data=data, evidence=tuple(refs)
        )
    require(
        journal.read(stream)[0][0]["data"] == data, "Conflicting validation receipt"
    )
    return {"stream": stream, "head": asdict(journal.read(stream)[1])}


def gh(endpoint: str) -> Any:
    result = subprocess.run(
        ["gh", "api", endpoint], capture_output=True, timeout=30, check=True
    )
    return a.h.parse(result.stdout, ws.MAX_EVENT)


def _pages(endpoint: str, *, key: str | None = None) -> list[Json]:
    rows = []
    for page in range(1, 11):
        value = gh(
            endpoint + ("&" if "?" in endpoint else "?") + f"per_page=100&page={page}"
        )
        batch = value[key] if key else value
        require(isinstance(batch, list), "Hosting list unavailable")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError("Hosting pagination exceeds bound")


def hosting(root: Path, number: int, repository: str = REPO) -> Json:
    """Fresh read-only GitHub and origin facts; an unavailable endpoint refuses."""
    require(repository == REPO, "Destination repository required")
    require(type(number) is int and number > 0, "Positive PR number required")
    origin = handoff.git(root, "remote", "get-url", "origin").decode().strip()
    require(
        origin
        in {f"https://github.com/{repository}.git", f"git@github.com:{repository}.git"},
        "Origin is not destination",
    )
    repo = gh(f"repos/{repository}")
    pr = gh(f"repos/{repository}/pulls/{number}")
    head, base = pr["head"], pr["base"]
    branch = gh(f"repos/{repository}/branches/{quote(base['ref'], safe='')}")
    required = []
    if branch["protected"]:
        protection = gh(
            f"repos/{repository}/branches/{quote(base['ref'], safe='')}/protection"
        )
        checks = protection.get("required_status_checks") or {}
        required.extend(
            checks.get("checks")
            or [{"context": c, "app_id": None} for c in checks.get("contexts", [])]
        )
    rules = gh(f"repos/{repository}/rules/branches/{quote(base['ref'], safe='')}")
    unsupported = []
    for rule in rules:
        if rule["type"] == "required_status_checks":
            required.extend(
                {"context": c["context"], "app_id": c.get("integration_id")}
                for c in rule["parameters"]["required_status_checks"]
            )
        elif rule["type"] in {
            "workflows",
            "required_workflows",
            "required_deployments",
            "required_code_scanning",
        }:
            unsupported.append(rule["type"])
    statuses = _pages(f"repos/{repository}/commits/{head['sha']}/statuses")
    checks = _pages(
        f"repos/{repository}/commits/{head['sha']}/check-runs", key="check_runs"
    )
    reviews = _pages(f"repos/{repository}/pulls/{number}/reviews")
    comments = _pages(f"repos/{repository}/issues/{number}/comments")
    query = "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){pageInfo{hasNextPage} nodes{isResolved}}}}}"
    owner, name = repository.split("/")
    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            "query=" + query,
            "-f",
            "owner=" + owner,
            "-f",
            "name=" + name,
            "-F",
            "number=" + str(number),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    threads = a.h.parse(result.stdout, ws.MAX_EVENT)["data"]["repository"][
        "pullRequest"
    ]["reviewThreads"]
    remote = {}
    for row in (
        handoff.git(root, "ls-remote", "--heads", "origin").decode().splitlines()
    ):
        oid, ref = row.split()
        remote[ref.removeprefix("refs/heads/")] = oid
    return {
        "repository": repo["full_name"],
        "delete_branch_on_merge": repo["delete_branch_on_merge"],
        "number": number,
        "state": pr["state"],
        "draft": pr["draft"],
        "head": head["sha"],
        "branch": head["ref"],
        "head_repository": head["repo"]["full_name"],
        "base": base["sha"],
        "base_branch": base["ref"],
        "base_repository": base["repo"]["full_name"],
        "mergeable": pr["mergeable"],
        "mergeable_state": pr["mergeable_state"],
        "required": sorted(
            {(r["context"], r.get("app_id")) for r in required},
            key=lambda r: (r[0], str(r[1])),
        ),
        "required_policy": "CONFIGURED" if required else "NONE_CONFIGURED",
        "unsupported_rules": unsupported,
        "statuses": statuses,
        "checks": checks,
        "reviews": reviews,
        "comments": comments,
        "unresolved": sum(not t["isResolved"] for t in threads["nodes"]),
        "more_threads": threads["pageInfo"]["hasNextPage"],
        "remote_branches": remote,
    }


def _checks(live: Json) -> list[str]:
    blockers = []
    if live["required_policy"] not in {"CONFIGURED", "NONE_CONFIGURED"}:
        blockers.append("LIVE_REQUIRED_POLICY_UNAVAILABLE")
    if bool(live["required"]) != (live["required_policy"] == "CONFIGURED"):
        blockers.append("LIVE_REQUIRED_POLICY_INCONSISTENT")
    for name, app in live["required"]:
        runs = [
            c
            for c in live["checks"]
            if c["name"] == name
            and c["head_sha"] == live["head"]
            and (app in (None, -1) or c["app"]["id"] == app)
        ]
        # A rerun's latest ID replaces its earlier result for that app.
        by_app = {}
        for check in runs:
            key = check["app"]["id"]
            if key not in by_app or by_app[key]["id"] < check["id"]:
                by_app[key] = check
        statuses = [
            s for s in live["statuses"] if s["context"] == name and app in (None, -1)
        ]
        latest_status = max(statuses, key=lambda s: s["id"], default=None)
        outcomes = [
            c["status"] == "completed" and c["conclusion"] == "success"
            for c in by_app.values()
        ]
        if latest_status:
            outcomes.append(latest_status["state"] == "success")
        if not outcomes or not all(outcomes):
            blockers.append("REQUIRED_CHECK_MISSING_OR_NOT_SUCCESS:" + name)
    return blockers


def _validation(
    journal: ws.Journal,
    receipt: Json,
    task_stream: str,
    binding: Json,
    live: Json,
    accepted: Json,
) -> Json:
    events, head = journal.read(receipt["stream"])
    require(
        asdict(head) == receipt["head"] and len(events) == 1, "Stale validation receipt"
    )
    data = events[0]["data"]
    require(
        data["version"] == "destination-integration-validation-1"
        and data["task_stream"] == task_stream
        and data["binding"] == binding,
        "Wrong integration evidence binding",
    )
    ref = _reference(journal, data["manifest"])
    manifest = a.h.parse(a.h.read_file(journal.directory / ref.path), ws.MAX_EVENT)
    f.exact(manifest, {"binding", "checks", "review", "interface_change"})
    require(manifest["binding"] == binding, "Stale check candidate")
    require(
        isinstance(manifest["checks"], list)
        and len(manifest["checks"]) == 3
        and {c["id"] for c in manifest["checks"]}
        == {"contract", "boundary", "affected-runtime"},
        "Contract/boundary/affected checks required",
    )
    for check in manifest["checks"]:
        f.exact(check, {"id", "status", "log"})
        require(check["status"] == "PASSED", "Independent candidate check not passed")
        _reference(journal, check["log"])
    review = manifest["review"]
    f.exact(review, {"actor", "head", "verdict", "report"})
    a.independent(review["actor"], accepted["implementers"])
    require(
        review["head"] == binding["commit"] and review["verdict"] == "APPROVE",
        "Review must approve exact candidate head",
    )
    _reference(journal, review["report"])
    s = accepted["submission"]
    base_tree, current_tree = (
        tree(journal.root, live["base"]),
        tree(journal.root, binding["commit"]),
    )
    changed = {
        p
        for p in base_tree.keys() | current_tree.keys()
        if p.startswith("contracts/") and base_tree.get(p) != current_tree.get(p)
    }
    all_changed = {
        p
        for p in base_tree.keys() | current_tree.keys()
        if base_tree.get(p) != current_tree.get(p)
    }
    allowed = {change["path"] for change in s["bundle"]["changes"]}
    interface = manifest["interface_change"]
    if changed:
        require(
            interface is not None,
            "Interface change requires owner approval and linked UI/mocks",
        )
        f.exact(
            interface,
            {
                "owner",
                "architect",
                "ui_commit",
                "mocks_path",
                "linked_paths",
                "approval",
            },
        )
        linked = interface["linked_paths"]
        require(
            isinstance(linked, list)
            and 1 <= len(linked) <= 128
            and len(set(linked)) == len(linked),
            "Exact bounded linked interface paths required",
        )
        for path in linked:
            a.h.checked_path(path)
            require(
                path.startswith(
                    ("contracts/", "src/ui/", "tests/ui/", "tests/test_contract_")
                )
                or path == "tests/test_ui.py",
                "Unrelated path in interface approval",
            )
        require(
            changed <= set(linked) and set(linked) <= all_changed,
            "Interface linked paths differ from candidate",
        )
        allowed.update(linked)
        approval = a.h.parse(
            a.h.read_file(
                journal.directory / _reference(journal, interface["approval"]).path
            ),
            ws.MAX_EVENT,
        )
        owner = f.wp.read_json(journal.root / "config/workflow-bootstrap.json")[
            "approval"
        ]["approved_by"]
        require(
            f.actor_identity(interface["owner"]) == f.actor_identity(owner)
            and f.actor_identity(interface["architect"])
            == f.actor_identity(accepted["architect"]),
            "Named owner/architect interface approval required",
        )
        require(
            interface["ui_commit"] == s["commits"]["ui"]
            and interface["mocks_path"] == "src/ui/mocks.py",
            "Linked accepted UI and mocks required",
        )
        ui = tree(journal.root, interface["ui_commit"])
        require(
            all(
                ui.get(path) == current_tree.get(path)
                for path in linked
                if path.startswith(("src/ui/", "tests/ui/"))
                or path == "tests/test_ui.py"
            ),
            "Linked UI paths differ from accepted UI commit",
        )
        require(
            ui.get("src/ui/mocks.py") == current_tree.get("src/ui/mocks.py")
            and "src/ui/mocks.py" in ui,
            "UI mocks differ from candidate",
        )
        require(
            any(
                p.startswith("src/ui/") and base_tree.get(p) != current_tree.get(p)
                for p in current_tree
            ),
            "Changed interface needs linked UI work",
        )
        require(
            approval
            == {
                "candidate": binding,
                "interface_revision": s["scope"]["interface_revision"],
                "changed_paths": sorted(changed),
                "owner": interface["owner"],
                "architect": interface["architect"],
                "ui_commit": interface["ui_commit"],
                "mocks_path": interface["mocks_path"],
                "linked_paths": linked,
            },
            "Interface approval binding differs",
        )
    else:
        require(interface is None, "Unexpected interface-change declaration")
    require(
        all_changed <= allowed,
        "Candidate carries unrelated unaccepted changes from its base",
    )
    return {
        "manifest": asdict(ref),
        "review_actor": review["actor"],
        "interface_changed": bool(changed),
    }


def review_history(live, *, allow_unverified=False):
    """Shared automated-review history gates for offline and live delivery."""
    blockers = []
    rounds = [
        r
        for r in live["reviews"]
        if r["user"]["login"] in BOTS
        and r.get("commit_id")
        and (r.get("body", "").strip() or r["state"] != "COMMENTED")
    ]
    clean_rounds = [
        comment
        for comment in live.get("comments", [])
        if comment["user"]["login"] in BOTS
        and re.search(
            r"\*\*Reviewed commit:\*\*\s*`[0-9a-f]{7,40}`", comment.get("body") or ""
        )
    ]
    round_count = len(rounds) + len(clean_rounds)
    ambiguous_round_history = any(
        comment["user"]["login"] in BOTS
        and (
            "codex-pull-request-review-summary" in (comment.get("body") or "")
            or (
                "Review trigger" in (comment.get("body") or "")
                and "Completed" in (comment.get("body") or "")
            )
            or (
                comment in clean_rounds
                and comment.get("updated_at") != comment.get("created_at")
            )
        )
        for comment in live.get("comments", [])
    )
    if ambiguous_round_history and not allow_unverified:
        blockers.append("AUTOMATED_REVIEW_HISTORY_UNVERIFIABLE")
    if round_count > REVIEW_CAP:
        blockers.append("REVIEW_ROUND_CAP_EXCEEDED")
    if live["unresolved"] or live["more_threads"]:
        blockers.append("UNRESOLVED_OR_UNOBSERVED_REVIEW_THREADS")
    return {
        "blockers": blockers,
        "round_count": round_count,
        "ambiguous": ambiguous_round_history,
    }


def assess(
    journal: ws.Journal,
    task_stream: str,
    candidate_commit: str,
    receipt: Json,
    pr: int,
    *,
    retained: Json | None = None,
) -> Json:
    """Reobserve all facts on every call. A saved READY result grants no authority."""
    view = handoff.build(journal, task_stream)
    accepted, _, native, _ = a.current(journal, task_stream)
    require(
        accepted["anchor"] == native["anchor"] == ws.active_anchor(journal.root),
        "Current approval differs from accepted task",
    )
    require(
        accepted["accepted"] is not None
        and accepted["synced"] is not None
        and native["status"] == "ACCEPTED"
        and a.satisfied(accepted),
        "Independent synchronized acceptance required",
    )
    binding = candidate_tree(journal, accepted["submission"], candidate_commit)
    live = hosting(journal.root, pr)
    blockers = list(view["content"]["blockers"])
    require(
        live["repository"]
        == live["head_repository"]
        == live["base_repository"]
        == REPO,
        "Cross-repository promotion refused",
    )
    require(
        live["head"] == candidate_commit, "Changed PR head invalidates review/checks"
    )
    require(
        live["branch"].startswith(("feature/", "ui/"))
        and live["base_branch"] == "main",
        "Retained feature/UI PR into main required",
    )
    local = (
        handoff.git(journal.root, "rev-parse", "refs/heads/" + live["branch"])
        .decode()
        .strip()
    )
    require(
        local == live["head"] == live["remote_branches"].get(live["branch"]),
        "Local/origin/PR branch differs",
    )
    require(
        live["base"] == live["remote_branches"].get(live["base_branch"]),
        "PR base differs from current origin main",
    )
    handoff.git(
        journal.root, "merge-base", "--is-ancestor", live["base"], candidate_commit
    )
    for commit in accepted["submission"]["commits"].values():
        tree(journal.root, commit)
    validation = _validation(journal, receipt, task_stream, binding, live, accepted)
    if live["delete_branch_on_merge"] is not False:
        blockers.append("AUTOMATIC_BRANCH_DELETION_MUST_BE_DISABLED")
    if (
        live["state"] != "open"
        or live["draft"]
        or live["mergeable"] is not True
        or live["mergeable_state"] not in {"clean", "unstable"}
    ):
        blockers.append("PR_NOT_READY")
    if not view["content"]["git"]["clean"]:
        blockers.append("WORKTREE_NOT_CLEAN")
    if live["unsupported_rules"]:
        blockers.append("UNSUPPORTED_LIVE_REQUIRED_RULE")
    blockers.extend(_checks(live))
    review_status = review_history(live)
    blockers.extend(review_status["blockers"])
    round_count = review_status["round_count"]
    ambiguous_round_history = review_status["ambiguous"]
    latest = {}
    for review in live["reviews"]:
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            actor = review["user"]["login"]
            if actor not in latest or review["id"] > latest[actor]["id"]:
                latest[actor] = review
    if any(r["state"] == "CHANGES_REQUESTED" for r in latest.values()):
        blockers.append("OUTSTANDING_CHANGES_REQUESTED")
    local_refs = {
        row.split()[1].removeprefix("refs/heads/"): row.split()[0]
        for row in handoff.git(journal.root, "show-ref", "--heads")
        .decode()
        .splitlines()
    }
    refs = {"local": local_refs, "origin": live["remote_branches"]}
    if retained is not None:
        f.exact(retained, {"local", "origin"})
        require(
            all(isinstance(values, dict) and values for values in retained.values()),
            "Nonempty retained branch baselines required",
        )
        for where, values in retained.items():
            for name, commit in values.items():
                require(name in refs[where], "Retained branch disappeared")
                handoff.git(
                    journal.root,
                    "merge-base",
                    "--is-ancestor",
                    commit,
                    refs[where][name],
                )
    else:
        blockers.append("RETAINED_BRANCH_BASELINE_REQUIRED")
    handoff.verify(journal, view)
    require(
        hosting(journal.root, pr) == live,
        "Live facts changed during readiness; reobserve",
    )
    return {
        "version": "destination-readiness-1",
        "observed_at": handoff.now(),
        "binding": binding,
        "readiness": "READY_FOR_EXPLICIT_INTEGRATION" if not blockers else "HOLD",
        "blockers": sorted(set(blockers)),
        "view_authority_sha256": view["authority_sha256"],
        "hosting_sha256": sha(live),
        "required_policy": live["required_policy"],
        "validation": validation,
        "retained_refs": refs,
        "review_rounds": None if ambiguous_round_history else round_count,
        "observed_immutable_review_rounds": round_count,
        "review_history": "UNVERIFIED"
        if ambiguous_round_history
        else "COMPLETE_FROM_HOST_RECORDS",
        "review_cap": REVIEW_CAP,
        "accepted": True,
        "integrated": "NOT_ESTABLISHED",
        "verified_dependencies": view["content"]["tasks"][0]["dependencies"],
        "deployed": "NOT_ESTABLISHED",
        "execution_authorized": False,
        "merge_authorized": False,
        "branches_retained": True if retained is not None else "BASELINE_REQUIRED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ready = sub.add_parser("ready")
    ready.add_argument("task")
    ready.add_argument("--candidate", required=True)
    ready.add_argument("--receipt", required=True, type=Path)
    ready.add_argument("--pr", required=True, type=int)
    ready.add_argument(
        "--retained", type=Path, help="Prior readiness retained_refs baseline"
    )
    register = sub.add_parser("record-validation")
    register.add_argument("task")
    register.add_argument("--candidate", required=True)
    register.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        journal = ws.Journal(args.root)
        result = (
            assess(
                journal,
                args.task,
                args.candidate,
                a.h.parse(a.h.read_file(args.receipt), handoff.MAX_VIEW),
                args.pr,
                retained=a.h.parse(a.h.read_file(args.retained), handoff.MAX_VIEW)
                if args.retained
                else None,
            )
            if args.command == "ready"
            else record_validation(journal, args.task, args.candidate, args.manifest)
        )
        print(json.dumps(result, indent=2))
        return 2 if result.get("readiness") == "HOLD" else 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ):
        print(
            "Readiness refused; current acceptance, candidate, evidence or live facts unavailable/stale",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
