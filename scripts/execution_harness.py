"""Coordinator Docker dispatch and stopped-output ingestion; never accepts or applies work.

Adapted from the pinned donor d6e582b7 execution harness. Host subprocess
workers, environment forwarding and worker-authoritative cost settlement are
deliberately absent. JSON at these boundaries is dynamic and validated here.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from string import Formatter
import sys
import tarfile
import uuid
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import dispatch_state as ds  # noqa: E402
from scripts import feedback as f  # noqa: E402
from scripts import workflow_budget as budget  # noqa: E402
from scripts import workflow_runtime as runtime  # noqa: E402
from scripts import workflow_state as ws  # noqa: E402
from scripts.workflow_scope import (  # noqa: E402
    MAX_EXPORT,
    MAX_FILE,
    Ownership,
    SessionScope,
    checked_path,
    digest,
    local_file,
    verify_baseline,
    verify_bundle,
)

REPORT_FIELDS = {
    "dispatch_id",
    "outcome",
    "summary",
    "scope_status",
    "architecture_conflict",
    "validation",
    "evidence",
    "discoveries",
    "api_cost_usd",
    "cost_evidence",
    "run",
}
METADATA_TOKENS = 4096
RULES = """Read brief.json and dispatch.json before editing. The full context, contract,
architect guidance, prior failures, review rejections and cumulative bounds in
the brief constrain this attempt. Read startup.documents in order. Missing
input: stop BLOCKED and name exact missing paths/symbols and reasons in evidence.
Scope or architecture conflict: stop and report it. Never widen scope, edit
immutable inputs, retry a worker, change a contract or accept your own result.
Run each contract validation and report each ID exactly once. Unrun checks fail.
Write only enumerated workspace files and /session/report.json. Report exactly
the report_contract fields. Echo the dispatch binding and absolute deadline;
compute bundle_sha256 over the canonical replacement bundle for workspace
changes. PASS needs every check passing, scope within and no conflict. Worker
costs are claims. Never put credentials or private keys in output or logs.
Anything outside this contract is a discovery, never additional implementation.
"""
SECRETS = (
    re.compile(
        r"(?i)\b(api[_-]?key|secret|passwd|password|token|authorization|bearer)\b\s*[:=]"
    ),
    re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\baws_secret_access_key\b"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def secret_free(value, where="Input"):
    text = value if isinstance(value, str) else f.wp.canonical(value)
    require(
        not any(p.search(text) for p in SECRETS),
        where + " contains credential-like content",
    )


def json_bytes(value) -> bytes:
    return f.wp.canonical(value).encode("utf-8")


def sha(value) -> str:
    return digest(json_bytes(value))


def parse(raw: bytes, limit: int):
    require(len(raw) <= limit, "JSON exceeds byte bound")
    try:
        text = raw.decode("utf-8")
        secret_free(text)
        value = json.loads(
            text,
            object_pairs_hook=ws.approval.unique_object,
            parse_constant=lambda _: require(False, "Nonfinite JSON"),
        )
        secret_free(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid bounded JSON") from exc


def read_file(path: Path, limit=MAX_EXPORT * 2) -> bytes:
    # Inspect all ancestors, including a caller-supplied run directory.
    for component in [path, *path.parents]:
        require(
            not component.is_symlink()
            and not getattr(component, "is_junction", lambda: False)(),
            "Linked evidence path",
        )
    require(
        path.is_file() and path.stat().st_nlink == 1,
        "Evidence must be a singly linked regular file",
    )
    require(path.stat().st_size <= limit, "Evidence exceeds byte bound")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Evidence exceeds byte bound")
    return raw


def write_once(path: Path, raw: bytes):
    if path.exists():
        require(read_file(path) == raw, "Conflicting preserved evidence")
        return
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def config_valid(config):
    secret_free(config, "Harness configuration")
    schema = f.wp.read_json(ROOT / "config/execution-harness.schema.json")
    require(
        not list(f.wp.Draft202012Validator(schema).iter_errors(config)),
        "Invalid Docker harness configuration",
    )
    ids = [h["id"] for h in config["harnesses"]]
    require(len(set(ids)) == len(ids), "Duplicate harness ID")
    resources = [b["resource_id"] for b in config["bindings"]]
    require(len(set(resources)) == len(resources), "Duplicate resource binding")
    for h in config["harnesses"]:
        try:
            fields = [field for arg in h["argv"] for field in Formatter().parse(arg)]
        except ValueError as exc:
            raise ValueError("Malformed invocation placeholders") from exc
        placeholders = [name for _, name, _, _ in fields if name is not None]
        require(
            all(not spec and conversion is None for _, _, spec, conversion in fields),
            "Invocation format modifiers are prohibited",
        )
        require(
            all(
                p in {"brief", "report", "rules", "workspace", "provider", "model"}
                for p in placeholders
            ),
            "Unknown invocation placeholder",
        )
        require(
            "brief" in placeholders and "report" in placeholders,
            "Invocation must name brief and report",
        )
    for b in config["bindings"]:
        require(b["harness_id"] in ids, "Unknown harness binding")
    return config


def selected(config, resource):
    bindings = [b for b in config["bindings"] if b["resource_id"] == resource["id"]]
    require(len(bindings) == 1, "Missing exact harness binding")
    b = bindings[0]
    require(
        b["provider"] == resource["provider_id"] and b["model"] == resource["model"],
        "Resource/provider/model binding differs",
    )
    require(
        b["served_context_window"] is None
        or b["served_context_window"] <= resource["context_window"],
        "Served context exceeds declared capacity",
    )
    h = next(h for h in config["harnesses"] if h["id"] == b["harness_id"])
    return b, h


def invocation(binding, harness):
    values = {
        "brief": "/session/brief.json",
        "report": "/session/report.json",
        "rules": "/session/worker-rules.md",
        "workspace": "/session/workspace",
        "provider": binding["provider"],
        "model": binding["model"],
    }
    return [harness["command"], *[a.format(**values) for a in harness["argv"]]]


def stream_name(dispatch_id):
    return "dispatch:" + dispatch_id


def run_path(journal, dispatch_id):
    return journal.directory / ("run-dispatch-" + dispatch_id)


def reservation(
    journal, task_stream, dispatch_id
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], ws.Head]:
    state, seq, head = f.replay(journal, task_stream)
    attempt = next((a for a in state["attempts"] if a["id"] == dispatch_id), None)
    if attempt is None:
        raise ValueError("Dispatch has no lifetime attempt")
    events, _ = journal.read(task_stream)
    event = next(
        (
            e
            for e in events
            if e["kind"] == "DISPATCH"
            and e["data"]["plan"]["routing"]["decision"]["decision_id"] == dispatch_id
        ),
        None,
    )
    if event is None:
        raise ValueError("Missing dispatch event")
    return state, attempt, event, ws.Head(seq, head)


def load(journal: ws.Journal, dispatch_id: str) -> tuple[dict[str, Any], ws.Head]:
    return journal.replay(stream_name(dispatch_id), ds.apply)


def advance(journal, dispatch_id, kind, data, *, evidence=(), timestamp=None):
    _, head = load(journal, dispatch_id)
    return journal.append(
        stream_name(dispatch_id),
        kind,
        data,
        expected=head,
        reducer=ds.apply,
        evidence=evidence,
        timestamp=timestamp or f.wp.now(),
    )


def current(journal, record, *, scheduling=False):
    state, attempt, event, head = reservation(
        journal, record["task_stream"], record["dispatch_id"]
    )
    binding, intent = record["binding"], record["intent"]
    require(
        sha(event["data"]["config"]) == binding["router_config_sha256"],
        "Saved router configuration differs",
    )
    require(
        attempt["actor"] == binding["actor"]
        and attempt["rates"] == binding["rates"]
        and attempt["resource_id"] == binding["resource_id"]
        and attempt["deadline"] == binding["deadline"]
        and attempt["tier"] == binding["tier"]
        and attempt["model_family"] == binding["model_family"],
        "Saved attempt binding differs",
    )
    require(
        f.binding(state["packet"]) == binding["packet"]
        and (
            record["phase"] == "CLOSED"
            or sha(state["packet"]) == binding["packet_sha256"]
        ),
        "Stale packet/contract binding",
    )
    brief = event["data"]["options"]["context_envelope"]["brief"]
    require(
        sha(intent) == binding["intent_sha256"]
        and parse(brief.encode(), MAX_FILE)["preparation"] == intent,
        "Reservation intent differs",
    )
    scope = SessionScope.load(intent["scope"])
    scope.verify_base()
    verify_baseline(scope, intent["baseline"])
    # The task controller advances its packet on DISPATCH. Re-export the READY
    # packet saved in the reservation context, never relabel the current packet.
    saved_packet = event["data"].get("m4_packet")
    if saved_packet is None:
        saved_packet = intent["packet"]
    export, baseline = scope.export(saved_packet, intent["graph"])
    require(
        digest(export) == intent["source_export_sha256"]
        and baseline == intent["baseline"],
        "Changed source export",
    )
    if record["phase"] != "CLOSED":
        require(
            state["pending"] == record["dispatch_id"]
            and asdict(head) == binding["task_head"],
            "Stale task dispatch/head",
        )
    if scheduling:
        ws.active_anchor(journal.root, binding["anchor"])
        foundation = f.wp.read_json(journal.root / "config/workflow-bootstrap.json")[
            "policy"
        ]
        require(
            foundation["resources_enabled"] and not attempt["api_metered"],
            "Live/metered execution is disabled",
        )
        require(
            f.instant(f.wp.now()) < f.instant(binding["deadline"]),
            "Reservation deadline expired",
        )
        for account, expected in binding["ledger_heads"].items():
            require(
                asdict(journal.read(account)[1]) == expected, "Stale accounting head"
            )
    return state, attempt, scope, event


def dispatch(
    journal,
    task_stream,
    config,
    router_config,
    options,
    scope: SessionScope,
    *,
    timestamp=None,
):
    """Reserve then prepare one Docker run. Nothing launches here."""
    config_valid(config)
    require(config["enabled"], "Execution harness dispatch is disabled")
    state, seq, last = f.replay(journal, task_stream)
    require(not state["pending"], "Pending dispatch already exists")
    require(
        scope.data["owner"] == state["destination"]["implementer"],
        "Scope actor differs from implementer",
    )
    ready = state["packet"]
    if ready["state"] != "READY":
        events, _ = journal.read(task_stream)
        candidates = [e["data"].get("packet") for e in events]
        candidates = [
            p
            for p in candidates
            if isinstance(p, dict)
            and p.get("state") == "READY"
            and f.binding(p) == f.binding(ready)
        ]
        require(candidates, "No saved READY authority for this revision")
        ready = candidates[-1]
    graph = [
        p for p in f.current_graph(state, ready) if p["task_id"] != ready["task_id"]
    ]
    export, baseline = scope.export(ready, graph)
    require(not owner_rows(journal, scope), "Scope run identity was already used")
    for raw in scope.files().values():
        secret_free(raw.decode("utf-8", errors="replace"), "Scope input")
    # Validate all declared bindings and instructions before consuming an attempt.
    for resource in router_config["resources"]:
        if resource["enabled"]:
            selected(config, resource)
    documents = []
    for path in f.wp.current(state["packet"])["contract"].get(
        "worker_instructions", []
    ):
        require(
            path in scope.data["read_paths"] and path not in scope.data["write_paths"],
            "Instruction outside immutable read scope",
        )
        raw = read_file(local_file(scope.root, path), MAX_FILE)
        text = raw.decode("utf-8")
        secret_free(text, "Worker instruction")
        documents.append({"path": path, "sha256": digest(raw), "text": text})
    require(
        sum(len(d["text"]) for d in documents) + len(RULES)
        <= config["limits"].get("startup_max_chars", 12000),
        "Startup instructions exceed bound",
    )
    intent: dict[str, Any] = {
        "scope": scope.data,
        "harness_config": copy.deepcopy(config),
        "packet": ready,
        "graph": graph,
        "baseline": baseline,
        "source_export_sha256": digest(export),
    }
    brief = (
        json.dumps(
            {
                "schema_version": ds.VERSION,
                "preparation": intent,
                "context": f.worker_context(state),
                "startup": {
                    "documents": documents,
                    "rules_sha256": digest(RULES.encode()),
                    "governance": {
                        p: digest((ROOT / p).read_bytes())
                        for p in ("CLAUDE.md", "PROMPTS.md", "BRANCH_RETENTION.md")
                    },
                },
                "report_contract": {
                    "write_to": "/session/report.json",
                    "required_fields": sorted(REPORT_FIELDS),
                    "validation_check_fields": sorted(
                        f.SCHEMA["$defs"]["validation_check"]["required"]
                    ),
                    "run_fields": ["binding_sha256", "deadline", "bundle_sha256"],
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    require(
        len(brief) <= config["limits"]["brief_max_chars"],
        "Rendered brief exceeds bound",
    )
    secret_free(brief, "Rendered brief")
    overhead = (
        max(h["context_overhead_tokens"] for h in config["harnesses"])
        + config["limits"]["context_growth_reserve_tokens"]
        + METADATA_TOKENS
    )
    opts = {
        **options,
        "context_envelope": {
            "brief": brief,
            "rules": RULES,
            "overhead_tokens": overhead,
        },
    }
    preview = f.plan(state, router_config, opts)
    if preview["status"] == "DISPATCH":
        resource_id = preview["routing"]["decision"]["selected"]["resource_id"]
        resource = next(r for r in router_config["resources"] if r["id"] == resource_id)
        require(not f.router.metered(resource), "Metered launch is disabled")
        b, _ = selected(config, resource)
        window = b["served_context_window"] or resource["context_window"]
        request = preview["routing"]["inputs"]["request"]
        require(
            request["input_tokens"] + request["output_tokens"] <= window,
            "Rendered context exceeds served window",
        )
    reserved = f.reserve(
        journal,
        task_stream,
        router_config,
        opts,
        expected=ws.Head(seq, last),
        timestamp=timestamp,
    )
    if reserved["dispatch_id"] is None:
        return reserved
    dispatch_id = reserved["dispatch_id"]
    state, attempt, _, task_head = reservation(journal, task_stream, dispatch_id)
    binding = {
        "task_id": intent["packet"]["task_id"],
        "role": "worker",
        "dispatch_id": dispatch_id,
        "packet": f.binding(intent["packet"]),
        "packet_sha256": sha(state["packet"]),
        "actor": attempt["actor"],
        "resource_id": attempt["resource_id"],
        "model_family": attempt["model_family"],
        "tier": attempt["tier"],
        "rates": attempt["rates"],
        "anchor": state["anchor"],
        "deadline": attempt["deadline"],
        "router_config_sha256": sha(router_config),
        "intent_sha256": sha(intent),
        "brief_sha256": digest(brief.encode()),
        "rules_sha256": digest(RULES.encode()),
        "task_head": asdict(task_head),
        "ledger_heads": {
            a: asdict(journal.read(a)[1]) for a in f.accounts(state, "worker")
        },
    }
    journal.create(
        stream_name(dispatch_id),
        family="project",
        binding={"dispatch_id": dispatch_id},
        data={
            "version": ds.VERSION,
            "task_stream": task_stream,
            "dispatch_id": dispatch_id,
            "binding": binding,
            "intent": intent,
        },
        reducer=ds.apply,
        timestamp=timestamp,
    )
    try:
        b, h = selected(config, attempt["rates"])
        public = {
            "dispatch_id": dispatch_id,
            "binding_sha256": sha(binding),
            "deadline": attempt["deadline"],
            "scope_sha256": scope.hash,
            "base_commit": scope.data["base_commit"],
            "image": b["image"],
            "brief_sha256": binding["brief_sha256"],
            "rules_sha256": binding["rules_sha256"],
        }
        require(
            len(json_bytes(public)) <= METADATA_TOKENS,
            "Dispatch metadata exceeds reserved context",
        )
        instructions = {
            "brief.json": brief.encode(),
            "worker-rules.md": RULES.encode(),
            "dispatch.json": json_bytes(public),
            "report.json": b"",
        }
        run = runtime.prepare(
            scope,
            intent["packet"],
            intent["graph"],
            journal.directory,
            b["image"],
            invocation(b, h),
            run=run_path(journal, dispatch_id),
            instructions=instructions,
            dispatch_stream=stream_name(dispatch_id),
        )
        for name, raw in instructions.items():
            if name != "report.json":
                write_once(run / name, raw)
        files = {
            name: digest(read_file(run / name))
            for name in (
                "scope.json",
                "packet.json",
                "baseline.json",
                "input.tar",
                "brief.json",
                "worker-rules.md",
                "dispatch.json",
                "runtime.json",
            )
        }
        evidence = tuple(
            journal.evidence((run / name).relative_to(journal.directory).as_posix())
            for name in files
        )
        record = parse(read_file(run / "runtime.json"), MAX_FILE)
        advance(
            journal,
            dispatch_id,
            "PREPARED",
            {"run": run.name, "files": files, "runtime": record},
            evidence=evidence,
            timestamp=timestamp,
        )
    except Exception:
        # If Docker/state inspection cannot prove safety, reconciliation refuses
        # and the pending reservation/claim stays held for explicit recovery.
        reconcile(
            journal,
            task_stream,
            "Preparation failed after reservation; explicitly abandon this consumed attempt.",
        )
        raise
    return {
        "status": "PREPARED",
        "dispatch_id": dispatch_id,
        "deadline": attempt["deadline"],
        "run": str(run),
        "executed": False,
        "independent_acceptance": False,
    }


def prepared_files(journal, record):
    prepared = record["prepared"]
    require(prepared is not None, "Preparation incomplete; reconcile explicitly")
    run = run_path(journal, record["dispatch_id"])
    require(run.name == prepared["run"], "Wrong run directory")
    for name, expected in prepared["files"].items():
        require(digest(read_file(run / name)) == expected, "Prepared run bytes changed")
    return run


def owner_rows(journal, scope):
    db_path = journal.directory / "ownership.sqlite3"
    if not db_path.exists():
        return []
    read_file(db_path)
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM runs WHERE scope_hash=? AND run_id=?",
                (scope.hash, scope.data["run_id"]),
            )
        ]


def stopped_record(journal, record):
    """Capture the ownership store's exact preserved output, never a caller path."""
    scope = SessionScope.load(record["intent"]["scope"])
    rows = owner_rows(journal, scope)
    require(
        len(rows) == 1 and rows[0]["state"] in {"finished", "recovered"},
        "Stopped ownership evidence missing",
    )
    row = rows[0]
    require(runtime.stopped(row["container"]), "Worker tree is not stopped")
    run = run_path(journal, record["dispatch_id"])
    archive = Path(row["evidence"])
    require(archive.parent == run, "Preserved archive is outside run")
    read_file(archive)
    evidence = journal.evidence(archive.relative_to(journal.directory).as_posix())
    data = {
        "archive": asdict(evidence),
        "runtime": {k: row[k] for k in ("token", "container", "scope_hash")},
        "exit_code": runtime.inspect(row["container"])["State"]["ExitCode"],
        "finished_at": f.wp.now(),
    }
    advance(journal, record["dispatch_id"], "RECOVERY", data, evidence=(evidence,))
    return data


def report_valid(
    report, contract, dispatch_id, limits, size, *, binding, bundle_sha256
):
    require(size <= limits["report_max_bytes"], "Worker report exceeds byte bound")
    secret_free(report, "Worker report")
    f.exact(report, REPORT_FIELDS)
    f.exact(report["run"], {"binding_sha256", "deadline", "bundle_sha256"})
    require(
        report["run"]
        == {
            "binding_sha256": sha(binding),
            "deadline": binding["deadline"],
            "bundle_sha256": bundle_sha256,
        },
        "Wrong run/bundle/hash/deadline",
    )
    raw = {k: v for k, v in report.items() if k != "run"}
    # No schema error containing worker-controlled text escapes this boundary.
    try:
        f.shape("result", raw)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid report field types") from exc
    require(raw["dispatch_id"] == dispatch_id, "Wrong report dispatch")
    require(
        raw["evidence"]
        and raw["api_cost_usd"] is not None
        and type(raw["api_cost_usd"]) in {int, float}
        and math.isfinite(raw["api_cost_usd"]),
        "Report requires evidence and numeric cost claim",
    )
    ids = [c["check_id"] for c in raw["validation"]]
    require(
        len(set(ids)) == len(ids)
        and set(ids) == {c["id"] for c in contract["validation"]},
        "Duplicate/unknown/missing validation IDs",
    )
    if raw["outcome"] == "PASS":
        require(
            all(c["passed"] and not c["failure_code"] for c in raw["validation"])
            and raw["scope_status"] == "within"
            and not raw["architecture_conflict"],
            "Contradictory PASS",
        )
    return raw


def output(journal, record):
    """Check an opaque stopped session tar without extracting any member."""
    stopped = record["stopped"]
    require(stopped is not None, "Missing stopped output")
    archive_path = journal.directory / stopped["archive"]["path"]
    archive = read_file(archive_path)
    require(
        digest(archive) == stopped["archive"]["sha256"], "Stopped output hash differs"
    )
    run = prepared_files(journal, record)
    if (run / "stdout.log").exists():
        secret_free(
            read_file(run / "stdout.log", MAX_FILE).decode("utf-8", errors="replace"),
            "Worker log",
        )
    scope = SessionScope.load(record["intent"]["scope"])
    immutable = {
        n: read_file(run / n, MAX_FILE)
        for n in (
            "scope.json",
            "packet.json",
            "baseline.json",
            "brief.json",
            "worker-rules.md",
            "dispatch.json",
        )
    }
    expected_files = (
        set(immutable)
        | {"report.json"}
        | {"workspace/" + p for p in record["intent"]["baseline"]}
    )
    directories = {"session"}
    for name in expected_files:
        parent = Path("session/" + name).parent
        while parent.as_posix() != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    seen, payloads, total = set(), {}, 0
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            for member in tar:
                require(len(seen) < 600, "Too many output archive entries")
                name = member.name.rstrip("/")
                checked_path(name)
                require(name.casefold() not in seen, "Duplicate output archive path")
                seen.add(name.casefold())
                if member.isdir():
                    require(name in directories, "Unexpected output directory")
                    continue
                require(name.startswith("session/"), "Escaped output archive")
                relative = name[8:]
                require(
                    member.isfile()
                    and relative in expected_files
                    and member.size <= MAX_FILE,
                    "Linked, oversized or unexpected output file",
                )
                total += member.size
                require(
                    total <= MAX_EXPORT + MAX_FILE * 2,
                    "Output archive exceeds size bound",
                )
                stream = tar.extractfile(member)
                if stream is None:
                    raise ValueError("Missing archive member data")
                payloads[relative] = stream.read(MAX_FILE + 1)
    except (tarfile.TarError, EOFError) as exc:
        raise ValueError("Invalid stopped output archive") from exc
    require(set(payloads) == expected_files, "Missing stopped output files")
    require(
        all(payloads[n] == raw for n, raw in immutable.items()),
        "Immutable dispatch input changed",
    )
    for raw in payloads.values():
        secret_free(raw.decode("utf-8", errors="replace"), "Stopped output")
    # Reuse the runtime's immutable-workspace and exact replacement derivation.
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, raw in payloads.items():
            if name.startswith("workspace/"):
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                tar.addfile(info, io.BytesIO(raw))
    bundle = runtime.bundle_from_archive(
        scope, record["intent"]["baseline"], buffer.getvalue()
    )
    if bundle["changes"]:
        verify_bundle(scope, record["intent"]["baseline"], bundle)
    return payloads["report.json"], bundle


def settle(journal, record, kind, result, receipt, *, evidence=(), timestamp=None):
    """One transaction uses M3's reducers for all cost/lifetime semantics."""
    timestamp = timestamp or f.wp.now()
    state, attempt, _, task_head = reservation(
        journal, record["task_stream"], record["dispatch_id"]
    )
    require(state["pending"] == record["dispatch_id"], "Stale/conflicting result")
    usage = result.get("usage")
    require(
        usage is None or usage["evidence_sha256"] in {e.sha256 for e in evidence},
        "Usage requires coordinator evidence",
    )
    simulated = f.apply(
        state,
        {
            "kind": kind,
            "data": result,
            "timestamp": timestamp,
            "sequence": task_head.sequence + 1,
        },
    )
    if kind == "RESULT":
        receipt = {
            **receipt,
            "status": "INDEPENDENT_ACCEPTANCE_PENDING"
            if simulated["status"] == "REVIEW_PENDING"
            else simulated["status"],
        }
    accounted = next(a for a in simulated["attempts"] if a["id"] == attempt["id"])[
        "accounting"
    ]
    _, dispatch_head = load(journal, record["dispatch_id"])
    requests = [
        ws.Append(
            stream=record["task_stream"],
            kind=kind,
            data=result,
            expected=task_head,
            reducer=f.reducer(task_head),
            timestamp=timestamp,
            evidence=evidence,
        )
    ]
    for account in f.accounts(state, "worker"):
        requests.append(
            ws.Append(
                stream=account,
                kind="RESULT",
                data={"dispatch_id": attempt["id"], **accounted},
                expected=journal.read(account)[1],
                reducer=budget.apply,
                timestamp=timestamp,
                evidence=evidence,
            )
        )
    requests.append(
        ws.Append(
            stream=stream_name(attempt["id"]),
            kind=kind,
            data=receipt,
            expected=dispatch_head,
            reducer=ds.apply,
            timestamp=timestamp,
            evidence=evidence,
        )
    )
    journal.append_many(tuple(requests))
    return receipt


def ingest(journal, dispatch_id, *, usage=None, usage_evidence=(), timestamp=None):
    """Ingest only the archive bound by ownership; never applies or accepts output."""
    record, _ = load(journal, dispatch_id)
    state, attempt, scope, _ = current(journal, record)
    require(
        record["phase"] in {"STOPPED", "CLOSED"},
        "Run must be explicitly stopped and preserved",
    )
    raw, bundle = output(journal, record)
    report = parse(
        raw, record["intent"]["harness_config"]["limits"]["report_max_bytes"]
    )
    result = report_valid(
        report,
        f.wp.current(record["intent"]["packet"])["contract"],
        dispatch_id,
        record["intent"]["harness_config"]["limits"],
        len(raw),
        binding=record["binding"],
        bundle_sha256=sha(bundle),
    )
    require(
        result["outcome"] != "PASS" or bundle["changes"],
        "PASS requires a changed candidate",
    )
    require(
        result["outcome"] != "PASS" or record["stopped"]["exit_code"] == 0,
        "PASS contradicts worker exit status",
    )
    require(
        result["outcome"] != "PASS"
        or f.instant(record["stopped"]["finished_at"])
        <= f.instant(attempt["deadline"]),
        "PASS after reservation deadline",
    )
    if usage is not None:
        result["usage"] = usage
    fingerprint = sha(
        {
            "report_sha256": digest(raw),
            "bundle_sha256": sha(bundle),
            "binding_sha256": sha(record["binding"]),
            "archive_sha256": record["stopped"]["archive"]["sha256"],
            "usage": usage,
        }
    )
    if record["phase"] == "CLOSED":
        require(
            record["receipt"]["ingestion_sha256"] == fingerprint,
            "Conflicting duplicate ingestion",
        )
        return record["receipt"]
    run = run_path(journal, dispatch_id)
    target = run / ("replacement-" + sha(bundle) + "-" + uuid.uuid4().hex + ".json")
    write_once(target, json_bytes(bundle))
    evidence = (
        journal.evidence(target.relative_to(journal.directory).as_posix()),
        *usage_evidence,
    )
    receipt = {
        "dispatch_id": dispatch_id,
        "ingestion_sha256": fingerprint,
        "status": "INDEPENDENT_ACCEPTANCE_PENDING"
        if result["outcome"] == "PASS"
        else "RECORDED_ADVERSE_RESULT",
        "bundle_sha256": sha(bundle),
    }
    try:
        return settle(
            journal,
            record,
            "RESULT",
            result,
            receipt,
            evidence=evidence,
            timestamp=timestamp,
        )
    except ValueError:
        latest, _ = load(journal, dispatch_id)
        if (
            latest["phase"] == "CLOSED"
            and latest["receipt"]["ingestion_sha256"] == fingerprint
        ):
            return latest["receipt"]
        raise


def reconcile(journal, task_stream, reason, *, stop=False, timestamp=None):
    """Explicit recovery/abandonment. Never renders, retries or starts a worker."""
    secret_free(reason, "Recovery reason")
    require(
        isinstance(reason, str) and 20 <= len(reason) <= 1800,
        "Recovery needs a specific reason",
    )
    state, _, _ = f.replay(journal, task_stream)
    require(state["pending"], "No pending attempt to reconcile")
    dispatch_id = state["pending"]
    attempt = state["attempts"][-1]
    result = {
        "dispatch_id": dispatch_id,
        "outcome": "FAIL",
        "summary": "Explicit coordinator abandonment after interrupted preparation or execution.",
        "scope_status": "unknown",
        "architecture_conflict": False,
        "validation": [],
        "evidence": ["attempt-abandoned: " + reason],
        "discoveries": [],
        "api_cost_usd": None if attempt["api_metered"] else 0,
        "cost_evidence": "Missing usage remains held for a metered reservation.",
    }
    if stream_name(dispatch_id) not in journal.verify():
        # No run can precede the dispatch INIT in this adapter.
        require(
            not run_path(journal, dispatch_id).exists(), "Orphaned preparation holds"
        )
        return f.abandon(journal, task_stream, result, timestamp=timestamp)
    record, _ = load(journal, dispatch_id)
    run = run_path(journal, dispatch_id)
    scope = SessionScope.load(record["intent"]["scope"])
    evidence = ()
    if run.exists():
        require(
            (run / "runtime.json").exists(), "Incomplete run manifest; orphan holds"
        )
        manifest = parse(read_file(run / "runtime.json"), MAX_FILE)
        require(
            manifest["scope_sha256"] == scope.hash
            and manifest["dispatch_stream"] == stream_name(dispatch_id),
            "Orphaned runtime binding holds",
        )
        # A successful Docker inventory distinguishes a missing container from an
        # unavailable engine; a generic inspect failure is never terminal proof.
        ids = (
            runtime.docker("ps", "-a", "--no-trunc", "--format", "{{.ID}}")
            .decode()
            .split()
        )
        for name in (manifest["container"], manifest["setup_container"]):
            # Resolve durable names as well as IDs without swallowing engine errors.
            names = (
                runtime.docker(
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--filter",
                    "name=^/" + name + "$",
                    "--format",
                    "{{.ID}}",
                )
                .decode()
                .split()
            )
            if name in ids or names:
                require(len(names) <= 1, "Ambiguous Docker identity")
                container = name if name in ids else names[0]
                if not runtime.stopped(container) and stop:
                    runtime.docker("kill", container)
                require(
                    runtime.stopped(container),
                    "Orphaned live container holds; explicitly stop before abandonment",
                )
        rows = owner_rows(journal, scope)
        require(len(rows) <= 1, "Ambiguous ownership holds")
        if rows:
            row = rows[0]
            require(
                row["container"] == manifest["container"],
                "Ownership/container mismatch",
            )
            if row["state"] == "claimed":
                Ownership(journal.directory).finish(
                    row["token"],
                    runtime.stopped,
                    lambda c: runtime.preserve(c, run, session=True),
                )
            if record["phase"] != "STOPPED":
                stopped_record(journal, record)
            record, _ = load(journal, dispatch_id)
            a = record["stopped"]["archive"]
            evidence = (ws.Evidence(**a),)
        else:
            require(
                manifest["ownership_token"] is None, "Missing ownership history holds"
            )
    receipt = {
        "dispatch_id": dispatch_id,
        "ingestion_sha256": sha(result),
        "status": "ABANDONED",
        "bundle_sha256": None,
    }
    return settle(
        journal,
        record,
        "ABANDON",
        result,
        receipt,
        evidence=evidence,
        timestamp=timestamp,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-config").add_argument(
        "--config", type=Path, default=ROOT / "config/execution-harness.json"
    )
    prep = commands.add_parser("dispatch")
    prep.add_argument("task_stream")
    for name in ("config", "router-config", "options", "scope"):
        prep.add_argument("--" + name, type=Path, required=True)
    take = commands.add_parser("ingest")
    take.add_argument("dispatch_id")
    recover = commands.add_parser("reconcile")
    recover.add_argument("task_stream")
    recover.add_argument("--reason", required=True)
    recover.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-config":
            config_valid(parse(read_file(args.config, MAX_FILE), MAX_FILE))
            result = {"valid": True}
        else:
            journal = ws.Journal(args.root)
            if args.command == "dispatch":
                values = [
                    parse(read_file(p, MAX_FILE), MAX_FILE)
                    for p in (args.config, args.router_config, args.options, args.scope)
                ]
                result = dispatch(
                    journal,
                    args.task_stream,
                    values[0],
                    values[1],
                    values[2],
                    SessionScope.load(values[3]),
                )
            elif args.command == "ingest":
                result = ingest(journal, args.dispatch_id)
            else:
                result = reconcile(
                    journal, args.task_stream, args.reason, stop=args.stop
                )
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print(
            "Dispatch refused; inspect preserved coordinator state. No output accepted or applied."
        )
        return 1


if __name__ == "__main__":
    from scripts import cli_exit

    raise SystemExit(cli_exit.run(main))
