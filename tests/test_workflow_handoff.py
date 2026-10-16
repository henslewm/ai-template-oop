"""M6 derived views on disposable actual Journals, Git and ownership stores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import json
import sqlite3
import threading

import pytest

from scripts import workflow_handoff as v
from scripts import execution_harness as h
from scripts import feedback as f
from scripts import worker_launcher as launcher
from test_execution_harness import execution as _execution, prepare
from test_feedback import journal as _journal, options, stamp
from test_acceptance import accepted_candidate as _accepted_candidate
from scripts import acceptance as a
from scripts import acceptance_runtime as ar

journal = _journal
execution = _execution
accepted_candidate = _accepted_candidate


def clean_view(e, **kwargs):
    return v.build(e.journal, e.stream, scope=e.scope.data, **kwargs)


def test_clean_start_has_objective_scope_diff_caps_and_unknown_context(execution):
    e = execution
    before = e.journal.verify()
    view = clean_view(e, audience="worker")
    body = v.verify(e.journal, view)
    assert body["tasks"][0]["objective"]
    assert body["scope"]["scope"]["write_paths"] == ["src/features/auth.py"]
    assert body["scope"]["scope"]["base_commit"] == e.scope.data["base_commit"]
    assert (
        body["scope"]["scope"]["interface_revision"]
        == e.scope.data["interface_revision"]
    )
    assert "diff_sha256" in body["git"]
    assert body["tasks"][0]["attempts_used"] == 0
    assert body["tasks"][0]["attempt_cap"] == 2
    assert view["context"]["measured_tokens"] is None
    assert view["context"]["estimated_input_tokens"] == len(h.json_bytes(view))
    assert len(h.json_bytes(view)) <= 40000
    assert "workspace" not in json.dumps(view)
    assert not v.resume(e.journal, view)["execution_authorized"]
    assert e.journal.verify() == before and not e.docker.starts
    assert not (e.journal.directory / "ownership.sqlite3").exists()


@pytest.mark.parametrize(
    "change", ["task", "file", "index", "ref", "approval", "edit", "time"]
)
def test_stale_view_refuses_without_mutation(execution, change):
    e = execution
    view = clean_view(e)
    if change == "task":
        f.reserve(e.journal, e.stream, e.routing, options(), timestamp=stamp(1))
    elif change == "file":
        (e.scope.root / "src/features/auth.py").write_text("changed")
    elif change == "index":
        v.git(e.scope.root, "add", "config")
    elif change == "ref":
        v.git(e.scope.root, "branch", "feature/retained")
    elif change == "approval":
        e.monkeypatch.setattr(v.ws, "active_anchor", lambda *args: "b" * 64)
    elif change == "edit":
        view["content"]["next_action"] = "LAUNCH"
    else:
        view["created_at"] = (f.instant(v.now()) - timedelta(seconds=400)).isoformat()
        view["expires_at"] = (
            f.instant(view["created_at"]) + timedelta(seconds=300)
        ).isoformat()
    heads = e.journal.verify()
    with pytest.raises(ValueError):
        v.resume(e.journal, view)
    assert e.journal.verify() == heads and not e.docker.starts


def test_prepare_and_consumed_start_interruption_never_restart(execution):
    e = execution
    dispatch = prepare(e)
    view = v.build(e.journal, e.stream)
    assert view["content"]["tasks"][0]["pending_dispatch"] == dispatch["dispatch_id"]
    assert "EXPLICIT_LAUNCH_OR_ABANDON" in v.resume(e.journal, view)["next_action"]
    token = h.load(e.journal, dispatch["dispatch_id"])[0]["prepared"]["runtime"][
        "ownership_token"
    ]
    with h.Ownership(e.journal.directory).transaction() as db:
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    owner = h.Ownership(e.journal.directory)
    with pytest.raises(RuntimeError):
        owner.start(
            token,
            lambda _: (_ for _ in ()).throw(RuntimeError("crash after consumption")),
        )
    before = e.journal.verify()
    interrupted = v.build(e.journal, e.stream)
    assert interrupted["content"]["ownership"][0]["consumed"] == 1
    assert "CONSUMED_START_NEVER_RESTART" in interrupted["content"]["blockers"]
    assert (
        v.resume(e.journal, interrupted)["next_action"]
        == "EXPLICIT_STOP_PRESERVE_RECONCILE"
    )
    with pytest.raises(ValueError):
        v.resume(e.journal, view)
    with pytest.raises(ValueError, match="consumed"):
        launcher.launch(e.journal, dispatch["dispatch_id"])
    assert (
        e.journal.verify() == before
        or h.load(e.journal, dispatch["dispatch_id"])[0]["phase"] == "LAUNCHING"
    )
    assert not e.docker.starts
    assert token not in json.dumps(interrupted)


def test_reservation_before_dispatch_init_is_explicit_abandon(execution):
    e = execution
    f.reserve(e.journal, e.stream, e.routing, options(), timestamp=stamp(1))
    view = clean_view(e)
    assert view["content"]["tasks"][0]["dispatches"][0]["phase"] == "RESERVATION_ONLY"
    assert v.resume(e.journal, view)["next_action"] == "EXPLICIT_WORKER_RECONCILE"
    assert view["content"]["tasks"][0]["attempts_used"] == 1


def test_concurrent_change_during_build_refuses(execution, monkeypatch):
    e = execution
    real = v._observe
    count = 0

    def interleave(*args, **kwargs):
        nonlocal count
        result = real(*args, **kwargs)
        count += 1
        if count == 1:
            f.reserve(e.journal, e.stream, e.routing, options(), timestamp=stamp(1))
        return result

    monkeypatch.setattr(v, "_observe", interleave)
    with pytest.raises(ValueError, match="Concurrent"):
        clean_view(e)
    assert not e.docker.starts


def test_parallel_views_replay_without_writes(execution):
    e = execution
    before = e.journal.verify()
    with ThreadPoolExecutor(2) as pool:
        views = list(pool.map(lambda _: clean_view(e), range(2)))
    assert views[0]["authority_sha256"] == views[1]["authority_sha256"]
    assert all(v.resume(e.journal, x)["execution_authorized"] is False for x in views)
    assert e.journal.verify() == before


def test_pending_and_accepted_check_views_remain_separate(accepted_candidate):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    view = v.build(e.journal, e.stream)
    assert view["content"]["tasks"][0]["acceptance"]["runs"][0]["run_id"] == rid
    assert (
        v.resume(e.journal, view)["next_action"] == "EXPLICIT_CHECK_RECONCILE_OR_INGEST"
    )
    ar.launch_check(e.journal, e.stream, rid)
    ar.ingest_check(e.journal, e.stream, rid)
    a.accept(e.journal, e.stream, "Independent")
    view = v.build(e.journal, e.stream)
    assert (
        v.resume(e.journal, view)["next_action"]
        == "EXPLICIT_ACCEPTANCE_SYNCHRONIZATION"
    )
    a.sync_feedback(e.journal, e.stream)
    view = v.build(e.journal, e.stream)
    assert v.resume(e.journal, view)["next_action"] == "ASSESS_INTEGRATION_READINESS"
    task = view["content"]["tasks"][0]
    assert task["integrated"] == task["deployed"] == "NOT_ESTABLISHED"


def test_missing_context_approval_is_smallest_read_only_revision(execution):
    e = execution
    path = "src/features/auth/helper.py"
    p = e.scope.root / path
    p.parent.mkdir(parents=True)
    p.write_text("def requested_symbol(): pass\n")
    view = clean_view(e)
    requests = [
        {
            "path": path,
            "symbol": "requested_symbol",
            "reason": "Need exact caller signature",
        }
    ]
    proposal = v.propose_context(e.journal, view, requests)
    assert proposal["revised_scope"]["write_paths"] == e.scope.data["write_paths"]
    assert set(proposal["revised_scope"]["read_paths"]) - set(
        e.scope.data["read_paths"]
    ) == {path}
    before = e.journal.verify()
    with pytest.raises(ValueError, match="architect"):
        v.approve_context(e.journal, view, requests, "Implementer")
    assert e.journal.verify() == before
    receipt = v.approve_context(e.journal, view, requests, "Architect")
    heads = e.journal.verify()
    assert v.approve_context(e.journal, view, requests, "Architect") == receipt
    assert e.journal.verify() == heads
    revised = v.context_scope(e.journal, receipt, view)
    assert revised == proposal["revised_scope"]
    assert f.replay(e.journal, e.stream)[0]["attempts"] == []
    p.write_text("changed")
    with pytest.raises(ValueError):
        v.context_scope(e.journal, receipt, view)
    assert not e.docker.starts


def test_context_approval_commit_interruption_replays_receipt(execution, monkeypatch):
    e = execution
    path = e.scope.root / "src/features/auth/needed.py"
    path.parent.mkdir()
    path.write_text("VALUE = 1\n")
    view = clean_view(e)
    requests = [
        {
            "path": "src/features/auth/needed.py",
            "symbol": "VALUE",
            "reason": "Need exact constant",
        }
    ]
    create = e.journal.create

    def interrupted(*args, **kwargs):
        create(*args, **kwargs)
        raise SystemExit(73)

    monkeypatch.setattr(e.journal, "create", interrupted)
    with pytest.raises(SystemExit):
        v.approve_context(e.journal, view, requests, "Architect")
    heads = e.journal.verify()
    receipt = v.approve_context(e.journal, view, requests, "Architect")
    assert (
        v.context_scope(e.journal, receipt, view)["write_paths"]
        == e.scope.data["write_paths"]
    )
    assert e.journal.verify() == heads and not e.docker.starts


def test_startup_includes_prepared_task_owned_paths(execution):
    e = execution
    prepare(e)
    view = v.build(e.journal, audience="startup")
    task = view["content"]["tasks"][0]
    assert task["owned_scope"]["write_paths"] == e.scope.data["write_paths"]
    assert task["owned_scope"]["base_commit"] == e.scope.data["base_commit"]
    assert (
        task["owned_scope"]["interface_revision"] == e.scope.data["interface_revision"]
    )


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "src/ui/mocks.py",
        "contracts/auth.py",
        "src/features/auth.py",
        ".git/config",
        "src/features/auth/*",
    ],
)
def test_missing_context_cannot_widen_writes_interfaces_or_siblings(execution, path):
    e = execution
    before = e.journal.verify()
    with pytest.raises(ValueError):
        v.propose_context(
            e.journal,
            clean_view(e),
            [{"path": path, "symbol": "symbol", "reason": "need"}],
        )
    assert e.journal.verify() == before


def test_unknown_liability_and_missing_start_history_fail_closed(execution):
    e = execution
    prepared = prepare(e)
    path = e.journal.directory / "startup.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM startup_authority")
    with pytest.raises(ValueError, match="history"):
        v.build(e.journal, e.stream)
    assert h.load(e.journal, prepared["dispatch_id"])[0]["phase"] == "PREPARED"


def test_bounded_context_refusal_preserves_state(execution):
    e = execution
    e.monkeypatch.setattr(v, "MAX_VIEW", 10)
    before = e.journal.verify()
    with pytest.raises(ValueError, match="Context limit"):
        clean_view(e)
    assert before == e.journal.verify()


@pytest.mark.parametrize(
    "key,value",
    [
        ("measurement", "measured"),
        ("measured_tokens", 0),
        ("estimated_input_tokens", 0),
        ("provider_usage", "measured"),
    ],
)
def test_edited_context_measurements_are_refused(execution, key, value):
    e = execution
    view = clean_view(e)
    view["context"][key] = value
    with pytest.raises(ValueError, match="context"):
        v.verify(e.journal, view)


def test_context_approval_race_replays_one_receipt(execution, monkeypatch):
    e = execution
    helper = e.scope.root / "src/features/auth/helper.py"
    helper.parent.mkdir()
    helper.write_text("VALUE = 1\n")
    view = clean_view(e)
    requests = [
        {
            "path": "src/features/auth/helper.py",
            "symbol": "VALUE",
            "reason": "Needed constant",
        }
    ]
    create = e.journal.create
    barrier = threading.Barrier(2)

    def collide(*args, **kwargs):
        barrier.wait(timeout=30)
        return create(*args, **kwargs)

    monkeypatch.setattr(e.journal, "create", collide)
    with ThreadPoolExecutor(2) as pool:
        receipts = list(
            pool.map(
                lambda _: v.approve_context(
                    e.journal, view, copy.deepcopy(requests), "Architect"
                ),
                range(2),
            )
        )
    assert receipts[0] == receipts[1]
    assert len([s for s in e.journal.verify() if s.startswith("context:")]) == 1
    assert f.replay(e.journal, e.stream)[0]["attempts"] == []


def test_shared_coordinator_uses_saved_worker_workspace_for_context(
    execution, tmp_path
):
    e = execution
    helper = e.scope.root / "src/features/auth/helper.py"
    helper.parent.mkdir()
    helper.write_text("EXACT_WORKER_SYMBOL = 1\n")
    prepare(e)
    sibling = tmp_path / "coordinator"
    v.git(e.journal.root, "worktree", "add", "-b", "feature/coordinator", str(sibling))
    coordinator = v.ws.Journal(sibling)
    assert coordinator.directory == e.journal.directory
    view = v.build(coordinator, e.stream)
    requests = [
        {
            "path": "src/features/auth/helper.py",
            "symbol": "EXACT_WORKER_SYMBOL",
            "reason": "Worker-owned context only",
        }
    ]
    proposal = v.propose_context(coordinator, view, requests)
    assert proposal["revised_scope"]["workspace"] == str(e.scope.root)
    receipt = v.approve_context(coordinator, view, requests, "Architect")
    assert v.context_scope(coordinator, receipt, view) == proposal["revised_scope"]
    assert not (sibling / "src/features/auth/helper.py").exists()
    assert not e.docker.starts
