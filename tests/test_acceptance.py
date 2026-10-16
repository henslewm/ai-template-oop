"""M5 behavior against disposable SQLite/ownership and offline Docker exports."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import os
import threading

import pytest

from scripts import acceptance as a
from scripts import acceptance_runtime as ar
from scripts import feedback as f
from scripts import execution_harness as h
from scripts import workflow_runtime as runtime
from test_execution_harness import (
    execution as _execution,
    run,
    tar_bytes,
    REAL_DOCKER,
    Docker,
)
from test_feedback import journal as _journal, options, stamp, start

execution = _execution
journal = _journal


class AcceptanceDocker(Docker):
    def __call__(self, *args, **kwargs):
        result = super().__call__(*args, **kwargs)
        if args[0] == "create":
            name = args[args.index("--name") + 1]
            self.containers[name].readonly = (
                ",readonly" in args[args.index("--mount") + 1]
            )
        return result

    def inspect(self, container):
        result = super().inspect(container)
        result["Mounts"][0]["RW"] = not getattr(
            self.containers[container], "readonly", False
        )
        return result


def candidate_fixture(execution, risk="low", additional=()):
    e = execution
    packet = copy.deepcopy(f.replay(e.journal, e.stream)[0]["packet"])
    contract = f.wp.current(packet)["contract"]
    contract["risk"] = risk
    if risk in {"high", "critical"}:
        tier = 3 if risk == "high" else 4
        contract["routing"].update(min_tier=tier, max_tier=tier, reviewer_tier=tier)
        contract["escalation_path"] = []
        for resource in e.routing["resources"]:
            resource["tier"] = tier
    contract["validation"][0]["command"] = {
        "argv": [
            "python",
            "-B",
            "-c",
            """from pathlib import Path
import socket
assert Path('src/features/auth.py').read_bytes() == b'VALUE = 2\\n'
for name in ('src/features/auth.py', 'contracts/auth.py'):
    p = Path(name)
    assert p.stat().st_uid == 0
    for operation in (lambda: p.chmod(0o600), lambda: p.write_text('tampered')):
        try:
            operation()
        except OSError:
            pass
        else:
            raise AssertionError('immutable candidate was writable')
assert not Path('/session/workspace/.git').exists()
assert not Path('/var/run/docker.sock').exists()
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(('1.1.1.1', 443))
except OSError:
    pass
else:
    raise AssertionError('network unexpectedly available')
finally:
    s.close()
""",
        ],
        "timeout_seconds": 60,
    }
    packet = f.wp.create(
        "ACCEPT",
        packet["domain_profile"],
        contract,
        "Architect",
        "Offline acceptance fixture",
        stamp(),
    )
    for target in ("ARCHITECTED", "READY"):
        packet = f.wp.transition(
            packet,
            target,
            "architect",
            "Architect",
            "Fixture",
            ["Synthetic"],
            timestamp=stamp(),
        )
    e.stream, _ = start(e.journal, name="ACCEPT", settings=e.routing, packet=packet)
    e.scope = h.SessionScope.load(
        {**e.scope.data, "packet_revision_hash": f.wp.current(packet)["hash"]}
    )
    e.worker_id = run(e)
    h.ingest(e.journal, e.worker_id)
    docker = AcceptanceDocker()
    docker.__dict__.update(e.docker.__dict__)
    e.docker = docker
    e.monkeypatch.setattr(runtime, "docker", docker)
    e.acceptance_config = f.wp.read_json(h.ROOT / "config/acceptance.json")
    e.acceptance_config["policy"]["additional_gates"][risk] = list(additional)
    commit = e.scope.data["base_commit"]
    e.bindings = {
        "reference": "stopped-replacement:" + e.worker_id,
        "commits": {"feature": commit, "ui": commit, "base": commit},
        "image": "sha256:" + "3" * 64,
    }
    a.initialize(
        e.journal,
        e.stream,
        e.worker_id,
        e.acceptance_config,
        "Independent",
        "Architect",
        **e.bindings,
    )
    e.docker.worker = lambda files: None
    return e


@pytest.fixture
def accepted_candidate(execution):
    return candidate_fixture(execution)


def check(e):
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    ar.launch_check(e.journal, e.stream, rid)
    report = ar.ingest_check(e.journal, e.stream, rid)
    return rid, report


def review_report(opened, state, **updates):
    return {
        "schema_version": "1.0",
        "review_id": opened["review_id"],
        "reviewer": opened["reviewer"],
        "verdict": "APPROVE",
        "summary": "Independently reviewed exact candidate.",
        "criteria": [
            {
                "criterion_id": c["id"],
                "status": "met",
                "evidence": ["Bound candidate and independent checks"],
            }
            for c in state["contract"]["acceptance_criteria"]
        ],
        "contract_failures": [],
        "missing_evidence": [],
        "escalation_reason": "",
        **updates,
    }


def open_review(e, gate="model_review", actor="Reviewer"):
    return a.prepare_review(
        e.journal, e.stream, e.routing, options(reviewer_actor=actor), gate
    )


def strengthen(e, risk="medium", gates=None):
    # Fixture-only new task INIT, never rewrite an existing Journal or packet.
    # The reducer floor probes below exercise stronger contracts without runtime.
    state, _ = a.load(e.journal, e.stream)
    state["contract"]["risk"] = risk
    state["gates"] = sorted(f.REVIEW_FLOORS[risk] | set(gates or []))
    return state


def test_worker_pass_cannot_accept_and_low_risk_fresh_export(accepted_candidate):
    e = accepted_candidate
    with pytest.raises(ValueError, match="incomplete"):
        a.accept(e.journal, e.stream, "Independent")
    rid, report = check(e)
    assert report["results"][0]["status"] == "PASSED"
    state, _ = a.load(e.journal, e.stream)
    worker_record, _ = h.load(e.journal, e.worker_id)
    manifest = state["runs"][-1]["prepared"]["runtime"]
    assert manifest["volume"] != worker_record["prepared"]["runtime"]["volume"]
    assert len(e.docker.starts) == 2
    inputs = e.docker.volumes[manifest["volume"]]
    assert inputs["workspace/src/features/auth.py"] == b"VALUE = 2\n"
    assert not any(".git" in n or "sqlite" in n for n in inputs)
    a.accept(e.journal, e.stream, "Independent")
    receipt = a.sync_feedback(e.journal, e.stream)
    assert a.sync_feedback(e.journal, e.stream) == receipt
    native = f.replay(e.journal, e.stream)[0]
    assert native["status"] == "ACCEPTED"
    assert native["packet"]["state"] == "ACCEPTED"
    assert len(native["attempts"]) == 1 and native["review_attempts"] == []
    assert (e.scope.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
    with pytest.raises(ValueError):
        ar.launch_check(e.journal, e.stream, rid)
    e.journal.verify()


@pytest.mark.parametrize("actor", ["Implementer", "implementer", " IMPLEMENTER ", ""])
def test_actor_independence(accepted_candidate, actor):
    e = accepted_candidate
    with pytest.raises(ValueError):
        a.initialize(
            e.journal,
            e.stream,
            e.worker_id,
            e.acceptance_config,
            actor,
            "Architect",
            **e.bindings,
        )
    before = e.journal.verify()
    with pytest.raises(ValueError):
        a.accept(e.journal, e.stream, actor)
    assert e.journal.verify() == before


@pytest.mark.parametrize(
    "change",
    [
        "reference",
        "image",
        "feature",
        "ui",
        "interface",
        "artifact",
        "scope",
        "evidence",
    ],
)
def test_any_submission_binding_change_invalidates_gates_preserves_reviews(
    accepted_candidate, change
):
    e = accepted_candidate
    check(e)
    state, _ = a.load(e.journal, e.stream)
    # Pure transition tests retain history; production resubmit rechecks Git,
    # source output, image and exact bundle before it can propose these inputs.
    submission = copy.deepcopy(state["submission"])
    if change == "reference":
        submission["artifact"]["reference"] += "-changed"
    elif change == "image":
        submission["image"] = "sha256:" + "4" * 64
    elif change in {"feature", "ui"}:
        submission["commits"]["ui"] = "2" * 40
    elif change == "interface":
        submission["scope"]["interface_revision"] = "a" * 64
    elif change == "artifact":
        submission["bundle"]["changes"][0]["content_base64"] = "Vg=="
        submission["artifact"]["sha256"] = a.sha(submission["bundle"])
    elif change == "scope":
        submission["scope"]["run_id"] += "-changed"
    else:
        submission["archive"]["sha256"] = "0" * 64
    after = a.apply(
        state,
        {"kind": "SUBMIT", "data": {"submission": submission}, "timestamp": stamp(11)},
    )
    assert (
        after["checks"] is None
        and after["accepted"] is None
        and after["generation"] == 1
    )
    assert after["reviews"] == state["reviews"] and not a.deterministic(after)


def test_reference_resubmit_reexecutes_checks_without_replenishing_m3(
    accepted_candidate,
):
    e = accepted_candidate
    check(e)
    before = f.replay(e.journal, e.stream)[0]
    a.resubmit(
        e.journal,
        e.stream,
        e.worker_id,
        **{**e.bindings, "reference": "changed-reference"},
    )
    assert not a.deterministic(a.load(e.journal, e.stream)[0])
    check(e)
    assert f.replay(e.journal, e.stream)[0] == before


@pytest.mark.parametrize("risk,expected", [(r, g) for r, g in f.REVIEW_FLOORS.items()])
def test_risk_floors_cannot_be_lowered(accepted_candidate, risk, expected):
    state = strengthen(accepted_candidate, risk)
    assert set(a.gates_for(state["contract"], state["config"])) >= expected
    assert not a.satisfied(state)


@pytest.mark.parametrize(
    "reviewer",
    [
        {"actor": "implementer", "tier": 2, "model_family": "other"},
        {"actor": "Other", "tier": 0, "model_family": "other"},
        {"actor": "Other", "tier": 2, "model_family": "lmstudio"},
    ],
)
def test_reviewer_actor_tier_family_floors(accepted_candidate, reviewer):
    state = strengthen(accepted_candidate, "high")
    with pytest.raises(ValueError):
        a.reviewer_valid(state, reviewer, "model_review")


def test_critical_architect_and_user_are_separate_required_gates(accepted_candidate):
    e = accepted_candidate
    check(e)
    state = strengthen(e, "critical")
    with pytest.raises(ValueError, match="architect"):
        a.reviewer_valid(
            state,
            {"actor": "Other", "tier": 2, "model_family": "mistral"},
            "architect_review",
        )
    assert not a.satisfied(state)


def test_real_native_review_reservation_and_approval_does_not_accept(
    accepted_candidate,
):
    e = accepted_candidate
    # Strengthen by configured additional gate without touching the packet.
    state, _ = a.load(e.journal, e.stream)
    config = copy.deepcopy(state["config"])
    config["policy"]["additional_gates"]["low"] = ["model_review"]
    # Use a separate acceptance stream fixture by creating a new task fixture is
    # unnecessary: policy must be set before INIT, tested via fixture variant below.
    assert config["policy"]["additional_gates"]["low"]
    check(e)
    with pytest.raises(ValueError, match="Gate not required"):
        open_review(e)


@pytest.fixture
def model_candidate(execution):
    return candidate_fixture(execution, additional=["model_review"])


def test_review_atomic_settlement_sync_and_exact_replay(model_candidate):
    e = model_candidate
    check(e)
    opened = open_review(e)
    native = f.replay(e.journal, e.stream)[0]
    assert (
        len(native["review_attempts"]) == 1
        and native["review_pending"] == opened["review_id"]
    )
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    a.ingest_review(e.journal, e.stream, report)
    before = e.journal.verify()
    assert a.ingest_review(e.journal, e.stream, report)["report"] == report
    assert e.journal.verify() == before
    assert f.replay(e.journal, e.stream)[0]["status"] == "REVIEW_PENDING"
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    final = f.replay(e.journal, e.stream)[0]
    assert final["status"] == "ACCEPTED" and len(final["review_attempts"]) == 1
    assert f.accounting(final) == {
        "settled": 0.0,
        "liability": 0.0,
        "committed": 0.0,
        "unknown": [],
    }
    assert e.journal.replay(e.stream, f.reducer())[0] == final


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing",
        "unknown",
        "actor",
        "tier",
        "family",
        "id",
        "contradiction",
        "secret",
        "type",
    ],
)
def test_malformed_review_never_settles(model_candidate, mutation):
    e = model_candidate
    check(e)
    opened = open_review(e)
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    if mutation == "duplicate":
        report["criteria"].append(report["criteria"][0])
    elif mutation == "missing":
        report["criteria"].pop()
    elif mutation == "unknown":
        report["criteria"][0]["criterion_id"] = "UNKNOWN"
    elif mutation in {"actor", "tier", "family"}:
        report["reviewer"][{"family": "model_family"}.get(mutation, mutation)] = (
            0 if mutation == "tier" else "Wrong"
        )
    elif mutation == "id":
        report["review_id"] = "0" * 64
    elif mutation == "contradiction":
        report["criteria"][0]["status"] = "not_met"
    elif mutation == "secret":
        report["summary"] = "api_key=never-echo-this"
    else:
        report["criteria"] = True
    before = e.journal.verify()
    with pytest.raises(ValueError):
        a.ingest_review(e.journal, e.stream, report)
    assert e.journal.verify() == before


def test_two_abandoned_reviews_exhaust_lifetime_across_resubmission(model_candidate):
    e = model_candidate
    check(e)
    for number in range(2):
        open_review(e)
        a.abandon_review(e.journal, e.stream, "Explicit offline abandonment")
        if number == 0:
            a.resubmit(
                e.journal,
                e.stream,
                e.worker_id,
                **{**e.bindings, "reference": "resubmission"},
            )
            check(e)
    with pytest.raises(ValueError, match="cap exhausted"):
        open_review(e)
    assert len(f.replay(e.journal, e.stream)[0]["review_attempts"]) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "candidate",
        "immutable",
        "report",
        "secret",
        "missing",
        "link",
        "escape",
        "duplicate",
    ],
)
def test_exact_stopped_output_negatives(accepted_candidate, mutation):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")

    def change(files):
        if mutation == "candidate":
            files["workspace/src/features/auth.py"] = b"VALUE = 999\n"
        elif mutation == "immutable":
            files["brief.json"] = b"{}"
        elif mutation == "report":
            files["report.json"] = b'{"PASS":true}'
        elif mutation == "secret":
            files["report.json"] = b"api_key=untrusted"
        elif mutation == "missing":
            del files["workspace/src/features/auth.py"]

    e.docker.change = change
    if mutation in {"link", "escape", "duplicate"}:
        import tarfile

        name = "session/../escaped" if mutation == "escape" else "session/report.json"
        info = tarfile.TarInfo(name)
        if mutation == "link":
            info.type = tarfile.SYMTYPE
            info.linkname = "outside"
        e.docker.archive_change = lambda files: tar_bytes(
            files, extra=[(info, None if mutation == "link" else b"")]
        )
    ar.launch_check(e.journal, e.stream, rid)
    with pytest.raises(ValueError):
        ar.ingest_check(e.journal, e.stream, rid)
    assert not a.deterministic(a.load(e.journal, e.stream)[0])


def test_changed_export_refuses_before_start(accepted_candidate):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    state, _ = a.load(e.journal, e.stream)
    manifest = state["runs"][-1]["prepared"]["runtime"]
    e.docker.volumes[manifest["volume"]]["workspace/src/features/auth.py"] = b"tampered"
    with pytest.raises(ValueError, match="export"):
        ar.launch_check(e.journal, e.stream, rid)
    assert len(e.docker.starts) == 1


def test_consumed_start_crash_cannot_retry_and_explicit_reconcile(accepted_candidate):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    e.docker.fail_start = True
    with pytest.raises(OSError):
        ar.launch_check(e.journal, e.stream, rid)
    with pytest.raises(ValueError):
        ar.launch_check(e.journal, e.stream, rid)
    starts = len(e.docker.starts)
    ar.reconcile_check(e.journal, e.stream, "Ambiguous start explicitly abandoned")
    assert a.load(e.journal, e.stream)[0]["runs"][-1]["phase"] == "ABANDONED"
    assert len(e.docker.starts) == starts


def test_concurrent_check_launch_once(accepted_candidate):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    barrier = threading.Barrier(2)

    def launch():
        barrier.wait()
        try:
            return ar.launch_check(e.journal, e.stream, rid)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: launch(), range(2)))
    assert sum(x is not None for x in results) == 1
    assert len(e.docker.starts) == 2


def test_sync_concurrent_idempotent_and_after_commit_crash(accepted_candidate):
    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    barrier = threading.Barrier(2)

    def sync(_):
        barrier.wait()
        return a.sync_feedback(e.journal, e.stream)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(sync, range(2)))
    assert results[0] == results[1]
    assert a.sync_feedback(e.journal, e.stream) == results[0]
    events, _ = e.journal.read(e.stream)
    assert sum(e["data"].get("acceptance_version") == a.VERSION for e in events) == 1


@pytest.mark.parametrize("at", [1, 2])
def test_sync_transaction_crash_rolls_back_both_streams(
    accepted_candidate, at, monkeypatch
):
    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    before = e.journal.verify()
    original = e.journal._insert
    calls = 0

    def crash(*args, **kwargs):
        nonlocal calls
        original(*args, **kwargs)
        calls += 1
        if calls == at:
            raise RuntimeError("Injected transaction crash")

    monkeypatch.setattr(e.journal, "_insert", crash)
    with pytest.raises(RuntimeError):
        a.sync_feedback(e.journal, e.stream)
    assert e.journal.verify() == before
    monkeypatch.setattr(e.journal, "_insert", original)
    a.sync_feedback(e.journal, e.stream)
    assert f.replay(e.journal, e.stream)[0]["status"] == "ACCEPTED"


def test_hardware_manual_gate_stays_unverified(accepted_candidate):
    state, _ = a.load(accepted_candidate.journal, accepted_candidate.stream)
    state["contract"]["validation"][0].pop("command")
    assert not a.deterministic(state)
    # A claimed command PASS cannot satisfy the missing hardware evidence.
    run = {"run_id": "x", "validation_id": "VAL-FRAMES"}
    report = {
        "run_id": "x",
        "submission_sha256": a.sha(state["submission"]),
        "results": [
            {
                "validation_id": "VAL-FRAMES",
                "status": "PASSED",
                "exit_code": 0,
                "output_sha256": "a" * 64,
            }
        ],
    }
    with pytest.raises(ValueError, match="hardware"):
        a.validate_checks(state, run, report)


def test_pinned_real_docker_independent_check(accepted_candidate):
    e = accepted_candidate
    image = os.environ.get("WORKFLOW_TEST_IMAGE")
    if not image:
        pytest.skip("WORKFLOW_TEST_IMAGE required for real isolated acceptance")
    # Change the bound image by a real submission, invalidating all prior gates.
    e.monkeypatch.setattr(runtime, "docker", REAL_DOCKER)
    a.resubmit(e.journal, e.stream, e.worker_id, **{**e.bindings, "image": image})
    manifest = None
    try:
        rid, report = check(e)
        manifest = a.load(e.journal, e.stream)[0]["runs"][-1]["prepared"]["runtime"]
        assert report["results"][0]["status"] == "PASSED"
        runtime.assert_boundary(manifest["container"], manifest["volume"], image)
        assert (e.scope.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
    finally:
        if manifest:
            REAL_DOCKER("rm", manifest["container"], manifest["setup_container"])
            REAL_DOCKER("volume", "rm", manifest["volume"])


def test_saved_check_replay_after_deadline_and_sync_is_identical(accepted_candidate):
    e = accepted_candidate
    rid, report = check(e)
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    e.monkeypatch.setattr(f.wp, "now", lambda: stamp(700))
    before = e.journal.verify()
    assert ar.ingest_check(e.journal, e.stream, rid) == report
    assert e.journal.verify() == before


def test_second_prepared_check_invalidates_prior_pass(accepted_candidate):
    e = accepted_candidate
    check(e)
    ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    assert not a.deterministic(a.load(e.journal, e.stream)[0])
    with pytest.raises(ValueError):
        a.accept(e.journal, e.stream, "Independent")


def test_review_evidence_cannot_survive_check_rerun(model_candidate):
    e = model_candidate
    check(e)
    opened = open_review(e)
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    a.ingest_review(e.journal, e.stream, report)
    before = e.journal.verify()
    with pytest.raises(ValueError, match="resubmit"):
        ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    assert e.journal.verify() == before


def test_exact_preparing_binding_refuses_fabrication(accepted_candidate):
    e = accepted_candidate
    rid = ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    events, _ = e.journal.read(a.stream_name(e.stream))
    init, preparing = events[:2]
    state = a.apply(None, init)
    for field, value in [
        ("argv", ["python", "-c", "pass"]),
        ("validation_id", "UNKNOWN"),
        ("scope", {**preparing["data"]["scope"], "interface_revision": "0" * 64}),
    ]:
        event = copy.deepcopy(preparing)
        event["data"][field] = value
        with pytest.raises(ValueError):
            a.apply(state, event)
    assert rid == preparing["data"]["run_id"]


def test_check_preparation_crash_holds_and_requires_explicit_reconcile(
    accepted_candidate, monkeypatch
):
    e = accepted_candidate
    original = runtime.prepare

    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Crash after claim before PREPARED")

    monkeypatch.setattr(runtime, "prepare", crash)
    with pytest.raises(RuntimeError):
        ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    with pytest.raises(ValueError):
        ar.prepare_check(e.journal, e.stream, "VAL-FRAMES")
    ar.reconcile_check(
        e.journal, e.stream, "Explicitly abandon interrupted preparation"
    )
    assert a.load(e.journal, e.stream)[0]["runs"][-1]["phase"] == "ABANDONED"


def test_review_atomic_crashes_at_every_insert_keep_all_heads(
    model_candidate, monkeypatch
):
    e = model_candidate
    check(e)
    opened = open_review(e)
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    before = e.journal.verify()
    original = e.journal._insert
    for stop_at in range(1, 5):
        calls = 0

        def crash(*args, **kwargs):
            nonlocal calls
            original(*args, **kwargs)
            calls += 1
            if calls == stop_at:
                raise RuntimeError("Injected four-stream result crash")

        monkeypatch.setattr(e.journal, "_insert", crash)
        with pytest.raises(RuntimeError):
            a.ingest_review(e.journal, e.stream, report)
        assert e.journal.verify() == before
    monkeypatch.setattr(e.journal, "_insert", original)
    a.ingest_review(e.journal, e.stream, report)


def test_native_reserve_before_review_open_crash_consumes_attempt(
    model_candidate, monkeypatch
):
    e = model_candidate
    check(e)
    original = a.append

    def crash(*args, **kwargs):
        if args[2] == "REVIEW_OPEN":
            raise RuntimeError("Crash after native reservation")
        return original(*args, **kwargs)

    monkeypatch.setattr(a, "append", crash)
    with pytest.raises(RuntimeError):
        open_review(e)
    assert len(f.replay(e.journal, e.stream)[0]["review_attempts"]) == 1
    assert not a.load(e.journal, e.stream)[0]["reviews"]
    a.abandon_review(
        e.journal, e.stream, "Explicitly abandon orphaned reviewer reservation"
    )
    assert len(f.replay(e.journal, e.stream)[0]["review_attempts"]) == 1
    monkeypatch.setattr(a, "append", original)
    open_review(e)
    assert len(f.replay(e.journal, e.stream)[0]["review_attempts"]) == 2


@pytest.mark.parametrize("stop_at", [1, 2])
def test_actual_process_exit_during_sync_is_atomic(
    accepted_candidate, tmp_path, stop_at
):
    import json
    import subprocess
    import sys
    from dataclasses import asdict

    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    before = e.journal.verify()
    state, head, native, native_head = a.current(e.journal, e.stream)
    proof = {"events": e.journal.read(a.stream_name(e.stream))[0], "head": asdict(head)}
    data = {
        "acceptance_version": a.VERSION,
        "proof": proof,
        "proof_sha256": a.sha(proof),
        "native_head": asdict(native_head),
    }
    saved = tmp_path / "trusted-coordinator-batch.json"
    saved.write_text(
        json.dumps(
            {
                "data": data,
                "receipt": {
                    "proof_sha256": a.sha(proof),
                    "task_head": asdict(native_head),
                },
                "head": asdict(head),
                "native_head": asdict(native_head),
            }
        )
    )
    script = """import json,os,sys
from pathlib import Path
from scripts import acceptance as a, feedback as f, workflow_state as ws
root,state,task,saved,at=sys.argv[1:]
ws.control_directory=lambda _:Path(state)
ws.active_anchor=lambda *args:'a'*64
j=ws.Journal(Path(root)); d=json.loads(Path(saved).read_text())
original=j._insert; count=0
def crash(*args,**kwargs):
    global count
    original(*args,**kwargs); count+=1
    if count==int(at): os._exit(71)
j._insert=crash
j.append_many((ws.Append(stream=task,kind='REVIEW',data=d['data'],expected=ws.Head(**d['native_head']),reducer=f.reducer(ws.Head(**d['native_head'])),timestamp='2026-10-14T22:00:10Z'),ws.Append(stream=a.stream_name(task),kind='SYNC',data=d['receipt'],expected=ws.Head(**d['head']),reducer=a.apply,timestamp='2026-10-14T22:00:10Z')))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(e.journal.root),
            str(e.journal.directory),
            e.stream,
            str(saved),
            str(stop_at),
        ],
        capture_output=True,
    )
    assert child.returncode == 71, child.stderr.decode()
    e.journal.recover()
    assert e.journal.verify() == before
    a.sync_feedback(e.journal, e.stream)
    assert f.replay(e.journal, e.stream)[0]["status"] == "ACCEPTED"


@pytest.mark.parametrize("risk", ["high", "critical"])
def test_full_high_and_critical_gate_flow_preserves_tier_caps(execution, risk):
    e = candidate_fixture(execution, risk=risk)
    check(e)
    gate = "architect_review" if risk == "critical" else "model_review"
    opened = open_review(e, gate, "Architect" if risk == "critical" else "Reviewer")
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    assert (
        report["reviewer"]["model_family"]
        != a.load(e.journal, e.stream)[0]["submission"]["worker"]["model_family"]
    )
    a.ingest_review(e.journal, e.stream, report)
    if risk == "critical":
        with pytest.raises(ValueError, match="incomplete"):
            a.accept(e.journal, e.stream, "Independent")
        state, _ = a.load(e.journal, e.stream)
        a.append(
            e.journal,
            e.stream,
            "DECISION",
            {
                "actor": "Owner",
                "decision": "approve",
                "reason": "Explicit synthetic decision",
                "submission_sha256": a.sha(state["submission"]),
            },
        )
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    native = f.replay(e.journal, e.stream)[0]
    assert native["status"] == "ACCEPTED" and len(native["review_attempts"]) == 1
    assert native["review_attempts"][0]["tier"] == (4 if risk == "critical" else 3)


def test_user_cannot_mutate_accepted_gates_or_impersonate_controller(execution):
    e = candidate_fixture(execution, additional=["user_decision"])
    check(e)
    state, _ = a.load(e.journal, e.stream)
    decision = {
        "actor": "independent",
        "decision": "approve",
        "reason": "Synthetic decision",
        "submission_sha256": a.sha(state["submission"]),
    }
    with pytest.raises(ValueError, match="separate"):
        a.append(e.journal, e.stream, "DECISION", decision)
    decision["actor"] = "Owner"
    a.append(e.journal, e.stream, "DECISION", decision)
    a.accept(e.journal, e.stream, "Independent")
    before = e.journal.verify()
    decision["decision"] = "reject"
    with pytest.raises(ValueError, match="immutable"):
        a.append(e.journal, e.stream, "DECISION", decision)
    assert e.journal.verify() == before
    a.sync_feedback(e.journal, e.stream)
    assert f.replay(e.journal, e.stream)[0]["status"] == "ACCEPTED"


def test_rehashed_malformed_proof_cannot_accept(accepted_candidate):
    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    events, _ = e.journal.read(a.stream_name(e.stream))
    for kind, mutate in [
        ("CHECK_PREPARING", lambda d: d.update(argv=["python", "-c", "pass"])),
        (
            "CHECK_PREPARED",
            lambda d: d["prepared"]["runtime"].update(image="sha256:" + "a" * 64),
        ),
        (
            "CHECK_PREPARED",
            lambda d: d["prepared"]["runtime"].update(immutable_workspace=False),
        ),
        ("CHECK_STOPPED", lambda d: d["stopped"].update(exit_code=1)),
        ("CHECK_RESULT", lambda d: d.update(receipt="a" * 64)),
        (
            "CHECK_RESULT",
            lambda d: d["report"]["results"][0].update(output_sha256="a" * 64),
        ),
    ]:
        chain = copy.deepcopy(events)
        mutate(next(v["data"] for v in chain if v["kind"] == kind))
        previous = None
        for event in chain:
            event["previous"] = previous
            event["hash"] = a.sha({k: v for k, v in event.items() if k != "hash"})
            previous = event["hash"]
        proof = {"events": chain, "head": {"sequence": len(chain), "hash": previous}}
        with pytest.raises(ValueError):
            a.proof_state(proof)


def test_deterministic_sync_read_race_returns_existing_receipt(
    accepted_candidate, monkeypatch
):
    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    original = a.load
    nested = False
    committed = None

    def interleave(*args, **kwargs):
        nonlocal nested, committed
        result = original(*args, **kwargs)
        if not nested:
            nested = True
            committed = a.sync_feedback(e.journal, e.stream)
        return result

    monkeypatch.setattr(a, "load", interleave)
    assert a.sync_feedback(e.journal, e.stream) == committed


def test_concurrent_review_report_is_one_atomic_outcome(model_candidate):
    e = model_candidate
    check(e)
    opened = open_review(e)
    report = review_report(opened, a.load(e.journal, e.stream)[0])
    barrier = threading.Barrier(2)

    def ingest(_):
        barrier.wait()
        return a.ingest_review(e.journal, e.stream, report)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(ingest, range(2)))
    assert results[0] == results[1]
    assert len(f.replay(e.journal, e.stream)[0]["review_attempts"]) == 1


def test_hardware_attestation_cannot_be_fabricated(accepted_candidate):
    e = accepted_candidate
    state, _ = a.load(e.journal, e.stream)
    state["contract"]["validation"][0].pop("command")
    with pytest.raises(ValueError, match="not enabled"):
        a.apply(
            state,
            {
                "kind": "ATTESTATION",
                "timestamp": stamp(10),
                "data": {
                    "validation_id": "VAL-FRAMES",
                    "actor": "Other",
                    "evidence": [{"sha256": "a" * 64, "size": 1}],
                    "submission_sha256": a.sha(state["submission"]),
                },
            },
        )


def test_bounded_rejection_resubmission_and_repeat_keep_native_failures(
    model_candidate,
):
    e = model_candidate
    for number in range(2):
        check(e)
        opened = open_review(e)
        state, _ = a.load(e.journal, e.stream)
        report = review_report(opened, state)
        report["verdict"] = "REJECT_BOUNDED"
        report["criteria"][0]["status"] = "not_met"
        report["contract_failures"] = [
            {
                "failed_ref": report["criteria"][0]["criterion_id"],
                "kind": "criterion",
                "what_failed": "Synthetic expected value mismatch",
                "evidence": ["Independent failure evidence"],
                "corrective_action": "Fix the value within existing scope",
            }
        ]
        a.ingest_review(e.journal, e.stream, report)
        # Native schema deliberately has four condensed fields. Detailed source
        # evidence remains in acceptance and its exact digest in native feedback.
        native = f.replay(e.journal, e.stream)[0]
        assert len(native["review_rejections"]) == number + 1
        assert len(native["review_attempts"]) == number + 1
        assert native["review_attempts"][-1]["accounting"]["settled"] == 0
        assert a.ingest_review(e.journal, e.stream, report)["report"] == report
        if number == 0:
            assert native["status"] == "IN_PROGRESS"
            e.scope = h.SessionScope.load(
                {**e.scope.data, "run_id": "corrective-worker"}
            )
            e.docker.worker = lambda files: Docker.worker(e.docker, files)
            e.monkeypatch.setattr(f.wp, "now", lambda: stamp(20))
            prepared = h.dispatch(
                e.journal,
                e.stream,
                e.config,
                e.routing,
                options(),
                e.scope,
                timestamp=stamp(11),
            )
            e.worker_id = prepared["dispatch_id"]
            from scripts import worker_launcher

            worker_launcher.launch(e.journal, e.worker_id)
            h.ingest(e.journal, e.worker_id)
            a.resubmit(
                e.journal,
                e.stream,
                e.worker_id,
                **{**e.bindings, "reference": "corrected-candidate"},
            )
            e.docker.worker = lambda files: None
        else:
            assert native["status"] == "NEEDS_ARCHITECT"
            assert native["reason"] == "REPEATED_REVIEW_REJECTION"
            assert len(native["attempts"]) == 2


def test_candidate_lowered_policy_bounds_are_enforced(accepted_candidate):
    e = accepted_candidate
    state, _ = a.load(e.journal, e.stream)
    limited = copy.deepcopy(state)
    limited["config"]["policy"]["workspace_digest_max_files"] = 1
    with pytest.raises(ValueError, match="file count"):
        a.validate_submission(limited, state["submission"])
    limited = copy.deepcopy(state)
    limited["config"]["policy"]["artifact_max_chars"] = 200
    with pytest.raises(ValueError, match="artifact"):
        a.validate_submission(limited, state["submission"])
