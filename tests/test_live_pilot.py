"""Live-pilot boundaries with fake transport; no paid calls or historical state."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from scripts import dispatch_state as ds
from scripts import execution_harness as h
from scripts import openai_transport as provider
from scripts import pilot_authority as authority
from scripts import pilot_controller as pilot
from scripts import pilot_delivery as delivery
from scripts import pilot_state
from scripts import workflow_budget as budget
from scripts import workflow_state as ws
from scripts.workflow_scope import SessionScope

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return (
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "pilot checkout"
    git(ROOT, "clone", "--no-hardlinks", "--quiet", str(ROOT), str(root))
    git(root, "checkout", "-b", "feature/pilot-test")
    for name in ("scripts", "contracts", "config", "tools"):
        for path in (ROOT / name).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json"}:
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    shutil.copyfile(
        ROOT / "tests/pilot_shell_checks.py", root / "tests/pilot_shell_checks.py"
    )
    git(
        root,
        "add",
        "scripts",
        "contracts",
        "config",
        "tools",
        "tests/pilot_shell_checks.py",
    )
    git(
        root,
        "-c",
        "user.name=Pilot fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-qm",
        "Fixture pilot",
    )
    return root


def approve(root):
    git(
        root,
        "remote",
        "set-url",
        "origin",
        "https://github.com/henslewm/ai-template-oop.git",
    )
    journal = ws.Journal(root)
    commit = git(root, "rev-parse", "HEAD")
    body = {
        "version": "live-pilot-1",
        "approved_by": "Winston",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "foundation": ws.active_anchor(root),
        "identity": journal.identity,
        "implementation_commit": commit,
        "implementation": authority.inventory(root, commit),
        "review": {
            "head": commit,
            "actor": "Fixture independent reviewer",
            "verdict": "APPROVE",
            "report_sha256": "a" * 64,
            "pr": 1,
        },
        "image": authority.IMAGE,
        "read_paths": authority.READ_PATHS,
        "write_paths": authority.WRITE_PATHS,
        "provider": authority.PROVIDER,
        "limits": authority.LIMITS,
        "project": authority.PROJECT,
        "objective": authority.OBJECTIVE,
        "delivery": {
            "repository": "henslewm/ai-template-oop",
            "base": "main",
            "publish": True,
            "merge_after_gates": True,
            "retain_branches": True,
        },
    }
    target = journal.directory / authority.PROFILE
    target.parent.mkdir(parents=True)
    target.write_bytes(authority.profile_bytes({**body, "fingerprint": h.sha(body)}))
    return authority.load_profile(root)


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def send(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def response(text="{}", *, model="gpt-6-luna", status="completed"):
    return {
        "id": "resp_fixture",
        "model": model,
        "status": status,
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 50,
            "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 0},
        },
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": text}]}
        ],
    }


@pytest.fixture
def service(checkout, monkeypatch):
    profile = approve(checkout)
    operator = pilot.Operator(checkout, transport=FakeTransport(response()))
    operator.journal.initialize()
    operator._initialize(profile, operator.journal.verify())
    monkeypatch.setattr(pilot.Operator, "_prerequisites", lambda self: None)
    return operator


def test_default_disabled_and_inspection_has_no_side_effects(checkout):
    transport = FakeTransport(error=AssertionError("paid call"))
    operator = pilot.Operator(checkout, transport=transport)
    assert operator.status().progress == "NOT_STARTED"
    assert operator.resume().progress == "NOT_STARTED"
    assert not operator.journal.directory.exists()
    with pytest.raises(ValueError, match="approval missing"):
        operator.start(authority.OBJECTIVE)
    assert not transport.calls


def test_approval_isolation_and_immutable_controller(service):
    scope = service.state()["scope"]
    for path in (
        "scripts/pilot_controller.py",
        "scripts/openai_transport.py",
        "config/workflow-bootstrap.json",
        "../outside",
    ):
        with pytest.raises(ValueError):
            SessionScope.load(
                {
                    **scope,
                    "write_paths": [path],
                    "read_paths": [*scope["read_paths"], path],
                }
            )
    (service.root / "scripts/openai_transport.py").write_text("changed\n")
    with pytest.raises(ValueError, match="implementation differs"):
        authority.load_profile(service.root)


def test_profile_cannot_move_to_another_checkout(service, tmp_path):
    other = tmp_path / "other"
    git(service.root, "clone", "--quiet", str(service.root), str(other))
    journal = ws.Journal(other)
    target = journal.directory / authority.PROFILE
    target.parent.mkdir(parents=True)
    target.write_bytes((service.journal.directory / authority.PROFILE).read_bytes())
    with pytest.raises(ValueError, match="different checkout"):
        authority.load_profile(other)


def test_usage_rates_cache_and_request_contract():
    request = provider.request_for("gpt-6-luna", "bounded", pilot.WORKER_SCHEMA)
    assert request["store"] is False and request["max_output_tokens"] == 8192
    assert "tools" not in request and request["reasoning"] == {"effort": "medium"}
    usage, cost = provider.usage_cost(
        response(), "gpt-6-luna", provider.RATES["gpt-6-luna"]
    )
    assert cost == 0.000116 and usage["cached_input_tokens"] == 100
    raw = response()
    raw["usage"]["input_tokens_details"]["cache_write_tokens"] = 200
    assert (
        provider.usage_cost(raw, "gpt-6-luna", provider.RATES["gpt-6-luna"])[1]
        == 0.000121
    )
    assert provider.ceiling(request, provider.RATES["gpt-6-luna"]) > cost
    for value in (True, -1, 2.5):
        raw["usage"]["output_tokens"] = value
        with pytest.raises(ValueError):
            provider.usage_cost(raw, "gpt-6-luna", provider.RATES["gpt-6-luna"])


def test_known_usage_settles_before_invalid_output(service):
    raw, attempt = service._paid("worker", "fixture prompt", pilot.WORKER_SCHEMA)
    service._worker_result(raw, attempt)
    assert service.state()["phase"] == "READY"
    assert service.status().settled_usd == 0.000116
    assert service.status().failed_attempt_usd == 0.000116
    assert service.status().liability_usd == 0
    assert len(service.state()["attempts"]) == 1
    record, _ = service.journal.replay(pilot._dispatch(attempt["id"]), ds.apply)
    assert record["response"]["usage"]["provider_response_id"] == "resp_fixture"


@pytest.mark.parametrize("error", [TimeoutError("ambiguous"), KeyboardInterrupt()])
def test_ambiguous_request_cannot_resend_or_reset(service, error):
    service.transport = FakeTransport(error=error)
    if isinstance(error, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    else:
        assert service._paid("worker", "fixture", pilot.WORKER_SCHEMA)[0] is None
    restarted = pilot.Operator(
        service.root, transport=FakeTransport(error=AssertionError("resent"))
    )
    before = restarted.journal.verify()
    assert restarted.status().liability_usd > 0
    assert "unknown" in " ".join(restarted.status().blockers)
    restarted.resume()
    assert restarted.journal.verify() == before
    if isinstance(error, KeyboardInterrupt):
        with pytest.raises(ValueError, match="never resend"):
            restarted.resume(run=True)
    else:
        restarted.resume(run=True)
    assert not restarted.transport.calls
    assert len(restarted.state()["attempts"]) == 1


def test_cumulative_and_shared_task_budgets(service):
    for stream in (pilot.TASK_BUDGET, pilot.PROJECT_BUDGET):
        state, head = service.journal.replay(stream, budget.apply)
        for n in range(5 if stream == pilot.PROJECT_BUDGET else 1):
            ident = h.sha([stream, n])
            service.journal.append(
                stream,
                "RESERVE",
                {
                    "dispatch_id": ident,
                    "task_id": "prior-task",
                    "role": "worker",
                    "ceiling": 1,
                    "metered": True,
                },
                expected=head,
                reducer=budget.apply,
            )
            service.journal.append(
                stream,
                "RESULT",
                {"dispatch_id": ident, "settled": 1, "liability": 0, "unknown": False},
                expected=service.journal.read(stream)[1],
                reducer=budget.apply,
            )
            head = service.journal.read(stream)[1]
    with pytest.raises(ValueError, match="Budget cap"):
        service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    assert not service.transport.calls
    assert not service.state()["attempts"]


def test_concurrent_starts_consume_at_most_one_request(service):
    barrier = threading.Barrier(2)
    original = provider.request_for

    def request(*args):
        barrier.wait(timeout=10)
        return original(*args)

    from unittest.mock import patch

    def run():
        try:
            return service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
        except ValueError:
            return None

    with (
        patch.object(provider, "request_for", request),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        list(pool.map(lambda _: run(), range(2)))
    assert len(service.transport.calls) == 1
    assert len(service.state()["attempts"]) == 1


def test_review_cannot_accept_implementer_or_different_bundle(service):
    from scripts.acceptance import pilot_review

    state = service.state()
    state["attempts"] = [{"actor": pilot.WORKER_ACTOR}]
    state["bundle"] = {"fixture": True}
    state["checks"] = {"checks": [{"passed": True}]}
    report = {
        "verdict": "APPROVE",
        "summary": "fixture",
        "bundle_sha256": h.sha(state["bundle"]),
        "criteria": [
            {"id": c["id"], "met": True, "reason": "fixture"}
            for c in h.f.wp.current(state["packet"])["contract"]["acceptance_criteria"]
        ],
    }
    attempt = {"role": "reviewer", "model": "gpt-6.1-sol", "actor": pilot.WORKER_ACTOR}
    with pytest.raises(ValueError, match="independent"):
        pilot_review(state, report, attempt)
    attempt["actor"] = pilot.REVIEW_ACTOR
    pilot_review(state, report, attempt)
    report["bundle_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="different candidate"):
        pilot_review(state, report, attempt)


def test_candidate_only_changes_accepted_files_and_delivery_is_idempotent(service):
    state = service.state()
    scope = SessionScope.load(state["scope"])
    state["bundle"] = {
        "scope_sha256": scope.hash,
        "base_commit": scope.data["base_commit"],
        "changes": [
            {
                "path": "README.md",
                "before_sha256": h.digest((service.root / "README.md").read_bytes()),
                "content_base64": "dGVzdAo=",
            }
        ],
    }
    commit = delivery.candidate(service.root, state)
    delivery.verify_candidate(service.root, state, commit)
    assert (
        git(service.root, "diff", "--name-only", scope.data["base_commit"], commit)
        == "README.md"
    )
    assert not git(service.root, "status", "--porcelain")
    before = pilot_state.apply(
        None,
        {
            "kind": "INIT",
            "data": {
                k: state[k]
                for k in (
                    "version",
                    "profile",
                    "packet",
                    "scope",
                    "objective",
                    "baseline",
                )
            },
        },
    )
    before["phase"] = "ACCEPTED"
    before["blocker"] = "old delivery hold"
    data = {"commit": commit}
    once = pilot_state.apply(before, {"kind": "DELIVERY", "data": data})
    assert once["blocker"] is None
    assert pilot_state.apply(once, {"kind": "DELIVERY", "data": data}) == once
    with pytest.raises(ValueError, match="duplicate delivery"):
        pilot_state.apply(once, {"kind": "DELIVERY", "data": {"commit": "b" * 40}})


def test_scoped_replacements_reject_self_modification_before_docker(service):
    text = json.dumps(
        {
            "outcome": "IMPLEMENTED",
            "summary": "escape",
            "replacements": [
                {"path": "scripts/openai_transport.py", "content": "escape"}
            ],
        }
    )
    service.transport = FakeTransport(response(text))
    raw, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    service._worker_result(raw, attempt)
    assert service.state()["phase"] == "READY"
    assert not (service.journal.directory / "ownership.sqlite3").exists()


def test_lifetime_attempts_are_bounded(service):
    for model in ("gpt-6-luna", "gpt-6.1-sol"):
        service.transport = FakeTransport(response(model=model))
        raw, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
        assert attempt["model"] == model
        service._worker_result(raw, attempt)
    assert service.state()["phase"] == "HELD"
    with pytest.raises(ValueError):
        service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    assert len(service.state()["attempts"]) == 2


def test_repair_keeps_unchanged_prior_candidate_files(service, monkeypatch):
    state = service.state()
    scope = SessionScope.load(state["scope"])
    prior = {
        "scope_sha256": scope.hash,
        "base_commit": scope.data["base_commit"],
        "changes": [
            {
                "path": "README.md",
                "before_sha256": state["baseline"]["README.md"],
                "content_base64": "cHJpb3IK",
            }
        ],
    }
    state["attempts"] = [{"result": {"bundle": prior}}, {"id": h.sha("repair")}]
    monkeypatch.setattr(service, "state", lambda: state)
    captured = []
    monkeypatch.setattr(
        service,
        "_sandbox_worker",
        lambda scope, packet, proposal, attempt: captured.append(proposal),
    )
    raw = response(
        json.dumps(
            {
                "outcome": "IMPLEMENTED",
                "summary": "one file repair",
                "replacements": [
                    {"path": "scripts/operator_cli.py", "content": "repair\n"}
                ],
            }
        )
    )
    service._worker_result(raw, state["attempts"][-1])
    assert {item["path"]: item["content"] for item in captured[0]["replacements"]} == {
        "README.md": "prior\n",
        "scripts/operator_cli.py": "repair\n",
    }


def test_missing_cache_usage_keeps_liability(service):
    raw = response()
    del raw["usage"]["input_tokens_details"]["cache_write_tokens"]
    service.transport = FakeTransport(raw)
    with pytest.raises(ValueError, match="cache breakdown"):
        service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    assert service.status().settled_usd == 0
    assert service.status().liability_usd > 0
    assert service.state()["phase"] == "HELD"


def test_new_scope_file_cannot_change_after_request(service):
    raw, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    (service.root / "start.ps1").write_text("user work\n")
    raw["output"][0]["content"][0]["text"] = json.dumps(
        {
            "outcome": "IMPLEMENTED",
            "summary": "fixture",
            "replacements": [{"path": "start.ps1", "content": "replacement"}],
        }
    )
    service._worker_result(raw, attempt)
    assert service.state()["phase"] == "READY"
    assert "changed since export" in service.state()["attempts"][-1]["result"]["reason"]
    assert (service.root / "start.ps1").read_text() == "user work\n"


def test_saved_response_resume_does_not_resend(service, monkeypatch):
    raw, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    restarted = pilot.Operator(
        service.root, transport=FakeTransport(error=AssertionError("resent"))
    )
    assert restarted._saved_response(attempt) == raw
    assert not restarted.transport.calls
    assert len(restarted.state()["attempts"]) == 1


def test_origin_change_is_refused_before_any_delivery(service):
    git(
        service.root,
        "remote",
        "set-url",
        "origin",
        "https://example.invalid/unauthorized.git",
    )
    with pytest.raises(ValueError, match="approved delivery repository"):
        authority.load_profile(service.root)


def test_saved_over_ceiling_response_remains_held_after_interruption(
    service, monkeypatch
):
    raw = response()
    raw["usage"]["output_tokens"] = 8193
    service.transport = FakeTransport(raw)
    with monkeypatch.context() as patch:

        def interrupted(*args, **kwargs):
            raise KeyboardInterrupt()

        patch.setattr(service, "event", interrupted)
        with pytest.raises(KeyboardInterrupt):
            service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    attempt = service.state()["attempts"][-1]
    with pytest.raises(ValueError, match="approved ceiling"):
        service._saved_response(attempt)
    assert service.state()["phase"] == "HELD"
    assert service.status().liability_usd == 0


def test_hosting_history_holds_are_shared():
    from scripts import workflow_closeout as c

    live = {
        "reviews": [],
        "comments": [
            {
                "user": {"login": "chatgpt-codex-connector[bot]"},
                "body": "codex-pull-request-review-summary",
                "created_at": "a",
                "updated_at": "b",
            }
        ],
        "unresolved": 0,
        "more_threads": False,
    }
    assert "AUTOMATED_REVIEW_HISTORY_UNVERIFIABLE" in c.review_history(live)["blockers"]


def test_deleted_delivery_branch_prevents_merged_receipt(monkeypatch):
    head = "a" * 40
    pull = {
        "merged": True,
        "head": {
            "sha": head,
            "ref": delivery.BRANCH,
            "repo": {"full_name": "henslewm/ai-template-oop"},
        },
        "base": {"ref": "main", "repo": {"full_name": "henslewm/ai-template-oop"}},
        "merge_commit_sha": "b" * 40,
    }
    monkeypatch.setattr(delivery.closeout, "gh", lambda endpoint: pull)
    monkeypatch.setattr(delivery, "_git", lambda *args, **kwargs: b"")
    monkeypatch.setattr(
        delivery.closeout,
        "hosting",
        lambda *args: {"unresolved": 0, "more_threads": False},
    )
    monkeypatch.setattr(delivery, "_hosting_holds", lambda *args: [])
    monkeypatch.setattr(delivery, "retained", lambda root: {"local": {}, "origin": {}})
    with pytest.raises(ValueError, match="not retained"):
        delivery.verify_merged(
            ROOT,
            1,
            head,
            {},
            review={
                "head": head,
                "actor": "Independent",
                "verdict": "APPROVE",
                "blocking_findings": [],
                "report_sha256": "f" * 64,
            },
        )


def test_pilot_review_policy_requires_exact_independent_evidence(monkeypatch):
    head = "a" * 40
    live = {
        "head": head,
        "base": "b" * 40,
        "repository": "henslewm/ai-template-oop",
        "head_repository": "henslewm/ai-template-oop",
        "base_repository": "henslewm/ai-template-oop",
        "branch": delivery.BRANCH,
        "base_branch": "main",
        "delete_branch_on_merge": False,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "required_policy": "NONE_CONFIGURED",
        "required": [],
        "statuses": [],
        "checks": [],
        "unsupported_rules": [],
        "unresolved": 0,
        "more_threads": False,
        "reviews": [],
        "comments": [
            {
                "user": {"login": "chatgpt-codex-connector[bot]"},
                "body": "codex-pull-request-review-summary",
            }
        ],
        "remote_branches": {delivery.BRANCH: head, "main": "b" * 40},
    }
    monkeypatch.setattr(
        delivery.closeout, "hosting", lambda *args: json.loads(json.dumps(live))
    )
    monkeypatch.setattr(
        delivery,
        "retained",
        lambda root: {
            "local": {delivery.BRANCH: head},
            "origin": {delivery.BRANCH: head},
        },
    )
    monkeypatch.setattr(delivery, "_git", lambda *args, **kwargs: b"")
    proof = {
        "head": head,
        "actor": "Independent",
        "verdict": "APPROVE",
        "blocking_findings": [],
        "report_sha256": "f" * 64,
    }
    assert "INDEPENDENT_EXACT_REVIEW_REQUIRED" in delivery.gates(ROOT, 1, head, {})[0]
    blockers, observed = delivery.gates(ROOT, 1, head, {}, review=proof)
    assert blockers == []
    assert observed["automated_review_history"] == "UNVERIFIED"
    monkeypatch.setattr(
        delivery.closeout,
        "gh",
        lambda endpoint: {
            "merged": True,
            "head": {
                "sha": head,
                "ref": delivery.BRANCH,
                "repo": {"full_name": "henslewm/ai-template-oop"},
            },
            "base": {"ref": "main", "repo": {"full_name": "henslewm/ai-template-oop"}},
            "merge_commit_sha": "b" * 40,
        },
    )
    delivery.verify_merged(ROOT, 1, head, {}, review=proof)
    for invalid in (
        {**proof, "head": "c" * 40},
        {**proof, "implementer": "Independent"},
        {**proof, "report_sha256": None},
    ):
        assert (
            "INDEPENDENT_EXACT_REVIEW_REQUIRED"
            in delivery.gates(ROOT, 1, head, {}, review=invalid)[0]
        )
    live["checks"] = [
        {
            "id": 1,
            "name": "CI",
            "app": {"id": 1},
            "head_sha": head,
            "status": "completed",
            "conclusion": "failure",
        }
    ]
    assert (
        "HOSTING_CHECK_PENDING_OR_FAILED"
        in delivery.gates(ROOT, 1, head, {}, review=proof)[0]
    )
    with pytest.raises(ValueError, match="unresolved check or review-history"):
        delivery.verify_merged(ROOT, 1, head, {}, review=proof)
    live["checks"] = []
    for status in ("pending", "failure", "error"):
        live["statuses"] = [{"id": 1, "context": "legacy CI", "state": status}]
        assert (
            "HOSTING_STATUS_PENDING_OR_FAILED"
            in delivery.gates(ROOT, 1, head, {}, review=proof)[0]
        )
        with pytest.raises(ValueError, match="unresolved check or review-history"):
            delivery.verify_merged(ROOT, 1, head, {}, review=proof)
    live["statuses"].append({"id": 2, "context": "legacy CI", "state": "success"})
    assert delivery.gates(ROOT, 1, head, {}, review=proof)[0] == []
    delivery.verify_merged(ROOT, 1, head, {}, review=proof)
    live["statuses"] = []
    live["reviews"] = [
        {"id": 1, "user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED"}
    ]
    assert (
        "OUTSTANDING_CHANGES_REQUESTED"
        in delivery.gates(ROOT, 1, head, {}, review=proof)[0]
    )
    with pytest.raises(ValueError, match="unresolved check or review-history"):
        delivery.verify_merged(ROOT, 1, head, {}, review=proof)
    live["reviews"] = []
    live["unresolved"] = 1
    assert (
        "UNRESOLVED_OR_UNOBSERVED_REVIEW_THREADS"
        in delivery.gates(ROOT, 1, head, {}, review=proof)[0]
    )
    live["unresolved"] = 0
    live["reviews"] = [
        {
            "id": n,
            "user": {"login": "chatgpt-codex-connector[bot]"},
            "commit_id": head,
            "body": "observed round",
            "state": "COMMENTED",
        }
        for n in range(5)
    ]
    assert (
        "REVIEW_ROUND_CAP_EXCEEDED"
        in delivery.gates(ROOT, 1, head, {}, review=proof)[0]
    )


def test_explicit_incomplete_check_reconciliation_preserves_failures(
    service, monkeypatch
):
    from scripts import acceptance_runtime as ar
    from scripts import workflow_runtime as runtime

    state = service.state()
    state["attempts"] = [{"id": h.sha("fixture worker")}]
    scope = SessionScope.load(state["scope"])
    state["bundle"] = {
        "scope_sha256": scope.hash,
        "base_commit": scope.data["base_commit"],
        "changes": [
            {
                "path": "README.md",
                "before_sha256": state["baseline"]["README.md"],
                "content_base64": "dGVzdAo=",
            }
        ],
    }

    def incomplete(*args, run, **kwargs):
        run.mkdir()
        raise KeyboardInterrupt()

    monkeypatch.setattr(runtime, "prepare", incomplete)
    with pytest.raises(KeyboardInterrupt):
        ar.pilot_checks(service.journal, state)
    with pytest.raises(ValueError, match="reconcile-checks"):
        ar.pilot_checks(service.journal, state)
    with pytest.raises(KeyboardInterrupt):
        ar.pilot_checks(service.journal, state, reconcile=True)
    checks = ar.pilot_checks(service.journal, state, reconcile=True)
    assert len(checks["checks"]) == 2
    assert all(not check["passed"] for check in checks["checks"])
    assert ar.pilot_checks(service.journal, state) == checks


def test_explicit_reconciliation_preserves_attempt(service):
    service.transport = FakeTransport(error=TimeoutError("ambiguous"))
    _, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    assert service.state()["phase"] == "HELD"
    service.reconcile_provider(attempt["id"], response())
    assert service.state()["phase"] == "WORKER_RUNNING"
    assert service.status().liability_usd == 0
    assert service.status().settled_usd == 0.000116
    assert len(service.state()["attempts"]) == 1
    assert len(service.transport.calls) == 1


def test_reconciliation_cannot_reopen_settled_intentional_hold(service):
    raw, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    service.event("HOLD", {"reason": "ARCHITECTURE_CONFLICT: owner decision required"})
    before = service.journal.verify()
    with pytest.raises(ValueError, match="intentional review/scope holds"):
        service.reconcile_provider(attempt["id"], raw)
    assert service.journal.verify() == before
    assert service.state()["phase"] == "HELD"


def test_corrected_usage_retains_original_response(service):
    raw = response()
    del raw["usage"]["input_tokens_details"]["cache_write_tokens"]
    service.transport = FakeTransport(raw)
    with pytest.raises(ValueError):
        service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    attempt = service.state()["attempts"][-1]
    original = (
        service.journal.directory / ("run-provider-" + attempt["id"]) / "response.json"
    )
    before = original.read_bytes()
    service.reconcile_provider(attempt["id"], response())
    assert original.read_bytes() == before
    assert service.status().liability_usd == 0
    assert service.status().settled_usd == 0.000116


def test_real_sandbox_stopped_replay_and_independent_rejection(service, monkeypatch):
    if os.environ.get("WORKFLOW_TEST_IMAGE") != authority.IMAGE:
        pytest.skip(
            reason="Exact WORKFLOW_TEST_IMAGE required; skipped Docker is not live pilot proof"
        )
    from scripts import acceptance_runtime as ar
    from scripts import workflow_runtime as runtime

    proposal = {
        "outcome": "IMPLEMENTED",
        "summary": "Fixture verification only",
        "replacements": [{"path": "README.md", "content": "fixture candidate\n"}],
    }
    service.transport = FakeTransport(response(json.dumps(proposal)))
    _, attempt = service._paid("worker", "fixture", pilot.WORKER_SCHEMA)
    state = service.state()
    scope = SessionScope.load(state["scope"])
    before = (service.root / "README.md").read_bytes()
    first = service._sandbox_worker(scope, state["packet"], proposal, attempt)
    assert not first["passed"]
    assert (service.root / "README.md").read_bytes() == before
    again = service._sandbox_worker(scope, state["packet"], proposal, attempt)
    assert again == first
    state["bundle"] = first["bundle"]
    prepare = runtime.prepare

    def interrupt_prepared(*args, **kwargs):
        prepare(*args, **kwargs)
        raise KeyboardInterrupt()

    with monkeypatch.context() as patch:
        patch.setattr(runtime, "prepare", interrupt_prepared)
        with pytest.raises(KeyboardInterrupt):
            ar.pilot_checks(service.journal, state)
    append = service.journal.append

    def interrupt_result(stream, kind, *args, **kwargs):
        if stream.startswith("pilot-check:") and kind == "RESULT":
            raise KeyboardInterrupt()
        return append(stream, kind, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(service.journal, "append", interrupt_result)
        with pytest.raises(KeyboardInterrupt):
            ar.pilot_checks(service.journal, state)
    checks = ar.pilot_checks(service.journal, state)
    assert ar.pilot_checks(service.journal, state) == checks
    assert not all(c["passed"] for c in checks["checks"])
    assert all(c["image"] == authority.IMAGE for c in checks["checks"])
    # Retain evidence; remove only this fixture's own confirmed stopped Docker objects.
    for path in service.journal.directory.glob("run-*/runtime.json"):
        manifest = h.f.wp.read_json(path)
        assert runtime.stopped(manifest["container"])
        assert runtime.stopped(manifest["setup_container"])
        runtime.docker("rm", manifest["container"], manifest["setup_container"])
        runtime.docker("volume", "rm", manifest["volume"])


def test_consumed_unstarted_check_never_passes_after_abandonment(service, monkeypatch):
    if os.environ.get("WORKFLOW_TEST_IMAGE") != authority.IMAGE:
        pytest.skip(
            reason="Exact WORKFLOW_TEST_IMAGE required for interrupted-start proof"
        )
    from scripts import acceptance_runtime as ar
    from scripts import workflow_runtime as runtime

    state = service.state()
    scope = SessionScope.load(state["scope"])
    state["attempts"] = [{"id": h.sha("interrupted-start fixture")}]
    state["bundle"] = {
        "scope_sha256": scope.hash,
        "base_commit": scope.data["base_commit"],
        "changes": [
            {
                "path": "README.md",
                "before_sha256": state["baseline"]["README.md"],
                "content_base64": "dGVzdAo=",
            }
        ],
    }
    docker = runtime.docker

    def interrupt_start(*args, **kwargs):
        if args[0] == "start" and len(args) == 2:
            raise KeyboardInterrupt()
        return docker(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(runtime, "docker", interrupt_start)
        with pytest.raises(KeyboardInterrupt):
            ar.pilot_checks(service.journal, state)
    with pytest.raises(ValueError, match="Consumed check start never executed"):
        ar.pilot_checks(service.journal, state)
    append = service.journal.append

    def interrupt_abandonment(stream, kind, *args, **kwargs):
        if stream.startswith("pilot-check:") and kind == "RESULT":
            raise KeyboardInterrupt()
        return append(stream, kind, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(service.journal, "append", interrupt_abandonment)
        with pytest.raises(KeyboardInterrupt):
            ar.pilot_checks(service.journal, state, reconcile=True)
    checks = ar.pilot_checks(service.journal, state)
    assert not checks["checks"][0]["passed"]
    manifests = [
        h.f.wp.read_json(path)
        for path in service.journal.directory.glob("run-*/runtime.json")
    ]
    assert any(
        runtime.inspect(item["container"])["State"]["Status"] == "created"
        for item in manifests
    )
    for manifest in manifests:
        assert runtime.stopped(manifest["container"])
        assert runtime.stopped(manifest["setup_container"])
        runtime.docker("rm", manifest["container"], manifest["setup_container"])
        runtime.docker("volume", "rm", manifest["volume"])
