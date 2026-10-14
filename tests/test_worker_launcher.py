"""M4 launch/preflight/recovery races, tampering and consumed-start crashes."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from scripts import execution_harness as h
from scripts import worker_launcher as launcher
from scripts import workflow_runtime as runtime
from test_execution_harness import execution as _execution
from test_execution_harness import prepare
from test_feedback import journal as _journal
from test_feedback import stamp

execution = _execution
journal = _journal


def test_concurrent_dispatch_one_whole_reservation(execution):
    e = execution
    barrier = Barrier(2)
    original = h.f.reserve

    def reserve(*args, **kwargs):
        barrier.wait(timeout=10)
        return original(*args, **kwargs)

    e.monkeypatch.setattr(h.f, "reserve", reserve)

    def contender(_):
        try:
            return prepare(e)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contender, range(2)))
    assert sum(x is not None for x in outcomes) == 1
    assert len(h.f.replay(e.journal, e.stream)[0]["attempts"]) == 1
    assert not e.docker.starts


def test_concurrent_launcher_starts_once_and_never_revives_consumed_authority(
    execution,
):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    barrier = Barrier(2)
    original = launcher.prepared_run

    def checked(*args, **kwargs):
        result = original(*args, **kwargs)
        if not kwargs.get("launching"):
            barrier.wait(timeout=15)
        return result

    e.monkeypatch.setattr(launcher, "prepared_run", checked)

    def contender(_):
        try:
            return launcher.launch(e.journal, dispatch_id)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contender, range(2)))
    assert sum(x is not None for x in outcomes) == 1
    assert len(e.docker.starts) == 1
    token = h.load(e.journal, dispatch_id)[0]["prepared"]["runtime"]["ownership_token"]
    assert launcher.startup_attempted(e.journal, token) == 1
    with pytest.raises(ValueError):
        launcher.launch(e.journal, dispatch_id)


@pytest.mark.parametrize(
    "timeout", [0, -1, 301, float("nan"), float("inf"), True, "10"]
)
def test_invalid_operator_timeout_does_not_consume_start(execution, timeout):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    with pytest.raises(ValueError):
        launcher.prepared_run(e.journal, dispatch_id, timeout=timeout)
    assert h.load(e.journal, dispatch_id)[0]["phase"] == "PREPARED"
    assert not e.docker.starts


@pytest.mark.parametrize(
    "filename",
    [
        "brief.json",
        "worker-rules.md",
        "runtime.json",
        "scope.json",
        "input.tar",
        "dispatch.json",
    ],
)
def test_changed_prepared_bytes_refuse_launch(execution, filename):
    e = execution
    prepared = prepare(e)
    (Path(prepared["run"]) / filename).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        launcher.launch(e.journal, prepared["dispatch_id"])
    assert not e.docker.starts


@pytest.mark.parametrize(
    "change",
    [
        "volume",
        "approval",
        "config",
        "deadline",
        "base",
        "interface",
        "report",
        "consumed",
        "lease",
        "account-head",
    ],
)
def test_launch_preflight_binding_negatives(execution, change):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    record, _ = h.load(e.journal, dispatch_id)
    run_dir = h.run_path(e.journal, dispatch_id)
    manifest = record["prepared"]["runtime"]
    kwargs = {}
    if change == "volume":
        e.docker.volumes[manifest["volume"]]["brief.json"] = b"changed volume brief"
    elif change == "approval":
        e.monkeypatch.setattr(
            h.ws,
            "active_anchor",
            lambda *args: (_ for _ in ()).throw(ValueError("Revoked approval")),
        )
    elif change == "config":
        config = copy.deepcopy(e.config)
        config["bindings"][0]["image"] = "sha256:" + "4" * 64
        kwargs["config"] = config
    elif change == "deadline":
        e.monkeypatch.setattr(h.f.wp, "now", lambda: stamp(900))
    elif change == "base":
        import subprocess

        subprocess.run(
            [
                "git",
                "-C",
                str(e.scope.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "New base",
            ],
            check=True,
            capture_output=True,
        )
    elif change == "interface":
        (e.scope.root / "contracts/auth.py").write_bytes(b"new interface")
    elif change == "report":
        (run_dir / "report.json").write_bytes(b"existing report")
    elif change in {"consumed", "lease"}:
        filename = "startup.sqlite3" if change == "consumed" else "ownership.sqlite3"
        with sqlite3.connect(e.journal.directory / filename) as db:
            db.execute(
                "UPDATE startup_authority SET attempted=1"
                if change == "consumed"
                else "UPDATE runs SET expires=0"
            )
    elif change == "account-head":
        account = h.f.accounts(h.f.replay(e.journal, e.stream)[0], "worker")[0]
        e.journal.append(
            account,
            "RESERVE",
            {
                "dispatch_id": "9" * 64,
                "task_id": "OTHER",
                "role": "worker",
                "ceiling": 0,
                "metered": False,
            },
            expected=e.journal.read(account)[1],
            reducer=h.budget.apply,
            timestamp=stamp(9),
        )
    with pytest.raises(ValueError):
        launcher.launch(e.journal, dispatch_id, **kwargs)
    assert not e.docker.starts


def test_expiry_between_preflight_and_consumed_start_holds_without_launch(execution):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    original = launcher.prepared_run

    def checked(*args, **kwargs):
        value = original(*args, **kwargs)
        if kwargs.get("consumed"):
            raise KeyboardInterrupt("Injected crash after consumed-start commit")
        return value

    e.monkeypatch.setattr(launcher, "prepared_run", checked)
    with pytest.raises(KeyboardInterrupt):
        launcher.launch(e.journal, dispatch_id)
    record, _ = h.load(e.journal, dispatch_id)
    assert record["phase"] == "LAUNCHING"
    token = record["prepared"]["runtime"]["ownership_token"]
    assert launcher.startup_attempted(e.journal, token) == 1
    assert not e.docker.starts
    with pytest.raises(ValueError):
        launcher.launch(e.journal, dispatch_id)
    receipt = h.reconcile(
        e.journal,
        e.stream,
        "Injected crash was inspected; the created worker never started and its output is preserved.",
        timestamp=stamp(11),
    )
    assert receipt["status"] == "ABANDONED"
    assert launcher.startup_attempted(e.journal, token) == 1
    assert h.f.replay(e.journal, e.stream)[0]["pending"] is None


def test_ambiguous_start_failure_never_restarts_and_recovery_preserves(execution):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    e.docker.fail_start = True
    with pytest.raises(OSError):
        launcher.launch(e.journal, dispatch_id)
    assert len(e.docker.starts) == 1
    with pytest.raises(ValueError):
        launcher.launch(e.journal, dispatch_id)
    receipt = h.reconcile(
        e.journal,
        e.stream,
        "Ambiguous Docker start failed; inspected the stopped container and preserved exact output.",
        timestamp=stamp(11),
    )
    assert receipt["status"] == "ABANDONED" and len(e.docker.starts) == 1
    assert list(h.run_path(e.journal, dispatch_id).glob("output-*.tar"))


def test_runtime_direct_execute_cannot_bypass_journal_preflight(execution):
    e = execution
    prepared = prepare(e)
    with pytest.raises(ValueError, match="Journal launcher"):
        runtime.execute(Path(prepared["run"]), e.journal.directory, 60)
    assert not e.docker.starts


def test_crash_after_claim_before_manifest_token_preserves_and_abandons(execution):
    e = execution
    original = runtime.Ownership.claim

    def claimed_then_crash(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise KeyboardInterrupt("Injected crash after durable ownership claim")

    e.monkeypatch.setattr(runtime.Ownership, "claim", claimed_then_crash)
    with pytest.raises(KeyboardInterrupt):
        prepare(e)
    state, _, _ = h.f.replay(e.journal, e.stream)
    dispatch_id = state["pending"]
    record, _ = h.load(e.journal, dispatch_id)
    assert record["phase"] == "PREPARING"
    manifest = h.parse(
        h.read_file(h.run_path(e.journal, dispatch_id) / "runtime.json"), h.MAX_FILE
    )
    assert manifest["ownership_token"] is None
    rows = h.owner_rows(e.journal, e.scope)
    assert len(rows) == 1 and rows[0]["state"] == "claimed"
    receipt = h.reconcile(
        e.journal,
        e.stream,
        "Durable claim survived the manifest-token write; inspected and preserved stopped output.",
        timestamp=stamp(11),
    )
    assert receipt["status"] == "ABANDONED"
    assert not e.docker.starts
    assert h.owner_rows(e.journal, e.scope)[0]["state"] == "finished"
    assert list(h.run_path(e.journal, dispatch_id).glob("output-*.tar"))


def test_unavailable_docker_observation_holds_pending_ownership(execution):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    original = runtime.docker

    def unavailable(*args, **kwargs):
        if args[0] == "ps":
            raise OSError("Injected transient observation failure")
        return original(*args, **kwargs)

    e.monkeypatch.setattr(runtime, "docker", unavailable)
    before = e.journal.verify()
    with pytest.raises(OSError):
        h.reconcile(
            e.journal,
            e.stream,
            "Inspecting prepared artifacts after coordinator interruption; no automatic retry.",
        )
    assert e.journal.verify() == before
    assert h.owner_rows(e.journal, e.scope)[0]["state"] == "claimed"
    assert h.f.replay(e.journal, e.stream)[0]["pending"] == dispatch_id
    assert not e.docker.starts


@pytest.mark.parametrize("delay", ["preflight", "consumed", "ownership"])
def test_operator_bound_expiring_before_docker_start_never_starts(execution, delay):
    e = execution
    dispatch_id = prepare(e)["dispatch_id"]
    clock = [0.0]
    e.monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    original = launcher.prepared_run

    def checked(*args, **kwargs):
        value = original(*args, **kwargs)
        if (
            kwargs.get("launching")
            and delay in {"preflight", "consumed"}
            and kwargs.get("consumed") == (delay == "consumed")
        ):
            clock[0] = 2.0
        return value

    e.monkeypatch.setattr(launcher, "prepared_run", checked)
    if delay == "ownership":
        start = runtime.Ownership.start

        def delayed_start(self, *args, **kwargs):
            clock[0] = 2.0
            return start(self, *args, **kwargs)

        e.monkeypatch.setattr(runtime.Ownership, "start", delayed_start)
    with pytest.raises(ValueError, match="Execution timeout"):
        launcher.launch(e.journal, dispatch_id, timeout=1.0)
    assert not e.docker.starts
    record, _ = h.load(e.journal, dispatch_id)
    token = record["prepared"]["runtime"]["ownership_token"]
    assert launcher.startup_attempted(e.journal, token) == int(delay != "preflight")
    assert h.owner_rows(e.journal, e.scope)[0]["state"] == "claimed"
    assert (
        h.reconcile(
            e.journal,
            e.stream,
            "Operator timeout expired before Docker start; exact stopped output is preserved.",
            timestamp=stamp(11),
        )["status"]
        == "ABANDONED"
    )


def test_two_worker_attempts_keep_lifetime_history_and_do_not_apply(execution):
    from test_execution_harness import mutate_report

    e = execution

    def adverse(files):
        mutate_report(
            files,
            lambda report: report.update(
                outcome="FAIL", summary="Offline bounded corrective failure"
            ),
        )

    e.docker.change = adverse
    ids = []
    for n in range(2):
        e.scope = h.SessionScope.load({**e.scope.data, "run_id": "lifetime-" + str(n)})
        prepared = h.dispatch(
            e.journal,
            e.stream,
            e.config,
            e.routing,
            __import__("test_feedback").options(),
            e.scope,
            timestamp=stamp(11 + n * 3),
        )
        dispatch_id = prepared["dispatch_id"]
        ids.append(dispatch_id)
        e.monkeypatch.setattr(h.f.wp, "now", lambda: stamp(12 + n * 3))
        e.monkeypatch.setattr(runtime.wp, "now", lambda: stamp(12 + n * 3))
        launcher.launch(e.journal, dispatch_id)
        h.ingest(e.journal, dispatch_id, timestamp=stamp(13 + n * 3))
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert len(state["attempts"]) == 2 and [a["id"] for a in state["attempts"]] == ids
    assert state["total_cap"] == 2 and len(set(ids)) == 2
    assert len(e.docker.starts) == 2
    assert (e.scope.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
