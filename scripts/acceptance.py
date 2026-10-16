"""Independent Journal acceptance; untrusted commands run only in fresh Docker exports."""

from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import acceptance_report as reports
from scripts import execution_harness as h
from scripts import feedback as f
from scripts import workflow_budget as budget
from scripts import workflow_state as ws
from scripts.workflow_scope import git as scope_git

VERSION = "destination-acceptance-1"
require = h.require
sha = h.sha


def pilot_review(state, report, attempt):
    """Independent pilot review binds exact candidate and all preset criteria."""
    from scripts import pilot_authority

    require(
        attempt["role"] == "reviewer" and attempt["model"] == "gpt-6.1-sol",
        "Pilot requires its separate Sol reviewer invocation",
    )
    independent(attempt["actor"], [a["actor"] for a in state["attempts"]])
    require(
        state["checks"] is not None
        and all(c["passed"] for c in state["checks"]["checks"]),
        "Independent deterministic checks must pass before review",
    )
    contract = f.wp.current(state["packet"])["contract"]
    require(
        contract["risk"] in {"low", "medium"},
        "Higher risk review requirements remain in force",
    )
    found = [c["id"] for c in report["criteria"]]
    expected = [c["id"] for c in contract["acceptance_criteria"]]
    require(
        len(found) == len(set(found)) and set(found) == set(expected),
        "Every criterion must be reviewed exactly once",
    )
    require(
        report["bundle_sha256"] == h.sha(state["bundle"]),
        "Review binds a different candidate",
    )
    require(
        state["scope"]["write_paths"] == pilot_authority.WRITE_PATHS,
        "Pilot scope differs",
    )
    if report["verdict"] == "APPROVE":
        require(
            all(c["met"] for c in report["criteria"]), "Approval has unmet criteria"
        )
    if report["verdict"] == "REJECT_BOUNDED":
        require(
            any(not c["met"] for c in report["criteria"]),
            "Bounded rejection needs an unmet criterion",
        )
    require(bool(report["summary"].strip()), "Review summary required")


def config_valid(config):
    reports.shape("config", config)
    h.secret_free(config)
    p = config["policy"]
    require(p["max_review_attempts"] <= 2, "Review cap exceeds destination floor")
    require(p["check_timeout_seconds"] <= 300, "Docker timeout exceeds bound")
    require(p["review_packet_max_chars"] <= 40000, "Context exceeds bound")
    return config


def independent(actor, implementers):
    name = f.actor_identity(actor)
    require(
        name not in {f.actor_identity(a) for a in implementers},
        "Named independent actor required",
    )


def gates_for(contract, config):
    gates = (
        f.REVIEW_FLOORS[contract["risk"]]
        | set(contract.get("review", {}).get("required_gates", []))
        | set(config["policy"]["additional_gates"][contract["risk"]])
    )
    if "cross_family_review" in gates:
        gates |= {"model_review"}
    return sorted(gates)


def stream_name(task_stream):
    return "acceptance:" + task_stream.removeprefix("task:")


def load(journal, task_stream):
    return journal.replay(stream_name(task_stream), apply)


def event_data(state, event):
    """Pure gate validation shared by append, replay and embedded feedback proofs."""
    kind, data = event["kind"], event["data"]
    if state is None:
        require(kind == "INIT", "Acceptance requires INIT")
        f.exact(
            data,
            {
                "version",
                "task_stream",
                "controller",
                "architect",
                "config",
                "submission",
                "anchor",
            },
        )
        require(data["version"] == VERSION, "Unsupported acceptance version")
        reports.shape("sha256", data["anchor"])
        config_valid(data["config"])
        state = {
            **copy.deepcopy(data),
            "reviews": [],
            "checks": None,
            "attestations": {},
            "decision": None,
            "pending": None,
            "accepted": None,
            "synced": None,
            "runs": [],
            "generation": 0,
            "submitted_at": event["timestamp"],
        }
        validate_submission(state, data["submission"])
        return state
    state = copy.deepcopy(state)
    require(state["synced"] is None, "Acceptance already synchronized")
    require(
        state["accepted"] is None or kind in {"SUBMIT", "SYNC"},
        "Accepted gates are immutable; resubmit to invalidate",
    )
    if kind == "SUBMIT":
        require(
            not state["pending"]
            and not any(
                r["phase"] not in {"CLOSED", "ABANDONED"} for r in state["runs"]
            ),
            "Pending work requires explicit reconciliation",
        )
        f.exact(data, {"submission"})
        validate_submission(state, data["submission"])
        require(
            sha(data["submission"]) != sha(state["submission"]), "Unchanged submission"
        )
        state.update(
            submission=copy.deepcopy(data["submission"]),
            checks=None,
            attestations={},
            decision=None,
            accepted=None,
            generation=state["generation"] + 1,
            submitted_at=event["timestamp"],
        )
    elif kind == "CHECK_PREPARING":
        require(
            state["accepted"] is None and not state["pending"],
            "Gate closed or review pending",
        )
        require(
            not any(r["phase"] not in {"CLOSED", "ABANDONED"} for r in state["runs"]),
            "A check run is pending",
        )
        require(
            not any(r["generation"] == state["generation"] for r in state["reviews"])
            and state["decision"] is None,
            "Review or user evidence exists; resubmit before rerunning checks",
        )
        f.exact(
            data,
            {
                "run_id",
                "scope",
                "deadline",
                "binding_sha256",
                "argv",
                "validation_id",
                "native_head",
            },
        )
        require(
            data["binding_sha256"] == sha(state["submission"]), "Wrong check binding"
        )
        require(
            data["run_id"] not in {r["run_id"] for r in state["runs"]},
            "Repeated run identity",
        )
        f.instant(data["deadline"])
        if state["checks"] is not None:
            state["checks"].pop(data["validation_id"], None)
        check = next(
            (
                c
                for c in state["contract"]["validation"]
                if c["id"] == data["validation_id"]
            ),
            None,
        )
        require(
            check is not None and check.get("command", {}).get("argv") == data["argv"],
            "Check command differs from contract",
        )
        if check is None:
            raise ValueError("Missing contract check")
        expected_scope = {
            **state["submission"]["scope"],
            "owner": state["controller"],
            "run_id": "accept-" + data["run_id"],
        }
        require(data["scope"] == expected_scope, "Check scope differs from submission")
        require(re.fullmatch("[a-f0-9]{32}", data["run_id"]), "Invalid check identity")
        bound = min(
            300,
            check["command"]["timeout_seconds"],
            state["config"]["policy"]["check_timeout_seconds"],
        )
        require(
            0
            < (
                f.instant(data["deadline"]) - f.instant(event["timestamp"])
            ).total_seconds()
            <= bound,
            "Wrong check deadline",
        )
        state["runs"].append(
            {
                **copy.deepcopy(data),
                "phase": "PREPARING",
                "prepared": None,
                "stopped": None,
                "generation": state["generation"],
            }
        )
    elif kind in {
        "CHECK_PREPARED",
        "CHECK_LAUNCHING",
        "CHECK_STOPPED",
        "CHECK_RESULT",
        "CHECK_ABANDONED",
    }:
        run = state["runs"][-1]
        require(data["run_id"] == run["run_id"], "Wrong check run")
        if kind == "CHECK_PREPARED":
            require(run["phase"] == "PREPARING", "Preparation already recorded")
            f.exact(data, {"run_id", "prepared"})
            prepared = data["prepared"]
            f.exact(prepared, {"run", "files", "runtime"})
            manifest = prepared["runtime"]
            require(
                prepared["run"] == "run-dispatch-" + run["run_id"]
                and manifest["image"] == state["submission"]["image"]
                and manifest.get("immutable_workspace") is True
                and manifest["argv"] == run["argv"]
                and manifest["scope_sha256"] == h.SessionScope.load(run["scope"]).hash
                and manifest["dispatch_stream"] == stream_name(state["task_stream"]),
                "Wrong prepared run binding",
            )
            require(
                set(prepared["files"])
                == {
                    "scope.json",
                    "packet.json",
                    "baseline.json",
                    "input.tar",
                    "brief.json",
                    "worker-rules.md",
                    "dispatch.json",
                    "runtime.json",
                }
                and all(
                    isinstance(v, str) and re.fullmatch("[a-f0-9]{64}", v)
                    for v in prepared["files"].values()
                ),
                "Wrong prepared evidence inventory",
            )
            run.update(prepared=copy.deepcopy(data["prepared"]), phase="PREPARED")
        elif kind == "CHECK_LAUNCHING":
            f.exact(data, {"run_id"})
            require(run["phase"] == "PREPARED", "Run cannot restart")
            run["phase"] = "LAUNCHING"
        elif kind == "CHECK_STOPPED":
            f.exact(data, {"run_id", "stopped"})
            require(
                run["phase"] in {"PREPARING", "PREPARED", "LAUNCHING"},
                "Run already stopped",
            )
            stopped = data["stopped"]
            f.exact(stopped, {"archive", "runtime", "exit_code", "finished_at"})
            require(
                run["prepared"] is not None,
                "Stopped evidence requires prepared binding",
            )
            manifest = run["prepared"]["runtime"]
            require(
                stopped["runtime"]
                == {
                    "token": manifest["ownership_token"],
                    "container": manifest["container"],
                    "scope_hash": manifest["scope_sha256"],
                },
                "Wrong stopped runtime",
            )
            archive = stopped["archive"]
            f.exact(archive, {"path", "sha256", "size"})
            require(
                re.fullmatch(
                    "run-dispatch-" + run["run_id"] + r"/output-[a-f0-9]{32}\.tar",
                    archive["path"],
                )
                and re.fullmatch("[a-f0-9]{64}", archive["sha256"])
                and type(archive["size"]) is int
                and 0 < archive["size"] <= h.MAX_EXPORT * 2
                and type(stopped["exit_code"]) is int,
                "Wrong stopped archive binding",
            )
            run.update(stopped=copy.deepcopy(data["stopped"]), phase="STOPPED")
        elif kind == "CHECK_ABANDONED":
            f.exact(data, {"run_id", "reason"})
            require(
                run["phase"] not in {"CLOSED", "ABANDONED"} and data["reason"].strip(),
                "Run already closed",
            )
            run.update(phase="ABANDONED", reason=data["reason"])
        else:
            f.exact(data, {"run_id", "receipt", "report"})
            require(run["phase"] == "STOPPED", "Checks require stopped output")
            validate_checks(state, run, data["report"])
            result = data["report"]["results"][0]
            require(
                result["exit_code"] == run["stopped"]["exit_code"],
                "Check result contradicts stopped exit",
            )
            if result["status"] == "PASSED":
                require(
                    f.instant(run["stopped"]["finished_at"])
                    <= f.instant(run["deadline"])
                    and f.instant(event["timestamp"]) <= f.instant(run["deadline"]),
                    "Late check cannot pass",
                )
            require(
                data["receipt"]
                == sha(
                    {
                        "report": data["report"],
                        "archive": run["stopped"]["archive"],
                        "log": result["output_sha256"],
                    }
                ),
                "Wrong check receipt",
            )
            run.update(
                phase="CLOSED",
                receipt=copy.deepcopy(data["receipt"]),
                report=copy.deepcopy(data["report"]),
            )
            if state["checks"] is None:
                state["checks"] = {}
            state["checks"][run["validation_id"]] = copy.deepcopy(data)
    elif kind == "REVIEW_OPEN":
        f.exact(data, {"review_id", "gate", "reviewer", "deadline", "native_head"})
        require(
            state["accepted"] is None and not state["pending"],
            "Review already pending or gate closed",
        )
        require(deterministic(state), "Independent deterministic gate must pass first")
        require(
            all(r["phase"] in {"CLOSED", "ABANDONED"} for r in state["runs"]),
            "A check run is pending",
        )
        require(
            data["gate"] in {"model_review", "architect_review"}
            and data["gate"] in state["gates"],
            "Gate is not required",
        )
        require(
            len(state["reviews"]) < state["config"]["policy"]["max_review_attempts"],
            "Cumulative review cap exhausted",
        )
        reviewer_valid(state, data["reviewer"], data["gate"])
        require(
            data["review_id"] not in {r["review_id"] for r in state["reviews"]},
            "Duplicate review",
        )
        state["reviews"].append(
            {
                **copy.deepcopy(data),
                "generation": state["generation"],
                "report": None,
                "abandoned": None,
            }
        )
        state["pending"] = data["review_id"]
    elif kind == "REVIEW_RESULT":
        f.exact(data, {"report"})
        require(state["pending"] is not None, "No pending review")
        opened = state["reviews"][-1]
        reports.report_valid(
            data["report"], state["contract"], opened, state["config"]["policy"]
        )
        require(
            f.instant(event["timestamp"]) <= f.instant(opened["deadline"]),
            "Review deadline expired; abandon explicitly",
        )
        opened["report"] = copy.deepcopy(data["report"])
        state["pending"] = None
    elif kind == "REVIEW_ABANDONED":
        f.exact(data, {"review_id", "reason"})
        require(
            data["review_id"] == state["pending"] and data["reason"].strip(),
            "No matching pending review",
        )
        state["reviews"][-1]["abandoned"] = data["reason"]
        state["pending"] = None
    elif kind == "ATTESTATION":
        f.exact(data, {"validation_id", "actor", "evidence", "submission_sha256"})
        require(
            data["submission_sha256"] == sha(state["submission"]), "Stale attestation"
        )
        independent(data["actor"], state["implementers"])
        check = next(
            (
                v
                for v in state["contract"]["validation"]
                if v["id"] == data["validation_id"]
            ),
            None,
        )
        require(
            check is not None and "command" not in check,
            "Attestation cannot waive a command",
        )
        require(
            data["evidence"]
            and all(e["sha256"] and e["size"] > 0 for e in data["evidence"]),
            "Actual evidence required",
        )
        raise ValueError(
            "Hardware evidence ingestion is not enabled; manual checks remain UNVERIFIED"
        )
    elif kind == "DECISION":
        f.exact(data, {"actor", "decision", "reason", "submission_sha256"})
        independent(data["actor"], state["implementers"])
        require(
            "user_decision" in state["gates"] and state["decision"] is None,
            "No open user-decision gate",
        )
        other_gates = {
            **state,
            "gates": [g for g in state["gates"] if g != "user_decision"],
        }
        require(
            satisfied(other_gates)
            and not state["pending"]
            and all(r["phase"] in {"CLOSED", "ABANDONED"} for r in state["runs"]),
            "Other acceptance gates must pass before user decision",
        )
        require(
            data["decision"] in {"approve", "reject"}
            and data["reason"].strip()
            and data["submission_sha256"] == sha(state["submission"]),
            "Invalid user decision",
        )
        require(
            f.actor_identity(data["actor"]) != f.actor_identity(state["controller"]),
            "User decision must be separate from controller",
        )
        state["decision"] = copy.deepcopy(data)
    elif kind == "ACCEPT":
        f.exact(data, {"actor", "submission_sha256", "native_head"})
        require(
            state["accepted"] is None and not state["pending"],
            "Acceptance closed or review pending",
        )
        require(
            all(r["phase"] in {"CLOSED", "ABANDONED"} for r in state["runs"]),
            "A check run is pending",
        )
        independent(data["actor"], state["implementers"])
        require(
            f.actor_identity(data["actor"]) == f.actor_identity(state["controller"]),
            "Only bound controller can accept",
        )
        require(
            data["submission_sha256"] == sha(state["submission"]) and satisfied(state),
            "Required acceptance gates incomplete",
        )
        state["accepted"] = copy.deepcopy(data)
    elif kind == "SYNC":
        f.exact(data, {"proof_sha256", "task_head"})
        require(state["accepted"] is not None, "Acceptance not granted")
        state["synced"] = copy.deepcopy(data)
    else:
        raise ValueError("Invalid acceptance transition")
    return state


def apply(state, event):
    h.secret_free(event["data"], "Acceptance event")
    return event_data(state, event)


def validate_submission(state, submission):
    f.exact(
        submission,
        {
            "task",
            "worker_dispatch_id",
            "worker",
            "contract",
            "packet",
            "graph",
            "scope",
            "baseline",
            "artifact",
            "commits",
            "image",
            "environment_sha256",
            "archive",
            "bundle",
        },
    )
    require(submission["task"]["role"] == "worker", "Worker task binding required")
    packet = submission["packet"]
    f.wp.require_valid(packet)
    require(
        submission["task"] == f.binding(packet)
        and submission["contract"] == f.wp.current(packet)["contract"],
        "Wrong task/contract",
    )
    require(state["task_stream"] == "task:" + packet["task_id"], "Wrong task stream")
    scope = h.SessionScope.load(submission["scope"])
    require(
        len(scope.data["read_paths"])
        <= state["config"]["policy"]["workspace_digest_max_files"],
        "Candidate exceeds configured file count",
    )
    require(
        len(f.wp.canonical(submission["bundle"]))
        <= state["config"]["policy"]["artifact_max_chars"],
        "Candidate artifact exceeds configured bound; decompose",
    )
    reports.shape("sha256", submission["environment_sha256"])
    require(
        scope.data["packet_revision_hash"] == submission["task"]["contract_hash"],
        "Wrong scope contract",
    )
    f.exact(submission["commits"], {"feature", "ui", "base"})
    require(
        all(
            isinstance(v, str) and re.fullmatch("[0-9a-f]{40}", v)
            for v in submission["commits"].values()
        ),
        "Exact commit identities required",
    )
    require(
        submission["commits"]["base"] == scope.data["base_commit"]
        and submission["commits"][
            "feature" if scope.data["role"] == "feature" else "ui"
        ]
        == scope.data["base_commit"],
        "Commit/scope binding differs",
    )
    artifact = submission["artifact"]
    f.exact(artifact, {"reference", "sha256"})
    require(
        isinstance(artifact["reference"], str)
        and 0 < len(artifact["reference"]) <= 2000
        and artifact["sha256"] == sha(submission["bundle"]),
        "Exact artifact reference/digest required",
    )
    require(
        re.fullmatch("sha256:[0-9a-f]{64}", submission["image"]),
        "Immutable image required",
    )
    state["contract"] = copy.deepcopy(submission["contract"])
    state["gates"] = gates_for(state["contract"], state["config"])
    state["implementers"] = [submission["worker"]["actor"]]
    independent(state["controller"], state["implementers"])
    independent(state["architect"], state["implementers"])


def reviewer_valid(state, reviewer, gate):
    reports.shape("reviewer", reviewer)
    independent(reviewer["actor"], state["implementers"])
    require(
        reviewer["tier"] >= state["contract"]["routing"]["reviewer_tier"],
        "Reviewer tier below contract floor",
    )
    if "cross_family_review" in state["gates"]:
        require(
            f.actor_identity(reviewer["model_family"])
            != f.actor_identity(state["submission"]["worker"]["model_family"]),
            "Cross-family reviewer required",
        )
    if gate == "architect_review":
        require(
            f.actor_identity(reviewer["actor"]) == f.actor_identity(state["architect"]),
            "Named architect required",
        )


def validate_checks(state, run, report):
    f.exact(report, {"submission_sha256", "run_id", "results"})
    require(
        report["submission_sha256"] == sha(state["submission"])
        and report["run_id"] == run["run_id"],
        "Wrong deterministic binding",
    )
    ids = [r["validation_id"] for r in report["results"]]
    require(ids == [run["validation_id"]], "Duplicate/unknown/missing validation IDs")
    for result in report["results"]:
        f.exact(result, {"validation_id", "status", "exit_code", "output_sha256"})
        require(
            result["status"] in {"PASSED", "FAILED", "UNVERIFIED"},
            "Invalid deterministic status",
        )
        require(
            result["exit_code"] is None or type(result["exit_code"]) is int,
            "Invalid exit status",
        )
        require(
            isinstance(result["output_sha256"], str)
            and re.fullmatch("[0-9a-f]{64}", result["output_sha256"]),
            "Output digest required",
        )
        check = next(
            v
            for v in state["contract"]["validation"]
            if v["id"] == result["validation_id"]
        )
        require(
            ("command" in check) == (result["status"] != "UNVERIFIED"),
            "Missing hardware stays unverified",
        )
        require(
            result["status"] != "PASSED" or result["exit_code"] == 0,
            "Contradictory deterministic PASS",
        )


def deterministic(state):
    return all(
        (state["checks"] or {})
        .get(v["id"], {})
        .get("report", {})
        .get("results", [{}])[0]
        .get("status")
        == "PASSED"
        if "command" in v
        else v["id"] in state["attestations"]
        for v in state["contract"]["validation"]
    )


def satisfied(state):
    if not deterministic(state):
        return False
    for gate in set(state["gates"]) & {"model_review", "architect_review"}:
        current = [
            r
            for r in state["reviews"]
            if (
                r["gate"] == gate
                or gate == "model_review"
                and r["gate"] == "architect_review"
            )
            and r["generation"] == state["generation"]
        ]
        if (
            not current
            or current[-1]["report"] is None
            or current[-1]["report"]["verdict"] != "APPROVE"
        ):
            return False
    # Any adverse current report remains a hold until a new submission.
    if any(
        r["report"] and r["report"]["verdict"] != "APPROVE"
        for r in state["reviews"]
        if r["generation"] == state["generation"]
    ):
        return False
    return (
        "user_decision" not in state["gates"]
        or state["decision"] is not None
        and state["decision"]["decision"] == "approve"
    )


def append(
    journal, task_stream, kind, data, *, evidence=(), timestamp=None, expected=None
):
    _, head = load(journal, task_stream)
    return journal.append(
        stream_name(task_stream),
        kind,
        data,
        expected=expected or head,
        reducer=apply,
        evidence=evidence,
        timestamp=timestamp or f.wp.now(),
    )


def candidate(journal, task_stream, worker_dispatch_id, *, reference, commits, image):
    record, _ = h.load(journal, worker_dispatch_id)
    native, attempt, scope, _ = h.current(journal, record)
    require(
        record["task_stream"] == task_stream
        and record["phase"] == "CLOSED"
        and record["receipt"]["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
        and native["status"] == "REVIEW_PENDING"
        and not native["pending"]
        and not native["review_pending"]
        and not f.accounting(native)["unknown"],
        "Exact worker PASS awaiting acceptance required",
    )
    _, bundle = h.output(journal, record)
    require(
        sha(bundle) == record["receipt"]["bundle_sha256"], "Candidate bundle differs"
    )
    for commit in commits.values():
        require(
            re.fullmatch("[0-9a-f]{40}", commit)
            and scope_git(scope.root, "cat-file", "-t", commit) == "commit",
            "Commit object missing",
        )
    env = json.loads(h.runtime.docker("image", "inspect", image))[0]["Config"]["Env"]
    return {
        "task": f.binding(native["packet"]),
        "worker_dispatch_id": worker_dispatch_id,
        "worker": {k: attempt[k] for k in ("actor", "model_family", "tier")},
        "contract": f.wp.current(native["packet"])["contract"],
        "packet": record["intent"]["packet"],
        "graph": record["intent"]["graph"],
        "scope": scope.data,
        "baseline": record["intent"]["baseline"],
        "artifact": {"reference": reference, "sha256": sha(bundle)},
        "commits": commits,
        "image": image,
        "environment_sha256": sha(env),
        "archive": record["stopped"]["archive"],
        "bundle": bundle,
    }


def initialize(
    journal, task_stream, worker_dispatch_id, config, controller, architect, **bindings
):
    config_valid(config)
    submission = candidate(journal, task_stream, worker_dispatch_id, **bindings)
    native = f.replay(journal, task_stream)[0]
    return journal.create(
        stream_name(task_stream),
        family="project",
        binding={"task_stream": task_stream},
        data={
            "version": VERSION,
            "task_stream": task_stream,
            "controller": controller,
            "architect": architect,
            "config": config,
            "submission": submission,
            "anchor": native["anchor"],
        },
        reducer=apply,
        timestamp=f.wp.now(),
    )


def current(journal, task_stream):
    state, head = load(journal, task_stream)
    s = state["submission"]
    native, seq, last = f.replay(journal, task_stream)
    require(
        (
            native["status"] == "REVIEW_PENDING"
            or native["status"] == "ACCEPTED"
            and state["synced"] is not None
        )
        and not native["pending"]
        and not f.accounting(native)["unknown"],
        "Native feedback hold",
    )
    # A review may be pending; candidate() deliberately refuses it, so verify its
    # exact worker inputs directly without reinitializing or losing history.
    record, _ = h.load(journal, s["worker_dispatch_id"])
    h.current(journal, record)
    _, bundle = h.output(journal, record)
    require(
        bundle == s["bundle"]
        and record["stopped"]["archive"] == s["archive"]
        and f.binding(native["packet"]) == s["task"]
        and native["attempts"][-1]["id"] == s["worker_dispatch_id"],
        "Stale candidate/task binding",
    )
    env = json.loads(h.runtime.docker("image", "inspect", s["image"]))[0]["Config"][
        "Env"
    ]
    require(sha(env) == s["environment_sha256"], "Changed image environment")
    return state, head, native, ws.Head(seq, last)


def resubmit(journal, task_stream, worker_dispatch_id, **bindings):
    submission = candidate(journal, task_stream, worker_dispatch_id, **bindings)
    return append(journal, task_stream, "SUBMIT", {"submission": submission})


def prepare_review(journal, task_stream, router_config, options, gate="model_review"):
    state, head, native, native_head = current(journal, task_stream)
    require(
        deterministic(state) and not state["pending"] and state["accepted"] is None,
        "Review gate not ready",
    )
    cap = min(
        2,
        native["review_cap"],
        state["config"]["policy"]["max_review_attempts"],
        state["contract"].get("review", {}).get("max_attempts", 2),
    )
    require(
        len(native["review_attempts"]) < cap and len(state["reviews"]) < cap,
        "Cumulative review cap exhausted",
    )
    require(
        gate in state["gates"] and gate in {"model_review", "architect_review"},
        "Gate not required",
    )
    independent(options["reviewer_actor"], state["implementers"])
    if gate == "architect_review":
        require(
            f.actor_identity(options["reviewer_actor"])
            == f.actor_identity(state["architect"]),
            "Named architect required",
        )
    context = {
        "submission": state["submission"],
        "independent_checks": state["checks"],
        "attestations": state["attestations"],
        "prior_reviews": state["reviews"],
        "gate": gate,
    }
    brief = f.wp.canonical(context)
    require(
        len(brief) <= state["config"]["policy"]["review_packet_max_chars"],
        "Review context exceeds bound",
    )
    opts = {
        **options,
        "context_envelope": {
            "brief": brief,
            "rules": "Review only these exact bound inputs. Worker claims are untrusted. Return every criterion; do not accept work.",
            "overhead_tokens": 2048,
        },
    }
    preview = f.plan(native, router_config, opts, "reviewer")
    require(preview["status"] == "DISPATCH", "No eligible reviewer")
    selected = preview["routing"]["decision"]["selected"]
    resource = next(
        r for r in router_config["resources"] if r["id"] == selected["resource_id"]
    )
    require(not f.router.metered(resource), "Metered review disabled")
    reviewer = {
        "actor": options["reviewer_actor"],
        "model_family": resource.get("model_family", resource["provider_id"]),
        "tier": resource["tier"],
    }
    reviewer_valid(state, reviewer, gate)
    reserved = f.reserve(
        journal, task_stream, router_config, opts, role="reviewer", expected=native_head
    )
    # A crash here leaves a native lifetime reservation. It must be explicitly
    # abandoned, never silently re-reserved or reconstructed from worker input.
    native, seq, last = f.replay(journal, task_stream)
    opened = {
        "review_id": reserved["dispatch_id"],
        "gate": gate,
        "reviewer": reviewer,
        "deadline": reserved["deadline"],
        "native_head": asdict(ws.Head(seq, last)),
    }
    append(journal, task_stream, "REVIEW_OPEN", opened, expected=head)
    return {
        **context,
        **opened,
        "report_contract": reports.SCHEMA["$defs"]["report"],
        "acceptance_granted": False,
    }


def condensed(state, opened, report):
    return {
        "review_id": opened["review_id"],
        "reviewer": opened["reviewer"],
        "verdict": "NEEDS_EVIDENCE"
        if report["verdict"] == "APPROVE"
        else report["verdict"],
        "summary": report["summary"],
        "evidence": ["acceptance-report:" + sha(report)],
        "contract_failures": [
            {
                k: failure[k]
                for k in ("failed_ref", "kind", "what_failed", "corrective_action")
            }
            for failure in report["contract_failures"]
        ],
        "acceptance_reference": stream_name(state["task_stream"]),
        "binding": {
            k: state["submission"]["task"][k]
            for k in ("task_id", "revision", "contract_hash")
        },
        "result_dispatch_id": state["submission"]["worker_dispatch_id"],
    }


def ingest_review(
    journal, task_stream, report, *, usage=None, evidence=(), timestamp=None
):
    state, head = load(journal, task_stream)
    native, _, _ = f.replay(journal, task_stream)
    # Exact duplicate delivery succeeds without another task result or attempt.
    old = next(
        (r for r in state["reviews"] if r["review_id"] == report.get("review_id")), None
    )
    if old and old["report"] is not None:
        require(old["report"] == report, "Conflicting duplicate reviewer report")
        events, _ = journal.read(stream_name(task_stream))
        require(
            any(
                e["kind"] == "REVIEW_RESULT" and e["data"]["report"] == report
                for e in events
            ),
            "Missing review receipt",
        )
        # Usage is part of the atomic native event, not a reviewer assertion.
        saved = native["review_attempts"][
            [a["id"] for a in native["review_attempts"]].index(report["review_id"])
        ]
        require(saved.get("usage") == usage, "Conflicting duplicate usage")
        return old
    state, head, native, native_head = current(journal, task_stream)
    require(
        state["pending"] == native["review_pending"] and state["pending"] is not None,
        "Pending reviewer binding differs",
    )
    opened = state["reviews"][-1]
    require(asdict(native_head) == opened["native_head"], "Stale review feedback head")
    reports.report_valid(report, state["contract"], opened, state["config"]["policy"])
    timestamp = timestamp or f.wp.now()
    data = {
        "dispatch_id": opened["review_id"],
        "decision": condensed(state, opened, report),
        "usage": usage,
    }
    require(
        usage is None or usage["evidence_sha256"] in {e.sha256 for e in evidence},
        "Usage requires coordinator evidence",
    )
    simulated = f.apply(
        native,
        {
            "kind": "REVIEW",
            "data": data,
            "timestamp": timestamp,
            "sequence": native_head.sequence + 1,
        },
    )
    outcome = {
        "dispatch_id": opened["review_id"],
        **simulated["review_attempts"][-1]["accounting"],
    }
    requests = [
        ws.Append(
            stream=task_stream,
            kind="REVIEW",
            data=data,
            expected=native_head,
            reducer=f.reducer(native_head),
            timestamp=timestamp,
            evidence=evidence,
        ),
        ws.Append(
            stream=stream_name(task_stream),
            kind="REVIEW_RESULT",
            data={"report": report},
            expected=head,
            reducer=apply,
            timestamp=timestamp,
            evidence=evidence,
        ),
    ]
    for account in f.accounts(native, "reviewer"):
        requests.append(
            ws.Append(
                stream=account,
                kind="RESULT",
                data=outcome,
                expected=journal.read(account)[1],
                reducer=budget.apply,
                timestamp=timestamp,
                evidence=evidence,
            )
        )
    try:
        journal.append_many(tuple(requests))
    except ValueError:
        latest, _ = load(journal, task_stream)
        if not any(r["report"] == report for r in latest["reviews"]):
            raise
        return ingest_review(
            journal,
            task_stream,
            report,
            usage=usage,
            evidence=evidence,
            timestamp=timestamp,
        )
    return load(journal, task_stream)[0]["reviews"][-1]


def abandon_review(journal, task_stream, reason):
    state, head = load(journal, task_stream)
    native, seq, last = f.replay(journal, task_stream)
    require(native["review_pending"] is not None, "No native review pending")
    rid = native["review_pending"]
    if state["pending"] is None:
        # Explicit recovery of reserve-before-REVIEW_OPEN: M3 owns its lifetime
        # count and all accounting even though no acceptance review was opened.
        return f.finish(
            journal,
            task_stream,
            "REVIEW_ABANDONED",
            {"dispatch_id": rid, "reason": reason},
        )
    require(state["pending"] == rid, "Review binding differs")
    native_head = ws.Head(seq, last)
    timestamp = f.wp.now()
    data = {"dispatch_id": rid, "reason": reason}
    simulated = f.apply(
        native,
        {
            "kind": "REVIEW_ABANDONED",
            "data": data,
            "timestamp": timestamp,
            "sequence": seq + 1,
        },
    )
    requests = [
        ws.Append(
            stream=task_stream,
            kind="REVIEW_ABANDONED",
            data=data,
            expected=native_head,
            reducer=f.reducer(native_head),
            timestamp=timestamp,
        ),
        ws.Append(
            stream=stream_name(task_stream),
            kind="REVIEW_ABANDONED",
            data={"review_id": rid, "reason": reason},
            expected=head,
            reducer=apply,
            timestamp=timestamp,
        ),
    ]
    for account in f.accounts(native, "reviewer"):
        requests.append(
            ws.Append(
                stream=account,
                kind="RESULT",
                data={
                    "dispatch_id": rid,
                    **simulated["review_attempts"][-1]["accounting"],
                },
                expected=journal.read(account)[1],
                reducer=budget.apply,
                timestamp=timestamp,
            )
        )
    journal.append_many(tuple(requests))


def accept(journal, task_stream, actor):
    state, head, native, native_head = current(journal, task_stream)
    require(not native["review_pending"], "Native reviewer pending")
    ws.active_anchor(journal.root, native["anchor"])
    return append(
        journal,
        task_stream,
        "ACCEPT",
        {
            "actor": actor,
            "submission_sha256": sha(state["submission"]),
            "native_head": asdict(native_head),
        },
        expected=head,
    )


def proof_state(proof):
    f.exact(proof, {"events", "head"})
    state, previous = None, None
    require(
        isinstance(proof["events"], list) and 1 <= len(proof["events"]) <= 1000,
        "Bounded proof required",
    )
    for number, event in enumerate(proof["events"], 1):
        require(
            event["sequence"] == number and event["previous"] == previous,
            "Broken acceptance proof chain",
        )
        raw = {k: v for k, v in event.items() if k != "hash"}
        require(sha(raw) == event["hash"], "Acceptance proof hash differs")
        state = apply(state, raw)
        previous = event["hash"]
    if state is None:
        raise ValueError("Empty acceptance proof")
    require(
        proof["head"] == {"sequence": len(proof["events"]), "hash": previous}
        and state["accepted"] is not None
        and satisfied(state)
        and state["synced"] is None,
        "Incomplete acceptance proof",
    )
    return state


def apply_feedback(native, event):
    """Explicit M5 extension. Called only for a versioned digest-bound proof."""
    data = event["data"]
    f.exact(data, {"acceptance_version", "proof", "proof_sha256", "native_head"})
    require(
        data["acceptance_version"] == VERSION
        and sha(data["proof"]) == data["proof_sha256"],
        "Wrong acceptance proof",
    )
    state = proof_state(data["proof"])
    require(
        state["accepted"]["native_head"] == data["native_head"]
        and data["native_head"]["sequence"] == event["sequence"] - 1
        and data["native_head"]["hash"] == event["previous"],
        "Stale acceptance/native head",
    )
    s = state["submission"]
    require(
        native["controller_version"] == f.VERSION
        and native["anchor"] == state["anchor"]
        and native["status"] == "REVIEW_PENDING"
        and not native["pending"]
        and not native["review_pending"]
        and not f.accounting(native)["unknown"],
        "Feedback hold",
    )
    require(
        f.binding(native["packet"]) == s["task"]
        and native["attempts"][-1]["id"] == s["worker_dispatch_id"]
        and {k: native["attempts"][-1][k] for k in ("actor", "model_family", "tier")}
        == s["worker"],
        "Wrong native task/result/actor",
    )
    for review in state["reviews"]:
        attempt = next(
            (a for a in native["review_attempts"] if a["id"] == review["review_id"]),
            None,
        )
        if attempt is None or attempt["result"] is None:
            raise ValueError("Missing native reviewer reservation/settlement")
        require(
            {
                "actor": attempt["actor"],
                "tier": attempt["tier"],
                "model_family": attempt["model_family"],
            }
            == review["reviewer"]
            and attempt["result"] is not None,
            "Missing native reviewer reservation/settlement",
        )
        if review["report"]:
            require(
                attempt["result"]["evidence"]
                == ["acceptance-report:" + sha(review["report"])],
                "Review report/native evidence differs",
            )
    decision = {
        "review_id": data["proof_sha256"],
        "verdict": "APPROVE",
        "reviewer": {
            "actor": state["controller"],
            "model_family": "independent-acceptance",
            "tier": 0,
        },
        "summary": "All exact-bound independent acceptance gates passed.",
        "evidence": ["acceptance-proof:" + data["proof_sha256"]],
        "contract_failures": [],
        "acceptance_reference": stream_name(state["task_stream"]),
        "binding": {k: s["task"][k] for k in ("task_id", "revision", "contract_hash")},
        "result_dispatch_id": s["worker_dispatch_id"],
    }
    result = copy.deepcopy(native)
    f.apply_review(result, decision, event["timestamp"])
    return result


def _sync_feedback(journal, task_stream):
    state, head = load(journal, task_stream)
    if state["synced"]:
        events, _ = journal.read(task_stream)
        require(
            any(
                e["kind"] == "REVIEW"
                and e["data"].get("proof_sha256") == state["synced"]["proof_sha256"]
                for e in events
            ),
            "Sync receipt missing",
        )
        return state["synced"]
    state, head, native, native_head = current(journal, task_stream)
    if state["synced"]:
        return _sync_feedback(journal, task_stream)
    require(
        state["accepted"] is not None
        and state["accepted"]["native_head"] == asdict(native_head),
        "Acceptance stale or incomplete",
    )
    events, proof_head = journal.read(stream_name(task_stream))
    if proof_head != head:
        latest, _ = load(journal, task_stream)
        if latest["synced"]:
            return _sync_feedback(journal, task_stream)
        raise ValueError("Stale acceptance proof head")
    proof = {"events": events, "head": asdict(head)}
    data = {
        "acceptance_version": VERSION,
        "proof": proof,
        "proof_sha256": sha(proof),
        "native_head": asdict(native_head),
    }
    receipt = {"proof_sha256": sha(proof), "task_head": asdict(native_head)}
    timestamp = f.wp.now()
    try:
        journal.append_many(
            (
                ws.Append(
                    stream=task_stream,
                    kind="REVIEW",
                    data=data,
                    expected=native_head,
                    reducer=f.reducer(native_head),
                    timestamp=timestamp,
                ),
                ws.Append(
                    stream=stream_name(task_stream),
                    kind="SYNC",
                    data=receipt,
                    expected=head,
                    reducer=apply,
                    timestamp=timestamp,
                ),
            )
        )
    except ValueError:
        latest, _ = load(journal, task_stream)
        if latest["synced"] != receipt:
            raise
    return receipt


def sync_feedback(journal, task_stream):
    try:
        return _sync_feedback(journal, task_stream)
    except ValueError:
        # Another identical synchronizer may commit between any two read
        # snapshots, including before current() obtains the native task head.
        latest, _ = load(journal, task_stream)
        if latest["synced"]:
            return _sync_feedback(journal, task_stream)
        raise


def summary(state):
    return {
        "task_stream": state["task_stream"],
        "submission_sha256": sha(state["submission"]),
        "gates": state["gates"],
        "deterministic": deterministic(state),
        "unverified": [
            v["id"] for v in state["contract"]["validation"] if "command" not in v
        ],
        "pending_review": state["pending"],
        "review_attempts_in_acceptance": len(state["reviews"]),
        "accepted": state["accepted"] is not None,
        "synchronized": state["synced"] is not None,
        "generation": state["generation"],
    }


def main(argv=None):
    import argparse
    from scripts import acceptance_runtime as isolated

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=h.ROOT)
    parser.add_argument(
        "--config", type=Path, default=h.ROOT / "config/acceptance.json"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-config")
    for command in (
        "status",
        "init",
        "resubmit",
        "prepare-check",
        "launch-check",
        "ingest-check",
        "prepare-review",
        "ingest-review",
        "abandon-review",
        "reconcile-check",
        "decide",
        "accept",
        "sync-feedback",
    ):
        p = commands.add_parser(command)
        p.add_argument("task_stream")
        if command in {"init", "resubmit"}:
            for key in ("worker", "reference", "feature", "ui", "base", "image"):
                p.add_argument("--" + key, required=True)
            if command == "init":
                p.add_argument("--controller", required=True)
                p.add_argument("--architect", required=True)
        if command == "prepare-check":
            p.add_argument("--validation-id", required=True)
        if command in {"launch-check", "ingest-check"}:
            p.add_argument("--run-id", required=True)
        if command == "prepare-review":
            p.add_argument(
                "--gate", choices=["model_review", "architect_review"], required=True
            )
            p.add_argument("--router-config", type=Path, required=True)
            p.add_argument("--options", type=Path, required=True)
        if command == "ingest-review":
            p.add_argument("--report", type=Path, required=True)
        if command in {"abandon-review", "reconcile-check", "decide"}:
            p.add_argument("--reason", required=True)
        if command == "reconcile-check":
            p.add_argument("--stop", action="store_true")
        if command in {"decide", "accept"}:
            p.add_argument("--actor", required=True)
        if command == "decide":
            p.add_argument("--decision", choices=["approve", "reject"], required=True)
    args = parser.parse_args(argv)
    try:
        config = config_valid(h.parse(h.read_file(args.config, h.MAX_FILE), h.MAX_FILE))
        if args.command == "validate-config":
            print(
                "Acceptance configuration valid; resources remain subject to ACTIVE policy."
            )
            return 0
        journal = ws.Journal(args.root)
        task = args.task_stream
        result = None
        if args.command in {"init", "resubmit"}:
            bindings = {
                "reference": args.reference,
                "commits": {"feature": args.feature, "ui": args.ui, "base": args.base},
                "image": args.image,
            }
            if args.command == "init":
                initialize(
                    journal,
                    task,
                    args.worker,
                    config,
                    args.controller,
                    args.architect,
                    **bindings,
                )
            else:
                resubmit(journal, task, args.worker, **bindings)
        elif args.command == "prepare-check":
            result = {
                "run_id": isolated.prepare_check(journal, task, args.validation_id),
                "started": False,
            }
        elif args.command == "launch-check":
            result = isolated.launch_check(journal, task, args.run_id)
        elif args.command == "ingest-check":
            result = isolated.ingest_check(journal, task, args.run_id)
        elif args.command == "prepare-review":
            result = prepare_review(
                journal,
                task,
                h.parse(h.read_file(args.router_config, h.MAX_FILE), h.MAX_FILE),
                h.parse(h.read_file(args.options, h.MAX_FILE), h.MAX_FILE),
                args.gate,
            )
        elif args.command == "ingest-review":
            state, _ = load(journal, task)
            bound = state["config"]["policy"]["review_report_max_bytes"]
            result = ingest_review(
                journal, task, h.parse(h.read_file(args.report, bound), bound)
            )
        elif args.command == "abandon-review":
            abandon_review(journal, task, args.reason)
        elif args.command == "reconcile-check":
            isolated.reconcile_check(journal, task, args.reason, stop=args.stop)
        elif args.command == "decide":
            state, head, native, _ = current(journal, task)
            require(not native["review_pending"], "Reviewer pending")
            append(
                journal,
                task,
                "DECISION",
                {
                    "actor": args.actor,
                    "decision": args.decision,
                    "reason": args.reason,
                    "submission_sha256": sha(state["submission"]),
                },
                expected=head,
            )
        elif args.command == "accept":
            accept(journal, task, args.actor)
        elif args.command == "sync-feedback":
            result = sync_feedback(journal, task)
        if result is None:
            result = summary(load(journal, task)[0])
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError):
        print(
            "Acceptance refused; inspect preserved coordinator state. No retry or acceptance authorized.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    from scripts import cli_exit

    raise SystemExit(cli_exit.run(main))
