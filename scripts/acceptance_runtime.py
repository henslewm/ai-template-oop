"""Fresh Docker runs for architect checks; only coordinator-observed exits count."""

from __future__ import annotations

import base64
import copy
from dataclasses import asdict
from datetime import timedelta
import io
from pathlib import Path
import tarfile
import time
import uuid

from scripts import acceptance as a
from scripts import execution_harness as h
from scripts import worker_launcher as launcher
from scripts import workflow_runtime as runtime


class _CandidateScope:
    """Export adapter: original clean base plus exact stopped candidate bytes."""

    def __init__(self, scope, submission):
        self.scope, self.submission = scope, submission
        self.data, self.root, self.hash = scope.data, scope.root, scope.hash

    def verify_base(self):
        self.scope.verify_base()

    def export(self, packet, graph, *, instructions=None):
        raw, baseline = self.scope.export(packet, graph, instructions=instructions)
        replacements = {
            "workspace/" + c["path"]: base64.b64decode(
                c["content_base64"], validate=True
            )
            for c in self.submission["bundle"]["changes"]
        }
        output = io.BytesIO()
        with (
            tarfile.open(fileobj=io.BytesIO(raw)) as source,
            tarfile.open(fileobj=output, mode="w") as target,
        ):
            for member in source:
                stream = source.extractfile(member) if member.isfile() else None
                content = stream.read() if stream is not None else None
                if member.name in replacements:
                    content = replacements[member.name]
                    member.size = len(content)
                if member.name.startswith("workspace/") and member.isfile():
                    member.mode = 0o444
                    member.uid = member.gid = 0
                target.addfile(
                    member, io.BytesIO(content) if content is not None else None
                )
        return output.getvalue(), baseline


def _pilot_abandon_check(journal, stream, run, scope):
    """Persist failure before stopping anything; created/consumed can never pass."""
    from scripts.workflow_scope import Ownership
    import sqlite3

    events, _ = journal.read(stream)
    if not any(e["kind"] == "CHECK_ABANDONED" for e in events):
        journal.append(
            stream,
            "CHECK_ABANDONED",
            {"run": run.name, "reason": "Interrupted check explicitly abandoned"},
            expected=journal.read(stream)[1],
        )
    manifest_path = run / "runtime.json"
    if manifest_path.exists():
        manifest = h.f.wp.read_json(manifest_path)
        listing = (
            runtime.docker("ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.Names}}")
            .decode()
            .splitlines()
        )
        containers = {value: row.split()[0] for row in listing for value in row.split()}
        for name in (manifest["container"], manifest["setup_container"]):
            if name in containers:
                actual = containers[name]
                if runtime.inspect(actual)["State"]["Running"]:
                    runtime.docker("kill", actual)
                h.require(
                    not runtime.inspect(actual)["State"]["Running"],
                    "Interrupted check did not stop",
                )
        if (journal.directory / "ownership.sqlite3").exists():
            with sqlite3.connect(journal.directory / "ownership.sqlite3") as db:
                claims = db.execute(
                    "SELECT token,container FROM runs WHERE scope_hash=? AND state='claimed'",
                    (scope.hash,),
                ).fetchall()
            for token, container in claims:
                h.require(
                    not runtime.inspect(container)["State"]["Running"],
                    "Check owner remains active",
                )
                Ownership(journal.directory).finish(
                    token,
                    lambda c: not runtime.inspect(c)["State"]["Running"],
                    lambda c: runtime.preserve(c, run, session=True),
                )
    if not (run / "stdout.log").exists():
        h.write_once(
            run / "stdout.log",
            b"Interrupted check explicitly abandoned; it did not pass.\n",
        )


def pilot_checks(journal, state, *, reconcile=False):
    """Separate immutable checks; resume original runs without resetting starts."""
    from scripts import pilot_authority as authority
    from scripts.workflow_scope import Ownership
    import sqlite3

    authority.load_profile(journal.root)
    original = h.SessionScope.load(state["scope"])
    h.verify_baseline(original, state["baseline"])
    h.verify_bundle(original, state["baseline"], state["bundle"])
    worker_id = state["attempts"][-1]["id"]
    checks = []
    for check in h.f.wp.current(state["packet"])["contract"]["validation"]:
        stream = "pilot-check:" + worker_id[:32] + ":" + check["id"]
        command = check["command"]
        h.require(command["argv"][0] == "python", "Pilot check entry point differs")
        workdir = runtime.workspace_directory(
            command.get("cwd", ""), original.data["read_paths"]
        )
        if stream not in journal.verify():
            scope = h.SessionScope.load(
                {
                    **original.data,
                    "owner": "Independent-pilot-checks",
                    "run_id": "check-" + uuid.uuid4().hex,
                }
            )
            journal.create(
                stream,
                family="acceptance",
                binding={"worker": worker_id, "bundle_sha256": h.sha(state["bundle"])},
                data={
                    "check": check,
                    "scope": scope.data,
                    "run": "run-pilot-check-" + h.sha([worker_id, check["id"]]),
                },
            )
        events, _ = journal.read(stream)
        initial = events[0]["data"]
        h.require(initial["check"] == check, "Independent check contract changed")
        if events[-1]["kind"] == "RESULT":
            result = events[-1]["data"]
            prepared = next(
                (e["data"] for e in events if e["kind"] == "CHECK_PREPARED"), None
            )
            h.require(
                not result["passed"]
                or (
                    prepared is not None
                    and prepared["runtime"].get("workdir", "/session/workspace")
                    == workdir
                ),
                "Independent check cwd differs from contract",
            )
            checks.append(result)
            continue
        scope = h.SessionScope.load(initial["scope"])
        run = journal.directory / initial["run"]
        aborted = any(e["kind"] == "CHECK_ABANDONED" for e in events)
        if not aborted and events[-1]["kind"] == "INIT":
            if not run.exists():
                runtime.prepare(
                    _CandidateScope(scope, {"bundle": state["bundle"]}),
                    state["packet"],
                    [],
                    journal.directory,
                    authority.IMAGE,
                    command["argv"],
                    cwd=command.get("cwd", ""),
                    immutable_workspace=True,
                    dispatch_stream=stream,
                    run=run,
                )
            manifest_path = run / "runtime.json"
            manifest = (
                h.f.wp.read_json(manifest_path) if manifest_path.exists() else None
            )
            if manifest is None or manifest["status"] != "prepared":
                if not reconcile:
                    raise ValueError(
                        "Interrupted check preparation; run python -B tools/pilot_admin.py reconcile-checks to stop/preserve and fail the existing check"
                    )
                aborted = True
            else:
                saved = {
                    name: h.digest(h.read_file(run / name))
                    for name in (
                        "scope.json",
                        "packet.json",
                        "baseline.json",
                        "input.tar",
                        "runtime.json",
                    )
                }
                journal.append(
                    stream,
                    "CHECK_PREPARED",
                    {"run": run.name, "runtime": manifest, "files": saved},
                    expected=journal.read(stream)[1],
                )
                events, _ = journal.read(stream)
        exit_code, executed = None, False
        if not aborted:
            prepared = next(e["data"] for e in events if e["kind"] == "CHECK_PREPARED")
            manifest, saved = prepared["runtime"], prepared["files"]
            h.require(
                manifest.get("workdir", "/session/workspace") == workdir,
                "Independent check cwd differs from contract",
            )
            if events[-1]["kind"] == "CHECK_PREPARED":
                deadline = (
                    h.f.instant(h.f.wp.now()) + timedelta(seconds=180)
                ).isoformat()
                journal.append(
                    stream,
                    "CHECK_LAUNCHING",
                    {"deadline": deadline},
                    expected=journal.read(stream)[1],
                )
                events, _ = journal.read(stream)
            deadline = events[-1]["data"]["deadline"]

            def preflight(_consumed):
                authority.load_profile(journal.root)
                h.require(
                    journal.read(stream)[0][-1]["kind"] == "CHECK_LAUNCHING",
                    "Independent check phase changed",
                )
                for name, expected in saved.items():
                    h.require(
                        h.digest(h.read_file(run / name)) == expected,
                        "Independent check input changed",
                    )
                actual = runtime.docker("cp", manifest["container"] + ":/session", "-")
                h.require(
                    launcher.archive_files(actual, prefix="session/")
                    == launcher.archive_files(
                        h.read_file(run / "input.tar"), prefix=""
                    ),
                    "Independent check volume changed",
                )

            runtime.assert_boundary(
                manifest["container"], manifest["volume"], authority.IMAGE, workdir
            )
            info = runtime.inspect(manifest["container"])
            h.require(
                info["Mounts"][0].get("RW") is False, "Independent check mount changed"
            )
            if info["State"]["Status"] == "created":
                if reconcile:
                    aborted = True
                elif launcher.startup_attempted(journal, manifest["ownership_token"]):
                    raise ValueError(
                        "Consumed check start never executed; run python -B tools/pilot_admin.py reconcile-checks; it cannot pass"
                    )
                else:
                    runtime.execute(
                        run,
                        journal.directory,
                        min(180, command["timeout_seconds"]),
                        preflight=preflight,
                        absolute_deadline=deadline,
                    )
            elif info["State"]["Running"]:
                if not reconcile and h.f.instant(h.f.wp.now()) < h.f.instant(deadline):
                    raise ValueError(
                        "Interrupted check still runs; resume --run after "
                        + deadline
                        + " to stop/preserve it"
                    )
                runtime.docker("kill", manifest["container"])
            if not aborted:
                info = runtime.inspect(manifest["container"])
                physical = info["State"]
                executed = (
                    physical["Status"] in {"exited", "dead"}
                    and isinstance(physical.get("StartedAt"), str)
                    and bool(physical["StartedAt"])
                    and not physical["StartedAt"].startswith("0001-")
                    and isinstance(physical.get("FinishedAt"), str)
                    and bool(physical["FinishedAt"])
                    and not physical["FinishedAt"].startswith("0001-")
                    and bool(
                        launcher.startup_attempted(journal, manifest["ownership_token"])
                    )
                )
                h.require(
                    executed,
                    "Independent check has no confirmed executed terminal state; reconcile-checks must record failure",
                )
                h.write_once(
                    run / "stdout.log", runtime.docker("logs", manifest["container"])
                )
                with sqlite3.connect(journal.directory / "ownership.sqlite3") as db:
                    claim = db.execute(
                        "SELECT state FROM runs WHERE token=?",
                        (manifest["ownership_token"],),
                    ).fetchone()
                if claim and claim[0] == "claimed":
                    Ownership(journal.directory).finish(
                        manifest["ownership_token"],
                        runtime.stopped,
                        lambda c: runtime.preserve(c, run, session=True),
                    )
                exit_code = physical["ExitCode"]
        if aborted:
            _pilot_abandon_check(journal, stream, run, scope)
        evidence = journal.evidence(
            (run / "stdout.log").relative_to(journal.directory).as_posix()
        )
        result = {
            "id": check["id"],
            "passed": executed and exit_code == 0 and not aborted,
            "bundle_sha256": h.sha(state["bundle"]),
            "image": authority.IMAGE,
            "argv": command["argv"],
            "evidence": asdict(evidence),
            "log": h.read_file(run / "stdout.log").decode(errors="replace")[-4000:],
        }
        journal.append(
            stream,
            "RESULT",
            result,
            expected=journal.read(stream)[1],
            evidence=(evidence,),
        )
        checks.append(result)
    return {"checks": checks, "bundle_sha256": h.sha(state["bundle"])}


def prepare_check(journal, task_stream, validation_id):
    state, head, native, native_head = a.current(journal, task_stream)
    a.require(
        not native["review_pending"] and state["accepted"] is None,
        "Pending review or accepted submission",
    )
    policy = h.f.wp.read_json(journal.root / "config/workflow-bootstrap.json")["policy"]
    a.require(policy["resources_enabled"], "ACTIVE foundation disables execution")
    check = next(
        (v for v in state["contract"]["validation"] if v["id"] == validation_id), None
    )
    if check is None or "command" not in check:
        raise ValueError("Hardware/manual validation remains UNVERIFIED")
    command = check["command"]
    a.require(
        command["argv"][0] in {"python", "sh"},
        "Only offline Python or POSIX shell checks supported",
    )
    # Never let repeated check execution become an unbounded implicit retry loop.
    a.require(
        sum(
            r["generation"] == state["generation"]
            and r["validation_id"] == validation_id
            for r in state["runs"]
        )
        < 2,
        "Deterministic check attempt cap exhausted",
    )
    run_id = uuid.uuid4().hex
    data = copy.deepcopy(state["submission"]["scope"])
    data.update(owner=state["controller"], run_id="accept-" + run_id)
    scope = h.SessionScope.load(data)
    runtime.workspace_directory(command.get("cwd", ""), data["read_paths"])
    bound = min(
        300,
        command["timeout_seconds"],
        state["config"]["policy"]["check_timeout_seconds"],
    )
    deadline = (h.f.instant(h.f.wp.now()) + timedelta(seconds=bound)).isoformat()
    a.append(
        journal,
        task_stream,
        "CHECK_PREPARING",
        {
            "run_id": run_id,
            "scope": data,
            "deadline": deadline,
            "binding_sha256": a.sha(state["submission"]),
            "argv": command["argv"],
            "validation_id": validation_id,
            "native_head": asdict(native_head),
        },
        expected=head,
    )
    # Intent and durable names precede all external mutations. A preparation
    # crash is retained and must be explicitly reconciled, never auto-retried.
    instructions = {
        "brief.json": h.json_bytes(
            {"submission_sha256": a.sha(state["submission"]), "validation": check}
        ),
        "worker-rules.md": b"Independent acceptance check. Supplied candidate inputs are immutable. No host access.\n",
        "dispatch.json": h.json_bytes({"run_id": run_id, "deadline": deadline}),
        "report.json": b"",
    }
    run = runtime.prepare(
        _CandidateScope(scope, state["submission"]),
        state["submission"]["packet"],
        state["submission"]["graph"],
        journal.directory,
        state["submission"]["image"],
        command["argv"],
        cwd=command.get("cwd", ""),
        run=h.run_path(journal, run_id),
        instructions=instructions,
        dispatch_stream=a.stream_name(task_stream),
        immutable_workspace=True,
    )
    for name, raw in instructions.items():
        if name != "report.json":
            h.write_once(run / name, raw)
    files = {
        name: h.digest(h.read_file(run / name))
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
        journal.evidence((run / n).relative_to(journal.directory).as_posix())
        for n in files
    )
    prepared = {
        "run": run.name,
        "files": files,
        "runtime": h.parse(h.read_file(run / "runtime.json"), h.MAX_FILE),
    }
    a.append(
        journal,
        task_stream,
        "CHECK_PREPARED",
        {"run_id": run_id, "prepared": prepared},
        evidence=evidence,
    )
    return run_id


def run_record(journal, state):
    r = state["runs"][-1]
    return {
        "dispatch_id": r["run_id"],
        "intent": {"scope": r["scope"], "baseline": state["submission"]["baseline"]},
        "prepared": r["prepared"],
        "stopped": r["stopped"],
    }


def preflight(journal, task_stream, run_id, *, launching=False, consumed=False):
    state, _, native, native_head = a.current(journal, task_stream)
    r = state["runs"][-1]
    a.require(
        r["run_id"] == run_id
        and r["phase"] == ("LAUNCHING" if launching else "PREPARED"),
        "Check already launched or incomplete",
    )
    a.require(
        r["native_head"] == asdict(native_head) and not native["review_pending"],
        "Stale native feedback head",
    )
    h.ws.active_anchor(journal.root, native["anchor"])
    policy = h.f.wp.read_json(journal.root / "config/workflow-bootstrap.json")["policy"]
    a.require(policy["resources_enabled"], "ACTIVE foundation disables execution")
    record = run_record(journal, state)
    run = h.prepared_files(journal, record)
    manifest = r["prepared"]["runtime"]
    check = next(
        c for c in state["contract"]["validation"] if c["id"] == r["validation_id"]
    )
    workdir = runtime.workspace_directory(check["command"].get("cwd", ""))
    a.require(
        manifest["image"] == state["submission"]["image"]
        and manifest.get("immutable_workspace") is True
        and manifest["argv"] == r["argv"]
        and manifest.get("workdir", "/session/workspace") == workdir
        and manifest["scope_sha256"] == h.SessionScope.load(r["scope"]).hash
        and manifest["dispatch_stream"] == a.stream_name(task_stream),
        "Changed check runtime binding",
    )
    runtime.assert_boundary(
        manifest["container"], manifest["volume"], manifest["image"], workdir
    )
    info = runtime.inspect(manifest["container"])
    a.require(
        info["Mounts"][0].get("RW") is False, "Acceptance session must stay read-only"
    )
    a.require(
        info["State"]["Status"] == "created"
        and info["Config"]["Entrypoint"] == r["argv"][:1]
        and info["Config"]["Cmd"] == r["argv"][1:],
        "Container already started or command changed",
    )
    a.require(
        launcher.archive_files(
            runtime.docker("cp", manifest["container"] + ":/session", "-"),
            prefix="session/",
        )
        == launcher.archive_files(h.read_file(run / "input.tar"), prefix=""),
        "Changed check export",
    )
    scope = h.SessionScope.load(r["scope"])
    rows = h.owner_rows(journal, scope)
    a.require(
        len(rows) == 1
        and rows[0]["state"] == "claimed"
        and rows[0]["token"] == manifest["ownership_token"]
        and rows[0]["container"] == manifest["container"]
        and rows[0]["owner"] == state["controller"]
        and rows[0]["expires"] > time.time(),
        "Exact live ownership required",
    )
    a.require(
        launcher.startup_attempted(journal, rows[0]["token"]) == int(consumed),
        "Startup authority consumed or inconsistent",
    )
    left = (h.f.instant(r["deadline"]) - h.f.instant(h.f.wp.now())).total_seconds()
    a.require(left > 0, "Check deadline expired")
    return run, r, left


def launch_check(journal, task_stream, run_id):
    run, r, left = preflight(journal, task_stream, run_id)
    a.append(journal, task_stream, "CHECK_LAUNCHING", {"run_id": run_id})
    runtime.execute(
        run,
        journal.directory,
        min(300, left),
        preflight=lambda consumed: preflight(
            journal, task_stream, run_id, launching=True, consumed=consumed
        ),
        absolute_deadline=r["deadline"],
    )
    return capture_stopped(journal, task_stream, run_id)


def capture_stopped(journal, task_stream, run_id):
    state, _ = a.load(journal, task_stream)
    r = state["runs"][-1]
    a.require(r["run_id"] == run_id, "Wrong run")
    scope = h.SessionScope.load(r["scope"])
    rows = h.owner_rows(journal, scope)
    a.require(
        len(rows) == 1 and rows[0]["state"] in {"finished", "recovered"},
        "Exact stopped ownership missing",
    )
    row = rows[0]
    a.require(runtime.stopped(row["container"]), "Check tree still live")
    archive = Path(row["evidence"])
    a.require(
        archive.parent == h.run_path(journal, run_id), "Wrong stopped archive directory"
    )
    evidence = journal.evidence(archive.relative_to(journal.directory).as_posix())
    stopped = {
        "archive": asdict(evidence),
        "runtime": {k: row[k] for k in ("token", "container", "scope_hash")},
        "exit_code": runtime.inspect(row["container"])["State"]["ExitCode"],
        "finished_at": h.f.wp.now(),
    }
    a.append(
        journal,
        task_stream,
        "CHECK_STOPPED",
        {"run_id": run_id, "stopped": stopped},
        evidence=(evidence,),
    )
    return stopped


def ingest_check(journal, task_stream, run_id):
    state, head, _, native_head = a.current(journal, task_stream)
    r = state["runs"][-1]
    a.require(
        r["run_id"] == run_id and r["phase"] in {"STOPPED", "CLOSED"},
        "Stopped run required",
    )
    a.require(
        r["phase"] == "CLOSED" or r["native_head"] == asdict(native_head),
        "Stale check/native head",
    )
    # The exact M4 archive validator also rejects links, secrets, unexpected,
    # missing or modified immutable inputs. Never extracts anything on the host.
    raw_report, bundle = h.output(journal, run_record(journal, state))
    a.require(raw_report == b"", "Check must not write a worker report")
    a.require(
        bundle["changes"] == state["submission"]["bundle"]["changes"],
        "Acceptance check changed the candidate",
    )
    manifest = r["prepared"]["runtime"]
    a.require(runtime.stopped(manifest["container"]), "Check tree is not stopped")
    exit_code = runtime.inspect(manifest["container"])["State"]["ExitCode"]
    a.require(exit_code == r["stopped"]["exit_code"], "Observed check exit differs")
    log = h.read_file(h.run_path(journal, run_id) / "stdout.log", h.MAX_FILE)
    evidence = journal.evidence(
        (h.run_path(journal, run_id) / "stdout.log")
        .relative_to(journal.directory)
        .as_posix()
    )
    on_time = h.f.instant(r["stopped"]["finished_at"]) <= h.f.instant(
        r["deadline"]
    ) and h.f.instant(h.f.wp.now()) <= h.f.instant(r["deadline"])
    report = {
        "submission_sha256": a.sha(state["submission"]),
        "run_id": run_id,
        "results": [
            {
                "validation_id": r["validation_id"],
                "status": "PASSED" if exit_code == 0 and on_time else "FAILED",
                "exit_code": exit_code,
                "output_sha256": evidence.sha256,
            }
        ],
    }
    if r["phase"] == "CLOSED":
        # Replay uses the coordinator's durable effective result, including a
        # late first ingestion. Wall-clock passage cannot revise that result.
        report = r["report"]
    receipt = a.sha(
        {"report": report, "archive": r["stopped"]["archive"], "log": h.digest(log)}
    )
    if r["phase"] == "CLOSED":
        a.require(r["receipt"] == receipt, "Conflicting check ingestion")
        return report
    try:
        a.append(
            journal,
            task_stream,
            "CHECK_RESULT",
            {"run_id": run_id, "receipt": receipt, "report": report},
            expected=head,
            evidence=(evidence,),
        )
    except ValueError:
        latest, _ = a.load(journal, task_stream)
        if latest["runs"][-1].get("receipt") != receipt:
            raise
    return report


def reconcile_check(journal, task_stream, reason, *, stop=False):
    state, _ = a.load(journal, task_stream)
    r = state["runs"][-1]
    a.require(
        r["phase"] not in {"CLOSED", "ABANDONED"} and reason.strip(),
        "No pending check or reason",
    )
    scope = h.SessionScope.load(r["scope"])
    run = h.run_path(journal, r["run_id"])
    rows = h.owner_rows(journal, scope)
    manifest = h.parse(h.read_file(run / "runtime.json"), h.MAX_FILE)
    if rows:
        a.require(
            len(rows) == 1 and rows[0]["container"] == manifest["container"],
            "Ambiguous check ownership",
        )
        row = rows[0]
        launcher.startup_attempted(journal, row["token"])
        if not runtime.stopped(row["container"]):
            a.require(stop, "Live check; explicit stop required")
            runtime.docker("kill", row["container"])
        a.require(runtime.stopped(row["container"]), "Check stop not confirmed")
        if row["state"] == "claimed":
            h.Ownership(journal.directory).finish(
                row["token"],
                runtime.stopped,
                lambda c: runtime.preserve(c, run, session=True),
            )
        rows = h.owner_rows(journal, scope)
        journal.evidence(
            Path(rows[0]["evidence"]).relative_to(journal.directory).as_posix()
        )
    else:
        # An existing manifest names both containers even if preparation died
        # before the ownership claim. Both must be observed stopped.
        a.require(
            runtime.stopped(manifest["container"])
            and runtime.stopped(manifest["setup_container"]),
            "Unclaimed preparation not confirmed stopped",
        )
    return a.append(
        journal,
        task_stream,
        "CHECK_ABANDONED",
        {"run_id": r["run_id"], "reason": reason},
    )
