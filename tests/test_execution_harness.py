"""M4 behavior on real disposable Journals/ownership, with an offline Docker double."""

from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import pytest

from scripts import execution_harness as h
from scripts import worker_launcher as launcher
from scripts import workflow_runtime as runtime
from test_feedback import journal as _journal
from test_feedback import options, result, stamp, start

journal = _journal

IMAGE = "sha256:" + "3" * 64
REAL_DOCKER = runtime.docker


def tar_bytes(files, *, root="session", extra=()):
    buffer = io.BytesIO()
    with __import__("tarfile").open(fileobj=buffer, mode="w") as tar:
        for name, raw in files.items():
            info = __import__("tarfile").TarInfo((root + "/" if root else "") + name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
        for info, raw in extra:
            tar.addfile(info, io.BytesIO(raw) if raw is not None else None)
    return buffer.getvalue()


class Docker:
    """Only the Docker transport is replaced; boundary checks and stores are real."""

    def __init__(self):
        self.containers = {}
        self.volumes = {}
        self.starts = []
        self.change = None
        self.logs = b"Offline fixture completed\n"
        self.fail_start = False
        self.archive_change = None

    def inspect(self, container):
        c = self.containers[container]
        return {
            "Image": IMAGE,
            "State": {
                "Status": c.status,
                "Running": c.status == "running",
                "Paused": False,
                "Restarting": False,
                "ExitCode": c.exit_code,
            },
            "Config": {
                "User": "0:0" if c.setup else "1000:1000",
                "Env": ["PATH=/usr/bin"],
                "Entrypoint": c.argv[:1],
                "Cmd": c.argv[1:],
            },
            "Mounts": [{"Type": "volume", "Name": c.volume, "Destination": "/session"}],
            "HostConfig": {
                "NetworkMode": "none",
                "ReadonlyRootfs": True,
                "Privileged": False,
                "CapDrop": ["ALL"],
                "CapAdd": [],
                "SecurityOpt": ["no-new-privileges"],
                "Memory": 536870912,
                "PidsLimit": 64,
                "NanoCpus": 1000000000,
                "Ulimits": [{"Name": "fsize", "Hard": 2097152, "Soft": 2097152}],
                "LogConfig": {
                    "Type": "local",
                    "Config": {"max-file": "2", "max-size": "1m"},
                },
            },
        }

    def __call__(self, *args, data=None, timeout=60):
        if args[:2] == ("volume", "create"):
            self.volumes[args[2]] = {}
            return args[2].encode()
        if args[:2] == ("image", "inspect"):
            return json.dumps([{"Config": {"Env": ["PATH=/usr/bin"]}}]).encode()
        if args[0] == "create":
            name = args[args.index("--name") + 1]
            mount = args[args.index("--mount") + 1]
            volume = mount.split("source=")[1].split(",")[0]
            image_at = args.index(IMAGE)
            argv = [args[args.index("--entrypoint") + 1], *args[image_at + 1 :]]
            self.containers[name] = SimpleNamespace(
                status="created",
                setup=name.endswith("-setup"),
                volume=volume,
                argv=argv,
                exit_code=0,
            )
            return name.encode()
        if args[0] == "cp":
            if data is not None:
                name = args[-1].split(":")[0]
                self.volumes[self.containers[name].volume] = launcher.archive_files(
                    data, prefix=""
                )
                return b""
            name = args[1].split(":")[0]
            files = self.volumes[self.containers[name].volume]
            if (
                self.archive_change
                and self.containers[name].status == "exited"
                and not self.containers[name].setup
            ):
                return self.archive_change(files)
            return tar_bytes(files)
        if args[0] == "inspect":
            return json.dumps([self.inspect(args[1])]).encode()
        if args[0] == "start":
            name = args[-1]
            c = self.containers[name]
            if not c.setup:
                self.starts.append(name)
                if self.fail_start:
                    raise OSError("Injected ambiguous Docker start failure")
                self.worker(self.volumes[c.volume])
                if self.change:
                    self.change(self.volumes[c.volume])
            c.status = "exited"
            return b""
        if args[0] == "kill":
            self.containers[args[1]].status = "exited"
            return b""
        if args[0] == "logs":
            return self.logs
        if args[0] == "ps":
            names = list(self.containers)
            if "--filter" in args:
                pattern = args[args.index("--filter") + 1]
                names = [n for n in names if pattern == "name=^/" + n + "$"]
            return "\n".join(names).encode()
        raise AssertionError(args)

    def worker(self, files):
        public = json.loads(files["dispatch.json"])
        scope = h.SessionScope.load(json.loads(files["scope.json"]))
        baseline = json.loads(files["baseline.json"])
        files["workspace/src/features/auth.py"] = b"VALUE = 2\n"
        bundle = runtime.bundle_from_archive(
            scope,
            baseline,
            tar_bytes(
                {n: raw for n, raw in files.items() if n.startswith("workspace/")},
                root="",
            ),
        )
        packet = json.loads(files["packet.json"])
        report = result(public, packet, outcome="PASS", passed=True)
        report["run"] = {
            "binding_sha256": public["binding_sha256"],
            "deadline": public["deadline"],
            "bundle_sha256": h.sha(bundle),
        }
        files["report.json"] = h.json_bytes(report)


@pytest.fixture
def execution(journal, monkeypatch):
    root = journal.root
    for name, raw in {
        "contracts/auth.py": b"class Interface: pass\n",
        "src/features/auth.py": b"VALUE = 1\n",
    }.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    for args in [
        ("init", "-b", "feature/auth"),
        ("add", "contracts", "src"),
        (
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "Offline fixture",
        ),
    ]:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    stream, routing = start(journal)
    state = h.f.replay(journal, stream)[0]
    packet = state["packet"]
    data = {
        "schema_version": "1.0",
        "role": "feature",
        "feature_id": "auth",
        "owner": "Implementer",
        "run_id": "fixture-one",
        "branch": "feature/auth",
        "workspace": str(root),
        "base_commit": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"]
        )
        .decode()
        .strip(),
        "packet_revision_hash": h.f.wp.current(packet)["hash"],
        "interface_revision": h.sha(
            {"contracts/auth.py": h.digest((root / "contracts/auth.py").read_bytes())}
        ),
        "read_paths": ["contracts/auth.py", "src/features/auth.py"],
        "write_paths": ["src/features/auth.py"],
    }
    config = h.f.wp.read_json(h.ROOT / "config/execution-harness.json")
    config["enabled"] = True
    config["limits"]["context_growth_reserve_tokens"] = 100
    config["bindings"] = [
        {
            **config["bindings"][0],
            "resource_id": r["id"],
            "provider": r["provider_id"],
            "model": r["model"],
            "image": IMAGE,
        }
        for r in routing["resources"]
    ]
    docker = Docker()
    monkeypatch.setattr(runtime, "docker", docker)
    monkeypatch.setattr(runtime, "state_directory", lambda _: journal.directory)
    monkeypatch.setattr(h.f.wp, "now", lambda: stamp(10))
    monkeypatch.setattr(runtime.wp, "now", lambda: stamp(10))
    return SimpleNamespace(
        journal=journal,
        stream=stream,
        config=config,
        routing=routing,
        scope=h.SessionScope.load(data),
        docker=docker,
        monkeypatch=monkeypatch,
    )


def prepare(e):
    return h.dispatch(
        e.journal, e.stream, e.config, e.routing, options(), e.scope, timestamp=stamp(1)
    )


def run(e):
    prepared = prepare(e)
    launcher.launch(e.journal, prepared["dispatch_id"])
    return prepared["dispatch_id"]


def mutate_report(files, change):
    report = json.loads(files["report.json"])
    change(report)
    files["report.json"] = h.json_bytes(report)


def test_disabled_default_no_reservation_or_docker(execution):
    e = execution
    e.config["enabled"] = False
    before = e.journal.verify()
    with pytest.raises(ValueError, match="disabled"):
        prepare(e)
    assert e.journal.verify() == before
    assert not e.docker.containers


@pytest.mark.parametrize(
    "argv",
    [
        ["{brief}", "{report}", "{"],
        ["{{brief}}", "{report}"],
        ["{brief}", "{{report}}"],
        ["{brief!r}", "{report}"],
        ["{brief:>10}", "{report}"],
        ["{brief.__class__}", "{report}"],
    ],
)
def test_malformed_or_escaped_invocation_refuses_before_reservation(execution, argv):
    e = execution
    e.config["harnesses"][0]["argv"] = argv
    before = e.journal.verify()
    with pytest.raises(ValueError):
        prepare(e)
    assert e.journal.verify() == before
    assert not e.docker.containers


def test_dispatch_launch_ingest_preserves_m3_and_never_accepts_or_applies(execution):
    e = execution
    dispatch = prepare(e)
    assert not e.docker.starts
    record, _ = h.load(e.journal, dispatch["dispatch_id"])
    assert record["phase"] == "PREPARED"
    brief = json.loads((Path(dispatch["run"]) / "brief.json").read_text())
    assert set(h.f.worker_context(h.f.replay(e.journal, e.stream)[0])) == set(
        brief["context"]
    )
    launcher.prepared_run(e.journal, dispatch["dispatch_id"])
    launcher.launch(e.journal, dispatch["dispatch_id"])
    receipt = h.ingest(e.journal, dispatch["dispatch_id"], timestamp=stamp(11))
    assert receipt["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert state["status"] == "REVIEW_PENDING" and len(state["attempts"]) == 1
    assert state["pending"] is None
    assert state["attempts"][0]["accounting"] == {
        "settled": 0,
        "liability": 0,
        "unknown": False,
    }
    assert (e.journal.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
    heads = e.journal.verify()
    assert h.ingest(e.journal, dispatch["dispatch_id"], timestamp=stamp(12)) == receipt
    assert e.journal.verify() == heads
    assert len(e.docker.starts) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(dispatch_id="wrong"),
        lambda r: r["run"].update(deadline=stamp(700)),
        lambda r: r["run"].update(bundle_sha256="1" * 64),
        lambda r: r["run"].update(binding_sha256="2" * 64),
        lambda r: r["validation"].append(copy.deepcopy(r["validation"][0])),
        lambda r: r["validation"][0].update(check_id="UNKNOWN"),
        lambda r: r.update(validation=[]),
        lambda r: r["validation"][0].update(passed="false"),
        lambda r: r["validation"][0].update(passed=False),
        lambda r: r.update(scope_status="violated"),
        lambda r: r.update(architecture_conflict=True),
        lambda r: r.update(api_cost_usd=True),
        lambda r: r.update(api_cost_usd=None),
        lambda r: r.update(unknown_field="bad"),
        lambda r: r.update(summary="api_key=never-echo-this"),
        lambda r: r.update(evidence=[]),
        lambda r: r.update(discoveries="bad"),
    ],
    ids=[
        "dispatch",
        "deadline",
        "bundle",
        "binding",
        "duplicate-check",
        "unknown-check",
        "missing-check",
        "check-type",
        "contradictory-check",
        "scope",
        "architecture",
        "bool-cost",
        "null-cost",
        "unknown-field",
        "credential",
        "no-evidence",
        "nested-type",
    ],
)
def test_report_negatives_hold_pending_and_accounts(execution, change):
    e = execution
    e.docker.change = lambda files: mutate_report(files, change)
    dispatch_id = run(e)
    heads = e.journal.verify()
    with pytest.raises((ValueError, TypeError)):
        h.ingest(e.journal, dispatch_id, timestamp=stamp(11))
    assert e.journal.verify() == heads
    assert h.f.replay(e.journal, e.stream)[0]["pending"] == dispatch_id


@pytest.mark.parametrize(
    "name,content",
    [
        ("workspace/contracts/auth.py", b"changed interface"),
        ("brief.json", b"changed brief"),
        ("dispatch.json", b"changed binding"),
        ("worker-rules.md", b"changed rules"),
        ("packet.json", b"changed packet"),
        ("workspace/../escape.py", b"escape"),
        ("workspace/src/features/other.py", b"other"),
        ("workspace/src/features/auth.py", b"sk-abcdefghijklmnopqrstuvwx"),
    ],
)
def test_exact_stopped_export_negatives(execution, name, content):
    e = execution
    e.docker.change = lambda files: files.update({name: content})
    dispatch_id = run(e)
    with pytest.raises(ValueError):
        h.ingest(e.journal, dispatch_id)
    assert h.f.replay(e.journal, e.stream)[0]["pending"] == dispatch_id


def test_preparation_failure_explicitly_abandons_consumed_attempt(execution):
    e = execution
    e.monkeypatch.setattr(
        runtime,
        "prepare",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("Injected pre-render crash")
        ),
    )
    with pytest.raises(OSError):
        prepare(e)
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert state["pending"] is None and len(state["attempts"]) == 1
    assert state["attempts"][0]["result"]["outcome"] == "FAIL"
    assert (
        h.load(e.journal, state["attempts"][0]["id"])[0]["receipt"]["status"]
        == "ABANDONED"
    )


def test_atomic_result_failure_preserves_all_four_heads_and_replays(execution):
    e = execution
    dispatch_id = run(e)
    before = e.journal.verify()
    append = e.journal.append_many

    def refuse(requests):
        return append(
            tuple(
                [
                    *requests[:-1],
                    __import__("dataclasses").replace(
                        requests[-1], expected=h.ws.Head()
                    ),
                ]
            )
        )

    e.monkeypatch.setattr(e.journal, "append_many", refuse)
    with pytest.raises(ValueError, match="Stale"):
        h.ingest(e.journal, dispatch_id)
    assert e.journal.verify() == before
    e.monkeypatch.setattr(e.journal, "append_many", append)
    receipt = h.ingest(e.journal, dispatch_id)
    events, _ = e.journal.read(h.stream_name(dispatch_id))
    replayed = None
    for event in events:
        replayed = h.ds.apply(replayed, event)
    assert replayed == h.load(e.journal, dispatch_id)[0]
    assert replayed["receipt"] == receipt


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        "hardlink",
        "fifo",
        "duplicate",
        "escape",
        "missing",
        "oversized",
        "unknown",
    ],
)
def test_untrusted_archive_shapes_refuse_without_extracting(execution, kind):
    e = execution

    def bad_archive(files):
        files = dict(files)
        extra = []
        if kind in {"symlink", "hardlink", "fifo"}:
            files.pop("workspace/src/features/auth.py")
            info = tarfile.TarInfo("session/workspace/src/features/auth.py")
            info.type = {
                "symlink": tarfile.SYMTYPE,
                "hardlink": tarfile.LNKTYPE,
                "fifo": tarfile.FIFOTYPE,
            }[kind]
            info.linkname = "/outside/host"
            extra.append((info, None))
        elif kind == "duplicate":
            info = tarfile.TarInfo("session/report.json")
            info.size = 1
            extra.append((info, b"x"))
        elif kind == "escape":
            files["../../escape"] = b"escape"
        elif kind == "missing":
            files.pop("workspace/contracts/auth.py")
        elif kind == "oversized":
            files["workspace/src/features/auth.py"] = b"x" * (h.MAX_FILE + 1)
        else:
            files["workspace/src/features/unowned.py"] = b"unowned"
        return tar_bytes(files, extra=extra)

    e.docker.archive_change = bad_archive
    dispatch_id = run(e)
    before = e.journal.verify()
    with pytest.raises(ValueError):
        h.ingest(e.journal, dispatch_id)
    assert e.journal.verify() == before
    assert not (e.journal.root.parent / "escape").exists()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"dispatch_id":"one","dispatch_id":"two"}',
        b'{"value":NaN}',
        b"[]",
        b'"text"',
        b"\xff",
        b" " * 262145,
    ],
    ids=["duplicate-keys", "nonfinite", "array", "scalar", "invalid-utf8", "oversized"],
)
def test_bounded_duplicate_ambiguous_or_non_json_report_refuses(execution, raw):
    e = execution
    e.docker.change = lambda files: files.update({"report.json": raw})
    dispatch_id = run(e)
    with pytest.raises((ValueError, TypeError)):
        h.ingest(e.journal, dispatch_id)


def test_concurrent_identical_ingestion_is_idempotent(execution):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    e = execution
    dispatch_id = run(e)
    barrier = Barrier(2)
    original = h.settle

    def settle(*args, **kwargs):
        barrier.wait(timeout=20)
        return original(*args, **kwargs)

    e.monkeypatch.setattr(h, "settle", settle)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: h.ingest(e.journal, dispatch_id), range(2)))
    assert receipts[0] == receipts[1]
    assert [x["kind"] for x in e.journal.read(e.stream)[0]].count("RESULT") == 1
    assert len(h.f.replay(e.journal, e.stream)[0]["attempts"]) == 1


@pytest.mark.parametrize("cut", [1, 2, 3, 4])
def test_process_exit_during_result_transaction_recovers_all_heads(execution, cut):
    e = execution
    dispatch_id = run(e)
    before = e.journal.verify()
    # This is a coordinator fault-injection process, never a worker launch.
    code = f"""import os,sys
from pathlib import Path
sys.path.insert(0,{str(h.ROOT)!r})
from scripts import execution_harness as h
from scripts import workflow_state as ws
root=Path({str(e.journal.root)!r})
ws.control_directory=lambda _: Path({str(e.journal.directory)!r})
ws.approval.git=lambda *args: str(root/'.git').encode()
ws.active_anchor=lambda *args: {"a" * 64!r}
h.f.wp.now=lambda: {stamp(11)!r}
j=ws.Journal(root)
original=j._insert
count=0
def killed(*args,**kwargs):
 global count
 original(*args,**kwargs)
 count+=1
 if count=={cut}: os._exit(73)
j._insert=killed
h.ingest(j,{dispatch_id!r})
"""
    child = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, timeout=30
    )
    assert child.returncode == 73, child.stderr.decode(errors="replace")
    e.journal.recover()
    assert e.journal.verify() == before
    assert h.load(e.journal, dispatch_id)[0]["phase"] == "STOPPED"
    assert (
        h.ingest(e.journal, dispatch_id)["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
    )


def test_reserved_without_dispatch_record_reconciles_without_render_or_launch(
    execution,
):
    e = execution
    create = e.journal.create

    def crash(stream, **kwargs):
        if stream.startswith("dispatch:"):
            raise KeyboardInterrupt(
                "Injected crash between reservation and preparation INIT"
            )
        return create(stream, **kwargs)

    e.monkeypatch.setattr(e.journal, "create", crash)
    with pytest.raises(KeyboardInterrupt):
        prepare(e)
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert len(state["attempts"]) == 1 and state["pending"]
    assert not e.docker.containers
    h.reconcile(
        e.journal,
        e.stream,
        "Reservation committed before preparation INIT; no Docker side effect was possible.",
        timestamp=stamp(11),
    )
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert state["pending"] is None and len(state["attempts"]) == 1


def test_conflicting_duplicate_usage_refuses(execution):
    e = execution
    dispatch_id = run(e)
    h.ingest(e.journal, dispatch_id)
    before = e.journal.verify()
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        h.ingest(e.journal, dispatch_id, usage={"dispatch_id": "different"})
    assert e.journal.verify() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "disabled-resource",
        "served-context",
        "unknown-harness",
        "credential",
        "metered",
        "wrong-actor",
    ],
)
def test_known_preflight_refusals_do_not_spend_attempts(execution, mutation):
    e = execution
    if mutation == "disabled-resource":
        for r in e.routing["resources"]:
            r["enabled"] = False
    elif mutation == "served-context":
        e.config["bindings"][0]["served_context_window"] = 1
    elif mutation == "unknown-harness":
        e.config["bindings"][0]["harness_id"] = "unknown"
    elif mutation == "credential":
        e.config["bindings"][0]["credential_env"] = "API_KEY"
    elif mutation == "metered":
        for r in e.routing["resources"]:
            r["input_million_usd"] = 1
    else:
        e.scope = h.SessionScope.load({**e.scope.data, "owner": "Other"})
    try:
        value = prepare(e)
        assert value["dispatch_id"] is None
    except ValueError:
        pass
    assert not h.f.replay(e.journal, e.stream)[0]["attempts"]
    assert not e.docker.containers


def test_stopped_output_and_log_credentials_refuse(execution):
    e = execution
    e.docker.logs = b"authorization=do-not-echo"
    dispatch_id = run(e)
    with pytest.raises(ValueError, match="credential-like") as error:
        h.ingest(e.journal, dispatch_id)
    assert "do-not-echo" not in str(error.value)


def test_crash_after_result_commit_returns_same_receipt_on_replay(execution):
    e = execution
    dispatch_id = run(e)
    original = e.journal.append_many

    def committed_then_crash(requests):
        original(requests)
        raise KeyboardInterrupt("Injected interruption after committed result")

    e.monkeypatch.setattr(e.journal, "append_many", committed_then_crash)
    with pytest.raises(KeyboardInterrupt):
        h.ingest(e.journal, dispatch_id)
    before = e.journal.verify()
    receipt = h.ingest(e.journal, dispatch_id)
    assert receipt == h.load(e.journal, dispatch_id)[0]["receipt"]
    assert e.journal.verify() == before


def test_late_ingestion_receipt_matches_m3_timeout_not_worker_pass(execution):
    e = execution
    dispatch_id = run(e)
    receipt = h.ingest(e.journal, dispatch_id, timestamp=stamp(700))
    state, _, _ = h.f.replay(e.journal, e.stream)
    assert receipt["status"] == state["status"] == "IN_PROGRESS"
    assert state["reason"] == "ATTEMPT_TIMEOUT"
    assert state["attempts"][-1]["routing_outcome"] == "FAIL"
    assert h.ingest(e.journal, dispatch_id, timestamp=stamp(701)) == receipt


@pytest.mark.parametrize("claim", [None, 0, 0.25])
def test_m4_accounting_bridge_keeps_unmeasured_metered_liability(journal, claim):
    from test_model_router import config, resource
    from test_feedback import reserve

    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatched = reserve(journal, stream, settings)
    dispatch_id = dispatched["dispatch_id"]
    journal.create(
        h.stream_name(dispatch_id),
        family="project",
        binding={"dispatch_id": dispatch_id},
        data={
            "version": h.ds.VERSION,
            "task_stream": stream,
            "dispatch_id": dispatch_id,
            "binding": {},
            "intent": {},
        },
        reducer=h.ds.apply,
        timestamp=stamp(1),
    )
    h.advance(
        journal,
        dispatch_id,
        "RECOVERY",
        {"archive": {}, "runtime": {}, "exit_code": 1, "finished_at": stamp(2)},
        timestamp=stamp(2),
    )
    record, _ = h.load(journal, dispatch_id)
    packet = h.f.replay(journal, stream)[0]["packet"]
    receipt = {
        "dispatch_id": dispatch_id,
        "ingestion_sha256": "1" * 64,
        "status": "RECORDED_ADVERSE_RESULT",
        "bundle_sha256": "2" * 64,
    }
    h.settle(
        journal,
        record,
        "RESULT",
        result(dispatched, packet, api_cost_usd=claim),
        receipt,
        timestamp=stamp(3),
    )
    attempt = h.f.replay(journal, stream)[0]["attempts"][-1]
    assert attempt["accounting"]["unknown"] and attempt["accounting"]["settled"] == 0
    assert attempt["accounting"]["liability"] >= (claim or 0)
    assert attempt["raw_result"]["api_cost_usd"] == claim
    for account in h.f.accounts(h.f.replay(journal, stream)[0], "worker"):
        assert journal.replay(account, h.budget.apply)[0]["entries"][dispatch_id][
            "unknown"
        ]


@pytest.mark.parametrize(
    "fault", [None, "wrong-dispatch", "wrong-rates", "missing-evidence"]
)
def test_m4_accounting_bridge_prices_only_coordinator_usage_at_saved_rates(
    journal, fault
):
    from test_model_router import config, resource
    from test_feedback import reserve, usage

    stream, settings = start(journal, settings=config(resource(api=0.01)))
    dispatched = reserve(journal, stream, settings)
    dispatch_id = dispatched["dispatch_id"]
    journal.create(
        h.stream_name(dispatch_id),
        family="project",
        binding={"dispatch_id": dispatch_id},
        data={
            "version": h.ds.VERSION,
            "task_stream": stream,
            "dispatch_id": dispatch_id,
            "binding": {},
            "intent": {},
        },
        reducer=h.ds.apply,
        timestamp=stamp(1),
    )
    h.advance(
        journal,
        dispatch_id,
        "RECOVERY",
        {"archive": {}, "runtime": {}, "exit_code": 1, "finished_at": stamp(2)},
        timestamp=stamp(2),
    )
    state, _, _ = h.f.replay(journal, stream)
    attempt = state["attempts"][-1]
    measured, evidence = usage(journal, attempt)
    if fault == "wrong-dispatch":
        measured["dispatch_id"] = "f" * 64
    elif fault == "wrong-rates":
        measured["rates_hash"] = "f" * 64
    elif fault == "missing-evidence":
        evidence = ()
    record, _ = h.load(journal, dispatch_id)
    receipt = {
        "dispatch_id": dispatch_id,
        "ingestion_sha256": "1" * 64,
        "status": "RECORDED_ADVERSE_RESULT",
        "bundle_sha256": "2" * 64,
    }
    data = {**result(dispatched, state["packet"], api_cost_usd=99), "usage": measured}
    before = journal.verify()
    if fault:
        with pytest.raises(ValueError):
            h.settle(
                journal,
                record,
                "RESULT",
                data,
                receipt,
                evidence=evidence,
                timestamp=stamp(3),
            )
        assert journal.verify() == before
    else:
        expected = h.budget.measurement(attempt, measured)
        settings["resources"][0]["input_million_usd"] = 0
        h.settle(
            journal,
            record,
            "RESULT",
            data,
            receipt,
            evidence=evidence,
            timestamp=stamp(3),
        )
        after = h.f.replay(journal, stream)[0]["attempts"][-1]
        assert (
            after["accounting"]["settled"] == expected
            and not after["accounting"]["unknown"]
        )
        assert after["raw_result"]["api_cost_usd"] == 99


def test_real_pinned_docker_round_trip_uses_no_provider_or_host_mount(execution):
    e = execution
    image = os.environ.get("WORKFLOW_TEST_IMAGE")
    if not image:
        pytest.skip(
            "WORKFLOW_TEST_IMAGE is required for the pinned offline Docker fixture"
        )
    script = """import base64,hashlib,json,sys
from pathlib import Path
canon=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
brief=json.loads(Path(sys.argv[1]).read_text())
d=json.loads(Path('/session/dispatch.json').read_text())
baseline=json.loads(Path('/session/baseline.json').read_text())
payload=b'VALUE = 2\\n'
Path('src/features/auth.py').write_bytes(payload)
change=dict(path='src/features/auth.py',before_sha256=baseline['src/features/auth.py'],content_base64=base64.b64encode(payload).decode())
bundle=dict(scope_sha256=d['scope_sha256'],base_commit=d['base_commit'],changes=[change])
checks=[dict(check_id=c['id'],passed=True,failure_code='',expected='fixture',actual='fixture',evidence=['Offline fixture']) for c in brief['context']['contract']['validation']]
bound=dict(binding_sha256=d['binding_sha256'],deadline=d['deadline'],bundle_sha256=hashlib.sha256(canon(bundle).encode()).hexdigest())
r=dict(dispatch_id=d['dispatch_id'],outcome='PASS',summary='Offline Docker fixture',scope_status='within',architecture_conflict=False,validation=checks,evidence=['Offline scoped replacement'],discoveries=[],api_cost_usd=0,cost_evidence='Unmetered offline fixture',run=bound)
Path(sys.argv[2]).write_text(canon(r))
"""
    path = e.scope.root / "tests/test_feature_auth.py"
    path.parent.mkdir(exist_ok=True)
    path.write_text(script, encoding="utf-8")
    e.scope = h.SessionScope.load(
        {
            **e.scope.data,
            "run_id": "real-docker-one",
            "read_paths": [*e.scope.data["read_paths"], "tests/test_feature_auth.py"],
        }
    )
    e.config["harnesses"][0]["argv"] = [
        "tests/test_feature_auth.py",
        "{brief}",
        "{report}",
    ]
    for binding in e.config["bindings"]:
        binding["image"] = image
    e.monkeypatch.setattr(runtime, "docker", REAL_DOCKER)
    prepared = prepare(e)
    record, _ = h.load(e.journal, prepared["dispatch_id"])
    manifest = record["prepared"]["runtime"]
    try:
        launcher.launch(e.journal, prepared["dispatch_id"])
        receipt = h.ingest(e.journal, prepared["dispatch_id"])
        assert receipt["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
        info = runtime.inspect(manifest["container"])
        assert info["HostConfig"]["NetworkMode"] == "none"
        assert info["Config"]["User"] == "1000:1000"
        assert all(m["Type"] != "bind" for m in info["Mounts"])
        assert (e.scope.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
    finally:
        REAL_DOCKER("rm", manifest["container"], manifest["setup_container"])
        REAL_DOCKER("volume", "rm", manifest["volume"])
