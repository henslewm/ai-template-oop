"""Independent real-Docker AC-02/03 campaign on the delivered M5 adapters.

Only explicit fixture authority/clock and fault seams are replaced. Docker,
Git, archive validation, Journals, ownership and consumed starts are real.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any

import pytest

from scripts import acceptance as a
from scripts import acceptance_runtime as ar
from scripts import execution_harness as h
from scripts import feedback as f
from scripts import worker_launcher as launcher
from scripts import workflow_runtime as runtime
from tests.test_execution_harness import execution as _execution, REAL_DOCKER
from tests.test_feedback import journal as _journal, options, stamp, start

execution = _execution
journal = _journal
DRIVER = Path(__file__).with_name("ac02_ac03_process.py")
pytestmark = pytest.mark.skipif(
    not os.environ.get("WORKFLOW_TEST_IMAGE"),
    reason="WORKFLOW_TEST_IMAGE required for actual Docker AC-02/03",
)

# Fixed test payloads are exported into Docker, never run on the host.
PROBE = r"""
from pathlib import Path
import json, os, socket
assert os.getuid() == os.getgid() == 1000
assert 'AC02_HOST_CANARY' not in os.environ
targets = [
    'src/features/sibling.py', 'src/ui/private.py', '.git/config',
    '../.git/config', '../ownership.sqlite3', '../startup.sqlite3',
    '../control.sqlite3', '../runtime.json', '.env',
    '/root/.aws/credentials', '/root/.ssh/id_rsa', '/home/worker/.aws/credentials',
    '/var/run/docker.sock', '/run/docker.sock', '/run/connectors/private',
    HOST_PATH, SIBLING_PATH, CREDENTIAL_PATH, CONNECTOR_PATH,
] + HOST_ALIASES
denied = []
for i, name in enumerate(targets):
    p = Path(name)
    for op in ('read', 'write'):
        try:
            if op == 'read':
                p.read_bytes()
            else:
                with p.open('r+b') as stream:
                    stream.write(b'changed')
        except OSError:
            denied.append([name, op])
        else:
            raise AssertionError('outside target accessible: ' + name + ' ' + op)
    link = Path('/tmp/link-' + str(i))
    link.symlink_to(p.absolute())
    for op in ('read', 'write'):
        try:
            if op == 'read':
                link.read_bytes()
            else:
                with link.open('r+b') as stream:
                    stream.write(b'changed')
        except OSError:
            denied.append([name, 'link-' + op])
        else:
            raise AssertionError('link escape accessible')
for name in ('contracts/auth.py', 'tests/test_feature_auth.py',
             '/session/packet.json', '/session/scope.json', '/session/baseline.json',
             '/session/brief.json', '/session/worker-rules.md', '/session/dispatch.json'):
    p = Path(name)
    assert p.stat().st_uid == 0
    for operation in (lambda: p.write_bytes(b'changed'), lambda: p.chmod(0o600)):
        try:
            operation()
        except OSError:
            pass
        else:
            raise AssertionError('immutable input changed')
for path in ('/etc/ac02-write', '/session/workspace/new-file'):
    try:
        Path(path).write_text('changed')
    except OSError:
        pass
    else:
        raise AssertionError('immutable directory write allowed')
for family, address in ((socket.AF_INET, ('1.1.1.1',443)),
                        (socket.AF_INET, ('host.docker.internal',443)),
                        (socket.AF_UNIX, '/var/run/docker.sock')):
    s = socket.socket(family)
    s.settimeout(0.2)
    try:
        s.connect(address)
    except OSError:
        pass
    else:
        raise AssertionError('network/socket/connector access allowed')
    finally:
        s.close()
print('AC02_DENIALS=' + json.dumps(denied, sort_keys=True), flush=True)
"""

WORKER = r"""
import base64, hashlib, json, sys
from pathlib import Path
canon = lambda v: json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
brief = json.loads(Path(sys.argv[1]).read_text())
d = json.loads(Path('/session/dispatch.json').read_text())
baseline = json.loads(Path('/session/baseline.json').read_text())
payload = b'VALUE = 2\n'
Path('src/features/auth.py').write_bytes(payload)
change = dict(path='src/features/auth.py',before_sha256=baseline['src/features/auth.py'],content_base64=base64.b64encode(payload).decode())
bundle = dict(scope_sha256=d['scope_sha256'],base_commit=d['base_commit'],changes=[change])
checks = [dict(check_id=c['id'],passed=True,failure_code='',expected='fixture',actual='fixture',evidence=['Real offline export']) for c in brief['context']['contract']['validation']]
bound = dict(binding_sha256=d['binding_sha256'],deadline=d['deadline'],bundle_sha256=hashlib.sha256(canon(bundle).encode()).hexdigest())
r = dict(dispatch_id=d['dispatch_id'],outcome='PASS',summary='Real scoped fixture',scope_status='within',architecture_conflict=False,validation=checks,evidence=['Real stopped replacement'],discoveries=[],api_cost_usd=0,cost_evidence='Unmetered fixture',run=bound)
Path(sys.argv[2]).write_text(canon(r))
print('AC03_EXECUTED', flush=True)
"""


@pytest.fixture
def real_pair(execution, tmp_path, request):
    e = execution
    image = os.environ.get("WORKFLOW_TEST_IMAGE")
    assert image is not None
    e.monkeypatch.setattr(runtime, "docker", REAL_DOCKER)
    e.monkeypatch.setenv("AC02_HOST_CANARY", "fixture-env-canary")
    canaries = [
        e.scope.root / "private/host.txt",
        tmp_path / "sibling/private.txt",
        e.scope.root / ".env",
        tmp_path / "connectors/private.txt",
        e.scope.root / "src/features/sibling.py",
        e.scope.root / "src/ui/private.py",
    ]
    for p in canaries:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"AC02 fixture canary\n")
    bindings = "\n".join(
        name + " = " + repr(str(path))
        for name, path in zip(
            ("HOST_PATH", "SIBLING_PATH", "CREDENTIAL_PATH", "CONNECTOR_PATH"),
            canaries,
        )
    )
    aliases = [
        prefix + p.drive[0].lower() + p.as_posix()[2:]
        for p in canaries[:4]
        for prefix in ("/run/desktop/mnt/host/", "/mnt/", "/host_mnt/")
    ]
    bindings += "\nHOST_ALIASES = " + repr(aliases)
    e.probe = bindings + "\n" + PROBE
    script = e.scope.root / "tests/test_feature_auth.py"
    script.parent.mkdir(exist_ok=True)
    long_running = getattr(request.node, "callspec", None)
    long_running = (
        long_running and long_running.params.get("fault") == "after_start_exit"
    )
    delay = "\nimport time; time.sleep(30)\n" if long_running else ""
    script.write_text(e.probe + "\n" + WORKER + delay, encoding="utf-8")
    packet = copy.deepcopy(f.replay(e.journal, e.stream)[0]["packet"])
    contract = f.wp.current(packet)["contract"]
    contract["risk"] = "low"
    contract["validation"][0]["command"] = {
        "argv": [
            "python",
            "-B",
            "-c",
            e.probe
            + "\n"
            + r"""
assert Path('src/features/auth.py').read_bytes() == b'VALUE = 2\n'
p = Path('src/features/auth.py')
assert p.stat().st_uid == 0
for op in (lambda: p.chmod(0o600), lambda: p.write_bytes(b'changed')):
    try:
        op()
    except OSError:
        pass
    else:
        raise AssertionError('acceptance candidate writable')
print('AC03_EXECUTED', flush=True)
"""
            + delay,
        ],
        "timeout_seconds": 60,
    }
    packet = f.wp.create(
        "AC02-03",
        packet["domain_profile"],
        contract,
        "Architect",
        "Real Docker acceptance fixture",
        stamp(),
    )
    for target in ("ARCHITECTED", "READY"):
        packet = f.wp.transition(
            packet,
            target,
            "architect",
            "Architect",
            "Fixture",
            ["Offline"],
            timestamp=stamp(),
        )
    e.stream, _ = start(e.journal, name="AC02-03", settings=e.routing, packet=packet)
    e.scope = h.SessionScope.load(
        {
            **e.scope.data,
            "packet_revision_hash": f.wp.current(packet)["hash"],
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
    e.image, e.manifests, e.canaries = image, [], canaries
    e.before = {str(p): h.digest(p.read_bytes()) for p in canaries}
    try:
        yield e
    finally:
        # Delete only this test's fresh Docker artifacts. Retained host run
        # directories, ownership/start records and opaque archives survive.
        for manifest in e.manifests:
            if not runtime.stopped(manifest["container"]):
                REAL_DOCKER("kill", manifest["container"])
            REAL_DOCKER("rm", manifest["container"], manifest["setup_container"])
            REAL_DOCKER("volume", "rm", manifest["volume"])
        assert {str(p): h.digest(p.read_bytes()) for p in canaries} == e.before
        assert (e.scope.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"


def prepared(e, mode):
    worker = h.dispatch(
        e.journal, e.stream, e.config, e.routing, options(), e.scope, timestamp=stamp(1)
    )["dispatch_id"]
    assert isinstance(worker, str)
    record = h.load(e.journal, worker)[0]
    e.manifests.append(record["prepared"]["runtime"])
    if mode == "worker":
        return worker, record["prepared"]["runtime"], record["binding"]["deadline"]
    launcher.launch(e.journal, worker)
    assert h.ingest(e.journal, worker)["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
    commit = e.scope.data["base_commit"]
    a.initialize(
        e.journal,
        e.stream,
        worker,
        f.wp.read_json(h.ROOT / "config/acceptance.json"),
        "Independent",
        "Architect",
        reference="stopped:" + worker,
        commits={"feature": commit, "ui": commit, "base": commit},
        image=e.image,
    )
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    record = a.load(e.journal, e.stream)[0]["runs"][-1]
    e.manifests.append(record["prepared"]["runtime"])
    return rid, record["prepared"]["runtime"], record["deadline"]


def owner(e, manifest):
    with sqlite3.connect(e.journal.directory / "ownership.sqlite3") as db:
        db.row_factory = sqlite3.Row
        return dict(
            db.execute(
                "SELECT * FROM runs WHERE token=?", (manifest["ownership_token"],)
            ).fetchone()
        )


def evidence(e, name, **facts):
    directory = os.environ.get("M1_EVIDENCE_DIR")
    if directory:
        dest = Path(directory)
        dest.mkdir(parents=True, exist_ok=True)
        facts.update(
            image=e.image,
            root=str(e.scope.root),
            journal_heads=e.journal.verify(),
            canaries_unchanged=True,
        )
        (dest / (name + ".json")).write_text(json.dumps(facts, indent=2, default=str))


def process(
    e,
    mode,
    rid,
    manifest,
    deadline,
    fault="none",
    action="launch",
    index=0,
    observations=(),
    scope=None,
):
    folder = e.journal.root.parent
    spec = dict(
        root=str(e.journal.root),
        state=str(e.journal.directory),
        mode=mode,
        id=rid,
        stream=e.stream,
        deadline=deadline,
        timestamp=stamp(10),
        fault=fault,
        action=action,
        run=str(h.run_path(e.journal, rid)),
        ready=str(folder / f"ready-{index}"),
        gate=str(folder / "go"),
        trace=str(folder / f"trace-{index}"),
        observed=str(folder / f"observed-{index}"),
        observations=observations,
        scope=scope,
        container=manifest["container"],
    )
    path = folder / f"spec-{index}.json"
    path.write_text(json.dumps(spec))
    p = subprocess.Popen(
        [sys.executable, "-B", str(DRIVER), str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return p, spec


def release(processes):
    until = time.monotonic() + 30
    while not all(Path(s["ready"]).exists() for _, s in processes):
        assert all(p.poll() is None for p, _ in processes), "Child failed before ready"
        assert time.monotonic() < until, "Child readiness timeout"
        time.sleep(0.01)
    Path(processes[0][1]["gate"]).write_text("go")
    results = []
    try:
        for p, spec in processes:
            out, err = p.communicate(timeout=90)
            results.append(
                dict(
                    exit=p.returncode,
                    stdout=out.decode(),
                    stderr=err.decode(),
                    trace=Path(spec["trace"]).read_text()
                    if Path(spec["trace"]).exists()
                    else "",
                )
            )
    finally:
        for p, _ in processes:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=10)
    return results


def launching(e, mode, rid):
    if mode == "worker":
        h.advance(e.journal, rid, "LAUNCHING", {"dispatch_id": rid})
    else:
        a.append(e.journal, e.stream, "CHECK_LAUNCHING", {"run_id": rid})


def capture(e, mode, rid):
    if mode == "worker":
        return h.stopped_record(e.journal, h.load(e.journal, rid)[0])
    return ar.capture_stopped(e.journal, e.stream, rid)


def abandon(e, mode):
    reason = "Explicit abandonment after the independent crash campaign"
    if mode == "worker":
        return h.reconcile(e.journal, e.stream, reason)
    return ar.reconcile_check(e.journal, e.stream, reason)


def forbidden(_):
    raise AssertionError("Refused authority invoked an external callback")


def test_paired_real_exports_and_exact_candidate_acceptance(real_pair):
    e = real_pair
    rid, manifest, _ = prepared(e, "acceptance")
    ar.launch_check(e.journal, e.stream, rid)
    report: dict[str, Any] = ar.ingest_check(e.journal, e.stream, rid)
    assert report["results"][0]["status"] == "PASSED"
    records: list[dict[str, Any]] = []
    for m in e.manifests:
        runtime.assert_boundary(m["container"], m["volume"], e.image)
        info = runtime.inspect(m["container"])
        row = owner(e, m)
        log = (Path(row["evidence"]).parent / "stdout.log").read_text()
        assert "AC02_DENIALS=" in log and log.count("AC03_EXECUTED") == 1
        denied = json.loads(log.split("AC02_DENIALS=")[1].splitlines()[0])
        assert len(denied) == 31 * 4
        assert row["state"] == "finished"
        assert launcher.startup_attempted(e.journal, row["token"]) == 1
        records.append(
            dict(
                inspect=info,
                ownership=row,
                log=log,
                archive_sha256=h.digest(Path(row["evidence"]).read_bytes()),
            )
        )
    assert records[0]["inspect"]["Mounts"][0]["RW"] is True
    assert records[1]["inspect"]["Mounts"][0]["RW"] is False
    assert e.manifests[0]["volume"] != e.manifests[1]["volume"]
    a.accept(e.journal, e.stream, "Independent")
    receipt = a.sync_feedback(e.journal, e.stream)
    assert f.replay(e.journal, e.stream)[0]["status"] == "ACCEPTED"
    evidence(
        e,
        "paired-isolation",
        exports=records,
        acceptance_receipt=receipt,
        image_inspect=json.loads(REAL_DOCKER("image", "inspect", e.image)),
    )


@pytest.mark.parametrize("mode", ["worker", "acceptance"])
@pytest.mark.parametrize("action", ["launch", "execute"])
def test_real_multiprocess_one_start(real_pair, mode, action):
    e = real_pair
    rid, manifest, deadline = prepared(e, mode)
    if action == "execute":
        launching(e, mode, rid)
    observations = [str(e.journal.root.parent / f"observed-{i}") for i in range(2)]
    children = [
        process(
            e,
            mode,
            rid,
            manifest,
            deadline,
            action=action,
            index=i,
            observations=observations,
        )
        for i in range(2)
    ]
    results = release(children)
    assert sorted(r["exit"] for r in results) == [0, 42], results
    assert sum(r["trace"].count("start\n") for r in results) == 1, results
    assert launcher.startup_attempted(e.journal, manifest["ownership_token"]) == 1
    assert owner(e, manifest)["state"] == "finished"
    assert runtime.stopped(manifest["container"])
    log = h.run_path(e.journal, rid) / "stdout.log"
    assert log.read_text().count("AC03_EXECUTED") == 1
    if action == "execute":
        capture(e, mode, rid)
    evidence(
        e,
        mode + "-race-" + action,
        processes=results,
        inspect=runtime.inspect(manifest["container"]),
        ownership=owner(e, manifest),
        log_sha256=h.digest(log.read_bytes()),
    )


@pytest.mark.parametrize("mode", ["worker", "acceptance"])
@pytest.mark.parametrize(
    "fault", ["before_start_exit", "after_start_exit", "start_refusal_log_failure"]
)
def test_real_crash_refuses_restart_and_requires_preservation(real_pair, mode, fault):
    e = real_pair
    rid, manifest, deadline = prepared(e, mode)
    results = release([process(e, mode, rid, manifest, deadline, fault=fault)])
    expected = {
        "before_start_exit": 73,
        "after_start_exit": 74,
        "start_refusal_log_failure": 42,
    }[fault]
    assert results[0]["exit"] == expected, results
    assert launcher.startup_attempted(e.journal, manifest["ownership_token"]) == 1
    assert owner(e, manifest)["state"] == "claimed"
    if fault == "after_start_exit":
        assert runtime.inspect(manifest["container"])["State"]["Running"] is True
    # Reopen every adapter in a fresh process, with its own Python module state.
    again = release([process(e, mode, rid, manifest, deadline, index=1)])
    assert again[0]["exit"] == 42 and again[0]["trace"] == "", again
    with pytest.raises(ValueError, match="consumed"):
        h.Ownership(e.journal.directory).start(manifest["ownership_token"], forbidden)
    scope = h.SessionScope.load(
        f.wp.read_json(h.run_path(e.journal, rid) / "scope.json")
    )
    with pytest.raises(ValueError, match="already has a writer"):
        h.Ownership(e.journal.directory).claim(scope, manifest["container"])
    # Fixture clock models expiry without changing any stored event/lease.
    expired = h.Ownership(e.journal.directory, clock=lambda: time.time() + 4000)
    with pytest.raises(ValueError, match="not confirmed stopped"):
        expired.finish(
            manifest["ownership_token"], lambda _: False, forbidden, recovering=True
        )
    if not runtime.stopped(manifest["container"]):
        with pytest.raises(ValueError, match="not confirmed stopped"):
            expired.finish(
                manifest["ownership_token"], runtime.stopped, forbidden, recovering=True
            )
        with pytest.raises(ValueError):
            abandon(e, mode)
        REAL_DOCKER("kill", manifest["container"])
    with pytest.raises(ValueError, match="missing"):
        expired.finish(
            manifest["ownership_token"],
            runtime.stopped,
            lambda _: e.journal.directory / "missing-output",
            recovering=True,
        )
    assert owner(e, manifest)["state"] == "claimed"
    run = h.run_path(e.journal, rid)
    expired.finish(
        manifest["ownership_token"],
        runtime.stopped,
        lambda c: runtime.preserve(c, run, session=True),
        recovering=True,
    )
    row = owner(e, manifest)
    raw = Path(row["evidence"]).read_bytes()
    assert launcher.archive_files(raw, prefix="session/")
    assert row["state"] == "recovered"
    abandon(e, mode)
    assert Path(row["evidence"]).read_bytes() == raw
    assert launcher.startup_attempted(e.journal, row["token"]) == 1
    with pytest.raises(ValueError, match="No active ownership"):
        h.Ownership(e.journal.directory).start(row["token"], forbidden)
    evidence(
        e,
        mode + "-" + fault,
        initial=results,
        restart=again,
        inspect=runtime.inspect(manifest["container"]),
        ownership=row,
        archive_sha256=h.digest(raw),
        archive_bytes=len(raw),
    )


@pytest.mark.parametrize("collision", ["branch", "workspace"])
def test_real_multiprocess_exclusive_owner(real_pair, collision):
    e = real_pair
    # Ownership claims for distinct scope identities race in separate processes
    # against one DB and an actual prepared/stopped Docker container.
    rid, manifest, deadline = prepared(e, "worker")
    h.Ownership(e.journal.directory).finish(
        manifest["ownership_token"],
        runtime.stopped,
        lambda c: runtime.preserve(c, h.run_path(e.journal, rid), session=True),
    )
    scopes = [copy.deepcopy(e.scope.data) for _ in range(2)]
    scopes[0]["run_id"], scopes[1]["run_id"] = "claim-one", "claim-two"
    if collision == "branch":
        other = e.journal.root.parent / "other-workspace"
        other.mkdir()
        scopes[1]["workspace"] = str(other)
    else:
        scopes[1]["branch"] = "feature/other"
    results = release(
        [
            process(
                e, "worker", rid, manifest, deadline, action="claim", index=i, scope=s
            )
            for i, s in enumerate(scopes)
        ]
    )
    assert sorted(r["exit"] for r in results) == [0, 42], results
    with sqlite3.connect(e.journal.directory / "ownership.sqlite3") as db:
        count = db.execute(
            "SELECT COUNT(*) FROM runs WHERE state='claimed'"
        ).fetchone()[0]
    assert count == 1
    assert all(r["trace"] == "" for r in results)
    evidence(e, "exclusive-" + collision, processes=results, active_claims=count)
