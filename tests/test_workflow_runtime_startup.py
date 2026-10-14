"""Offline fault injection for container startup and ownership cleanup."""
import signal
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier, Event, local
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cli_exit
import work_packet as wp
from workflow_scope import Ownership, SessionScope, digest
import workflow_runtime as runtime


@pytest.fixture
def execution(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    contents = {"contracts/auth.py": b"class Interface: pass\n",
                "src/features/auth.py": b"VALUE = 1\n"}
    for relative, content in contents.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    interfaces = {"contracts/auth.py": digest(contents["contracts/auth.py"])}
    scope = SessionScope.load({
        "schema_version": "1.0", "role": "feature", "feature_id": "auth",
        "owner": "Coordinator", "run_id": "startup-test", "branch": "feature/auth",
        "workspace": str(workspace), "base_commit": "1" * 40,
        "packet_revision_hash": "2" * 64,
        "interface_revision": digest(wp.canonical(interfaces).encode()),
        "read_paths": list(contents), "write_paths": ["src/features/auth.py"],
    })
    state, run = tmp_path / "state", tmp_path / "run"
    run.mkdir()
    ownership = Ownership(state)
    token = ownership.claim(scope, "test-container")
    record = {"container": "test-container", "volume": "test-volume",
              "image": "sha256:" + "3" * 64, "ownership_token": token,
              "scope_sha256": scope.hash, "status": "prepared"}
    for name, data in {"scope.json": scope.data, "runtime.json": record,
                       "baseline.json": {p: digest(b) for p, b in contents.items()}}.items():
        (run / name).write_text(wp.canonical(data), encoding="utf-8")

    worker = SimpleNamespace(status="created", start_status="running", start_error=None,
                             cleanup_error=None, interrupt_cleanup=False, events=[])

    def inspect(container):
        assert container == "test-container"
        if worker.cleanup_error == "inspect" and worker.events:
            raise ValueError("Injected inspection failure")
        return {"State": {"Status": worker.status, "Running": worker.status == "running",
                          "Paused": False, "Restarting": False, "ExitCode": 0}}

    def docker(*args, **kwargs):
        operation = args[0]
        worker.events.append(operation)
        if operation == "start":
            worker.status = worker.start_status
            if worker.start_error is not None:
                raise worker.start_error
        elif operation == "kill":
            if worker.interrupt_cleanup:
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            if worker.cleanup_error == "kill":
                raise ValueError("Injected stop failure")
            if worker.cleanup_error != "unconfirmed":
                worker.status = "exited"
        elif operation == "logs":
            if worker.cleanup_error == "logs":
                raise ValueError("Injected log failure")
            return b"worker log\n"
        elif operation == "cp":
            if worker.cleanup_error == "preserve":
                raise OSError("Injected preservation failure")
            return b"" if worker.cleanup_error == "empty" else b"opaque preserved output"
        else:
            pytest.fail("Unexpected Docker operation: " + operation)
        return b""

    # Only Docker and repository preflight are simulated. Baseline checks,
    # SQLite ownership, log writes and output preservation use the real code.
    monkeypatch.setattr(SessionScope, "verify_base", lambda self: None)
    monkeypatch.setattr(runtime, "check_state", lambda scope, state: None)
    monkeypatch.setattr(runtime, "assert_boundary", lambda *args: None)
    monkeypatch.setattr(runtime, "inspect", inspect)
    monkeypatch.setattr(runtime, "docker", docker)
    return SimpleNamespace(run=run, state=state, scope=scope, ownership=ownership,
                           token=token, worker=worker)


def ownership_row(execution):
    with execution.ownership.transaction() as db:
        return dict(db.execute("SELECT * FROM runs WHERE token=?", (execution.token,)).fetchone())


def startup_attempted(execution):
    connection = sqlite3.connect(execution.ownership.startup_db)
    try:
        row = connection.execute("SELECT attempted FROM startup_authority WHERE token=?",
                                 (execution.token,)).fetchone()
        return None if row is None else row[0]
    finally:
        connection.close()


def startup_error(kind):
    if kind == "timeout":
        return subprocess.TimeoutExpired(["docker", "start"], 60)
    if kind == "interrupt":
        return KeyboardInterrupt()
    return ValueError("Injected startup refusal")


@pytest.mark.parametrize("status", ["created", "running", "exited"])
@pytest.mark.parametrize("failure", ["timeout", "interrupt", "refusal"])
def test_startup_failure_stops_and_preserves_before_releasing(execution, status, failure):
    worker = execution.worker
    worker.start_status, worker.start_error = status, startup_error(failure)
    with pytest.raises(type(worker.start_error)) as raised:
        runtime.execute(execution.run, execution.state, 60)
    assert raised.value is worker.start_error
    assert worker.status != "running"
    assert worker.events == (["start", "kill", "logs", "cp"] if status == "running"
                             else ["start", "logs", "cp"])
    row = ownership_row(execution)
    assert row["state"] == "finished"
    assert Path(row["evidence"]).read_bytes() == b"opaque preserved output"
    assert (execution.run / "stdout.log").read_bytes() == b"worker log\n"
    with pytest.raises(ValueError, match="No active ownership"):
        execution.ownership.start(execution.token, lambda _: pytest.fail("Old token restarted"))
    assert execution.ownership.claim(execution.scope, "next-container")


@pytest.mark.parametrize("failure", ["inspect", "kill", "unconfirmed", "logs", "preserve", "empty"])
def test_startup_cleanup_failure_retains_ownership(execution, failure):
    worker = execution.worker
    worker.start_error, worker.cleanup_error = startup_error("timeout"), failure
    with pytest.raises((ValueError, OSError)):
        runtime.execute(execution.run, execution.state, 60)
    row = ownership_row(execution)
    assert row["state"] == "claimed"
    assert row["evidence"] is None
    with pytest.raises(ValueError, match="already has a writer"):
        execution.ownership.claim(execution.scope, "replacement-container")


def test_expired_ownership_refuses_start_without_cleanup(execution):
    with execution.ownership.transaction() as db:
        db.execute("UPDATE runs SET expires=0 WHERE token=?", (execution.token,))
    with pytest.raises(ValueError, match="Expired ownership cannot start"):
        runtime.execute(execution.run, execution.state, 60)
    assert execution.worker.events == []
    assert ownership_row(execution)["state"] == "claimed"
    assert not list(execution.run.glob("output-*.tar"))
    assert startup_attempted(execution) == 0


@pytest.mark.parametrize("failure,code", [("timeout", 1), ("interrupt", 130), ("refusal", 1)])
def test_startup_cleanup_preserves_cli_exit_codes(execution, monkeypatch, failure, code):
    execution.worker.start_error = startup_error(failure)
    monkeypatch.setattr(sys, "argv", ["workflow_runtime.py", "execute", "--run",
                                      str(execution.run), "--state", str(execution.state)])
    assert cli_exit.run(runtime.main) == code
    assert ownership_row(execution)["state"] == "finished"


def test_successful_execution_still_preserves_output(execution):
    execution.worker.start_status = "exited"
    record = runtime.execute(execution.run, execution.state, 60)
    assert record["status"] == "exited" and record["exit_code"] == 0
    assert wp.read_json(execution.run / "runtime.json") == record
    assert execution.worker.events == ["start", "logs", "cp"]
    assert ownership_row(execution)["state"] == "finished"


def test_execution_timeout_still_stops_and_preserves(execution, monkeypatch):
    times = iter([100, 101])
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(times))
    record = runtime.execute(execution.run, execution.state, 1)
    assert record["status"] == "timed_out"
    assert execution.worker.events == ["start", "kill", "logs", "cp"]
    assert ownership_row(execution)["state"] == "finished"


def test_interrupt_during_execution_still_stops_and_preserves(execution, monkeypatch):
    def interrupt(_):
        raise KeyboardInterrupt()
    monkeypatch.setattr(runtime.time, "sleep", interrupt)
    with pytest.raises(KeyboardInterrupt):
        runtime.execute(execution.run, execution.state, 60)
    assert execution.worker.events == ["start", "kill", "logs", "cp"]
    assert ownership_row(execution)["state"] == "finished"


def test_second_interrupt_waits_for_cleanup_to_finish(execution):
    execution.worker.start_error = startup_error("interrupt")
    execution.worker.interrupt_cleanup = True
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        with pytest.raises(KeyboardInterrupt):
            runtime.execute(execution.run, execution.state, 60)
        assert execution.worker.events == ["start", "kill", "logs", "cp"]
        assert ownership_row(execution)["state"] == "finished"
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, previous)


@pytest.mark.parametrize("startup_failure", ["refusal", "timeout", "interrupt"])
@pytest.mark.parametrize("cleanup_failure", ["logs", "preserve", "empty"])
def test_created_container_cannot_retry_after_failed_cleanup(execution, startup_failure, cleanup_failure):
    worker = execution.worker
    worker.start_status = "created"
    worker.start_error = startup_error(startup_failure)
    worker.cleanup_error = cleanup_failure
    with pytest.raises((ValueError, OSError)):
        runtime.execute(execution.run, execution.state, 60)
    assert startup_attempted(execution) == 1
    assert ownership_row(execution)["state"] == "claimed"
    assert wp.read_json(execution.run / "runtime.json")["status"] == "prepared"
    before = list(worker.events)
    worker.start_error = worker.cleanup_error = None
    worker.start_status = "exited"
    with pytest.raises(ValueError, match="already consumed"):
        runtime.execute(execution.run, execution.state, 60)
    assert worker.events == before  # The refused retry neither starts nor cleans up.
    assert ownership_row(execution)["state"] == "claimed"


@pytest.mark.parametrize("failure", ["refusal", "timeout", "interrupt"])
def test_consumption_committed_before_callback_survives_rollback_and_reopen(execution, failure):
    error = startup_error(failure)

    def callback(_):
        assert startup_attempted(execution) == 1
        raise error

    with pytest.raises(type(error)) as raised:
        execution.ownership.start(execution.token, callback)
    assert raised.value is error
    assert ownership_row(execution)["state"] == "claimed"
    reopened = Ownership(execution.state)
    with pytest.raises(ValueError, match="already consumed"):
        reopened.start(execution.token, lambda _: pytest.fail("Consumed token restarted"))


def test_legacy_token_requires_recovery_without_inventing_startup_history(execution):
    with sqlite3.connect(execution.ownership.startup_db) as connection:
        connection.execute("DELETE FROM startup_authority WHERE token=?", (execution.token,))
    reopened = Ownership(execution.state)
    with pytest.raises(ValueError, match="history missing"):
        reopened.start(execution.token, lambda _: pytest.fail("Legacy token started"))
    assert startup_attempted(execution) is None
    assert ownership_row(execution)["state"] == "claimed"
    with pytest.raises(ValueError, match="Live lease"):
        reopened.finish(execution.token, runtime.stopped,
                        lambda c: runtime.preserve(c, execution.run), recovering=True)
    with reopened.transaction() as db:
        db.execute("UPDATE runs SET expires=0 WHERE token=?", (execution.token,))
    reopened.finish(execution.token, runtime.stopped,
                    lambda c: runtime.preserve(c, execution.run), recovering=True)
    assert ownership_row(execution)["state"] == "recovered"
    with pytest.raises(ValueError, match="No active ownership"):
        reopened.start(execution.token, lambda _: pytest.fail("Recovered token restarted"))
    assert reopened.claim(execution.scope, "replacement-container")


def test_consumed_token_recovery_preserves_output_and_never_restores_authority(execution):
    execution.ownership.start(execution.token, lambda _: None)
    with execution.ownership.transaction() as db:
        db.execute("UPDATE runs SET expires=0 WHERE token=?", (execution.token,))
    execution.ownership.finish(execution.token, runtime.stopped,
                              lambda c: runtime.preserve(c, execution.run), recovering=True)
    assert startup_attempted(execution) == 1
    assert Path(ownership_row(execution)["evidence"]).read_bytes() == b"opaque preserved output"
    with pytest.raises(ValueError, match="No active ownership"):
        Ownership(execution.state).start(execution.token, lambda _: pytest.fail("Recovered token started"))


def test_rolled_back_claim_leaves_only_inert_startup_entry(execution, tmp_path, monkeypatch):
    ownership = Ownership(tmp_path / "orphan-state")
    original_transaction = ownership.transaction

    @contextmanager
    def failed_commit():
        with original_transaction() as db:
            yield db
            raise OSError("Injected claim commit failure")

    monkeypatch.setattr(ownership, "transaction", failed_commit)
    with pytest.raises(OSError, match="claim commit"):
        ownership.claim(execution.scope, "orphan-container")
    with sqlite3.connect(ownership.startup_db) as connection:
        token, attempted = connection.execute("SELECT token, attempted FROM startup_authority").fetchone()
    assert attempted == 0
    reopened = Ownership(ownership.directory)
    with pytest.raises(ValueError, match="No active ownership"):
        reopened.start(token, lambda _: pytest.fail("Orphan entry granted startup"))


def test_concurrent_connections_invoke_start_callback_once(execution):
    owners = [Ownership(execution.state), Ownership(execution.state)]
    barrier, calls = Barrier(2), []

    def compete(owner):
        barrier.wait(timeout=5)
        try:
            owner.start(execution.token, lambda c: calls.append(c))
            return "started"
        except ValueError as error:
            assert "already consumed" in str(error)
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(compete, owners))
    assert sorted(outcomes) == ["refused", "started"]
    assert calls == ["test-container"]
    assert ownership_row(execution)["state"] == "claimed"


def test_start_and_expired_recovery_share_lock(execution):
    start_owner = Ownership(execution.state, clock=lambda: 0)
    recover_owner = Ownership(execution.state, clock=lambda: float("inf"))
    entered, release, recovery_requested, inspected = Event(), Event(), Event(), Event()

    def callback(_):
        entered.set()
        assert release.wait(timeout=5)

    def stopped(_):
        inspected.set()
        assert release.is_set()
        return False

    def recover():
        recovery_requested.set()
        with pytest.raises(ValueError, match="not confirmed stopped"):
            recover_owner.finish(execution.token, stopped,
                                 lambda _: pytest.fail("Live output preserved"), recovering=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        starting = pool.submit(start_owner.start, execution.token, callback)
        try:
            assert entered.wait(timeout=5)
            recovering = pool.submit(recover)
            assert recovery_requested.wait(timeout=5)
            assert not inspected.wait(timeout=0.1)
        finally:
            release.set()
        starting.result(timeout=5)
        recovering.result(timeout=5)
    assert inspected.is_set() and startup_attempted(execution) == 1
    assert ownership_row(execution)["state"] == "claimed"


def test_competing_execute_cannot_clean_up_winning_start(execution, monkeypatch):
    ready, entered, release = Barrier(2), Event(), Event()
    original_inspect, original_docker = runtime.inspect, runtime.docker
    checks = local()

    def inspect(container):
        info = original_inspect(container)
        if not getattr(checks, "preflight_done", False):
            checks.preflight_done = True
            ready.wait(timeout=5)  # Both executors observe created before either starts.
        return info

    def docker(*args, **kwargs):
        if args[0] == "start":
            entered.set()
            assert release.wait(timeout=5)
            return original_docker(*args, **kwargs)
        if args[0] == "logs":
            original_docker(*args, **kwargs)
            raise ValueError("Injected winner cleanup failure")
        return original_docker(*args, **kwargs)

    monkeypatch.setattr(runtime, "inspect", inspect)
    monkeypatch.setattr(runtime, "docker", docker)
    execution.worker.start_status = "created"

    def execute():
        with pytest.raises(ValueError) as error:
            runtime.execute(execution.run, execution.state, 60)
        return str(error.value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(execute) for _ in range(2)]
        try:
            assert entered.wait(timeout=5)
        finally:
            release.set()
        errors = [attempt.result(timeout=5) for attempt in attempts]
    assert sorted(errors) == ["Injected winner cleanup failure",
                              "Startup authority already consumed; explicit recovery required"]
    assert execution.worker.events == ["start", "logs"]  # The competitor does no cleanup.
    assert ownership_row(execution)["state"] == "claimed"


def test_process_exit_after_consumption_cannot_restart(execution):
    script = ("import os,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
              "from workflow_scope import Ownership; "
              "Ownership(Path(sys.argv[2])).start(sys.argv[3],lambda _: os._exit(73))")
    result = subprocess.run([sys.executable, "-B", "-c", script, str(ROOT / "scripts"),
                             str(execution.state), execution.token], capture_output=True, timeout=10)
    assert result.returncode == 73, result.stderr.decode(errors="replace")
    assert startup_attempted(execution) == 1
    assert ownership_row(execution)["state"] == "claimed"
    with pytest.raises(ValueError, match="already consumed"):
        Ownership(execution.state).start(execution.token, lambda _: pytest.fail("Crashed token restarted"))


def test_competing_processes_invoke_start_callback_once(execution, tmp_path):
    gate, calls = tmp_path / "gate", tmp_path / "calls"
    script = '''
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_scope import Ownership
owner=Ownership(Path(sys.argv[2]))
Path(sys.argv[4]).write_text('ready')
deadline=time.monotonic()+5
while not Path(sys.argv[5]).exists():
    if time.monotonic()>deadline: raise RuntimeError('Gate timeout')
    time.sleep(0.01)
def callback(_):
    with Path(sys.argv[6]).open('a') as output: output.write('start\\n')
try:
    owner.start(sys.argv[3],callback)
except ValueError as error:
    assert 'already consumed' in str(error)
    raise SystemExit(42)
'''
    ready = [tmp_path / f"ready-{i}" for i in range(2)]
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(ROOT / "scripts"),
                                  str(execution.state), execution.token, str(path), str(gate), str(calls)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for path in ready]
    try:
        deadline = time.monotonic() + 5
        while not all(path.exists() for path in ready):
            assert time.monotonic() < deadline, "Process readiness timeout"
            time.sleep(0.01)
        gate.write_text("go")
        results = [process.communicate(timeout=10) for process in processes]
        assert sorted(process.returncode for process in processes) == [0, 42], results
        assert calls.read_text() == "start\n"
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
