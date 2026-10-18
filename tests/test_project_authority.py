"""Offline identity/approval lifecycle on disposable actual Git repositories.

Approval actors here are fixture declarations, never owner approval of this work.
No provider, worker, Docker, publication or real canonical journal is used.
"""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

from scripts import project_authority as authority
from scripts import workflow_state as ws
from scripts import validate_workflow_approval as legacy
from tools import project_admin

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return (
        subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            stderr=subprocess.PIPE,
        )
        .decode()
        .strip()
    )


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "host state"))
    root = tmp_path / "project with spaces"
    root.mkdir()
    git(root, "init", "-b", "feature/identity")
    for name in (
        "scripts/project_authority.py",
        "scripts/workflow_state.py",
        "tools/project_admin.py",
    ):
        target = root / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (root / "scripts/component.py").write_text("VALUE = 1\n")
    return root


def approve(root):
    fingerprint = authority.review(root)
    authority.decide(root, "Fixture owner", "APPROVE " + fingerprint)
    return fingerprint


def clone_files(root, destination):
    shutil.copytree(root, destination, ignore=shutil.ignore_patterns(".git"))
    git(destination, "init", "-b", "feature/copied")
    return destination


def contents(directory):
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }


def test_status_is_readonly_and_initialization_has_unique_unapproved_identity(
    repository, tmp_path
):
    before = contents(repository)
    assert authority.status(repository)["state"] == "UNINITIALIZED"
    assert contents(repository) == before
    assert not (tmp_path / "host state").exists()
    project = authority.initialize(repository, "example-project")
    assert authority.identity(repository) == project
    assert authority.status(repository)["state"] == "AWAITING_APPROVAL"
    directory, _ = authority._location(repository)
    assert not (directory / "decisions.json").exists()
    assert not (directory.parent / "control.sqlite3").exists()
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(repository)
    copied = clone_files(repository, tmp_path / "second")
    (copied / authority.IDENTITY).unlink()
    second = authority.initialize(copied, "second-project")
    assert second["id"] != project["id"]


@pytest.mark.parametrize("slug", ["", "../escape", "UpperCase", "two words", "x" * 65])
def test_invalid_slug_creates_nothing(repository, tmp_path, slug):
    with pytest.raises(ValueError):
        authority.initialize(repository, slug)
    assert not (repository / "config").exists()
    assert not (tmp_path / "host state").exists()


def test_reinitialization_cannot_replace_identity_or_existing_workflow_state(
    repository,
):
    project = authority.initialize(repository, "example")
    with pytest.raises(ValueError, match="never reinitialize"):
        authority.initialize(repository, "replacement")
    assert authority.identity(repository) == project
    fingerprint = approve(repository)
    journal = ws.Journal(repository)
    journal.initialize()
    journal.create(
        "TASK:worker",
        family="feedback",
        binding={},
        data={"attempts": 2, "spend": 1},
        timestamp="2026-10-15T12:00:00Z",
    )
    heads = journal.verify()
    # Revocation changes authority, not journal history, attempts or spending.
    authority.decide(repository, "Fixture owner", "REVOKE " + fingerprint, revoke=True)
    assert journal.verify() == heads
    assert journal.read("TASK:worker")[0][0]["data"] == {"attempts": 2, "spend": 1}
    with pytest.raises(ValueError):
        journal.create(
            "TASK:new",
            family="feedback",
            binding={},
            data={},
            timestamp="2026-10-15T12:00:01Z",
        )


def test_initialize_refuses_prior_canonical_journal(repository):
    journal = ws.Journal(repository)
    journal.directory.mkdir(parents=True)
    journal.db.write_bytes(b"existing state, never reset")
    with pytest.raises(ValueError, match="Existing workflow state"):
        authority.initialize(repository, "example")
    assert journal.db.read_bytes() == b"existing state, never reset"
    assert not (repository / authority.IDENTITY).exists()


def test_exact_literal_decision_required_and_review_never_activates(repository):
    authority.initialize(repository, "example")
    fingerprint = authority.review(repository)
    with pytest.raises(ValueError, match="Literal decision"):
        authority.decide(repository, "Fixture owner", "APPROVE " + "0" * 64)
    with pytest.raises(ValueError, match="identified owner"):
        authority.decide(repository, " ", "APPROVE " + fingerprint)
    assert authority.status(repository)["state"] == "AWAITING_APPROVAL"
    assert (
        authority.decide(repository, "Fixture owner", "APPROVE " + fingerprint)
        == fingerprint
    )
    assert ws.active_anchor(repository) == fingerprint
    assert authority.status(repository)["state"] == "ACTIVE_OFFLINE"
    assert not any(value is True for value in authority.POLICY.values())


def test_copied_project_and_even_copied_host_receipt_cannot_activate(
    repository, tmp_path
):
    authority.initialize(repository, "example")
    approve(repository)
    source, _ = authority._location(repository)
    copied = clone_files(repository, tmp_path / "copy")
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(copied)
    # Explicit review enrolls the copied checkout, but does not import approval.
    same_fingerprint = authority.review(copied)
    destination, _ = authority._location(copied)
    shutil.copyfile(source / "decisions.json", destination / "decisions.json")
    with pytest.raises(ValueError, match="different checkout"):
        ws.active_anchor(copied)
    assert authority.status(copied)["state"] == "AWAITING_APPROVAL"
    assert (
        authority.digest(json.loads((copied / authority.PACKAGE).read_text()))
        == same_fingerprint
    )


@pytest.mark.parametrize(
    "change",
    ["code", "new_code", "policy", "identity", "remove_identity", "remove_package"],
)
def test_mutations_hold_authority_without_legacy_fallback(repository, change):
    authority.initialize(repository, "example")
    approve(repository)
    if change == "code":
        (repository / "scripts/component.py").write_text("VALUE = 2\n")
    elif change == "new_code":
        (repository / "scripts/unreviewed.py").write_text("VALUE = 2\n")
    elif change == "policy":
        path = repository / authority.PACKAGE
        package = json.loads(path.read_text())
        package["policy"]["publication_authorized"] = True
        path.write_text(json.dumps(package))
    elif change == "identity":
        path = repository / authority.IDENTITY
        value = json.loads(path.read_text())
        value["slug"] = "changed"
        path.write_text(json.dumps(value))
    else:
        (
            repository
            / (authority.IDENTITY if change == "remove_identity" else authority.PACKAGE)
        ).unlink()
    assert authority.applies(repository)
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(repository)


def test_feature_work_does_not_require_control_plane_reapproval(repository):
    authority.initialize(repository, "example")
    fingerprint = approve(repository)
    feature = repository / "src/features/component.py"
    feature.parent.mkdir(parents=True)
    feature.write_text("class Component: pass\n")
    tests = repository / "tests"
    tests.mkdir()
    (tests / "test_component.py").write_text("def test_component(): assert True\n")
    (repository / "README.md").write_text("Ordinary application documentation\n")
    assert ws.active_anchor(repository) == fingerprint


@pytest.mark.parametrize("relative", ["runtime/firmware.bin", "config/device.bin"])
def test_byte_distinct_binary_control_inputs_invalidate_approval(repository, relative):
    authority.initialize(repository, "example")
    artifact = repository / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"A\r\nB")
    approve(repository)
    before = authority.inventory(repository)[relative]
    artifact.write_bytes(b"A\nB")
    assert authority.inventory(repository)[relative] != before
    with pytest.raises(ValueError, match="stale"):
        ws.active_anchor(repository)


def test_known_text_line_endings_retain_the_same_approval(repository):
    authority.initialize(repository, "example")
    script = repository / "scripts/component.py"
    script.write_bytes(b"VALUE = 1\r\n")
    fingerprint = approve(repository)
    script.write_bytes(b"VALUE = 1\n")
    assert ws.active_anchor(repository) == fingerprint


@pytest.mark.parametrize("damage", ["missing", "malformed"])
def test_status_reports_identity_damage_without_creating_or_resetting_state(
    repository, damage, capsys
):
    authority.initialize(repository, "example")
    record = repository / authority.IDENTITY
    if damage == "missing":
        record.unlink()
    else:
        record.write_text("{malformed")
    before = contents(repository)
    directory, _ = authority._location(repository)
    host_before = contents(directory)
    result = authority.status(repository)
    assert result["state"] == "AWAITING_APPROVAL" and result["blocker"]
    assert project_admin.main(["--root", str(repository), "status"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "AWAITING_APPROVAL"
    assert contents(repository) == before and contents(directory) == host_before


def test_removing_identity_in_a_copy_cannot_fall_back_to_legacy(repository, tmp_path):
    authority.initialize(repository, "example")
    approve(repository)
    copied = clone_files(repository, tmp_path / "copy")
    (copied / authority.IDENTITY).unlink()
    assert authority.applies(copied)
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(copied)


def test_hardlinked_input_is_refused_without_touching_its_other_name(
    repository, tmp_path
):
    authority.initialize(repository, "example")
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 7\n")
    target = repository / "scripts/component.py"
    target.unlink()
    os.link(outside, target)
    with pytest.raises(ValueError, match="Multiply linked"):
        authority.review(repository)
    assert outside.read_text() == "VALUE = 7\n"


def test_interrupted_identity_write_remains_held(repository, monkeypatch):
    write = authority._write

    def interrupt(path, value, **kwargs):
        if path == repository / authority.IDENTITY:
            raise OSError("fixture interruption")
        return write(path, value, **kwargs)

    monkeypatch.setattr(authority, "_write", interrupt)
    with pytest.raises(OSError):
        authority.initialize(repository, "example")
    assert authority.applies(repository)
    with pytest.raises(ValueError, match="Registered identity"):
        authority.initialize(repository, "replacement")
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(repository)

    result = authority.status(repository)
    assert result["state"] == "AWAITING_APPROVAL" and result["blocker"]


def test_code_change_during_activation_does_not_record_approval(
    repository, monkeypatch
):
    authority.initialize(repository, "example")
    fingerprint = authority.review(repository)
    package = authority._package
    calls = []

    def change(root):
        calls.append(root)
        if len(calls) == 2:
            (repository / "scripts/component.py").write_text("VALUE = 3\n")
        return package(root)

    monkeypatch.setattr(authority, "_package", change)
    with pytest.raises(ValueError, match="changed while"):
        authority.decide(repository, "Fixture owner", "APPROVE " + fingerprint)
    directory, _ = authority._location(repository)
    assert not (directory / "decisions.json").exists()


def test_refresh_and_new_decision_preserve_old_decisions_and_journal_binding(
    repository,
):
    authority.initialize(repository, "example")
    first = approve(repository)
    journal = ws.Journal(repository)
    journal.initialize()
    head = journal.create(
        "TASK:worker",
        family="feedback",
        binding={},
        data={"attempts": 2},
        timestamp="2026-10-15T12:00:00Z",
    )
    (repository / "scripts/component.py").write_text("VALUE = 2\n")
    second = authority.review(repository)
    assert second != first
    with pytest.raises(ValueError, match="stale"):
        ws.active_anchor(repository)
    authority.decide(repository, "Fixture owner", "APPROVE " + second)
    assert ws.active_anchor(repository) == second
    with pytest.raises(ValueError, match="anchor changed"):
        journal.append(
            "TASK:worker",
            "DISPATCH",
            {},
            expected=head,
            timestamp="2026-10-15T12:00:01Z",
        )
    directory, _ = authority._location(repository)
    assert len(json.loads((directory / "decisions.json").read_text())["events"]) == 2
    assert journal.read("TASK:worker")[1] == head


def test_corrupt_or_truncated_decision_history_is_never_replaced(repository):
    authority.initialize(repository, "example")
    fingerprint = approve(repository)
    directory, _ = authority._location(repository)
    path = directory / "decisions.json"
    history = json.loads(path.read_text())
    history["events"][0]["owner"] = "tampered"
    path.write_text(json.dumps(history))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="approval event"):
        authority.decide(repository, "Fixture owner", "APPROVE " + fingerprint)
    assert path.read_bytes() == before


def test_interrupted_operation_lock_refuses_without_reset(repository):
    authority.initialize(repository, "example")
    directory, _ = authority._location(repository)
    lock = directory / "operation.lock"
    lock.write_text("interrupted")
    before = contents(repository)
    with pytest.raises(ValueError, match="busy or interrupted"):
        authority.review(repository)
    assert contents(repository) == before
    assert lock.read_text() == "interrupted"


def test_concurrent_initialization_has_one_identity(repository):
    def initialize():
        try:
            return authority.initialize(repository, "example")
        except (ValueError, FileExistsError):
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: initialize(), range(2)))
    assert sum(item is not None for item in results) == 1
    assert authority.identity(repository) == next(item for item in results if item)


def test_worktrees_share_project_authority_and_subdirectories_are_refused(
    repository, tmp_path
):
    authority.initialize(repository, "example")
    authority.review(repository)
    git(repository, "add", ".")
    git(
        repository,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    fingerprint = approve(repository)
    other = tmp_path / "retained worktree"
    git(repository, "worktree", "add", "-b", "feature/other", str(other))
    assert ws.active_anchor(other) == fingerprint
    with pytest.raises(ValueError, match="worktree root"):
        authority.status(repository / "scripts")


def test_historical_active_copy_is_not_project_approval(repository, tmp_path):
    # Reproduce the original portability claim using the tracked historical tree.
    snapshot = tmp_path / "historical export"
    snapshot.mkdir()
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", "HEAD"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(snapshot, filter="data")
    git(snapshot, "init", "-b", "feature/historical-copy")
    before = (snapshot / legacy.PACKAGE).read_bytes()
    assert ws.active_anchor(snapshot) == legacy.fingerprint(json.loads(before))
    # Install the new lifecycle files as a template consumer would, then initialize.
    for name in (
        "scripts/project_authority.py",
        "tools/project_admin.py",
        "scripts/workflow_state.py",
    ):
        shutil.copyfile(ROOT / name, snapshot / name)
    authority.initialize(snapshot, "new-project")
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(snapshot)
    assert (snapshot / legacy.PACKAGE).read_bytes() == before


def test_interrupted_initialization_before_registration_cannot_use_legacy_approval(
    repository, tmp_path
):
    snapshot = tmp_path / "interrupted historical export"
    snapshot.mkdir()
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", "HEAD"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(snapshot, filter="data")
    git(snapshot, "init", "-b", "feature/interrupted-copy")
    assert ws.active_anchor(snapshot)
    directory, _ = authority._location(snapshot)
    directory.mkdir(parents=True)
    lock = directory / "operation.lock"
    lock.write_text("Interrupted before identity registration")
    assert not (directory / "identity.json").exists()
    assert not (snapshot / authority.IDENTITY).exists()
    assert authority.applies(snapshot)
    with pytest.raises((ValueError, OSError)):
        ws.active_anchor(snapshot)
    result = authority.status(snapshot)
    assert result["state"] == "AWAITING_APPROVAL" and result["blocker"]
    assert lock.read_text() == "Interrupted before identity registration"


def test_cli_forwards_exact_root_and_reports_held_decisions(repository, capsys):
    prefix = ["--root", str(repository)]
    assert project_admin.main([*prefix, "status"]) == 0
    assert project_admin.main([*prefix, "init", "--slug", "example"]) == 0
    assert project_admin.main([*prefix, "review"]) == 0
    fingerprint = authority.digest(
        json.loads((repository / authority.PACKAGE).read_text())
    )
    assert (
        project_admin.main(
            [*prefix, "activate", "--owner", "Fixture owner", "--decision", "wrong"]
        )
        == 1
    )
    assert "HELD" in capsys.readouterr().err
    assert (
        project_admin.main(
            [
                *prefix,
                "activate",
                "--owner",
                "Fixture owner",
                "--decision",
                "APPROVE " + fingerprint,
            ]
        )
        == 0
    )
    assert (
        project_admin.main(
            [
                *prefix,
                "revoke",
                "--owner",
                "Fixture owner",
                "--decision",
                "REVOKE " + fingerprint,
            ]
        )
        == 0
    )
    assert authority.status(repository)["state"] == "AWAITING_APPROVAL"


def test_cli_status_subprocess_does_not_create_state(repository, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "tools/project_admin.py"),
            "--root",
            str(repository),
            "status",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "UNINITIALIZED"
    assert not (tmp_path / "host state").exists()
