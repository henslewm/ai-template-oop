"""Exact accepted bundle publication; fresh hosting gates precede merge."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import tempfile

from scripts import execution_harness as h
from scripts import pilot_authority as authority
from scripts import workflow_closeout as closeout

BRANCH = "feature/operator-start-resume"


def _run(root, args, *, data=None, env=None):
    result = subprocess.run(
        args, cwd=root, input=data, capture_output=True, check=True, timeout=60, env=env
    )
    return result.stdout


def _git(root, *args, **kwargs):
    return _run(root, ["git", *args], **kwargs)


def retained(root):
    local = {
        r.split()[1].removeprefix("refs/heads/"): r.split()[0]
        for r in _git(root, "show-ref", "--heads").decode().splitlines()
    }
    remote = {
        r.split()[1].removeprefix("refs/heads/"): r.split()[0]
        for r in _git(root, "ls-remote", "--heads", "origin").decode().splitlines()
    }
    return {"local": local, "origin": remote}


def candidate(root, state):
    """Write Git objects only. No generated file or program executes on the host."""
    baseline = state["scope"]["base_commit"]
    with tempfile.TemporaryDirectory(prefix="pilot-index-") as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        _git(root, "read-tree", baseline, env=env)
        for item in state["bundle"]["changes"]:
            content = base64.b64decode(item["content_base64"], validate=True)
            blob = (
                _git(root, "hash-object", "-w", "--stdin", data=content)
                .decode()
                .strip()
            )
            _git(
                root,
                "update-index",
                "--add",
                "--cacheinfo",
                "100644",
                blob,
                item["path"],
                env=env,
            )
        tree = _git(root, "write-tree", env=env).decode().strip()
        commit = (
            _git(
                root,
                "commit-tree",
                tree,
                "-p",
                baseline,
                "-m",
                "Add worker-produced operator start and resume shell",
            )
            .decode()
            .strip()
        )
    verify_candidate(root, state, commit)
    return commit


def verify_candidate(root, state, commit):
    expected = closeout.tree(root, state["scope"]["base_commit"])
    for item in state["bundle"]["changes"]:
        content = base64.b64decode(item["content_base64"], validate=True)
        blob = _git(root, "hash-object", "--stdin", data=content).decode().strip()
        expected[item["path"]] = ("100644", blob)
    if closeout.tree(root, commit) != expected:
        raise ValueError("Delivery commit differs from independently accepted bundle")


def _exact_review(review, head):
    """Host-saved independent evidence; mutable hosting summaries add no authority."""
    return (
        isinstance(review, dict)
        and review.get("head") == head
        and review.get("verdict") == "APPROVE"
        and review.get("blocking_findings") == []
        and isinstance(review.get("actor"), str)
        and bool(review["actor"].strip())
        and isinstance(review.get("implementer", "Bootstrap implementer"), str)
        and bool(review.get("implementer", "Bootstrap implementer").strip())
        and review["actor"].strip().casefold()
        != review.get("implementer", "Bootstrap implementer").strip().casefold()
        and authority.approval.hex_digest(review.get("report_sha256"), 64)
    )


def _hosting_holds(live, head, review):
    """Review and check holds also apply when recovering an external merge."""
    blockers = closeout._checks(live)
    approved = _exact_review(review, head)
    history = closeout.review_history(live, allow_unverified=approved)
    blockers.extend(history["blockers"])
    live["automated_review_history"] = (
        "UNVERIFIED" if history["ambiguous"] else "OBSERVED"
    )
    if not approved:
        blockers.append("INDEPENDENT_EXACT_REVIEW_REQUIRED")
    if live["delete_branch_on_merge"] is not False:
        blockers.append("BRANCH_DELETION_ENABLED")
    if live["unsupported_rules"] or live["unresolved"] or live["more_threads"]:
        blockers.append("HOSTING_RULE_OR_REVIEW_THREADS_HELD")
    latest = {}
    for review in live["reviews"]:
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            actor = review["user"]["login"]
            if actor not in latest or review["id"] > latest[actor]["id"]:
                latest[actor] = review
    if any(r["state"] == "CHANGES_REQUESTED" for r in latest.values()):
        blockers.append("OUTSTANDING_CHANGES_REQUESTED")
    # Pending and failed checks remain holds even if a repository has no required policy.
    latest_checks = {}
    for check in live["checks"]:
        key = (check["name"], check["app"]["id"])
        if check["head_sha"] == head and (
            key not in latest_checks or check["id"] > latest_checks[key]["id"]
        ):
            latest_checks[key] = check
    if any(
        c["head_sha"] == head
        and (
            c["status"] != "completed"
            or c["conclusion"] not in {"success", "neutral", "skipped"}
        )
        for c in latest_checks.values()
    ):
        blockers.append("HOSTING_CHECK_PENDING_OR_FAILED")
    return sorted(set(blockers))


def gates(root, number, head, baseline, *, review=None):
    live = closeout.hosting(root, number)
    blockers = _hosting_holds(live, head, review)
    if live["head"] != head or live["remote_branches"].get(live["branch"]) != head:
        blockers.append("EXACT_PR_HEAD_CHANGED")
    if (
        live["repository"] != closeout.REPO
        or live["head_repository"] != closeout.REPO
        or live["base_repository"] != closeout.REPO
    ):
        blockers.append("CROSS_REPOSITORY_DELIVERY")
    if live["base_branch"] != "main" or not live["branch"].startswith("feature/"):
        blockers.append("WRONG_DELIVERY_BRANCH")
    if (
        live["state"] != "open"
        or live["draft"]
        or live["mergeable"] is not True
        or live["mergeable_state"] not in {"clean", "unstable"}
    ):
        blockers.append("PR_NOT_READY")
    current = retained(root)
    if (
        current["local"].get(live["branch"]) != head
        or current["origin"].get(live["branch"]) != head
    ):
        raise ValueError(
            "Published delivery branch was not retained at its accepted head"
        )
    for where, branches in baseline.items():
        for name, old in branches.items():
            new = current[where].get(name)
            if new is None:
                blockers.append("RETAINED_BRANCH_MISSING:" + name)
            else:
                _git(root, "merge-base", "--is-ancestor", old, new)
    _git(root, "merge-base", "--is-ancestor", live["base"], head)
    return sorted(set(blockers)), live


def verify_merged(root, number, head, baseline, *, review=None):
    if not _exact_review(review, head):
        raise ValueError(
            "Saved independent approval of the exact candidate is required"
        )
    pull = closeout.gh(f"repos/{closeout.REPO}/pulls/{number}")
    if (
        not pull["merged"]
        or pull["head"]["sha"] != head
        or pull["head"]["ref"] != BRANCH
        or pull["base"]["ref"] != "main"
        or pull["head"]["repo"]["full_name"] != closeout.REPO
        or pull["base"]["repo"]["full_name"] != closeout.REPO
        or not pull["merge_commit_sha"]
    ):
        raise ValueError(
            "Merged PR does not establish delivery of the exact candidate into main"
        )
    _git(root, "fetch", "origin")
    live = closeout.hosting(root, number)
    if _hosting_holds(live, head, review):
        raise ValueError("Merged PR still has unresolved check or review-history holds")
    current = retained(root)
    if current["local"].get(BRANCH) != head or current["origin"].get(BRANCH) != head:
        raise ValueError(
            "Published delivery branch was not retained at its accepted head"
        )
    for where, branches in baseline.items():
        for name, old in branches.items():
            if name not in current[where]:
                raise ValueError("Retained branch disappeared")
            _git(root, "merge-base", "--is-ancestor", old, current[where][name])
    main = live["remote_branches"]["main"]
    _git(root, "merge-base", "--is-ancestor", head, main)
    _git(root, "merge-base", "--is-ancestor", pull["merge_commit_sha"], main)


def synchronize(root):
    if _git(root, "status", "--porcelain").strip():
        raise ValueError(
            "Delivered remotely; preserve local changes before synchronizing this checkout"
        )
    _git(root, "fetch", "origin")
    _git(root, "merge", "--ff-only", "origin/main")


def deliver(operator):
    authority.load_profile(operator.root)
    state = operator.state()
    if state["phase"] == "DELIVERED":
        return state["delivery"]
    if state["phase"] != "ACCEPTED":
        raise ValueError("Independent acceptance required before delivery")
    if state["delivery"] is None:
        from scripts.acceptance import pilot_review

        attempt = state["reviews"][-1]
        report = attempt["result"]["report"]
        pilot_review(state, report, attempt)
        commit = candidate(operator.root, state)
        proof = {
            "head": commit,
            "actor": attempt["actor"],
            "implementer": state["attempts"][-1]["actor"],
            "verdict": report["verdict"],
            "blocking_findings": [],
            "report_sha256": h.sha(report),
            "bundle_sha256": h.sha(state["bundle"]),
        }
        saved = {
            "commit": commit,
            "branch": BRANCH,
            "retained": retained(operator.root),
            "review": proof,
        }
        operator.event("DELIVERY_PREPARED", saved)
        state = operator.state()
    saved = state["delivery"]
    head = saved["commit"]
    verify_candidate(operator.root, state, head)
    branches = retained(operator.root)
    if BRANCH in branches["local"]:
        if branches["local"][BRANCH] != head:
            raise ValueError(
                "Delivery branch already exists at a different commit; preserve it and inspect"
            )
    else:
        _git(operator.root, "branch", BRANCH, head)
    _git(operator.root, "push", "origin", BRANCH)
    pulls = h.parse(
        _run(
            operator.root,
            [
                "gh",
                "pr",
                "list",
                "--repo",
                closeout.REPO,
                "--state",
                "all",
                "--head",
                BRANCH,
                "--json",
                "number,headRefOid,state,url",
            ],
        ),
        h.ws.MAX_EVENT,
    )
    if len(pulls) > 1:
        raise ValueError(
            "Ambiguous existing delivery PRs; inspect without republishing"
        )
    if not pulls:
        body = (
            "A real OpenAI worker produced the operator launcher, shell, tests and README. "
            "The exact replacement bundle passed separate immutable Docker checks and an independent Sol review.\n\n"
            f"Accepted bundle: `{h.sha(state['bundle'])}`. Canonical local evidence: `{operator.journal.directory}`.\n"
            "The pilot retains lifetime attempts, all request costs, and permanent branches. No measured chat-baseline savings are claimed.\n"
        )
        with tempfile.TemporaryDirectory(prefix="pilot-pr-") as directory:
            path = Path(directory) / "body.txt"
            path.write_text(body, encoding="utf-8")
            _run(
                operator.root,
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    closeout.REPO,
                    "--base",
                    "main",
                    "--head",
                    BRANCH,
                    "--title",
                    "Add worker-produced operator start and resume",
                    "--body-file",
                    str(path),
                ],
            )
        pulls = h.parse(
            _run(
                operator.root,
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    closeout.REPO,
                    "--state",
                    "all",
                    "--head",
                    BRANCH,
                    "--json",
                    "number,headRefOid,state,url",
                ],
            ),
            h.ws.MAX_EVENT,
        )
    pull = pulls[0]
    if pull["headRefOid"] != head:
        raise ValueError("Existing delivery PR head differs")
    if pull["state"] == "MERGED":
        verify_merged(
            operator.root,
            pull["number"],
            head,
            saved["retained"],
            review=saved["review"],
        )
        synchronize(operator.root)
        operator.event("DELIVERY", saved)
        return saved
    blockers, live = gates(
        operator.root, pull["number"], head, saved["retained"], review=saved["review"]
    )
    if blockers:
        operator.event(
            "DELIVERY_HOLD",
            {
                "reason": "; ".join(blockers)
                + "; inspect "
                + pull["url"]
                + " then resume --run"
            },
        )
        return None
    # Reobserve immediately before the merge; gh also compares the exact head.
    blockers, second = gates(
        operator.root, pull["number"], head, saved["retained"], review=saved["review"]
    )
    if blockers or second != live:
        operator.event(
            "DELIVERY_HOLD",
            {"reason": "Hosting facts changed; inspect PR and resume --run"},
        )
        return None
    _run(
        operator.root,
        [
            "gh",
            "pr",
            "merge",
            "--repo",
            closeout.REPO,
            str(pull["number"]),
            "--merge",
            "--match-head-commit",
            head,
        ],
    )
    verify_merged(
        operator.root, pull["number"], head, saved["retained"], review=saved["review"]
    )
    synchronize(operator.root)
    operator.event("DELIVERY", saved)
    return saved
