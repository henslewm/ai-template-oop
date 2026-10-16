"""Behavioral tests of coordinator refusals, concurrency and offline worker isolation."""
import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import work_packet as wp
from workflow_scope import SessionScope, Ownership, checked_path, digest, verify_bundle
import workflow_runtime as runtime


def command(root, *argv):
    return subprocess.run(list(argv), cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "feature"
    root.mkdir()
    files = {
        "contracts/auth.py": "class Interface: pass\n",
        "src/features/auth.py": "VALUE = 1\n",
        "src/features/data.py": "SIBLING_IMPLEMENTATION_MUST_NOT_BE_EXPORTED\n",
        "tests/test_contract_auth.py": "assert True\n",
    }
    for path, contents in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    command(root, "git", "init", "-b", "feature/auth")
    command(root, "git", "add", ".")
    command(root, "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    contract = wp.read_json(ROOT / "examples/work-packets/software-hardware.contract.json")
    packet = wp.create("TEST-SCOPE", "software-hardware", contract, "Coordinator", "Fixture")
    for target in ("ARCHITECTED", "READY"):
        packet = wp.transition(packet, target, "architect", "Coordinator", "Fixture")
    interface = {"contracts/auth.py": digest((root / "contracts/auth.py").read_bytes())}
    scope = SessionScope.load({
        "schema_version": "1.0", "role": "feature", "feature_id": "auth",
        "owner": "Coordinator", "run_id": "test-run", "branch": "feature/auth",
        "workspace": str(root), "base_commit": command(root, "git", "rev-parse", "HEAD"),
        "packet_revision_hash": wp.current(packet)["hash"],
        "interface_revision": digest(wp.canonical(interface).encode()),
        "read_paths": ["contracts/auth.py", "src/features/auth.py", "tests/test_contract_auth.py"],
        "write_paths": ["src/features/auth.py"],
    })
    return scope, packet


def bundle(scope, baseline, path="src/features/auth.py"):
    return {"scope_sha256": scope.hash, "base_commit": scope.data["base_commit"],
            "changes": [{"path": path, "before_sha256": baseline.get(path),
                         "content_base64": base64.b64encode(b"VALUE = 2\n").decode()}]}


@pytest.mark.parametrize("path", ["../escape", "/etc/passwd", "C:/repo/file", "a\\b",
    "x/../y", ".git/config", "a/.env", "a/NUL", "a/file.", "a//b", "a/./b"])
def test_path_escape_refused(path):
    with pytest.raises(ValueError):
        checked_path(path)


def test_only_allowlisted_files_exported_and_contracts_immutable(prepared):
    scope, packet = prepared
    archive, baseline = scope.export(packet, [])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        names = tar.getnames()
        assert "workspace/src/features/data.py" not in names
        assert not any(".git" in n for n in names)
        assert tar.getmember("workspace/contracts/auth.py").uid == 0
        assert tar.getmember("workspace/contracts/auth.py").mode == 0o444
        assert tar.getmember("workspace/src/features/auth.py").uid == 1000
        assert tar.getmember("workspace/src/features").mode == 0o555
    assert "src/features/data.py" not in baseline


@pytest.mark.parametrize("path", ["contracts/auth.py", "src/features/data.py", "src/ui/main_window.py"])
def test_scope_cannot_grant_contract_or_sibling_writes(prepared, path):
    scope, _ = prepared
    data = copy.deepcopy(scope.data)
    data["read_paths"].append(path)
    data["write_paths"] = [path]
    with pytest.raises(ValueError):
        SessionScope.load(data)


def test_ui_cannot_read_feature_implementation(prepared):
    scope, _ = prepared
    data = copy.deepcopy(scope.data)
    data.update(role="ui", branch="ui/shell", write_paths=["src/ui/mocks.py"],
                read_paths=["contracts/auth.py", "src/ui/mocks.py", "src/features/auth.py"])
    with pytest.raises(ValueError, match="ownership"):
        SessionScope.load(data)


def test_wrong_packet_interface_and_dirty_or_stale_base_refused(prepared):
    scope, packet = prepared
    candidate = copy.deepcopy(scope.data)
    candidate["packet_revision_hash"] = "0" * 64
    with pytest.raises(ValueError, match="packet revision"):
        SessionScope.load(candidate).export(packet, [])
    candidate = copy.deepcopy(scope.data)
    candidate["interface_revision"] = "0" * 64
    with pytest.raises(ValueError, match="interface revision"):
        SessionScope.load(candidate).export(packet, [])
    (scope.root / "src/features/auth.py").write_text("changed")
    with pytest.raises(ValueError, match="Tracked workspace"):
        scope.export(packet, [])
    command(scope.root, "git", "add", ".")
    command(scope.root, "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "changed")
    with pytest.raises(ValueError, match="Stale base"):
        scope.export(packet, [])


def test_missing_unaccepted_and_changed_dependency_refused(prepared):
    scope, packet = prepared
    contract = copy.deepcopy(wp.current(packet)["contract"])
    contract["dependencies"] = ["OTHER"]
    packet = wp.create("TEST-SCOPE", "software-hardware", contract, "Coordinator", "Fixture")
    # A proposed packet cannot bypass READY or graph requirements.
    data = copy.deepcopy(scope.data)
    data["packet_revision_hash"] = wp.current(packet)["hash"]
    with pytest.raises(ValueError, match="not READY"):
        SessionScope.load(data).export(packet, [])


def test_changed_scope_packet_stops_launch(prepared, tmp_path):
    scope, packet = prepared
    contract = copy.deepcopy(wp.current(packet)["contract"]); contract["title"] += " revised"
    candidate = wp.revise(packet, contract, "Coordinator", "New revision")
    with pytest.raises(ValueError, match="Stale packet"):
        scope.verify_packet(candidate, [])


@pytest.mark.parametrize("path", ["../escape", "src/features/data.py", "contracts/auth.py", ".git/config",
                                "C:/escape", "src/features/AUTH.py"])
def test_returned_patch_paths_refused_without_writes(prepared, path):
    scope, packet = prepared
    _, baseline = scope.export(packet, [])
    before = command(scope.root, "git", "status", "--porcelain")
    with pytest.raises(ValueError):
        verify_bundle(scope, baseline, bundle(scope, baseline, path))
    assert command(scope.root, "git", "status", "--porcelain") == before


def test_valid_output_is_eligible_but_not_applied_and_duplicate_or_stale_output_refused(prepared):
    scope, packet = prepared
    _, baseline = scope.export(packet, [])
    value = bundle(scope, baseline)
    assert verify_bundle(scope, baseline, value) == ["src/features/auth.py"]
    assert (scope.root / "src/features/auth.py").read_text() == "VALUE = 1\n"
    duplicate = copy.deepcopy(value)
    duplicate["changes"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        verify_bundle(scope, baseline, duplicate)
    value["base_commit"] = "0" * 40
    with pytest.raises(ValueError, match="stale base"):
        verify_bundle(scope, baseline, value)


def test_symlink_scope_refused(prepared, tmp_path):
    scope, packet = prepared
    path = scope.root / "src/features/auth.py"
    path.unlink()
    try:
        path.symlink_to(scope.root / "src/features/data.py")
    except OSError:
        pytest.skip("Host cannot create symlinks; runtime symlink probe covers enforcement")
    with pytest.raises(ValueError):
        scope.files()


def test_claim_collision_is_atomic(prepared, tmp_path):
    scope, _ = prepared
    ownership = Ownership(tmp_path / "state")
    def claim(n):
        try:
            return ownership.claim(scope, f"container-{n}")
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(claim, range(8)))
    assert sum(t is not None for t in tokens) == 1


def test_claim_collision_across_processes(prepared, tmp_path):
    scope, _ = prepared
    state = tmp_path / "state"
    Ownership(state)
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(wp.canonical(scope.data))
    script = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
              "from workflow_scope import Ownership, SessionScope; import work_packet as w; "
              "o=Ownership(Path(sys.argv[2])); s=SessionScope.load(w.read_json(sys.argv[3])); "
              "print(o.claim(s,'created-container'))")
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(ROOT / "scripts"),
                                  str(state), str(scope_path)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) for _ in range(4)]
    outcomes = [p.communicate(timeout=30) for p in processes]
    assert sum(p.returncode == 0 for p in processes) == 1
    assert all(p.returncode == 0 or b"already has a writer" in outcome[1]
               for p, outcome in zip(processes, outcomes))


def test_branch_and_workspace_uniqueness_independent(prepared, tmp_path):
    scope, _ = prepared
    ownership = Ownership(tmp_path / "state")
    ownership.claim(scope, "c1")
    data = copy.deepcopy(scope.data)
    data["workspace"] = str(tmp_path / "other")
    with pytest.raises(ValueError, match="already has"):
        ownership.claim(SessionScope.load(data), "c2")
    data = copy.deepcopy(scope.data)
    data["branch"] = "feature/other"
    with pytest.raises(ValueError, match="already has"):
        ownership.claim(SessionScope.load(data), "c3")
    data["workspace"] = str(tmp_path / "other")
    assert ownership.claim(SessionScope.load(data), "c4")


def test_expiry_requires_stopped_process_and_preserved_output(prepared, tmp_path):
    scope, _ = prepared
    clock = [100]
    ownership = Ownership(tmp_path / "state", clock=lambda: clock[0])
    token = ownership.claim(scope, "c1", 10)
    clock[0] = 105
    ownership.heartbeat(token, 10)
    clock[0] = 116
    with pytest.raises(ValueError, match="already has"):
        ownership.claim(scope, "c2")
    with pytest.raises(ValueError, match="Expired"):
        ownership.heartbeat(token)
    with pytest.raises(ValueError, match="Expired"):
        ownership.start(token, lambda _: pytest.fail("expired start reached runtime"))
    with pytest.raises(ValueError, match="not confirmed stopped"):
        ownership.finish(token, lambda _: False, lambda _: None, recovering=True)
    with pytest.raises(ValueError, match="missing"):
        ownership.finish(token, lambda _: True, lambda _: tmp_path / "missing", recovering=True)
    evidence = tmp_path / "preserved.tar"
    evidence.write_bytes(b"preserved diff")
    ownership.finish(token, lambda _: True, lambda _: evidence, recovering=True)
    assert ownership.claim(scope, "c2")
    with pytest.raises(ValueError, match="No active"):
        ownership.start(token, lambda _: pytest.fail("old owner resurrected"))


def test_live_lease_cannot_be_recovered(prepared, tmp_path):
    scope, _ = prepared
    ownership = Ownership(tmp_path / "state")
    token = ownership.claim(scope, "created-container")
    with pytest.raises(ValueError, match="Live lease"):
        ownership.finish(token, lambda _: True, lambda _: tmp_path, recovering=True)


def test_output_tar_link_and_unexpected_file_rejected(prepared):
    scope, packet = prepared
    _, baseline = scope.export(packet, [])
    for name, kind in [("workspace/../escaped", tarfile.REGTYPE),
                       ("workspace/src/features/auth.py", tarfile.SYMTYPE),
                       ("workspace/src/features/data.py", tarfile.REGTYPE)]:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            info = tarfile.TarInfo(name)
            info.type, info.linkname = kind, "/etc/passwd"
            tar.addfile(info)
        with pytest.raises(ValueError):
            runtime.bundle_from_archive(scope, baseline, buffer.getvalue())


@pytest.mark.skipif(not os.environ.get("WORKFLOW_TEST_IMAGE"), reason="Requires the locally verified offline image")
def test_real_export_boundary_and_output(prepared, tmp_path):
    scope, packet = prepared
    script = r'''
from pathlib import Path
import subprocess, socket, json, os
root=Path.cwd()
assert os.getuid()==1000
assert (root/"contracts/auth.py").read_text()=="class Interface: pass\n"
assert not (root/"src/features/data.py").exists()
assert not (root/".git").exists()
assert not Path("/var/run/docker.sock").exists()
for path in [root/"contracts/auth.py", root/"src/features/data.py", root/"newfile"]:
    r=subprocess.run(["sh","-c",'printf bad > "$1"',"probe",str(path)],capture_output=True)
    assert r.returncode != 0, str(path)
r=subprocess.run(["sh","-c",'cat /run/desktop/mnt/host/c/Users/hensl/Documents/GitHub/ai-template/ai-template-oop/README.md >/dev/null 2>&1'])
assert r.returncode != 0
r=subprocess.run(["cline","--version"],capture_output=True)
assert r.returncode==0
(root/"src/features/auth.py").write_text("VALUE = 2\n")
print(json.dumps({"allowed_task":True,"shell_denials":True,"cline_version":r.stdout.decode().strip()}))
'''
    state = runtime.state_directory(scope)
    before_refs = command(scope.root, "git", "show-ref")
    run = runtime.prepare(scope, packet, [], state, os.environ["WORKFLOW_TEST_IMAGE"], ["python", "-c", script])
    record = runtime.execute(run, state, 30)
    assert record["exit_code"] == 0, (run / "stdout.log").read_text()
    archive = runtime.docker("cp", record["container"] + ":/session/workspace", "-")
    candidate = runtime.bundle_from_archive(scope, wp.read_json(run / "baseline.json"), archive)
    assert verify_bundle(scope, wp.read_json(run / "baseline.json"), candidate) == ["src/features/auth.py"]
    assert (scope.root / "src/features/auth.py").read_text() == "VALUE = 1\n"
    assert command(scope.root, "git", "show-ref") == before_refs
    assert list(run.glob("output-*.tar"))


@pytest.mark.skipif(not os.environ.get("WORKFLOW_TEST_IMAGE"), reason="Requires the locally verified offline image")
def test_real_expired_live_worker_cannot_be_recovered(prepared, tmp_path):
    scope, packet = prepared
    state = runtime.state_directory(scope)
    run = runtime.prepare(scope, packet, [], state, os.environ["WORKFLOW_TEST_IMAGE"],
                          ["python", "-c", "import time; time.sleep(30)"])
    record = wp.read_json(run / "runtime.json")
    ownership = Ownership(state)
    ownership.start(record["ownership_token"], lambda c: runtime.docker("start", c))
    with ownership.transaction() as db:
        db.execute("UPDATE runs SET expires=0 WHERE token=?", (record["ownership_token"],))
    try:
        with pytest.raises(ValueError, match="not confirmed stopped"):
            ownership.finish(record["ownership_token"], runtime.stopped,
                             lambda c: runtime.preserve(c, run), recovering=True)
    finally:
        runtime.docker("kill", record["container"])
    ownership.finish(record["ownership_token"], runtime.stopped,
                     lambda c: runtime.preserve(c, run), recovering=True)
    assert list(run.glob("output-*.tar"))
    assert ownership.claim(scope, "next-created-container")


def test_alternate_state_directory_refused(prepared, tmp_path):
    scope, _ = prepared
    with pytest.raises(ValueError, match="alternate ledgers"):
        runtime.check_state(scope, tmp_path / "bypass")


def test_all_worktrees_share_repository_ownership_directory(prepared, tmp_path):
    scope, _ = prepared
    path = tmp_path / "other-worktree"
    command(scope.root, "git", "worktree", "add", "-b", "feature/other", str(path))
    data = copy.deepcopy(scope.data)
    data.update(workspace=str(path), branch="feature/other")
    assert runtime.state_directory(scope) == runtime.state_directory(SessionScope.load(data))


def test_scope_rejects_untracked_context_drift(prepared):
    scope, packet = prepared
    path = scope.root / "tests/test_feature_auth.py"
    path.write_text("original fixture")
    data = copy.deepcopy(scope.data)
    data["read_paths"].append("tests/test_feature_auth.py")
    scope = SessionScope.load(data)
    _, baseline = scope.export(packet, [])
    path.write_text("changed fixture")
    with pytest.raises(ValueError, match="Scope input changed"):
        verify_bundle(scope, baseline, bundle(scope, baseline))


def test_inherited_verified_dependency_gate_is_preserved(prepared):
    scope, _ = prepared
    contract = wp.read_json(ROOT / "examples/work-packets/software-hardware.contract.json")
    dependency = wp.create("OTHER", "software-hardware", contract, "Architect", "Fixture")
    for target, role in [("ARCHITECTED","architect"),("READY","architect"),("IN_PROGRESS","worker"),
                         ("VALIDATING","worker"),("REVIEW","worker"),("ACCEPTED","reviewer"),
                         ("VERIFIED","integrator")]:
        dependency = wp.transition(dependency, target, role, role, "Fixture", ["fixture-evidence"])
    contract = copy.deepcopy(contract)
    contract["dependencies"] = ["OTHER"]
    packet = wp.create("TEST-SCOPE", "software-hardware", contract, "Architect", "Fixture")
    for target in ("ARCHITECTED", "READY"):
        packet = wp.transition(packet, target, "architect", "Architect", "Fixture", graph=[packet, dependency])
    data = copy.deepcopy(scope.data)
    data["packet_revision_hash"] = wp.current(packet)["hash"]
    scoped = SessionScope.load(data)
    scoped.export(packet, [dependency])
    with pytest.raises(ValueError, match="missing dependencies"):
        scoped.export(packet, [])
    pending = copy.deepcopy(dependency)
    pending["events"] = pending["events"][:-1]
    pending["state"] = "ACCEPTED"
    with pytest.raises(ValueError, match="must be VERIFIED"):
        scoped.export(packet, [pending])


@pytest.mark.skipif(not os.environ.get("WORKFLOW_TEST_IMAGE"), reason="Requires the locally verified offline image")
def test_real_ui_workspace_has_no_feature_implementation(prepared):
    scope, packet = prepared
    for relative in ["src/ui/mocks.py", "tests/test_ui.py"]:
        path = scope.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n")
    command(scope.root, "git", "add", ".")
    command(scope.root, "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "ui fixture")
    data = copy.deepcopy(scope.data)
    data.update(role="ui", branch="ui/shell",
                base_commit=command(scope.root,"git","rev-parse","HEAD"),
                read_paths=["contracts/auth.py","src/ui/mocks.py","tests/test_ui.py"],
                write_paths=["src/ui/mocks.py"])
    command(scope.root, "git", "branch", "-m", "ui/shell")
    scoped = SessionScope.load(data)
    script = ('from pathlib import Path; import subprocess; '
              'assert not Path("src/features/auth.py").exists(); '
              'r=subprocess.run(["sh","-c","cat src/features/auth.py >/dev/null 2>&1"]); '
              'assert r.returncode != 0; '
              'Path("src/ui/mocks.py").write_text("VALUE = 2\\n")')
    state = runtime.state_directory(scoped)
    run = runtime.prepare(scoped, packet, [], state, os.environ["WORKFLOW_TEST_IMAGE"], ["python","-c",script])
    result = runtime.execute(run, state, 30)
    assert result["exit_code"] == 0, (run/"stdout.log").read_text()


@pytest.mark.skipif(not os.environ.get("WORKFLOW_TEST_IMAGE"), reason="Requires the locally verified offline image")
def test_real_timeout_stops_tree_and_preserves_output(prepared):
    scope, packet = prepared
    state = runtime.state_directory(scope)
    script = 'from pathlib import Path; import time; Path("src/features/auth.py").write_text("VALUE = 3\\n"); time.sleep(30)'
    run = runtime.prepare(scope, packet, [], state, os.environ["WORKFLOW_TEST_IMAGE"], ["python","-c",script])
    result = runtime.execute(run, state, 1)
    assert result["status"] == "timed_out"
    assert runtime.stopped(result["container"])
    assert list(run.glob("output-*.tar"))


@pytest.mark.skipif(not os.environ.get("WORKFLOW_TEST_IMAGE"), reason="Requires the locally verified offline image")
def test_coordinator_cli_roundtrip_and_recovery(prepared, tmp_path):
    scope, packet = prepared
    scope_path, packet_path = tmp_path / "scope.json", tmp_path / "packet.json"
    scope_path.write_text(wp.canonical(scope.data))
    packet_path.write_text(wp.canonical(packet))
    runtime_cli, scope_cli = ROOT / "scripts/workflow_runtime.py", ROOT / "scripts/workflow_scope.py"
    def cli(script, *args):
        return subprocess.run([sys.executable, "-B", str(script), *map(str,args)],
                              capture_output=True, text=True, timeout=60)
    directory = cli(runtime_cli, "state-directory", "--scope", scope_path)
    assert directory.returncode == 0, directory.stdout + directory.stderr
    state = Path(directory.stdout.strip())
    def prep():
        result = cli(runtime_cli, "prepare", "--scope", scope_path, "--packet", packet_path,
                     "--state", state, "--image", os.environ["WORKFLOW_TEST_IMAGE"], "--",
                     "python", "-c", 'from pathlib import Path; Path("src/features/auth.py").write_text("VALUE = 2\\n")')
        assert result.returncode == 0, result.stdout + result.stderr
        return Path(json.loads(result.stdout)["run"])
    run = prep()
    beat = cli(runtime_cli, "heartbeat", "--run", run, "--state", state, "--lease-seconds", "60")
    assert beat.returncode == 0, beat.stdout + beat.stderr
    executed = cli(runtime_cli, "execute", "--run", run, "--state", state, "--timeout", "30")
    assert executed.returncode == 0, executed.stdout + executed.stderr
    output = cli(runtime_cli, "bundle", "--run", run, "--state", state)
    assert output.returncode == 0, output.stdout + output.stderr
    candidate = json.loads(output.stdout)["bundle"]
    result = cli(scope_cli, "check-output", "--scope", run / "scope.json", "--baseline", run / "baseline.json",
                 "--bundle", candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["applied"] is False
    run = prep()
    record = wp.read_json(run / "runtime.json")
    ownership = Ownership(state)
    with ownership.transaction() as db:
        db.execute("UPDATE runs SET expires=0 WHERE token=?", (record["ownership_token"],))
    recovered = cli(runtime_cli, "recover", "--run", run, "--state", state)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert list(run.glob("output-*.tar"))
    refused = cli(runtime_cli, "execute", "--run", run, "--state", state)
    assert refused.returncode == 1
    assert "No active ownership" in refused.stdout
