"""One operator walkthrough: real Docker, disposable authority, fixture hosting.

This composes existing controllers and test fixtures; it is not an orchestrator
or a way to enable execution against the shipped ACTIVE foundation.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import acceptance as a
from scripts import acceptance_runtime as ar
from scripts import execution_harness as h
from scripts import feedback as f
from scripts import worker_launcher as launcher
from scripts import workflow_closeout as c
from scripts import workflow_handoff as v
from scripts import workflow_runtime as runtime
from test_execution_harness import execution as _execution, REAL_DOCKER
from test_feedback import journal as _journal, options, stamp, start
from test_model_router import make_packet
from test_workflow_closeout import commit_candidate, live

journal = _journal
execution = _execution

# Exported as one immutable fixture input; only the owned auth file is writable.
WORKER = """import base64, hashlib, json, sys
from pathlib import Path
def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
brief = json.loads(Path(sys.argv[1]).read_text())
dispatch = json.loads(Path('/session/dispatch.json').read_text())
baseline = json.loads(Path('/session/baseline.json').read_text())
payload = b'VALUE = 2\\n'
Path('src/features/auth.py').write_bytes(payload)
bundle = dict(scope_sha256=dispatch['scope_sha256'], base_commit=dispatch['base_commit'], changes=[dict(path='src/features/auth.py', before_sha256=baseline['src/features/auth.py'], content_base64=base64.b64encode(payload).decode())])
checks = [dict(check_id=item['id'], passed=True, failure_code='', expected='fixture', actual='fixture', evidence=['Worker claim; independent checks still required']) for item in brief['context']['contract']['validation']]
report = dict(dispatch_id=dispatch['dispatch_id'], outcome='PASS', summary='Deterministic offline replacement', scope_status='within', architecture_conflict=False, validation=checks, evidence=['Scoped fixture replacement'], discoveries=[], api_cost_usd=0, cost_evidence='Unmetered; no provider', run=dict(binding_sha256=dispatch['binding_sha256'], deadline=dispatch['deadline'], bundle_sha256=hashlib.sha256(canon(bundle).encode()).hexdigest()))
Path(sys.argv[2]).write_text(canon(report))
"""

CHECKS = {
    "contract": "from src.features.auth import VALUE; assert VALUE == 2",
    "boundary": """from pathlib import Path
import socket
assert not Path('/session/workspace/.git').exists()
assert not Path('/var/run/docker.sock').exists()
for name in ('src/features/auth.py', 'contracts/auth.py'):
    p = Path(name)
    assert p.stat().st_uid == 0
    try:
        p.write_bytes(b'tampered')
    except OSError:
        pass
    else:
        raise AssertionError('candidate writable')
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(('1.1.1.1', 443))
except OSError:
    pass
else:
    raise AssertionError('network available')
finally:
    s.close()
""",
    "affected-runtime": "import runpy; assert runpy.run_path('src/features/auth.py')['VALUE'] == 2",
}


def test_offline_operator_workflow(execution, tmp_path):
    image = os.environ.get("WORKFLOW_TEST_IMAGE")
    if not image:
        pytest.skip(reason="WORKFLOW_TEST_IMAGE required; a skip is not operator proof")
    e = execution
    e.monkeypatch.setattr(runtime, "docker", REAL_DOCKER)
    source = Path(__file__).resolve().parents[1]
    receipt_before = (source / "config/workflow-bootstrap.json").read_bytes()
    root = e.journal.root
    worker = root / "tests/test_feature_auth.py"
    worker.parent.mkdir()
    worker.write_text(WORKER, encoding="utf-8")
    (root / ".git/info/exclude").write_text("/config/\n")
    for args in (
        ("add", "tests"),
        (
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "Explicit offline worker input",
        ),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    base = v.git(root, "rev-parse", "HEAD").decode().strip()
    contract = f.wp.current(make_packet(retries=2, reviewer=2))["contract"]
    contract.update(
        title="Replace one fixture value offline",
        goal="Replace VALUE = 1 with VALUE = 2 in the owned fixture file.",
        parent={
            "objective": "Prove the existing disposable offline operator workflow.",
            "milestone": "Accept an exact unapplied fixture replacement independently.",
        },
        scope={
            "allowed": ["Replace only src/features/auth.py with VALUE = 2."],
            "prohibited": [
                "Change contracts, sibling features, authority or host files."
            ],
        },
        inputs=[
            {
                "name": "Fixture source",
                "description": "src/features/auth.py contains VALUE = 1.",
            }
        ],
        outputs=[
            {
                "name": "Replacement",
                "description": "Exact VALUE = 2 source and bound worker report.",
            }
        ],
        interface={
            "name": "fixture_value",
            "version": "1.0",
            "description": "A module-level VALUE integer; no production application interface change.",
        },
        assumptions=["All inputs are fictional; no physical device has been observed."],
        sources=[
            {
                "id": "SRC-OPERATOR-VALUE",
                "reference": "The constant replacement and independent checks embedded in this fixture.",
                "authority": "Synthetic fixture specification only.",
            }
        ],
        context_scope=[
            "This packet, immutable contract, owned source and worker fixture."
        ],
        architecture_boundaries=[
            "Preserve the existing immutable export and independent acceptance boundary."
        ],
        acceptance_criteria=[
            {
                "id": "AC-EXACT",
                "description": "Exact replacement passes independent checks.",
            }
        ],
        validation=[
            {
                "id": "VAL-" + name.upper(),
                "description": name,
                "criterion_ids": ["AC-EXACT"],
                "evidence_required": ["Independent stopped log"],
                "command": {
                    "argv": [
                        "python",
                        "-B",
                        "-c",
                        code + "\nprint('PASSED: " + name + "')",
                    ],
                    "timeout_seconds": 60,
                },
            }
            for name, code in CHECKS.items()
        ],
    )
    contract["domain"].update(
        component="simulator_fake",
        hardware_assumptions=[
            {
                "assumption": "A fictional device would use VALUE = 2; this is unobserved fixture data.",
                "source_id": "SRC-OPERATOR-VALUE",
            }
        ],
        protocol_references=["SRC-OPERATOR-VALUE"],
    )
    contract["domain"]["validation_levels"] = {
        item["id"]: "unit" for item in contract["validation"]
    }
    packet = f.wp.create(
        "OPERATOR",
        "software-hardware",
        contract,
        "Architect",
        "Fixture authority only",
        stamp(),
    )
    for target in ("ARCHITECTED", "READY"):
        packet = f.wp.transition(
            packet,
            target,
            "architect",
            "Architect",
            "Fixture",
            ["Offline specification"],
            timestamp=stamp(),
        )
    e.stream, _ = start(e.journal, name="OPERATOR", settings=e.routing, packet=packet)
    e.scope = h.SessionScope.load(
        {
            **e.scope.data,
            "base_commit": base,
            "run_id": "operator-proof",
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
    (tmp_path / "packet.json").write_bytes(h.json_bytes(packet))
    (tmp_path / "scope.json").write_bytes(h.json_bytes(e.scope.data))
    clean = v.build(e.journal, e.stream, scope=e.scope.data)
    assert not v.resume(e.journal, clean)["execution_authorized"]

    manifests = []
    try:
        prepared = h.dispatch(
            e.journal,
            e.stream,
            e.config,
            e.routing,
            options(),
            e.scope,
            timestamp=stamp(1),
        )
        dispatch_id = prepared["dispatch_id"]
        manifests.append(h.load(e.journal, dispatch_id)[0]["prepared"]["runtime"])
        saved = tmp_path / "handoff.json"
        saved.write_bytes(h.json_bytes(v.build(e.journal, e.stream)))
        heads = e.journal.verify()
        # New Journal instance and disk-loaded view model a coordinator resume.
        resumed = v.resume(h.ws.Journal(root), json.loads(saved.read_bytes()))
        assert "EXPLICIT_LAUNCH_OR_ABANDON" in resumed["next_action"]
        assert not resumed["execution_authorized"] and not resumed["retry_granted"]
        assert e.journal.verify() == heads
        launcher.prepared_run(e.journal, dispatch_id)
        launcher.launch(e.journal, dispatch_id)
        worker_receipt = h.ingest(e.journal, dispatch_id)
        assert worker_receipt["status"] == "INDEPENDENT_ACCEPTANCE_PENDING"
        with pytest.raises(ValueError):
            v.resume(e.journal, json.loads(saved.read_bytes()))
        a.initialize(
            e.journal,
            e.stream,
            dispatch_id,
            f.wp.read_json(source / "config/acceptance.json"),
            "Independent",
            "Architect",
            reference="stopped-replacement:" + dispatch_id,
            commits={name: base for name in ("feature", "ui", "base")},
            image=image,
        )
        with pytest.raises(ValueError, match="incomplete"):
            a.accept(e.journal, e.stream, "Independent")
        logs = {}
        for name in CHECKS:
            rid = ar.prepare_check(e.journal, e.stream, "VAL-" + name.upper())
            manifests.append(
                a.load(e.journal, e.stream)[0]["runs"][-1]["prepared"]["runtime"]
            )
            ar.launch_check(e.journal, e.stream, rid)
            report = ar.ingest_check(e.journal, e.stream, rid)
            assert report["results"][0]["status"] == "PASSED"
            logs[name] = asdict(
                e.journal.evidence(
                    (h.run_path(e.journal, rid) / "stdout.log")
                    .relative_to(e.journal.directory)
                    .as_posix()
                )
            )
        a.accept(e.journal, e.stream, "Independent")
        synchronized = a.sync_feedback(e.journal, e.stream)
        assert a.sync_feedback(e.journal, e.stream) == synchronized
        native = f.replay(e.journal, e.stream)[0]
        assert native["status"] == "ACCEPTED" and len(native["attempts"]) == 1
        assert not f.accounting(native)["unknown"]
        assert all(
            f.accounting(native)[name] == 0
            for name in ("committed", "settled", "liability")
        )
        assert (root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
        assert len({m["volume"] for m in manifests}) == 4
        for m in manifests:
            runtime.assert_boundary(m["container"], m["volume"], image)
            assert runtime.stopped(m["container"])

        # Only this exact candidate exists in the disposable Git object database.
        e.candidate = commit_candidate(e, tmp_path)
        v.git(root, "branch", "feature/release", e.candidate)
        proof = e.journal.directory / "run-operator-integration"
        proof.mkdir()
        review = proof / "review.txt"
        review.write_text(
            "Fixture independent actor declaration: exact VALUE replacement; synthetic review, no live approval.\n"
        )
        manifest = {
            "binding": c.candidate_tree(
                e.journal, a.load(e.journal, e.stream)[0]["submission"], e.candidate
            ),
            "checks": [
                {"id": name, "status": "PASSED", "log": logs[name]} for name in CHECKS
            ],
            "review": {
                "actor": "Independent",
                "head": e.candidate,
                "verdict": "APPROVE",
                "report": asdict(
                    e.journal.evidence(
                        review.relative_to(e.journal.directory).as_posix()
                    )
                ),
            },
            "interface_change": None,
        }
        path = proof / "manifest.json"
        path.write_bytes(h.json_bytes(manifest))
        validation = c.record_validation(
            e.journal,
            e.stream,
            e.candidate,
            path.relative_to(e.journal.directory).as_posix(),
        )
        hosting = live(e, e.candidate)
        e.monkeypatch.setattr(
            c, "hosting", lambda *args: json.loads(json.dumps(hosting))
        )
        held = c.assess(e.journal, e.stream, e.candidate, validation, 1)
        assert held["readiness"] == "HOLD"
        assert "RETAINED_BRANCH_BASELINE_REQUIRED" in held["blockers"]
        ready = c.assess(
            e.journal,
            e.stream,
            e.candidate,
            validation,
            1,
            retained=held["retained_refs"],
        )
        assert ready["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION", ready
        assert not ready["merge_authorized"] and not ready["execution_authorized"]
        assert ready["integrated"] == ready["deployed"] == "NOT_ESTABLISHED"
        assert (
            source / "config/workflow-bootstrap.json"
        ).read_bytes() == receipt_before
        e.journal.verify()
        summary = {
            "authority": "DISPOSABLE_FIXTURE_ONLY",
            "hosting": "SIMULATED; no live PR",
            "image": image,
            "packet": "OPERATOR",
            "scope": e.scope.data,
            "resumed": resumed,
            "worker": worker_receipt,
            "checks": logs,
            "native_status": native["status"],
            "attempts": len(native["attempts"]),
            "accounting": f.accounting(native),
            "readiness": ready,
            "state": str(e.journal.directory),
            "hardware": "UNVERIFIED_ON_HARDWARE",
        }
        (tmp_path / "operator-proof.json").write_bytes(h.json_bytes(summary))
        print("Operator proof: " + str(tmp_path / "operator-proof.json"))
    finally:
        # Remove only this proof's stopped Docker objects; retain disk evidence.
        for m in manifests:
            if runtime.stopped(m["container"]) and runtime.stopped(
                m["setup_container"]
            ):
                REAL_DOCKER("rm", m["container"], m["setup_container"])
                REAL_DOCKER("volume", "rm", m["volume"])
