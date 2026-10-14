"""Offline approval integrity/refusal tests; no workers or Git fixture commits."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("approval_validator", ROOT / "scripts/validate_workflow_approval.py")
approval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(approval)


@pytest.fixture
def package(tmp_path, monkeypatch):
    data = approval.read_json(ROOT / approval.PACKAGE)
    for relative in set(data["bound_files"]) | set(data["baseline_files"]):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    def inspect(root, *args):
        if args == ("rev-parse", "HEAD"):
            return approval.BASE.encode()
        if args == ("branch", "--show-current"):
            return b"feature/workflow-migration"
        raise AssertionError("Unexpected external inspection")
    monkeypatch.setattr(approval, "git", inspect)
    return data, tmp_path


def test_inactive_package_validates_without_writing(package):
    data, root = package
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = approval.validate(data, root)
    assert result == approval.fingerprint(data)
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="not ACTIVE"):
        approval.validate(data, root, require_active=True)


@pytest.mark.parametrize("change", [
    lambda d: d["authority"].update(live_workers_enabled=True),
    lambda d: d["authority"].update(publication_authorized=True),
    lambda d: d["authority"].update(merge_authorized=True),
    lambda d: d["authority"].update(delegation_authorized=True),
    lambda d: d["boundary"].update(network="bridge"),
    lambda d: d["boundary"].update(host_bind_mounts=True),
    lambda d: d["state_layout"].update(task_review_project="ownership.sqlite3"),
    lambda d: d["state_layout"].update(branch_retention="delete_after_merge"),
    lambda d: d["policy"].update(worker_max_attempts=3),
    lambda d: d["policy"].update(reviewer_max_attempts=3),
    lambda d: d["policy"].update(task_api_budget_usd=5),
    lambda d: d["policy"].update(resources_enabled=True),
    lambda d: d["policy"].update(unknown_cost_action="ZERO"),
    lambda d: d["policy"]["review_floors"].update(high=["deterministic"]),
    lambda d: d["policy"]["risk_floor"].update(low=False),
    lambda d: d["boundary"].update(read_only_root=1),
    lambda d: d["approval"].update(approved=0),
    lambda d: d.update(autonomy_enabled=True),
    lambda d: d["acceptance_criteria"][0].update(status="accepted"),
    lambda d: d["milestones"][0].update(depends_on=["M6"]),
    lambda d: d["source_dependencies"].pop("scripts/progress.py"),
    lambda d: d["bound_files"].pop("BRANCH_RETENTION.md"),
])
def test_unsafe_or_incomplete_foundation_refused(package, change):
    data, root = package
    change(data)
    with pytest.raises(ValueError):
        approval.validate(data, root)


def receipt(data):
    data["state"] = "ACTIVE"
    data["autonomy_enabled"] = True
    digest = approval.fingerprint(data)
    data["approval"] = {"approved": True, "approved_by": "Test owner", "approved_at": "2026-10-12T12:00:00Z",
                        "architecture_fingerprint": digest, "decision": "APPROVE " + digest}


def test_receipt_fields_do_not_change_foundation_fingerprint(package):
    data, root = package
    digest = approval.fingerprint(data)
    receipt(data)
    assert approval.validate(data, root, require_active=True) == digest
    assert data["authority"]["live_workers_enabled"] is False
    assert approval.read_json(ROOT / approval.PACKAGE)["state"] == "AWAITING_APPROVAL"


@pytest.mark.parametrize("change", [
    lambda d: d["approval"].update(architecture_fingerprint="0" * 64),
    lambda d: d["approval"].update(decision="yes"),
    lambda d: d["approval"].update(approved_by=" "),
    lambda d: d["approval"].update(approved_at="2026-10-12T12:00:00"),
    lambda d: d["approval"].update(approved_at="2026-10-12T12:00:00-04:00"),
    lambda d: d["components"].update(routing="Changed design after receipt"),
])
def test_stale_or_invalid_receipt_refused(package, change):
    data, root = package
    receipt(data)
    change(data)
    with pytest.raises(ValueError):
        approval.validate(data, root, require_active=True)


def test_file_drift_refused_but_crlf_clone_preserves_fingerprint(package):
    data, root = package
    path = root / "BRANCH_RETENTION.md"
    original = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(original.replace(b"\n", b"\r\n"))
    assert approval.validate(data, root) == approval.fingerprint(data)
    path.write_bytes(original + b"Changed policy\n")
    with pytest.raises(ValueError, match="file changed"):
        approval.validate(data, root)


@pytest.mark.parametrize("path", ["../outside.txt", "C:/outside.txt", "src/../outside.txt", ".git/config", "src\\escape.py"])
def test_escaped_and_protected_binding_refused(package, path):
    data, root = package
    data["bound_files"][path] = "0" * 64
    with pytest.raises(ValueError):
        approval.validate(data, root)


def test_linked_input_refused_even_when_content_matches(package, monkeypatch):
    data, root = package
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "BRANCH_RETENTION.md" or original(p))
    with pytest.raises(ValueError, match="Linked"):
        approval.validate(data, root)


@pytest.mark.parametrize("serialized", ['{"state":1,"state":2}', '{"cap":NaN}', '{"cap":Infinity}'])
def test_ambiguous_json_refused(tmp_path, serialized):
    path = tmp_path / "bad.json"
    path.write_text(serialized, encoding="utf-8")
    with pytest.raises(ValueError):
        approval.read_json(path)


def test_imported_file_cannot_be_relabelled_as_new_source(package):
    data, root = package
    data["source_dependencies"]["scripts/work_packet.py"]["disposition"] = "adapt"
    with pytest.raises(ValueError, match="disposition"):
        approval.validate(data, root)


def test_source_check_refuses_wrong_git_blob(package, monkeypatch):
    data, root = package
    prior = approval.git
    def inspect(directory, *args):
        if directory == root:
            return prior(directory, *args)
        return b"0" * 40
    monkeypatch.setattr(approval, "git", inspect)
    with pytest.raises(ValueError, match="source blob"):
        approval.validate(data, root, check_source=True)


def test_preservation_check_refuses_ref_drift(package, monkeypatch):
    data, root = package
    monkeypatch.setattr(approval, "refs", lambda root: {})
    with pytest.raises(ValueError, match="branch refs changed"):
        approval.validate(data, root, check_preserved=True)


def test_task_edits_do_not_revoke_foundation_but_review_baseline_detects_them(package):
    data, root = package
    path = root / "src/features/auth.py"
    path.write_bytes(path.read_bytes() + b"\n# Candidate change\n")
    assert approval.validate(data, root) == approval.fingerprint(data)
    with pytest.raises(ValueError, match="baseline changed"):
        approval.validate(data, root, check_baseline=True)


def test_full_review_rejects_wrong_destination_branch(package, monkeypatch):
    data, root = package
    prior = approval.git
    monkeypatch.setattr(approval, "git", lambda directory, *args: b"main" if args == ("branch", "--show-current") else prior(directory, *args))
    with pytest.raises(ValueError, match="Wrong destination"):
        approval.validate(data, root, check_baseline=True)


def test_cli_refuses_activation_and_does_not_change_manifest():
    path = ROOT / approval.PACKAGE
    before = path.read_bytes()
    for arguments, code in [(["--require-active"], 1), (["--activate"], 2)]:
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/validate_workflow_approval.py"), *arguments],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert result.returncode == code
    assert path.read_bytes() == before
