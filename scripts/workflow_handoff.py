"""Bounded derived handoffs and explicit inspection-only resume; never launch."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import acceptance as a
from scripts import execution_harness as h
from scripts import feedback as f
from scripts import workflow_budget as budget
from scripts import workflow_state as ws
from scripts.workflow_scope import SessionScope, local_file

VERSION = "destination-handoff-1"
MAX_VIEW = 40000
MAX_ITEMS = 128
TTL = 300
Json = dict[str, Any]
require = h.require
sha = h.sha


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str) -> bytes:
    """Only callers in this module supply fixed read-only Git argument vectors."""
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        capture_output=True,
        check=True,
        timeout=30,
    )
    require(len(result.stdout) <= h.MAX_EXPORT, "Git observation exceeds bound")
    return result.stdout


def git_facts(root: Path) -> Json:
    status = git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    index = Path(
        git(root, "rev-parse", "--path-format=absolute", "--git-path", "index")
        .decode()
        .strip()
    )
    return {
        "head": git(root, "rev-parse", "HEAD").decode().strip(),
        "branch": git(root, "branch", "--show-current").decode().strip(),
        "clean": not status,
        "status_sha256": h.digest(status),
        "diff_sha256": h.digest(git(root, "diff", "--binary", "HEAD", "--")),
        "index_sha256": h.digest(h.read_file(index)),
        "refs_sha256": h.digest(git(root, "show-ref")),
    }


def ownership(journal: ws.Journal) -> list[Json]:
    """Observe existing databases only; Ownership construction would create state."""
    path = journal.directory / "ownership.sqlite3"
    if not path.exists():
        require(
            not (journal.directory / "startup.sqlite3").exists(), "Orphaned start store"
        )
        return []
    h.read_file(path)
    startup = journal.directory / "startup.sqlite3"
    h.read_file(startup)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        require(
            db.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
            "Ownership corrupt",
        )
        rows = [
            dict(r) for r in db.execute("SELECT * FROM runs ORDER BY token LIMIT 129")
        ]
    require(
        len(rows) <= MAX_ITEMS,
        "Ownership history exceeds handoff bound; inspect separately",
    )
    with sqlite3.connect(startup.as_uri() + "?mode=ro", uri=True) as db:
        require(
            db.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
            "Start store corrupt",
        )
        starts = dict(db.execute("SELECT token,attempted FROM startup_authority"))
    require(
        set(starts) == {r["token"] for r in rows}, "Ownership/start history differs"
    )
    for row in rows:
        require(starts[row["token"]] in (0, 1), "Invalid consumed start")
        row["consumed"] = starts[row["token"]]
        if row["evidence"]:
            evidence = Path(row["evidence"])
            require(
                evidence.parent.parent == journal.directory,
                "Ownership evidence escaped",
            )
            row["evidence_sha256"] = h.digest(h.read_file(evidence))
        try:
            info = h.runtime.inspect(row["container"])
            row["observation"] = {
                k: info["State"][k]
                for k in ("Status", "Running", "Paused", "Restarting", "ExitCode")
            }
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            row["observation"] = {"status": "UNAVAILABLE"}
    return rows


def _attempt(attempt: Json) -> Json:
    return {
        k: attempt.get(k)
        for k in (
            "id",
            "actor",
            "tier",
            "model_family",
            "deadline",
            "fingerprint",
            "routing_outcome",
            "accounting",
            "token_ceiling",
            "usage",
        )
    }


def _scope_facts(scope: SessionScope) -> Json:
    files = {}
    total = 0
    for relative in scope.data["read_paths"]:
        path = local_file(scope.root, relative, missing=True)
        if not path.exists():
            files[relative] = None
            continue
        raw = h.read_file(path, h.MAX_FILE)
        total += len(raw)
        require(total <= h.MAX_EXPORT, "Scope observation exceeds bound")
        files[relative] = h.digest(raw)
    observed_interface = sha(
        {p: digest for p, digest in files.items() if p.startswith("contracts/")}
    )
    return {
        "scope_sha256": scope.hash,
        "scope": {k: value for k, value in scope.data.items() if k != "workspace"},
        "files": files,
        "git": git_facts(scope.root),
        "interface_matches": observed_interface == scope.data["interface_revision"],
    }


def _task(
    journal: ws.Journal, stream: str, heads: Json, supplied: Json | None
) -> tuple[Json, SessionScope | None]:
    native, _, _ = f.replay(journal, stream)
    require(
        ws.active_anchor(journal.root, native["anchor"]) == native["anchor"],
        "Task approval anchor changed",
    )
    require(
        native.get("controller_version") == f.VERSION,
        "Imported source is inspection-only",
    )
    contract = f.wp.current(native["packet"])["contract"]
    scope = SessionScope.load(supplied) if supplied is not None else None
    dispatches = []
    for attempt in native["attempts"]:
        name = h.stream_name(attempt["id"])
        if name not in heads:
            dispatches.append({"id": attempt["id"], "phase": "RESERVATION_ONLY"})
            continue
        record, _ = h.load(journal, attempt["id"])
        scope = SessionScope.load(record["intent"]["scope"])
        if record["prepared"]:
            h.prepared_files(journal, record)
        if record["stopped"]:
            require(
                asdict(journal.evidence(record["stopped"]["archive"]["path"]))
                == record["stopped"]["archive"],
                "Changed stopped evidence",
            )
            if record["phase"] != "CLOSED":
                h.output(journal, record)
        dispatches.append(
            {
                "id": attempt["id"],
                "phase": record["phase"],
                "binding_sha256": sha(record["binding"]),
                "receipt": record["receipt"],
                "stopped": {
                    k: v for k, v in record["stopped"].items() if k != "runtime"
                }
                if record["stopped"]
                else None,
            }
        )
    acceptance = None
    if a.stream_name(stream) in heads:
        accepted, _ = a.load(journal, stream)
        s = accepted["submission"]
        acceptance = {
            "submission_sha256": sha(s),
            "artifact": s["artifact"],
            "commits": s["commits"],
            "image": s["image"],
            "environment_sha256": s["environment_sha256"],
            "accepted": accepted["accepted"] is not None,
            "synchronized": accepted["synced"] is not None,
            "checks": {
                k: v["report"]["results"] for k, v in (accepted["checks"] or {}).items()
            },
            "pending_review": accepted["pending"],
            "runs": [
                {k: r[k] for k in ("run_id", "phase", "validation_id", "deadline")}
                for r in accepted["runs"][-5:]
            ],
        }
    accounts = {}
    for name in sorted(
        {*f.accounts(native, "worker"), *f.accounts(native, "reviewer")}
    ):
        value, _ = journal.replay(name, budget.apply)
        accounts[name] = {"cap": value["cap"], **budget.totals(value)}
    body = {
        "stream": stream,
        "binding": f.binding(native["packet"]),
        "objective": contract["goal"],
        "status": native["status"],
        "reason": native["reason"],
        "architect": native["architect"],
        "contract_sha256": sha(contract),
        "dependencies": [
            {"task_id": p["task_id"], "state": p["state"], "sha256": sha(p)}
            for p in native["graph"]
        ],
        "attempts_used": len(native["attempts"]),
        "attempt_cap": native["total_cap"],
        "review_attempts_used": len(native["review_attempts"]),
        "review_cap": native["review_cap"],
        "tier_counts": f.tier_counts(native),
        "tier_caps": native["caps"],
        "repairs": native["repairs"],
        "resumptions": native["resumptions"],
        "pending_dispatch": native["pending"],
        "pending_review": native["review_pending"],
        "recent_attempts": [
            _attempt(x) for x in (native["attempts"] + native["review_attempts"])[-5:]
        ],
        "accounting": f.accounting(native),
        "accounts": accounts,
        "dispatches": dispatches[-5:],
        "acceptance": acceptance,
        "integrated": "NOT_ESTABLISHED",
        "deployed": "NOT_ESTABLISHED",
    }
    return body, scope


def _observe(
    journal: ws.Journal,
    task_stream: str | None,
    supplied: Json | None,
    *,
    ignore: str | None = None,
) -> tuple[Json, Json]:
    anchor = ws.active_anchor(journal.root)
    heads = {k: asdict(v) for k, v in journal.verify().items() if k != ignore}
    require(
        len(heads) <= MAX_ITEMS, "Journal exceeds view bound; select a separate audit"
    )
    streams = (
        [task_stream] if task_stream else [s for s in heads if s.startswith("task:")]
    )
    require(len(streams) <= 16, "Startup task count exceeds bound")
    tasks, scope = [], None
    task_scopes = {}
    for stream in streams:
        task, found = _task(journal, stream, heads, supplied)
        if found:
            task_scopes[stream] = _scope_facts(found)
            task["scope_current"] = (
                task_scopes[stream]["git"]["head"] == found.data["base_commit"]
                and task_scopes[stream]["interface_matches"]
            )
            task["owned_scope"] = {
                k: value for k, value in found.data.items() if k != "workspace"
            }
        tasks.append(task)
        if task_stream:
            scope = found
    if supplied is not None:
        require(task_stream is not None, "Scope requires one named task")
        require(
            Path(supplied["workspace"]).resolve() == journal.root,
            "Clean-start scope must use this checkout",
        )
        if scope is not None:
            require(
                scope.data == supplied,
                "Saved reservation scope cannot be replaced by a view",
            )
    scoped = None
    if scope is not None:
        require(
            scope.data["packet_revision_hash"] == tasks[0]["binding"]["contract_hash"],
            "Stale scope revision",
        )
        scoped = task_scopes[tasks[0]["stream"]]
    owners = ownership(journal)
    facts = {
        "anchor": anchor,
        "heads": heads,
        "repository": journal.identity,
        "git": git_facts(journal.root),
        "ownership": owners,
        "scoped": scoped,
        "task_scopes": task_scopes,
    }
    blockers = []
    if scoped and (
        scoped["git"]["head"] != scoped["scope"]["base_commit"]
        or not scoped["interface_matches"]
    ):
        blockers.append("SAVED_SCOPE_CHANGED_REQUIRES_NEW_PACKET")
    action = "SELECT_TASK_AND_APPROVED_SCOPE"
    if tasks:
        action = "INSPECT_TASK_AND_EXPLICITLY_PLAN"
        if not scope and task_stream:
            blockers.append("APPROVED_SCOPE_REQUIRED")
        for task in tasks:
            if task["accounting"]["unknown"] or any(
                v["unknown"] for v in task["accounts"].values()
            ):
                blockers.append("UNKNOWN_COST_REQUIRES_RECONCILIATION")
            if task["pending_dispatch"]:
                phase = (
                    task["dispatches"][-1]["phase"]
                    if task["dispatches"]
                    else "RESERVATION_ONLY"
                )
                action = (
                    "EXPLICIT_WORKER_RECONCILE"
                    if phase in {"LAUNCHING", "PREPARING", "RESERVATION_ONLY"}
                    else "INSPECT_THEN_EXPLICIT_LAUNCH_OR_ABANDON"
                    if phase == "PREPARED"
                    else "EXPLICIT_WORKER_INGEST_OR_RECONCILE"
                )
            elif task["pending_review"]:
                action = "EXPLICIT_REVIEW_INGEST_OR_ABANDON"
            elif task["acceptance"]:
                acceptance = task["acceptance"]
                if any(
                    r["phase"] not in {"CLOSED", "ABANDONED"}
                    for r in acceptance["runs"]
                ):
                    action = "EXPLICIT_CHECK_RECONCILE_OR_INGEST"
                elif acceptance["accepted"]:
                    action = (
                        "ASSESS_INTEGRATION_READINESS"
                        if acceptance["synchronized"]
                        else "EXPLICIT_ACCEPTANCE_SYNCHRONIZATION"
                    )
                else:
                    action = "INSPECT_INDEPENDENT_ACCEPTANCE_GATES"
            elif task["status"] in {"NEEDS_ARCHITECT", "NEEDS_DECISION", "BLOCKED"}:
                action = "NAMED_OWNER_DECISION_REQUIRED"
                blockers.append(task["reason"])
            if task.get("scope_current") is False and not task["pending_dispatch"]:
                action = "NEW_PACKET_FOR_CHANGED_WORKSPACE"
            task["next_action"] = action
    if any(r["state"] == "claimed" for r in owners):
        blockers.append("EXCLUSIVE_OWNERSHIP_HELD")
    if any(r["state"] == "claimed" and r["consumed"] for r in owners):
        blockers.append("CONSUMED_START_NEVER_RESTART")
        action = "EXPLICIT_STOP_PRESERVE_RECONCILE"
    if any(r["observation"].get("status") == "UNAVAILABLE" for r in owners):
        blockers.append("DOCKER_OBSERVATION_UNAVAILABLE")
    body = {
        "tasks": tasks,
        "git": facts["git"],
        "scope": scoped,
        "blockers": sorted(set(blockers)),
        "next_action": action,
        "ownership": [
            {
                "branch": r["branch"],
                "run_id": r["run_id"],
                "state": r["state"],
                "consumed": r["consumed"],
                "lease_expires_utc": datetime.fromtimestamp(
                    r["expires"], timezone.utc
                ).isoformat(),
                "observation": r["observation"],
                "evidence_sha256": r.get("evidence_sha256"),
            }
            for r in owners
        ],
        "execution_authorized": False,
        "retry_granted": False,
    }
    # Host paths and ownership tokens belong only to the private digest input.
    if scoped:
        body["scope"] = {k: v for k, v in scoped.items() if k != "files"} | {
            "files_sha256": sha(scoped["files"])
        }
    h.secret_free(body)
    return facts, body


def build(
    journal: ws.Journal,
    task_stream: str | None = None,
    *,
    scope: Json | None = None,
    audience: str = "coordinator",
) -> Json:
    require(
        audience in {"startup", "worker", "coordinator"}, "Unknown handoff audience"
    )
    facts, body = _observe(journal, task_stream, scope)
    require(
        _observe(journal, task_stream, scope) == (facts, body),
        "Concurrent change; regenerate view",
    )
    created = now()
    result = {
        "version": VERSION,
        "audience": audience,
        "created_at": created,
        "expires_at": (f.instant(created) + timedelta(seconds=TTL)).isoformat(),
        "selector": {
            "task_stream": task_stream,
            "scope": {k: v for k, v in scope.items() if k != "workspace"}
            if scope
            else None,
        },
        "authority_sha256": sha(facts),
        "content": body,
        "context": {
            "measurement": "unknown",
            "measured_tokens": None,
            "estimate_method": "one UTF-8 byte per input token; view only",
            "estimated_input_tokens": 0,
            "provider_usage": "unknown",
        },
    }
    # Fixed-point estimate includes its own decimal length, never claims actual usage.
    for _ in range(4):
        result["context"]["estimated_input_tokens"] = len(h.json_bytes(result))
    require(
        len(h.json_bytes(result)) <= MAX_VIEW, "Context limit requires decomposition"
    )
    return result


def verify(journal: ws.Journal, view: Json) -> Json:
    f.exact(
        view,
        {
            "version",
            "audience",
            "created_at",
            "expires_at",
            "selector",
            "authority_sha256",
            "content",
            "context",
        },
    )
    f.exact(view["selector"], {"task_stream", "scope"})
    require(
        view["context"]
        == {
            "measurement": "unknown",
            "measured_tokens": None,
            "estimate_method": "one UTF-8 byte per input token; view only",
            "estimated_input_tokens": len(h.json_bytes(view)),
            "provider_usage": "unknown",
        },
        "Edited context labels or estimate",
    )
    require(
        len(h.json_bytes(view)) <= MAX_VIEW and view.get("version") == VERSION,
        "Invalid bounded view",
    )
    created, expires, current = (
        f.instant(view["created_at"]),
        f.instant(view["expires_at"]),
        f.instant(now()),
    )
    require(
        created <= current <= expires and expires - created == timedelta(seconds=TTL),
        "Stale view timestamp",
    )
    selector = view["selector"]
    scope = (
        {**selector["scope"], "workspace": str(journal.root)}
        if selector["scope"]
        else None
    )
    fresh = build(
        journal, selector["task_stream"], scope=scope, audience=view["audience"]
    )
    require(
        fresh["authority_sha256"] == view["authority_sha256"]
        and fresh["content"] == view["content"],
        "Stale or edited derived view; regenerate",
    )
    return view["content"]


def resume(journal: ws.Journal, view: Json) -> Json:
    body = verify(journal, view)
    return {
        "next_action": body["next_action"],
        "blockers": body["blockers"],
        "execution_authorized": False,
        "retry_granted": False,
    }


def propose_context(journal: ws.Journal, view: Json, requests: list[Json]) -> Json:
    body = verify(journal, view)
    require(
        len(body["tasks"]) == 1 and body["scope"] is not None,
        "Named scoped task required",
    )
    require(
        isinstance(requests, list) and 1 <= len(requests) <= 8,
        "Bounded exact context requests required",
    )
    if view["selector"]["scope"] is not None:
        source_scope = SessionScope.load(
            {**view["selector"]["scope"], "workspace": str(journal.root)}
        )
    else:
        _, source_scope = _task(
            journal,
            body["tasks"][0]["stream"],
            {k: asdict(head) for k, head in journal.verify().items()},
            None,
        )
        require(source_scope is not None, "Authoritative worker scope required")
    if source_scope is None:
        raise ValueError("Authoritative worker scope required")
    scope: Json = source_scope.data
    source_scope.verify_base()
    additions = []
    for request in requests:
        f.exact(request, {"path", "symbol", "reason"})
        require(
            all(isinstance(v, str) and 0 < len(v) <= 500 for v in request.values()),
            "Exact path/symbol/reason required",
        )
        path = h.checked_path(request["path"])
        require(
            path not in scope["read_paths"] and path not in additions,
            "Already supplied or repeated context",
        )
        require(
            not path.startswith("contracts/"),
            "Interface changes require a separate contract/UI proposal",
        )
        local_file(source_scope.root, path)
        additions.append(path)
    revised = SessionScope.load(
        {**scope, "read_paths": sorted(scope["read_paths"] + additions)}
    )
    files = revised.files()
    result = {
        "version": "destination-context-proposal-1",
        "task_stream": body["tasks"][0]["stream"],
        "view_sha256": sha(view),
        "authority_sha256": view["authority_sha256"],
        "requests": requests,
        "revised_scope": revised.data,
        "new_files": {p: h.digest(files[p]) for p in additions},
        "execution_authorized": False,
        "approval_required": body["tasks"][0]["architect"],
    }
    h.secret_free(result)
    return result


def _context_receipt(
    journal: ws.Journal, view: Json, requests: list[Json], actor: str
) -> Json | None:
    # Replay a committed approval before freshness checks. This returns history,
    # not a usable scope: context_scope separately revalidates current facts.
    for stream in journal.verify():
        if stream.startswith("context:"):
            events, head = journal.read(stream)
            data = events[0]["data"]
            old = data["proposal"]
            if old["view_sha256"] == sha(view) and old["requests"] == requests:
                require(
                    len(events) == 1 and data["actor"] == actor,
                    "Conflicting context approval",
                )
                return {
                    "stream": stream,
                    "head": asdict(head),
                    "proposal_sha256": sha(old),
                }
    return None


def approve_context(
    journal: ws.Journal, view: Json, requests: list[Json], actor: str
) -> Json:
    receipt = _context_receipt(journal, view, requests, actor)
    if receipt:
        return receipt
    try:
        proposal = propose_context(journal, view, requests)
        require(
            f.actor_identity(actor) == f.actor_identity(proposal["approval_required"]),
            "Named architect approval required",
        )
        stream = "context:" + sha(proposal)
        data = {"proposal": proposal, "actor": actor}
        verify(journal, view)
        journal.create(
            stream,
            family="project",
            binding={"task_stream": proposal["task_stream"]},
            data=data,
        )
    except ValueError:
        # A racing identical commit can stale any read/check above. Resolve only
        # an exact durable match; unrelated stale state is still refused.
        receipt = _context_receipt(journal, view, requests, actor)
        if receipt:
            return receipt
        raise
    receipt = _context_receipt(journal, view, requests, actor)
    if receipt is None:
        raise ValueError("Committed context receipt missing")
    return receipt


def context_scope(journal: ws.Journal, receipt: Json, view: Json) -> Json:
    require(
        f.instant(view["created_at"])
        <= f.instant(now())
        <= f.instant(view["expires_at"]),
        "Stale view timestamp",
    )
    events, head = journal.read(receipt["stream"])
    require(
        len(events) == 1 and asdict(head) == receipt["head"], "Context receipt changed"
    )
    proposal = events[0]["data"]["proposal"]
    require(
        sha(proposal) == receipt["proposal_sha256"]
        and sha(view) == proposal["view_sha256"],
        "Wrong context proposal",
    )
    require(
        f.actor_identity(events[0]["data"]["actor"])
        == f.actor_identity(proposal["approval_required"]),
        "Wrong approving architect",
    )
    selector = view["selector"]
    scope = (
        {**selector["scope"], "workspace": str(journal.root)}
        if selector["scope"]
        else None
    )
    facts, _ = _observe(
        journal, selector["task_stream"], scope, ignore=receipt["stream"]
    )
    require(
        sha(facts) == proposal["authority_sha256"],
        "Stale approved context; propose again",
    )
    revised = SessionScope.load(proposal["revised_scope"])
    require(
        {
            p: h.digest(b)
            for p, b in revised.files().items()
            if p in proposal["new_files"]
        }
        == proposal["new_files"],
        "Changed added context",
    )
    require(
        _observe(journal, selector["task_stream"], scope, ignore=receipt["stream"])[0]
        == facts,
        "Concurrent context change; regenerate",
    )
    return revised.data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("view")
    create.add_argument("--task")
    create.add_argument("--scope", type=Path)
    create.add_argument(
        "--audience", choices=["startup", "worker", "coordinator"], default="startup"
    )
    inspect = sub.add_parser("resume")
    inspect.add_argument("view", type=Path)
    args = parser.parse_args(argv)
    try:
        journal = ws.Journal(args.root)
        result = (
            build(
                journal,
                args.task,
                scope=h.parse(h.read_file(args.scope, MAX_VIEW), MAX_VIEW)
                if args.scope
                else None,
                audience=args.audience,
            )
            if args.command == "view"
            else resume(journal, h.parse(h.read_file(args.view, MAX_VIEW), MAX_VIEW))
        )
        print(json.dumps(result, indent=2))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ):
        print(
            "Handoff refused; inspect current authority and regenerate", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
