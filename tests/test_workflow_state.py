"""M2 bootstrap/journal contracts on disposable Windows repositories and real SQLite."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import validate_workflow_approval as approval  # noqa: E402 -- existing scripts layout
import workflow_state as state  # noqa: E402
from workflow_state import Head, Journal, active_anchor, control_directory  # noqa: E402

STAMP = "2026-10-14T04:00:00Z"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    data = approval.read_json(ROOT / approval.PACKAGE)
    for relative in set(data["bound_files"]) | set(data["baseline_files"]):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (root / approval.PACKAGE).write_bytes(approval.canonical(data))
    git(root, "init", "-b", "feature/m2-fixture")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-state"))
    return root


@pytest.fixture
def journal(repository: Path) -> Journal:
    result = Journal(repository)
    result.initialize()
    return result


def create(journal: Journal, name: str = "TASK:worker", **kwargs) -> Head:
    return journal.create(
        name,
        family="feedback",
        binding={"task_id": "TASK", "role": "worker"},
        data={"attempts": 2, "spend": 0.75, "pending": "dispatch-1"},
        timestamp=STAMP,
        **kwargs,
    )


def package_change(root: Path, change) -> None:
    path = root / approval.PACKAGE
    data = approval.read_json(path)
    change(data)
    path.write_bytes(approval.canonical(data))


def inactive(data: dict) -> None:
    data.update(state="AWAITING_APPROVAL", autonomy_enabled=False)
    data["approval"] = dict(
        approved=False,
        approved_by=None,
        approved_at=None,
        architecture_fingerprint=None,
        decision=None,
    )


def reducer(prior, event):
    if prior is None:
        if event["kind"] != "INIT":
            raise ValueError("INIT required")
        return copy.deepcopy(event["data"])
    if event["kind"] == "DISPATCH":
        if prior["pending"] is not None:
            raise ValueError("Pending dispatch cannot be reset")
        prior["pending"] = event["data"]["dispatch_id"]
        prior["attempts"] += 1
    elif event["kind"] == "RESULT":
        if event["data"]["dispatch_id"] != prior["pending"]:
            raise ValueError("Wrong dispatch ID")
        prior["spend"] += event["data"]["spend"]
        prior["pending"] = None
    else:
        raise ValueError("Unknown controller event")
    return prior


def source_chain(directory: Path) -> tuple[list[dict], list[bytes]]:
    directory.mkdir()
    values = [
        ("INIT", {"attempts": 2, "spend": 0.75, "pending": "dispatch-1"}),
        ("RESULT", {"dispatch_id": "dispatch-1", "spend": 0.25}),
        ("DISPATCH", {"dispatch_id": "dispatch-2"}),
    ]
    events, raw, previous = [], [], None
    for sequence, (kind, data) in enumerate(values, 1):
        event = {
            "sequence": sequence,
            "previous": previous,
            "kind": kind,
            "timestamp": STAMP,
            "data": data,
        }
        event["hash"] = hashlib.sha256(approval.canonical(event)).hexdigest()
        content = (json.dumps(event, ensure_ascii=False, indent=2) + "\n").encode()
        (directory / f"{sequence:08d}.json").write_bytes(content)
        events.append(event)
        raw.append(content)
        previous = event["hash"]
    return events, raw


def backup_with_evidence(journal: Journal, tmp_path: Path) -> tuple[Path, str, Head]:
    evidence = journal.directory / "run-test/output.tar"
    evidence.parent.mkdir()
    evidence.write_bytes(b"preserved output")
    head = create(journal, evidence=(journal.evidence("run-test/output.tar"),))
    destination = tmp_path / "backup"
    digest = journal.backup(destination)
    return destination, digest, head


def test_active_foundation_and_resolution_create_nothing(repository: Path):
    before = {
        path.relative_to(repository): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }
    assert (
        active_anchor(repository)
        == "8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481"
    )
    directory = control_directory(repository)
    result = Journal(repository)
    assert result.directory == directory
    assert not directory.exists()
    with pytest.raises(ValueError, match="missing"):
        result.verify()
    assert not directory.exists()
    assert before == {
        path.relative_to(repository): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "change",
    [
        inactive,
        lambda data: data["approval"].update(architecture_fingerprint="0" * 64),
        lambda data: data["approval"].update(decision="APPROVE " + "0" * 64),
        lambda data: data["policy"].update(resources_enabled=True),
        lambda data: data["approval"].update(approved_by=" "),
    ],
)
def test_invalid_approval_refuses_initialization_without_creating_state(
    repository: Path, change
):
    package_change(repository, change)
    result = Journal(repository)
    with pytest.raises(ValueError):
        result.initialize()
    assert not result.directory.exists()


def test_changed_bound_file_refuses_adapter(repository: Path):
    (repository / "CLAUDE.md").write_text("Changed governance", encoding="utf-8")
    with pytest.raises(ValueError, match="bound file changed"):
        active_anchor(repository)


def test_alternate_control_directory_refused(repository: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="Alternate"):
        Journal(repository, state=tmp_path / "alternate")
    assert not (tmp_path / "alternate").exists()


def test_all_worktrees_share_canonical_control_directory(
    repository: Path, tmp_path: Path
):
    git(repository, "add", "CLAUDE.md")
    git(
        repository,
        "-c",
        "user.name=M2 fixture",
        "-c",
        "user.email=m2@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    second = tmp_path / "second-worktree"
    git(repository, "worktree", "add", "-b", "feature/m2-second", str(second))
    assert control_directory(second) == control_directory(repository)


def test_initialization_never_overwrites_existing_database(journal: Journal):
    head = create(journal)
    before = journal.db.read_bytes()
    with pytest.raises(FileExistsError):
        journal.initialize()
    assert journal.db.read_bytes() == before
    assert journal.read("TASK:worker")[1] == head
    assert not (journal.directory / "ownership.sqlite3").exists()
    assert not (journal.directory / "startup.sqlite3").exists()


def test_append_replay_preserves_ids_counts_spend_and_pending(journal: Journal):
    head = create(journal)
    head = journal.append(
        "TASK:worker",
        "RESULT",
        {"dispatch_id": "dispatch-1", "spend": 0.25},
        expected=head,
        timestamp=STAMP,
        reducer=reducer,
    )
    head = journal.append(
        "TASK:worker",
        "DISPATCH",
        {"dispatch_id": "dispatch-2"},
        expected=head,
        timestamp=STAMP,
        reducer=reducer,
    )
    value, actual = journal.replay("TASK:worker", reducer)
    assert value == {"attempts": 3, "spend": 1.0, "pending": "dispatch-2"}
    assert actual == head and head.sequence == 3


def test_semantic_refusal_is_atomic(journal: Journal):
    head = create(journal)
    with pytest.raises(ValueError, match="Wrong dispatch"):
        journal.append(
            "TASK:worker",
            "RESULT",
            {"dispatch_id": "wrong", "spend": 0},
            expected=head,
            timestamp=STAMP,
            reducer=reducer,
        )
    assert journal.read("TASK:worker")[1] == head


def test_semantic_init_refusal_leaves_no_stream(journal: Journal):
    def reject(prior, event):
        raise ValueError("Invalid initial contract")

    with pytest.raises(ValueError, match="Invalid initial"):
        create(journal, reducer=reject)
    assert journal.verify() == {}


def test_stale_head_and_duplicate_init_refused(journal: Journal):
    head = create(journal)
    newer = journal.append(
        "TASK:worker", "HOLD", {"reason": "review"}, expected=head, timestamp=STAMP
    )
    with pytest.raises(ValueError, match="Stale stream head"):
        journal.append("TASK:worker", "HOLD", {}, expected=head, timestamp=STAMP)
    with pytest.raises(ValueError, match="already exists"):
        create(journal)
    with pytest.raises(ValueError, match="INIT"):
        journal.append("TASK:worker", "INIT", {}, expected=newer, timestamp=STAMP)
    assert journal.read("TASK:worker")[1] == newer


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-10-13T00:00:00Z",
        "2026-10-14T04:00:00",
        "2026-10-14T04:00:00-04:00",
        "2026-02-31T00:00:00Z",
        "2026-10-14T04:00:00+01:00",
        False,
    ],
)
def test_descending_non_utc_or_invalid_timestamps_refused(journal: Journal, stamp):
    head = create(journal)
    with pytest.raises(ValueError):
        journal.append("TASK:worker", "HOLD", {}, expected=head, timestamp=stamp)
    assert journal.read("TASK:worker")[1] == head


@pytest.mark.parametrize(
    "head", [Head(True, "0" * 64), Head(-1), Head(0, "0" * 64), Head(1, None)]
)
def test_malformed_expected_heads_refused(journal: Journal, head: Head):
    create(journal)
    with pytest.raises(ValueError, match="expected stream head"):
        journal.append("TASK:worker", "HOLD", {}, expected=head, timestamp=STAMP)


@pytest.mark.parametrize(
    "change", [inactive, lambda data: data["approval"].update(decision="forged")]
)
def test_revoked_or_forged_approval_refuses_scheduling_but_retains_outcomes(
    journal: Journal, change
):
    head = create(journal)
    package_change(journal.root, change)
    with pytest.raises(ValueError):
        journal.append("TASK:worker", "DISPATCH", {}, expected=head, timestamp=STAMP)
    assert journal.read("TASK:worker")[1] == head
    outcome = journal.append(
        "TASK:worker",
        "RESULT",
        {"dispatch_id": "dispatch-1", "spend": 0},
        expected=head,
        timestamp=STAMP,
        reducer=reducer,
    )
    assert journal.read("TASK:worker")[1] == outcome


def test_changed_valid_approval_anchor_refuses_old_stream(journal: Journal):
    head = create(journal)

    def change(data):
        data["components"]["durable_shared_state"] += " Owner-approved replacement."
        digest = approval.fingerprint(data)
        data["approval"].update(
            architecture_fingerprint=digest, decision="APPROVE " + digest
        )

    package_change(journal.root, change)
    assert active_anchor(journal.root)
    with pytest.raises(ValueError, match="anchor changed"):
        journal.append("TASK:worker", "DISPATCH", {}, expected=head, timestamp=STAMP)


def test_sqlite_prevents_event_mutation_and_deletion(journal: Journal):
    create(journal)
    with journal._connection(write=True) as actual:
        assert actual.execute("PRAGMA synchronous").fetchone()[0] == 2
    with sqlite3.connect(journal.db) as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        for statement in (
            "UPDATE events SET hash='bad'",
            "DELETE FROM events",
            "DELETE FROM streams",
            "UPDATE streams SET anchor='bad'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
    assert journal.read("TASK:worker")[1].sequence == 1


@pytest.mark.parametrize(
    "damage", ["head", "gap", "digest", "canonical", "evidence_inventory", "repository"]
)
def test_corruption_refuses_read_and_new_writes(journal: Journal, damage: str):
    head = create(journal)
    journal.append("TASK:worker", "HOLD", {}, expected=head, timestamp=STAMP)
    with sqlite3.connect(journal.db) as connection:
        if damage == "head":
            connection.execute("UPDATE streams SET head=?", ("0" * 64,))
        elif damage == "repository":
            connection.execute(
                "UPDATE metadata SET value='wrong' WHERE key='repository'"
            )
        else:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute("DROP TRIGGER events_no_delete")
            if damage == "gap":
                connection.execute("DELETE FROM events WHERE sequence=1")
            elif damage == "digest":
                connection.execute(
                    "UPDATE events SET hash=? WHERE sequence=1", ("0" * 64,)
                )
            elif damage == "canonical":
                connection.execute(
                    "UPDATE events SET canonical=? WHERE sequence=1", (b"{}",)
                )
            else:
                connection.execute(
                    "UPDATE events SET references_sha256=? WHERE sequence=1",
                    ("0" * 64,),
                )
    with pytest.raises(ValueError):
        journal.read("TASK:worker")
    with pytest.raises(ValueError):
        create(journal, "OTHER:worker")


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "run-test/../escape",
        "C:/escape",
        ".git/index",
        "not-run/output",
        "run-test/NUL",
        "run-test/.env",
        "run-test/output.",
    ],
)
def test_evidence_paths_refuse_escape_and_protected_inputs(journal: Journal, path: str):
    with pytest.raises(ValueError):
        journal.evidence(path)


def test_changed_missing_and_duplicate_evidence_refused(journal: Journal):
    path = journal.directory / "run-evidence/result.json"
    path.parent.mkdir()
    path.write_bytes(b"first result")
    reference = journal.evidence("run-evidence/result.json")
    with pytest.raises(ValueError, match="Duplicate evidence"):
        create(journal, evidence=(reference, reference))
    head = create(journal, evidence=(reference,))
    path.write_bytes(b"other result")
    with pytest.raises(ValueError, match="evidence digest"):
        journal.read("TASK:worker")
    with pytest.raises(ValueError):
        journal.append("TASK:worker", "HOLD", {}, expected=head, timestamp=STAMP)
    path.unlink()
    with pytest.raises(ValueError):
        journal.read("TASK:worker")


def test_linked_evidence_refused(journal: Journal):
    directory = journal.directory / "run-evidence"
    directory.mkdir()
    first = directory / "first.txt"
    first.write_bytes(b"output")
    os.link(first, directory / "linked.txt")
    with pytest.raises(ValueError, match="singly linked"):
        journal.evidence("run-evidence/linked.txt")


def test_junction_paths_refused(repository: Path, monkeypatch: pytest.MonkeyPatch):
    original = Path.is_junction
    expected = control_directory(repository)
    monkeypatch.setattr(
        Path, "is_junction", lambda path: path == expected or original(path)
    )
    with pytest.raises(ValueError, match="links"):
        Journal(repository)


def test_thread_append_collision_has_one_winner(journal: Journal):
    head = create(journal)

    def append(number):
        try:
            return Journal(journal.root).append(
                "TASK:worker",
                "HOLD",
                {"writer": number},
                expected=head,
                timestamp=STAMP,
            )
        except ValueError as error:
            assert "Stale stream head" in str(error)
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append, range(8)))
    assert sum(item is not None for item in results) == 1
    assert journal.read("TASK:worker")[1].sequence == 2


def test_process_append_collision_has_one_winner(journal: Journal):
    head = create(journal)
    code = r"""
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_state import Journal,Head
try:
    Journal(Path(sys.argv[2])).append('TASK:worker','HOLD',{'writer':sys.argv[4]},expected=Head(1,sys.argv[3]),timestamp='2026-10-14T04:00:00Z')
except ValueError:
    sys.exit(7)
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                code,
                str(ROOT / "scripts"),
                str(journal.root),
                head.hash,
                str(number),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for number in range(4)
    ]
    codes = []
    for process in processes:
        _, error = process.communicate(timeout=20)
        assert process.returncode in {0, 7}, error.decode()
        codes.append(process.returncode)
    assert codes.count(0) == 1
    assert journal.read("TASK:worker")[1].sequence == 2


@pytest.mark.parametrize("committed", [False, True])
def test_actual_process_kill_reopens_atomic_history(
    journal: Journal, tmp_path: Path, committed: bool
):
    head = create(journal)
    marker = tmp_path / "ready"
    code = r"""
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_state import Journal,Head
journal=Journal(Path(sys.argv[2]))
head=Head(1,sys.argv[3])
if sys.argv[5]=='True':
    journal.append('TASK:worker','HOLD',{},expected=head,timestamp='2026-10-14T04:00:00Z')
    Path(sys.argv[4]).write_text('committed')
    while True: time.sleep(.05)
else:
    with journal._connection(write=True) as db:
        event=journal._new_event(head,'HOLD',{},'2026-10-14T04:00:00Z')
        journal._insert(db,'TASK:worker',event,__import__('validate_workflow_approval').canonical(event),())
        Path(sys.argv[4]).write_text('uncommitted')
        while True: time.sleep(.05)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(ROOT / "scripts"),
            str(journal.root),
            head.hash,
            str(marker),
            str(committed),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while (
            not marker.exists()
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert marker.exists(), process.poll()
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    reopened = Journal(journal.root)
    actual = reopened.read("TASK:worker")[1]
    assert actual.sequence == (2 if committed else 1)
    final = reopened.append("TASK:worker", "HOLD", {}, expected=actual, timestamp=STAMP)
    assert final.sequence == actual.sequence + 1


def test_one_time_import_keeps_raw_bytes_hashes_and_lifetime_state(
    journal: Journal, tmp_path: Path
):
    source = tmp_path / "source-chain"
    events, originals = source_chain(source)
    receipt = journal.import_chain(
        "imported:worker",
        source,
        family="feedback",
        binding={"task_id": "TASK"},
        reducer=reducer,
    )
    replayed, head = Journal(journal.root).replay("imported:worker", reducer)
    assert replayed == {"attempts": 3, "spend": 1.0, "pending": "dispatch-2"}
    assert receipt["count"] == 3 and receipt["head"] == events[-1]["hash"] == head.hash
    assert journal.read("imported:worker")[0] == events
    audit = tmp_path / "audit"
    journal.export("imported:worker", audit)
    assert [path.read_bytes() for path in sorted(audit.iterdir())] == originals
    with pytest.raises(ValueError, match="one-time"):
        journal.import_chain(
            "imported:worker", source, family="feedback", binding={}, reducer=reducer
        )
    assert journal.replay("imported:worker", reducer)[0] == replayed
    journal.append(
        "imported:worker",
        "RESULT",
        {"dispatch_id": "dispatch-2", "spend": 0.5},
        expected=head,
        timestamp=STAMP,
        reducer=reducer,
    )
    assert journal.replay("imported:worker", reducer)[0] == {
        "attempts": 3,
        "spend": 1.5,
        "pending": None,
    }


@pytest.mark.parametrize(
    "damage",
    ["gap", "extra", "duplicate-key", "nonfinite", "hash", "semantic", "bool-sequence"],
)
def test_bad_source_chain_never_creates_partial_import(
    journal: Journal, tmp_path: Path, damage: str
):
    source = tmp_path / "source-chain"
    events, _ = source_chain(source)
    target = source / "00000002.json"
    if damage == "gap":
        target.unlink()
    elif damage == "extra":
        (source / "unexpected.txt").write_text("unexpected")
    elif damage == "duplicate-key":
        target.write_text('{"sequence":2,"sequence":2}')
    elif damage == "nonfinite":
        target.write_text('{"cost":NaN}')
    else:
        value = events[1]
        if damage == "hash":
            value["hash"] = "0" * 64
        elif damage == "bool-sequence":
            value["sequence"] = True
        else:
            value["data"]["dispatch_id"] = "unrelated"
            value["hash"] = hashlib.sha256(
                approval.canonical(
                    {key: item for key, item in value.items() if key != "hash"}
                )
            ).hexdigest()
        target.write_bytes(approval.canonical(value))
    with pytest.raises(ValueError):
        journal.import_chain(
            "imported:worker", source, family="feedback", binding={}, reducer=reducer
        )
    assert journal.verify() == {}


def test_semantic_reducer_required_for_import(journal: Journal, tmp_path: Path):
    source = tmp_path / "source-chain"
    source_chain(source)
    with pytest.raises(ValueError, match="semantic replay"):
        journal.import_chain(
            "imported:worker", source, family="feedback", binding={}, reducer=None
        )
    assert journal.verify() == {}


def test_backup_restore_checks_heads_and_evidence_and_preserves_other_stores(
    journal: Journal, tmp_path: Path
):
    backup, digest, head = backup_with_evidence(journal, tmp_path)
    assert not (backup / "ownership.sqlite3").exists()
    assert not (backup / "startup.sqlite3").exists()
    with pytest.raises(ValueError, match="never overwrites"):
        journal.restore(backup, manifest_sha256=digest)
    # Dispose only this test's canonical control database, simulating lost control state.
    journal.db.unlink()
    ownership = journal.directory / "ownership.sqlite3"
    ownership.write_bytes(b"retained ownership sentinel")
    Journal(journal.root).restore(backup, manifest_sha256=digest)
    assert journal.verify() == {"TASK:worker": head}
    assert ownership.read_bytes() == b"retained ownership sentinel"
    assert (
        journal.directory / "run-test/output.tar"
    ).read_bytes() == b"preserved output"


@pytest.mark.parametrize(
    "damage", ["manifest", "database", "evidence", "head", "inventory", "identity"]
)
def test_damaged_backup_refuses_before_installation(
    journal: Journal, tmp_path: Path, damage: str
):
    backup, digest, _ = backup_with_evidence(journal, tmp_path)
    if damage == "manifest":
        (backup / "manifest.json").write_bytes(b"{}")
    elif damage == "database":
        (backup / "control.sqlite3").write_bytes(b"broken database")
    elif damage == "evidence":
        (backup / "run-test/output.tar").write_bytes(b"altered output")
    else:
        manifest = approval.read_json(backup / "manifest.json")
        if damage == "head":
            manifest["heads"]["TASK:worker"]["hash"] = "0" * 64
        elif damage == "inventory":
            manifest["evidence"] = []
        else:
            manifest["repository"] = "unrelated repository"
        raw = approval.canonical(manifest)
        (backup / "manifest.json").write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
    journal.db.unlink()
    with pytest.raises(ValueError):
        journal.restore(backup, manifest_sha256=digest)
    assert not journal.db.exists()


def test_backup_refuses_missing_evidence_and_retains_existing_destination(
    journal: Journal, tmp_path: Path
):
    backup, _, _ = backup_with_evidence(journal, tmp_path)
    before = (backup / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        journal.backup(backup)
    assert (backup / "manifest.json").read_bytes() == before
    (journal.directory / "run-test/output.tar").unlink()
    target = tmp_path / "missing-evidence-backup"
    with pytest.raises(ValueError):
        journal.backup(target)
    assert not target.exists()


def test_restore_refuses_changed_approval_anchor(journal: Journal, tmp_path: Path):
    backup, digest, _ = backup_with_evidence(journal, tmp_path)
    journal.db.unlink()
    package_change(journal.root, inactive)
    with pytest.raises(ValueError, match="not ACTIVE"):
        journal.restore(backup, manifest_sha256=digest)
    assert not journal.db.exists()


def test_interrupted_restore_leaves_no_partial_authoritative_database(
    journal: Journal, tmp_path: Path
):
    backup, digest, head = backup_with_evidence(journal, tmp_path)
    journal.db.unlink()
    marker = tmp_path / "restore-ready"
    code = r"""
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import workflow_state as state
def interrupted_link(source,destination):
    Path(sys.argv[5]).write_text('staged')
    while True: time.sleep(.05)
if state.os.name=='nt':
    state.os.rename=interrupted_link
else:
    state.os.link=interrupted_link
state.Journal(Path(sys.argv[2])).restore(Path(sys.argv[3]),manifest_sha256=sys.argv[4])
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(ROOT / "scripts"),
            str(journal.root),
            str(backup),
            digest,
            str(marker),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while (
            not marker.exists()
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert marker.exists(), process.poll()
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert not journal.db.exists()
    with pytest.raises(ValueError, match="missing"):
        journal.verify()
    journal.restore(backup, manifest_sha256=digest)
    assert journal.read("TASK:worker")[1] == head


def test_cli_readonly_commands_and_refusal_leave_receipt_unchanged(repository: Path):
    receipt = (repository / approval.PACKAGE).read_bytes()
    for operation, expected in (("foundation", 0), ("directory", 0), ("verify", 1)):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/workflow_state.py"),
                "--root",
                str(repository),
                operation,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == expected, result.stderr
    assert not control_directory(repository).exists()
    assert (repository / approval.PACKAGE).read_bytes() == receipt


def test_event_size_and_nonfinite_values_refused(journal: Journal):
    head = create(journal)
    for data in ({"value": float("nan")}, {"value": "x" * state.MAX_EVENT}):
        with pytest.raises(ValueError):
            journal.append("TASK:worker", "HOLD", data, expected=head, timestamp=STAMP)
    assert journal.read("TASK:worker")[1] == head


def test_reducer_mutation_cannot_change_stored_event_payloads(
    journal: Journal, tmp_path: Path
):
    source = tmp_path / "source-chain"
    original, _ = source_chain(source)

    def mutating_reducer(prior, event):
        result = reducer(prior, event)
        event["data"]["ignored-mutation"] = "must not reach canonical storage"
        return result

    journal.import_chain(
        "imported:worker",
        source,
        family="feedback",
        binding={},
        reducer=mutating_reducer,
    )
    assert journal.read("imported:worker")[0] == original
    journal.replay("imported:worker", mutating_reducer)
    assert journal.read("imported:worker")[0] == original


def test_import_database_failure_rolls_back_entire_chain(
    journal: Journal, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source-chain"
    source_chain(source)
    prior_insert = journal._insert

    def fail_second(connection, stream, event, raw, evidence):
        prior_insert(connection, stream, event, raw, evidence)
        if event["sequence"] == 2:
            raise sqlite3.OperationalError("Injected database interruption")

    monkeypatch.setattr(journal, "_insert", fail_second)
    with pytest.raises(sqlite3.OperationalError):
        journal.import_chain(
            "imported:worker", source, family="feedback", binding={}, reducer=reducer
        )
    assert Journal(journal.root).verify() == {}


def test_real_pinned_feedback_chain_import_replays_same_attempts_spend_and_dispatch(
    journal: Journal, tmp_path: Path
):
    donor = tmp_path / "pinned-donor"
    closure = [
        "scripts/feedback.py",
        "scripts/model_router.py",
        "scripts/validate_bootstrap.py",
        "scripts/work_packet.py",
        "scripts/software_hardware.py",
        "scripts/cli_exit.py",
        "config/feedback.schema.json",
        "config/model-router.schema.json",
        "config/work-packet.schema.json",
        "config/domains/software-hardware.schema.json",
        "config/feedback.example.json",
        "config/model-router.example.json",
        "examples/work-packets/software-hardware.contract.json",
        "tests/test_model_router.py",
        "tests/test_feedback.py",
    ]
    source = ROOT / "../universal-ai-project-template"
    for relative in closure:
        content = approval.git(source, "show", f"{approval.SOURCE_PIN}:{relative}")
        path = donor / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    code = r"""
import sys,json
from pathlib import Path
donor=Path(sys.argv[1])
sys.path[:0]=[str(donor/'scripts'),str(donor/'tests')]
import test_feedback as fixture
feedback=fixture.feedback
feedback.active_anchor=lambda *args,**kwargs: fixture.ANCHOR
packet=fixture.make_packet()
settings=fixture.router_config(fixture.resource('tier-1',tier=1,api=.1),fixture.resource('tier-2',tier=2,api=.1))
settings['policy']['failures_per_tier']=20
ledger=donor/'recorded-ledger'
feedback.initialize(ledger,packet,[packet],fixture.policy(),settings,donor,'Architect',fixture.timestamp())
dispatch=feedback.reserve(ledger,settings,fixture.options(),donor,fixture.timestamp(1))
report=fixture.result(dispatch,feedback.replay(ledger)[0]['packet'])
report['api_cost_usd']=.5
feedback.complete(ledger,report,fixture.timestamp(2))
second=feedback.reserve(ledger,settings,fixture.options(),donor,fixture.timestamp(3))
assert second['dispatch_id'] is not None
original,count,head=feedback.replay(ledger)
sys.path.insert(0,sys.argv[2])
from workflow_state import Journal
journal=Journal(Path(sys.argv[3]))
apply=lambda value,event: feedback.apply(value,event,stored=True)
receipt=journal.import_chain('pinned-feedback:worker',ledger,family='feedback',binding=feedback.binding(original['packet']),reducer=apply)
replayed,current=journal.replay('pinned-feedback:worker',apply)
assert feedback.wp.canonical(replayed)==feedback.wp.canonical(original)
assert current.sequence==count==4 and current.hash==head==receipt['head']
assert len(replayed['attempts'])==2 and replayed['pending']==second['dispatch_id']
assert replayed['attempts'][0]['result']['api_cost_usd']==.5
audit=donor/'audit'
journal.export('pinned-feedback:worker',audit)
assert [p.read_bytes() for p in sorted(audit.iterdir())]==[p.read_bytes() for p in sorted(ledger.iterdir())]
print(json.dumps({'events':count,'attempts':len(replayed['attempts']),'settled_cost':.5,'pending':second['dispatch_id']}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(donor),
            str(ROOT / "scripts"),
            str(journal.root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert (
        outcome["events"] == 4
        and outcome["attempts"] == 2
        and outcome["settled_cost"] == 0.5
    )
    assert Journal(journal.root).read("pinned-feedback:worker")[1].sequence == 4


def test_cli_initialization_export_backup_restore_roundtrip(
    repository: Path, tmp_path: Path, capsys
):
    base = ["--root", str(repository)]
    assert state.main([*base, "foundation"]) == 0
    assert "8e75e71b" in capsys.readouterr().out
    assert state.main([*base, "directory"]) == 0
    assert str(control_directory(repository)) in capsys.readouterr().out
    assert state.main([*base, "initialize"]) == 0
    capsys.readouterr()
    journal = Journal(repository)
    artifact = journal.directory / "run-cli/output.txt"
    artifact.parent.mkdir()
    artifact.write_bytes(b"CLI preserved output")
    head = create(journal, evidence=(journal.evidence("run-cli/output.txt"),))
    assert state.main([*base, "verify"]) == 0
    assert "1 streams" in capsys.readouterr().out
    audit = tmp_path / "cli-audit"
    assert (
        state.main([*base, "export", "--stream", "TASK:worker", "--out", str(audit)])
        == 0
    )
    capsys.readouterr()
    assert json.loads((audit / "00000001.json").read_bytes())["hash"] == head.hash
    backup = tmp_path / "cli-backup"
    assert state.main([*base, "backup", "--out", str(backup)]) == 0
    digest = capsys.readouterr().out.strip()
    assert digest == hashlib.sha256((backup / "manifest.json").read_bytes()).hexdigest()
    journal.db.unlink()
    artifact.unlink()
    assert (
        state.main(
            [*base, "restore", "--from", str(backup), "--manifest-sha256", digest]
        )
        == 0
    )
    assert "restored and verified" in capsys.readouterr().out
    assert Journal(repository).read("TASK:worker")[1] == head
    assert artifact.read_bytes() == b"CLI preserved output"
    assert (
        state.main(
            [*base, "restore", "--from", str(backup), "--manifest-sha256", digest]
        )
        == 1
    )
    assert "refused" in capsys.readouterr().err


def test_cli_interrupt_returns_130_without_changing_history(
    journal: Journal, monkeypatch: pytest.MonkeyPatch
):
    head = create(journal)

    def interrupted(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(Journal, "verify", interrupted)
    assert state.main(["--root", str(journal.root), "verify"]) == 130
    assert journal.read("TASK:worker")[1] == head


def test_source_bom_and_crlf_are_preserved_without_changing_hashes(
    journal: Journal, tmp_path: Path
):
    source = tmp_path / "source-chain"
    events, originals = source_chain(source)
    raw = b"\xef\xbb\xbf" + originals[0].replace(b"\n", b"\r\n")
    (source / "00000001.json").write_bytes(raw)
    journal.import_chain(
        "imported:worker", source, family="feedback", binding={}, reducer=reducer
    )
    assert journal.read("imported:worker")[0] == events
    audit = tmp_path / "bom-audit"
    journal.export("imported:worker", audit)
    assert (audit / "00000001.json").read_bytes() == raw


def test_invalid_repository_cli_refuses_without_creating_storage(
    tmp_path: Path, capsys
):
    assert state.main(["--root", str(tmp_path), "directory"]) == 1
    assert "refused" in capsys.readouterr().err


def test_atomic_task_role_project_append_commits_together(journal: Journal):
    heads = {name: create(journal, name) for name in ("task", "role", "project")}
    requests = tuple(
        state.Append(
            stream=name,
            kind="HOLD",
            data={"reservation": "same-dispatch"},
            expected=head,
            timestamp=STAMP,
        )
        for name, head in heads.items()
    )
    results = journal.append_many(requests)
    assert all(head.sequence == 2 for head in results)
    assert journal.verify() == dict(zip(heads, results))


@pytest.mark.parametrize("failure", ["stale", "semantic", "approval"])
def test_failure_in_later_atomic_append_rolls_back_all_streams(
    journal: Journal, failure: str
):
    first = create(journal, "task")
    second = create(journal, "project")

    def reject(value, event):
        if event["kind"] != "INIT":
            raise ValueError("Over project cap")
        return value

    if failure == "approval":
        package_change(journal.root, inactive)
    request = state.Append(
        stream="project",
        kind="DISPATCH" if failure == "approval" else "HOLD",
        data={},
        expected=Head() if failure == "stale" else second,
        timestamp=STAMP,
        reducer=reject if failure == "semantic" else None,
    )
    with pytest.raises(ValueError):
        journal.append_many(
            (
                state.Append(
                    stream="task", kind="HOLD", data={}, expected=first, timestamp=STAMP
                ),
                request,
            )
        )
    assert journal.verify() == {"project": second, "task": first}


def test_racing_atomic_appends_have_one_complete_winner(journal: Journal):
    heads = {name: create(journal, name) for name in ("task", "role", "project")}

    def append(writer):
        try:
            return journal.append_many(
                tuple(
                    state.Append(
                        stream=name,
                        kind="HOLD",
                        data={"writer": writer},
                        expected=head,
                        timestamp=STAMP,
                    )
                    for name, head in heads.items()
                )
            )
        except ValueError as error:
            assert "Stale stream head" in str(error)
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append, range(8)))
    assert sum(result is not None for result in results) == 1
    values = [journal.read(name)[0][-1]["data"]["writer"] for name in heads]
    assert len(set(values)) == 1
    assert all(head.sequence == 2 for head in journal.verify().values())


def test_atomic_append_refuses_empty_and_duplicate_stream_batches(journal: Journal):
    head = create(journal)
    request = state.Append(
        stream="TASK:worker", kind="HOLD", data={}, expected=head, timestamp=STAMP
    )
    for requests in ((), (request, request)):
        with pytest.raises(ValueError):
            journal.append_many(requests)
    assert journal.read("TASK:worker")[1] == head


def test_large_cache_spill_kill_recovers_through_public_existing_state_api(
    journal: Journal, tmp_path: Path
):
    head = create(journal)
    marker = tmp_path / "hot-journal-ready"
    code = r"""
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_state import Journal,Head
import validate_workflow_approval as approval
journal=Journal(Path(sys.argv[2]))
with journal._connection(write=True) as db:
    event=journal._new_event(Head(1,sys.argv[3]),'HOLD',{'large':'x'*(3*1024*1024)},'2026-10-14T04:00:00Z')
    journal._insert(db,'TASK:worker',event,approval.canonical(event),())
    Path(sys.argv[4]).write_text('spilled')
    while True: time.sleep(.05)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(ROOT / "scripts"),
            str(journal.root),
            head.hash,
            str(marker),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while (
            not marker.exists()
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert marker.exists(), process.poll()
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert Path(str(journal.db) + "-journal").is_file()
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        Journal(journal.root).read("TASK:worker")
    assert Journal(journal.root).recover() == {"TASK:worker": head}
    assert Journal(journal.root).read("TASK:worker")[1] == head
    assert (
        journal.append(
            "TASK:worker", "HOLD", {}, expected=head, timestamp=STAMP
        ).sequence
        == 2
    )


def test_recovery_refuses_missing_or_corrupted_state(
    repository: Path, journal: Journal
):
    missing = Journal(repository)
    # Same canonical journal initially exists; only remove this fixture's file.
    journal.db.unlink()
    with pytest.raises(ValueError, match="missing"):
        missing.recover()
    assert not missing.db.exists()
    journal.initialize()
    head = create(journal)
    with sqlite3.connect(journal.db) as connection:
        connection.execute("UPDATE streams SET head=?", ("0" * 64,))
    with pytest.raises(ValueError, match="head differs"):
        journal.recover()
    assert head.sequence == 1


def test_restore_uses_exact_verified_bytes_when_source_changes_after_validation(
    journal: Journal, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    backup, digest, head = backup_with_evidence(journal, tmp_path)
    manifest = approval.read_json(backup / "manifest.json")
    journal.db.unlink()
    evidence_path = journal.directory / "run-test/output.tar"
    evidence_path.unlink()
    original_write = state._write_new
    changed = []

    def mutate_backup_during_copy(path, content):
        if path == evidence_path:
            snapshot = object.__new__(Journal)
            snapshot.root, snapshot.directory, snapshot.db, snapshot.identity = (
                journal.root,
                backup,
                backup / "control.sqlite3",
                journal.identity,
            )
            snapshot.append(
                "TASK:worker",
                "HOLD",
                {"unexpected": "backup changed"},
                expected=head,
                timestamp=STAMP,
            )
            changed.append(True)
        original_write(path, content)

    monkeypatch.setattr(state, "_write_new", mutate_backup_during_copy)
    journal.restore(backup, manifest_sha256=digest)
    assert changed == [True]
    assert Journal(journal.root).read("TASK:worker")[1] == head
    assert (
        hashlib.sha256(journal.db.read_bytes()).hexdigest()
        == manifest["database_sha256"]
    )
    assert (
        hashlib.sha256((backup / "control.sqlite3").read_bytes()).hexdigest()
        != manifest["database_sha256"]
    )


def test_revocation_during_semantic_validation_rolls_back_entire_batch(
    journal: Journal,
):
    task = create(journal, "task")
    project = create(journal, "project")
    ready, resume = threading.Event(), threading.Event()

    def revocation(prior, event):
        if event["kind"] == "DISPATCH":
            ready.set()
            assert resume.wait(5)
        return prior

    requests = (
        state.Append(
            stream="task", kind="HOLD", data={}, expected=task, timestamp=STAMP
        ),
        state.Append(
            stream="project",
            kind="DISPATCH",
            data={},
            expected=project,
            timestamp=STAMP,
            reducer=revocation,
        ),
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(journal.append_many, requests)
        assert ready.wait(5)
        package_change(journal.root, inactive)
        resume.set()
        with pytest.raises(ValueError, match="not ACTIVE"):
            future.result(timeout=10)
    assert journal.verify() == {"project": project, "task": task}


def test_imported_state_digest_refuses_changed_reducer_semantics(
    journal: Journal, tmp_path: Path
):
    source = tmp_path / "source-chain"
    source_chain(source)
    journal.import_chain(
        "imported:worker", source, family="feedback", binding={}, reducer=reducer
    )
    head = journal.read("imported:worker")[1]

    def changed_reducer(value, event):
        result = reducer(value, event)
        result["changed-controller-semantics"] = True
        return result

    with pytest.raises(ValueError, match="semantic replay state differs"):
        journal.replay("imported:worker", changed_reducer)
    with pytest.raises(ValueError, match="semantic replay state differs"):
        journal.append(
            "imported:worker",
            "RESULT",
            {"dispatch_id": "dispatch-2", "spend": 0.5},
            expected=head,
            timestamp=STAMP,
            reducer=changed_reducer,
        )
    assert journal.read("imported:worker")[1] == head


def test_cli_recovery_verifies_existing_state(journal: Journal, capsys):
    head = create(journal)
    assert state.main(["--root", str(journal.root), "recover"]) == 0
    assert "recovered and verified: 1 streams" in capsys.readouterr().out
    assert journal.read("TASK:worker")[1] == head
