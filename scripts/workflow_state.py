"""Canonical host control journal; no worker launch, model call or promotion.

The approved foundation validator remains frozen. This adapter binds streams
to that foundation without rewriting its receipt or historical baseline.
"""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Callable, Generator
from typing import Any

# The project keeps executable scripts rather than an installed Python package.
# Explicit package imports also support controller adapters importing this module.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from scripts import validate_workflow_approval as approval  # noqa: E402
from scripts.workflow_runtime import check_state, state_directory  # noqa: E402
from scripts.workflow_scope import checked_path, local_file  # noqa: E402

__all__ = [
    "Journal",
    "Head",
    "Evidence",
    "Append",
    "active_anchor",
    "control_directory",
]
MAX_EVENT = 4 * 1024 * 1024
MAX_EVIDENCE = 32 * 1024 * 1024
MAX_CHAIN = 10000
MAX_TOTAL_EVIDENCE = 256 * 1024 * 1024
EVENT_FIELDS = {"sequence", "previous", "kind", "timestamp", "data", "hash"}
# Outcomes can be recorded after approval revocation; none issues new authority.
OUTCOMES = {
    "RESULT",
    "RESULT_COST_UNKNOWN",
    "ABANDON",
    "APPROVAL_HOLD",
    "HOLD",
    "REVIEW",
    "COST_RECONCILED",
    "RECOVERY",
    "REVIEW_ABANDONED",
}
Reducer = Callable[[Any, dict[str, Any]], Any]


@dataclass(frozen=True)
class Head:
    sequence: int = 0
    hash: str | None = None


@dataclass(frozen=True)
class Evidence:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, kw_only=True)
class Append:
    """One compare-and-swap update in an atomic multi-stream transaction."""

    stream: str
    kind: str
    data: dict[str, Any]
    expected: Head
    timestamp: str | None = None
    evidence: tuple[Evidence, ...] = ()
    reducer: Reducer | None = None


@dataclass(frozen=True)
class _Repository:
    root: Path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(content: bytes) -> Any:
    _require(len(content) <= MAX_EVENT, "JSON exceeds journal size bound")
    try:
        result = json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=approval.unique_object,
            parse_constant=_invalid_constant,
        )
        approval.canonical(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid journal JSON") from exc


def _invalid_constant(_value: str) -> None:
    raise ValueError("Nonfinite JSON number")


def _instant(value: Any) -> datetime:
    _require(
        isinstance(value, str)
        and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value
        )
        is not None,
        "Event timestamp must be timezone-aware UTC",
    )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(instant.utcoffset() == timedelta(0), "Event timestamp must be UTC")
        return instant
    except ValueError as exc:
        raise ValueError("Invalid UTC event timestamp") from exc


def _identifier(value: Any) -> None:
    _require(
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None,
        "Invalid journal identifier",
    )


def _no_links(path: Path) -> None:
    for item in [path, *path.parents]:
        _require(
            not item.is_symlink() and not getattr(item, "is_junction", lambda: False)(),
            "Linked journal path refused",
        )
    if path.is_file():
        _require(path.stat().st_nlink == 1, "Multiply linked journal file refused")


def control_directory(root: Path) -> Path:
    """Resolve, but never create, the runtime's Git-common-directory state root."""
    _require(
        sys.platform != "win32" or sys.version_info >= (3, 12),
        "Windows journal requires Python 3.12+ for junction checks",
    )
    repository = _Repository(Path(root).resolve())
    directory = state_directory(repository)
    check_state(repository, directory)
    return directory


def active_anchor(root: Path, expected: str | None = None) -> str:
    """Read-only bootstrap adapter; current ACTIVE receipt and all bindings required."""
    root = Path(root).resolve()
    package = approval.read_json(approval.safe_file(root, approval.PACKAGE))
    anchor = approval.validate(package, root, require_active=True)
    _require(
        expected is None or anchor == expected,
        "Approval anchor changed; scheduling held",
    )
    return anchor


def _event(
    raw: bytes, expected: Head, previous_time: datetime | None
) -> dict[str, Any]:
    _require(
        type(expected.sequence) is int
        and expected.sequence >= 0
        and (
            (expected.sequence == 0 and expected.hash is None)
            or (expected.sequence > 0 and approval.hex_digest(expected.hash, 64))
        ),
        "Invalid expected stream head",
    )
    event = _json(raw)
    _require(
        isinstance(event, dict) and set(event) == EVENT_FIELDS, "Invalid event fields"
    )
    _require(
        type(event["sequence"]) is int
        and event["sequence"] == expected.sequence + 1
        and event["previous"] == expected.hash,
        "Journal sequence/hash chain has a gap or mismatch",
    )
    _identifier(event["kind"])
    _require(isinstance(event["data"], dict), "Event data must be an object")
    instant = _instant(event["timestamp"])
    _require(
        previous_time is None or instant >= previous_time, "Journal timestamps descend"
    )
    _require(
        approval.hex_digest(event["hash"], 64)
        and event["hash"]
        == _digest(
            approval.canonical(
                {key: value for key, value in event.items() if key != "hash"}
            )
        ),
        "Journal event digest mismatch",
    )
    return event


def _evidence_path(root: Path, relative: str) -> Path:
    checked_path(relative)
    parts = relative.split("/")
    _require(
        len(parts) >= 2 and re.fullmatch(r"run-[A-Za-z0-9_-]+", parts[0]) is not None,
        "Evidence must belong to a canonical run directory",
    )
    _no_links(root)
    return local_file(root, relative)


def _check_evidence(root: Path, evidence: Evidence) -> bytes:
    _require(
        approval.hex_digest(evidence.sha256, 64)
        and type(evidence.size) is int
        and 0 <= evidence.size <= MAX_EVIDENCE,
        "Invalid evidence reference",
    )
    path = _evidence_path(root, evidence.path)
    _require(path.stat().st_size == evidence.size, "Referenced evidence size mismatch")
    content = path.read_bytes()
    _require(_digest(content) == evidence.sha256, "Referenced evidence digest mismatch")
    return content


class Journal:
    """Append-only streams with compare-and-swap heads, replay and verified backup.

    Construction and reads do not create files. Call initialize explicitly.
    Controllers supply their own pure semantic reducer; storage never changes
    canonical events, lifetime attempts, pending liabilities or task identities.
    """

    def __init__(self, root: Path, *, state: Path | None = None):
        self.root = Path(root).resolve()
        self.directory = control_directory(self.root)
        if state is not None:
            _require(
                Path(state).resolve() == self.directory.resolve(),
                "Alternate control state refused",
            )
        self.db = self.directory / "control.sqlite3"
        self.identity = str(
            Path(
                approval.git(
                    self.root, "rev-parse", "--path-format=absolute", "--git-common-dir"
                )
                .decode()
                .strip()
            ).resolve()
        )
        if os.name == "nt":
            self.identity = self.identity.casefold()
        _no_links(self.db)

    @contextmanager
    def _connection(
        self, *, write: bool = False
    ) -> Generator[sqlite3.Connection, None, None]:
        _no_links(self.db)
        _require(
            self.db.is_file(),
            "Control journal missing; initialize or restore explicitly",
        )
        connection = sqlite3.connect(
            self.db.as_uri() + "?mode=rw" if write else self.db.as_uri() + "?mode=ro",
            uri=True,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            _require(
                connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "Control database integrity check failed",
            )
            _require(
                connection.execute("PRAGMA foreign_key_check").fetchone() is None,
                "Orphan journal or evidence row",
            )
            metadata = dict(connection.execute("SELECT key,value FROM metadata"))
            _require(
                metadata == {"version": "1", "repository": self.identity},
                "Control journal repository/schema identity differs",
            )
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        active_anchor(self.root)
        _no_links(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        # Exclusive creation refuses an existing, interrupted or restored journal.
        descriptor = os.open(self.db, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        connection = sqlite3.connect(self.db, timeout=10)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE streams (
                    id TEXT PRIMARY KEY, family TEXT NOT NULL, anchor TEXT NOT NULL,
                    binding BLOB NOT NULL, sequence INTEGER NOT NULL, head TEXT);
                CREATE TABLE events (
                    stream TEXT NOT NULL REFERENCES streams(id), sequence INTEGER NOT NULL,
                    previous TEXT, hash TEXT NOT NULL, timestamp TEXT NOT NULL,
                    canonical BLOB NOT NULL, original BLOB NOT NULL, references_sha256 TEXT NOT NULL,
                    PRIMARY KEY(stream,sequence));
                CREATE TABLE evidence (
                    stream TEXT NOT NULL, sequence INTEGER NOT NULL, path TEXT NOT NULL,
                    sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                    PRIMARY KEY(stream,sequence,path),
                    FOREIGN KEY(stream,sequence) REFERENCES events(stream,sequence));
                CREATE TABLE imports (
                    stream TEXT PRIMARY KEY REFERENCES streams(id), receipt BLOB NOT NULL);
                CREATE TRIGGER events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
                CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence
                    BEGIN SELECT RAISE(ABORT,'evidence references are immutable'); END;
                CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence
                    BEGIN SELECT RAISE(ABORT,'evidence references are immutable'); END;
                CREATE TRIGGER imports_no_update BEFORE UPDATE ON imports
                    BEGIN SELECT RAISE(ABORT,'import receipts are immutable'); END;
                CREATE TRIGGER imports_no_delete BEFORE DELETE ON imports
                    BEGIN SELECT RAISE(ABORT,'import receipts are immutable'); END;
                CREATE TRIGGER stream_binding_no_update BEFORE UPDATE OF id,family,anchor,binding ON streams
                    BEGIN SELECT RAISE(ABORT,'stream bindings are immutable'); END;
                CREATE TRIGGER streams_no_delete BEFORE DELETE ON streams
                    BEGIN SELECT RAISE(ABORT,'stream history is retained'); END;
            """)
            connection.executemany(
                "INSERT INTO metadata VALUES (?,?)",
                [("version", "1"), ("repository", self.identity)],
            )
            connection.commit()
        finally:
            connection.close()

    def evidence(self, relative: str) -> Evidence:
        """Bind an existing coordinator evidence file; never writes that file."""
        path = _evidence_path(self.directory, relative)
        _require(path.stat().st_size <= MAX_EVIDENCE, "Evidence exceeds size bound")
        content = path.read_bytes()
        return Evidence(relative, _digest(content), len(content))

    def _read(
        self, connection: sqlite3.Connection, stream: str
    ) -> tuple[list[dict[str, Any]], Head]:
        _identifier(stream)
        record = connection.execute(
            "SELECT * FROM streams WHERE id=?", (stream,)
        ).fetchone()
        _require(record is not None, "Unknown journal stream")
        _require(
            approval.hex_digest(record["anchor"], 64)
            and isinstance(_json(record["binding"]), dict),
            "Invalid stream binding",
        )
        events, head, previous_time = [], Head(), None
        for row in connection.execute(
            "SELECT * FROM events WHERE stream=? ORDER BY sequence", (stream,)
        ):
            event = _event(row["original"], head, previous_time)
            _require(
                row["canonical"] == approval.canonical(event)
                and row["sequence"] == event["sequence"]
                and row["previous"] == event["previous"]
                and row["hash"] == event["hash"]
                and row["timestamp"] == event["timestamp"],
                "Stored journal event differs",
            )
            references = [
                Evidence(*reference)
                for reference in connection.execute(
                    "SELECT path,sha256,size FROM evidence WHERE stream=? AND sequence=? ORDER BY path",
                    (stream, event["sequence"]),
                )
            ]
            _require(
                row["references_sha256"]
                == _digest(
                    approval.canonical([reference.__dict__ for reference in references])
                ),
                "Evidence reference inventory differs",
            )
            for reference in references:
                _check_evidence(self.directory, reference)
            events.append(event)
            head, previous_time = (
                Head(event["sequence"], event["hash"]),
                _instant(event["timestamp"]),
            )
        _require(
            bool(events) and events[0]["kind"] == "INIT",
            "Stream requires one initial INIT event",
        )
        _require(
            all(event["kind"] != "INIT" for event in events[1:]),
            "Repeated INIT cannot reset history",
        )
        _require(
            type(record["sequence"]) is int
            and Head(record["sequence"], record["head"]) == head,
            "Stored stream head differs from journal history",
        )
        imported = connection.execute(
            "SELECT receipt FROM imports WHERE stream=?", (stream,)
        ).fetchone()
        if imported:
            receipt = _json(imported[0])
            count = receipt.get("count")
            _require(
                type(count) is int
                and 0 < count <= len(events)
                and receipt.get("head") == events[count - 1]["hash"]
                and approval.hex_digest(receipt.get("state_sha256"), 64),
                "Import receipt differs from source chain",
            )
            originals = [
                row[0]
                for row in connection.execute(
                    "SELECT original FROM events WHERE stream=? AND sequence<=? ORDER BY sequence",
                    (stream, count),
                )
            ]
            _require(
                receipt.get("source_sha256")
                == _digest(approval.canonical([_digest(raw) for raw in originals])),
                "Imported source bytes differ",
            )
        return events, head

    def read(self, stream: str) -> tuple[list[dict[str, Any]], Head]:
        with self._connection() as connection:
            return self._read(connection, stream)

    def verify(self) -> dict[str, Head]:
        with self._connection() as connection:
            return {
                row[0]: self._read(connection, row[0])[1]
                for row in connection.execute("SELECT id FROM streams ORDER BY id")
            }

    def recover(self) -> dict[str, Head]:
        """Recover spilled uncommitted pages in existing SQLite state, then verify.

        This explicit operation never initializes missing state or launches work.
        """
        with self._connection(write=True) as connection:
            self._verify_all(connection)
            return {
                row[0]: self._read(connection, row[0])[1]
                for row in connection.execute("SELECT id FROM streams ORDER BY id")
            }

    def replay(self, stream: str, reducer: Reducer) -> tuple[Any, Head]:
        with self._connection() as connection:
            events, head = self._read(connection, stream)
            return self._reduce_events(connection, stream, events, reducer), head

    def _reduce_events(
        self,
        connection: sqlite3.Connection,
        stream: str,
        events: list[dict[str, Any]],
        reducer: Reducer,
    ) -> Any:
        imported = connection.execute(
            "SELECT receipt FROM imports WHERE stream=?", (stream,)
        ).fetchone()
        receipt = _json(imported[0]) if imported else None
        result = None
        for event in events:
            result = reducer(
                result,
                copy.deepcopy(
                    {key: value for key, value in event.items() if key != "hash"}
                ),
            )
            if receipt and event["sequence"] == receipt["count"]:
                _require(
                    _digest(approval.canonical(result)) == receipt["state_sha256"],
                    "Imported semantic replay state differs; controller migration held",
                )
        return result

    def _insert(
        self,
        connection: sqlite3.Connection,
        stream: str,
        event: dict[str, Any],
        raw: bytes,
        evidence: tuple[Evidence, ...],
    ) -> None:
        _require(
            approval.canonical(_json(raw)) == approval.canonical(event),
            "Original event bytes differ",
        )
        _require(
            len({entry.path for entry in evidence}) == len(evidence),
            "Duplicate evidence path",
        )
        for entry in evidence:
            _check_evidence(self.directory, entry)
        references_hash = _digest(
            approval.canonical(
                [
                    entry.__dict__
                    for entry in sorted(evidence, key=lambda item: item.path)
                ]
            )
        )
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
            (
                stream,
                event["sequence"],
                event["previous"],
                event["hash"],
                event["timestamp"],
                approval.canonical(event),
                raw,
                references_hash,
            ),
        )
        connection.executemany(
            "INSERT INTO evidence VALUES (?,?,?,?,?)",
            [
                (stream, event["sequence"], item.path, item.sha256, item.size)
                for item in evidence
            ],
        )
        connection.execute(
            "UPDATE streams SET sequence=?,head=? WHERE id=?",
            (event["sequence"], event["hash"], stream),
        )

    def create(
        self,
        stream: str,
        *,
        family: str,
        binding: dict[str, Any],
        data: dict[str, Any],
        timestamp: str | None = None,
        evidence: tuple[Evidence, ...] = (),
        reducer: Reducer | None = None,
    ) -> Head:
        _identifier(stream)
        _require(
            family in {"feedback", "acceptance", "project"}, "Unknown journal family"
        )
        _require(isinstance(binding, dict), "Stream binding must be an object")
        anchor = active_anchor(self.root)
        event = self._new_event(Head(), "INIT", data, timestamp)
        if reducer is not None:
            reducer(
                None,
                copy.deepcopy(
                    {key: value for key, value in event.items() if key != "hash"}
                ),
            )
        with self._connection(write=True) as connection:
            self._verify_all(connection)
            active_anchor(self.root, anchor)
            _require(
                connection.execute(
                    "SELECT 1 FROM streams WHERE id=?", (stream,)
                ).fetchone()
                is None,
                "Stream already exists; INIT cannot reset history",
            )
            connection.execute(
                "INSERT INTO streams VALUES (?,?,?,?,0,NULL)",
                (stream, family, anchor, approval.canonical(binding)),
            )
            self._insert(connection, stream, event, approval.canonical(event), evidence)
            active_anchor(self.root, anchor)
        return Head(event["sequence"], event["hash"])

    def _verify_all(self, connection: sqlite3.Connection) -> None:
        for row in connection.execute("SELECT id FROM streams"):
            self._read(connection, row[0])

    @staticmethod
    def _new_event(
        expected: Head, kind: str, data: dict[str, Any], timestamp: str | None
    ) -> dict[str, Any]:
        event = {
            "sequence": expected.sequence + 1,
            "previous": expected.hash,
            "kind": kind,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if timestamp is None
            else timestamp,
            "data": data,
        }
        event["hash"] = _digest(approval.canonical(event))
        return _event(approval.canonical(event), expected, None)

    def append(
        self,
        stream: str,
        kind: str,
        data: dict[str, Any],
        *,
        expected: Head,
        timestamp: str | None = None,
        evidence: tuple[Evidence, ...] = (),
        reducer: Reducer | None = None,
    ) -> Head:
        return self.append_many(
            (
                Append(
                    stream=stream,
                    kind=kind,
                    data=data,
                    expected=expected,
                    timestamp=timestamp,
                    evidence=evidence,
                    reducer=reducer,
                ),
            )
        )[0]

    def append_many(self, requests: tuple[Append, ...]) -> tuple[Head, ...]:
        """Atomically update task/role/project streams; any stale head rolls back all.

        Controllers decide reservation/cap semantics. This storage operation only
        provides one durable transaction and independent expected stream heads.
        """
        _require(
            0 < len(requests) <= 16
            and all(isinstance(item, Append) for item in requests),
            "Atomic append requires one through sixteen Append requests",
        )
        _require(
            len({item.stream for item in requests}) == len(requests),
            "Atomic append requires distinct streams",
        )
        result = []
        scheduling_anchors: set[str] = set()
        with self._connection(write=True) as connection:
            self._verify_all(connection)
            for request in requests:
                _require(request.kind != "INIT", "Repeated INIT cannot reset history")
                event = self._new_event(
                    request.expected, request.kind, request.data, request.timestamp
                )
                events, current = self._read(connection, request.stream)
                _require(
                    current == request.expected,
                    "Stale stream head; replay before retrying",
                )
                record = connection.execute(
                    "SELECT anchor FROM streams WHERE id=?", (request.stream,)
                ).fetchone()
                if request.kind not in OUTCOMES:
                    active_anchor(self.root, record[0])
                    scheduling_anchors.add(record[0])
                _event(
                    approval.canonical(event),
                    current,
                    _instant(events[-1]["timestamp"]),
                )
                if request.reducer is not None:
                    self._reduce_events(
                        connection, request.stream, [*events, event], request.reducer
                    )
                self._insert(
                    connection,
                    request.stream,
                    event,
                    approval.canonical(event),
                    request.evidence,
                )
                result.append(Head(event["sequence"], event["hash"]))
            # Check after potentially slow reducers/evidence and just before commit.
            for anchor in scheduling_anchors:
                active_anchor(self.root, anchor)
        return tuple(result)

    def import_chain(
        self,
        stream: str,
        source: Path,
        *,
        family: str,
        binding: dict[str, Any],
        reducer: Reducer,
        evidence: tuple[Evidence, ...] = (),
    ) -> dict[str, Any]:
        """One-time trusted-controller import; full chain and semantic replay required."""
        _identifier(stream)
        _require(
            family in {"feedback", "acceptance", "project"}
            and isinstance(binding, dict),
            "Invalid import family/binding",
        )
        _require(
            callable(reducer),
            "Import requires the controller's semantic replay reducer",
        )
        source = Path(source).absolute()
        _no_links(source)
        paths = sorted(source.iterdir())
        _require(
            0 < len(paths) <= MAX_CHAIN, "Source chain is empty or exceeds import bound"
        )
        events, originals, head, instant, state = [], [], Head(), None, None
        total = 0
        for sequence, path in enumerate(paths, 1):
            _no_links(path)
            _require(
                path.name == f"{sequence:08d}.json" and path.is_file(),
                "Source ledger has a gap or unexpected entry",
            )
            _require(
                path.stat().st_size <= MAX_EVENT, "Source event exceeds size bound"
            )
            raw = path.read_bytes()
            total += len(raw)
            _require(total <= MAX_TOTAL_EVIDENCE, "Source ledger exceeds byte bound")
            event = _event(raw, head, instant)
            _require(
                (sequence == 1 and event["kind"] == "INIT")
                or (sequence > 1 and event["kind"] != "INIT"),
                "Source chain must start with one INIT",
            )
            state = reducer(
                state,
                copy.deepcopy(
                    {key: value for key, value in event.items() if key != "hash"}
                ),
            )
            events.append(event)
            originals.append(raw)
            head, instant = Head(sequence, event["hash"]), _instant(event["timestamp"])
        receipt = {
            "count": head.sequence,
            "head": head.hash,
            "source_sha256": _digest(
                approval.canonical([_digest(raw) for raw in originals])
            ),
            "state_sha256": _digest(approval.canonical(state)),
        }
        anchor = active_anchor(self.root)
        with self._connection(write=True) as connection:
            self._verify_all(connection)
            active_anchor(self.root, anchor)
            _require(
                connection.execute(
                    "SELECT 1 FROM streams WHERE id=?", (stream,)
                ).fetchone()
                is None,
                "Import is one-time; existing stream cannot be replaced",
            )
            connection.execute(
                "INSERT INTO streams VALUES (?,?,?,?,0,NULL)",
                (stream, family, anchor, approval.canonical(binding)),
            )
            for event, raw in zip(events, originals):
                self._insert(
                    connection,
                    stream,
                    event,
                    raw,
                    evidence if event["sequence"] == head.sequence else (),
                )
            connection.execute(
                "INSERT INTO imports VALUES (?,?)",
                (stream, approval.canonical(receipt)),
            )
            active_anchor(self.root, anchor)
        return receipt

    def export(self, stream: str, destination: Path) -> None:
        """Numbered JSON audit view; writes preserved bytes and never reads it as authority."""
        destination = Path(destination).absolute()
        _no_links(destination)
        with self._connection() as connection:
            self._read(connection, stream)
            destination.mkdir(parents=True, exist_ok=False)
            for row in connection.execute(
                "SELECT sequence,original FROM events WHERE stream=? ORDER BY sequence",
                (stream,),
            ):
                _write_new(destination / f"{row[0]:08d}.json", row[1])

    def backup(self, destination: Path) -> str:
        """Consistent SQLite backup plus every referenced evidence file; returns manifest digest."""
        destination = Path(destination).absolute()
        _no_links(destination)
        with self._connection() as connection:
            self._verify_all(connection)
            destination.mkdir(parents=True, exist_ok=False)
            database = destination / "control.sqlite3"
            snapshot = sqlite3.connect(database)
            try:
                connection.backup(snapshot)
            finally:
                snapshot.close()
            heads = {
                row[0]: {"sequence": row[1], "hash": row[2]}
                for row in connection.execute(
                    "SELECT id,sequence,head FROM streams ORDER BY id"
                )
            }
            references: dict[str, Evidence] = {}
            for row in connection.execute("SELECT path,sha256,size FROM evidence"):
                reference = Evidence(*row)
                _require(
                    reference.path not in references
                    or reference == references[reference.path],
                    "Conflicting evidence references",
                )
                references[reference.path] = reference
            _require(
                sum(item.size for item in references.values()) <= MAX_TOTAL_EVIDENCE,
                "Backup evidence exceeds size bound",
            )
            for relative, reference in sorted(references.items()):
                content = _check_evidence(self.directory, reference)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_new(target, content)
            manifest = {
                "version": 1,
                "repository": self.identity,
                "database_sha256": _digest(database.read_bytes()),
                "heads": heads,
                "evidence": [item.__dict__ for item in references.values()],
            }
            raw = approval.canonical(manifest)
            _write_new(destination / "manifest.json", raw)
        return _digest(raw)

    def restore(self, source: Path, *, manifest_sha256: str) -> None:
        """Verify an externally bound backup; install only into an absent control journal."""
        active_anchor(self.root)
        _no_links(self.db)
        _require(
            not self.db.exists(), "Restore never overwrites an existing control journal"
        )
        source = Path(source).absolute()
        _no_links(source)
        manifest_path = local_file(source, "manifest.json")
        raw = manifest_path.read_bytes()
        _require(
            approval.hex_digest(manifest_sha256, 64)
            and _digest(raw) == manifest_sha256,
            "Backup manifest digest mismatch",
        )
        manifest = _json(raw)
        _require(
            isinstance(manifest, dict)
            and set(manifest)
            == {"version", "repository", "database_sha256", "heads", "evidence"}
            and type(manifest["version"]) is int
            and manifest["version"] == 1
            and manifest["repository"] == self.identity,
            "Backup repository/schema identity differs",
        )
        database = local_file(source, "control.sqlite3")
        database_content = database.read_bytes()
        _require(
            _digest(database_content) == manifest["database_sha256"],
            "Backup database digest mismatch",
        )
        # Verify a private copy of exactly the digest-bound bytes. Never reread
        # a mutable source database to populate the authoritative staged file.
        with tempfile.TemporaryDirectory(prefix="workflow-control-restore-") as private:
            verified_database = Path(private) / "control.sqlite3"
            _write_new(verified_database, database_content)
            snapshot = object.__new__(Journal)
            snapshot.root, snapshot.directory, snapshot.db, snapshot.identity = (
                self.root,
                source,
                verified_database,
                self.identity,
            )
            actual = {
                key: {"sequence": head.sequence, "hash": head.hash}
                for key, head in snapshot.verify().items()
            }
            _require(actual == manifest["heads"], "Backup stream heads differ")
            with snapshot._connection() as connection:
                references = {
                    row[0]: Evidence(*row)
                    for row in connection.execute(
                        "SELECT path,sha256,size FROM evidence"
                    )
                }
                restore_anchors = [
                    row[0] for row in connection.execute("SELECT anchor FROM streams")
                ]
                for anchor in restore_anchors:
                    active_anchor(self.root, anchor)
        _require(
            isinstance(manifest["evidence"], list)
            and len(manifest["evidence"]) == len(references),
            "Backup evidence inventory differs",
        )
        expected = {item.path: item.__dict__ for item in references.values()}
        _require(
            {item["path"]: item for item in manifest["evidence"]} == expected,
            "Backup evidence inventory differs",
        )
        contents = {
            relative: _check_evidence(source, item)
            for relative, item in references.items()
        }
        _require(
            sum(len(content) for content in contents.values()) <= MAX_TOTAL_EVIDENCE,
            "Restore evidence exceeds size bound",
        )
        for relative, content in contents.items():
            target = self.directory / relative
            _no_links(target)
            if target.exists():
                _require(
                    _check_evidence(self.directory, references[relative]) == content,
                    "Restore evidence conflicts with preserved local file",
                )
        _no_links(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        for relative, content in contents.items():
            target = self.directory / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_new(target, content)
        # Fully flush a staged file, then install it atomically without replacement.
        # A crash before installation leaves no partial authoritative control database.
        descriptor, temporary = tempfile.mkstemp(
            prefix="restore-", suffix=".sqlite3", dir=self.directory
        )
        stage = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(database_content)
                output.flush()
                os.fsync(output.fileno())
            _require(
                _digest(stage.read_bytes()) == manifest["database_sha256"],
                "Staged database differs from verified backup",
            )
            for anchor in restore_anchors:
                active_anchor(self.root, anchor)
            if os.name == "nt":
                # Windows rename is atomic and refuses an existing destination.
                os.rename(stage, self.db)
            else:
                os.link(stage, self.db)
        finally:
            stage.unlink(missing_ok=True)
        installed = {
            key: {"sequence": head.sequence, "hash": head.hash}
            for key, head in self.verify().items()
        }
        _require(
            installed == manifest["heads"]
            and _digest(self.db.read_bytes()) == manifest["database_sha256"],
            "Installed database differs from verified backup",
        )


def _write_new(path: Path, content: bytes) -> None:
    with path.open("xb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("foundation", help="Read-only ACTIVE foundation inspection")
    commands.add_parser(
        "directory", help="Resolve canonical directory without creating storage"
    )
    commands.add_parser(
        "initialize", help="Create control.sqlite3 only with current ACTIVE approval"
    )
    commands.add_parser("verify", help="Read-only journal/head/evidence verification")
    commands.add_parser(
        "recover",
        help="Recover interrupted existing SQLite state and verify; never launch",
    )
    export = commands.add_parser(
        "export", help="Write a numbered, non-authoritative audit view"
    )
    export.add_argument("--stream", required=True)
    export.add_argument("--out", required=True, type=Path)
    backup = commands.add_parser(
        "backup", help="Write a consistent journal/evidence backup"
    )
    backup.add_argument("--out", required=True, type=Path)
    restore = commands.add_parser(
        "restore", help="Restore verified backup into absent control state"
    )
    restore.add_argument("--from", dest="source", required=True, type=Path)
    restore.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "foundation":
            print(active_anchor(args.root))
            return 0
        journal = Journal(args.root)
        if args.command == "directory":
            print(journal.directory)
        elif args.command == "initialize":
            journal.initialize()
            print("Control journal initialized; no dispatch or launch")
        elif args.command == "verify":
            heads = journal.verify()
            print(f"Control journal verified: {len(heads)} streams; evidence intact")
        elif args.command == "recover":
            heads = journal.recover()
            print(
                f"Control journal recovered and verified: {len(heads)} streams; no dispatch or launch"
            )
        elif args.command == "export":
            journal.export(args.stream, args.out)
            print("Audit view exported; canonical state unchanged")
        elif args.command == "backup":
            print(journal.backup(args.out))
        elif args.command == "restore":
            journal.restore(args.source, manifest_sha256=args.manifest_sha256)
            print("Journal and evidence restored and verified; no dispatch or launch")
        return 0
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ):
        print(
            "Control journal refused; verify foundation, chain, heads and evidence",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
