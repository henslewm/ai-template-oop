"""Coordinator-only packet scope, export, ownership and output checks.

No Git mutation, model invocation, task ledger, budget controller or promotion.
Canonical task lifecycle remains scripts/work_packet.py.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sqlite3
import os
import sys
import subprocess
import tarfile
import time
import uuid

import work_packet as wp

MAX_FILE = 2 * 1024 * 1024
MAX_EXPORT = 16 * 1024 * 1024
PROTECTED_PARTS = {".git", ".agents", ".codex", ".aws", ".env"}
SCOPE_KEYS = {
    "schema_version",
    "role",
    "feature_id",
    "owner",
    "run_id",
    "branch",
    "workspace",
    "base_commit",
    "packet_revision_hash",
    "interface_revision",
    "read_paths",
    "write_paths",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Scope paths must be nonempty relative POSIX paths")
    parts = value.split("/")
    if any(
        p in {"", ".", ".."}
        or p.casefold() in PROTECTED_PARTS
        or p.endswith((".", " "))
        or any(ord(c) < 32 for c in p)
        or re.match(r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", p)
        for p in parts
    ):
        raise ValueError("Unsafe scope path")
    if PurePosixPath(value).is_absolute():
        raise ValueError("Absolute scope path")
    return value


def local_file(root: Path, relative: str, missing=False) -> Path:
    checked_path(relative)
    target = root
    for part in relative.split("/"):
        target = target / part
        if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
            raise ValueError("Linked scope paths are prohibited")
    if not target.exists():
        if missing and target.parent.is_dir():
            return target
        raise ValueError("Scope file missing: " + relative)
    if not target.is_file() or target.stat().st_nlink != 1:
        raise ValueError("Scope files must be regular, singly linked files")
    return target


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def belongs(path: str, feature: str, role: str, writing=False) -> bool:
    if role == "feature":
        owned = (f"src/features/{feature}.py", f"tests/test_feature_{feature}.py")
        roots = (
            f"src/features/{feature}/",
            f"tests/features/{feature}/",
            f"handoffs/features/{feature}/",
        )
    else:
        owned = ("tests/test_ui.py",)
        roots = ("src/ui/", "tests/ui/", "handoffs/ui/")
    if path in owned or path.startswith(roots):
        return True
    if not writing:
        return path.startswith("contracts/") or path in {
            "src/__init__.py",
            "src/features/__init__.py" if role == "feature" else "src/ui/__init__.py",
            "tests/test_contract_" + feature + ".py",
        }
    return False


@dataclass(frozen=True)
class SessionScope:
    data: dict

    @classmethod
    def load(cls, value: dict) -> "SessionScope":
        if os.name == "nt" and sys.version_info < (3, 12):
            raise ValueError(
                "Windows scope controls require Python 3.12+ junction detection"
            )
        if not isinstance(value, dict) or set(value) != SCOPE_KEYS:
            raise ValueError("Scope fields do not match schema version 1.0")
        if value["schema_version"] != "1.0" or value["role"] not in {
            "feature",
            "ui",
            "maintenance",
        }:
            raise ValueError("Unsupported scope version or role")
        maintenance = None
        if value["role"] == "maintenance":
            from scripts.pilot_authority import load_profile

            maintenance = load_profile(Path(value["workspace"]))
        for key in ("owner", "run_id", "feature_id"):
            if not isinstance(value[key], str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value[key]
            ):
                raise ValueError("Invalid " + key)
        if not isinstance(value["branch"], str) or not value["branch"].startswith(
            ("feature/", "ui/")
        ):
            raise ValueError(
                "Only retained feature/UI branches are worker destinations"
            )
        for key, length in (
            ("base_commit", 40),
            ("packet_revision_hash", 64),
            ("interface_revision", 64),
        ):
            if not isinstance(value[key], str) or not re.fullmatch(
                "[a-f0-9]{" + str(length) + "}", value[key]
            ):
                raise ValueError("Invalid revision: " + key)
        root = Path(value["workspace"])
        if not root.is_absolute():
            raise ValueError("Workspace must be absolute")
        for key in ("read_paths", "write_paths"):
            paths = value[key]
            if (
                not isinstance(paths, list)
                or not paths
                or any(not isinstance(p, str) for p in paths)
            ):
                raise ValueError("Empty or malformed " + key)
            if len(paths) > (8 if key == "write_paths" else 128):
                raise ValueError("Scope path count exceeds runtime size bound")
            if len(set(p.casefold() for p in paths)) != len(paths):
                raise ValueError("Duplicate or case-colliding scope paths")
            for path in paths:
                checked_path(path)
                allowed = (
                    path in maintenance[key]
                    if maintenance is not None
                    else belongs(
                        path, value["feature_id"], value["role"], key == "write_paths"
                    )
                )
                if not allowed:
                    raise ValueError("Path outside role ownership: " + path)
        if not set(value["write_paths"]).issubset(value["read_paths"]):
            raise ValueError("Writable files must be explicitly included in read scope")
        paths = value["read_paths"]
        if any(a != b and b.startswith(a + "/") for a in paths for b in paths):
            raise ValueError("Scope file overlaps another file's directory")
        if not any(p.startswith("contracts/") for p in paths):
            raise ValueError("A scope must name its immutable interface inputs")
        return cls(json.loads(wp.canonical(value)))

    @property
    def root(self) -> Path:
        return Path(self.data["workspace"])

    @property
    def hash(self) -> str:
        return digest(wp.canonical(self.data).encode())

    def verify_base(self) -> None:
        if (
            git(self.root, "rev-parse", "--show-toplevel").replace("\\", "/").casefold()
            != self.root.as_posix().casefold()
        ):
            raise ValueError("Workspace must be the checkout root")
        if git(self.root, "branch", "--show-current") != self.data["branch"]:
            raise ValueError("Wrong branch")
        if git(self.root, "rev-parse", "HEAD") != self.data["base_commit"]:
            raise ValueError("Stale base")
        if git(self.root, "diff", "--name-only") or git(
            self.root, "diff", "--cached", "--name-only"
        ):
            raise ValueError(
                "Tracked workspace changes must be reconciled by its owner first"
            )

    def verify_packet(self, packet: dict, graph: list[dict]) -> None:
        wp.require_valid(packet)
        if wp.current(packet)["hash"] != self.data["packet_revision_hash"]:
            raise ValueError("Stale packet revision")
        if packet["state"] != "READY":
            raise ValueError("Packet is not READY")
        wp.graph_order([packet, *graph])
        states = {p["task_id"]: p["state"] for p in graph}
        for dependency in wp.current(packet)["contract"]["dependencies"]:
            if states.get(dependency) != "VERIFIED":
                raise ValueError("Dependency is not VERIFIED: " + dependency)

    def files(self) -> dict[str, bytes]:
        result = {}
        for relative in self.data["read_paths"]:
            path = self.root / relative
            if not path.exists() and relative in self.data["write_paths"]:
                # A declared new file may be supplied as an empty writable placeholder.
                local_file(self.root, relative, missing=True)
                result[relative] = b""
                continue
            path = local_file(self.root, relative)
            if path.stat().st_size > MAX_FILE:
                raise ValueError("Scope file too large")
            result[relative] = path.read_bytes()
        if sum(map(len, result.values())) > MAX_EXPORT:
            raise ValueError("Scope export too large")
        interfaces = {
            p: digest(b) for p, b in result.items() if p.startswith("contracts/")
        }
        if digest(wp.canonical(interfaces).encode()) != self.data["interface_revision"]:
            raise ValueError("Stale interface revision")
        return result

    def export(
        self, packet: dict, graph: list[dict], *, instructions=None
    ) -> tuple[bytes, dict]:
        self.verify_base()
        self.verify_packet(packet, graph)
        contents = self.files()
        baseline = {
            p: digest(b) if (self.root / p).exists() else None
            for p, b in contents.items()
        }
        records = {
            "packet.json": wp.canonical(packet).encode(),
            "scope.json": wp.canonical(self.data).encode(),
            "baseline.json": wp.canonical(baseline).encode(),
        }
        if instructions is not None:
            if (
                set(instructions)
                != {"brief.json", "worker-rules.md", "dispatch.json", "report.json"}
                or any(
                    not isinstance(b, bytes) or len(b) > MAX_FILE
                    for b in instructions.values()
                )
                or instructions["report.json"] != b""
            ):
                raise ValueError("Invalid bounded dispatch instructions")
            records.update(instructions)
        records.update({"workspace/" + p: b for p, b in contents.items()})
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            dirs = {"."}
            for name in records:
                parent = PurePosixPath(name).parent
                while str(parent) != ".":
                    dirs.add(str(parent))
                    parent = parent.parent
            for directory in sorted(dirs, key=lambda p: (p.count("/"), p)):
                info = tarfile.TarInfo(directory)
                info.type, info.mode, info.uid, info.gid = tarfile.DIRTYPE, 0o555, 0, 0
                archive.addfile(info)
            for name, data in sorted(records.items()):
                info = tarfile.TarInfo(name)
                writable = (
                    name.startswith("workspace/")
                    and name[10:] in self.data["write_paths"]
                    or instructions is not None
                    and name == "report.json"
                )
                info.size, info.mode = len(data), 0o644 if writable else 0o444
                info.uid = info.gid = 1000 if writable else 0
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue(), baseline


def verify_bundle(scope: SessionScope, baseline: dict, bundle: dict) -> list[str]:
    scope.verify_base()
    verify_baseline(scope, baseline)
    if set(bundle) != {"scope_sha256", "base_commit", "changes"}:
        raise ValueError("Unexpected output fields")
    if (
        bundle["scope_sha256"] != scope.hash
        or bundle["base_commit"] != scope.data["base_commit"]
    ):
        raise ValueError("Output is bound to a different scope or stale base")
    changes = bundle["changes"]
    if not isinstance(changes, list) or not changes:
        raise ValueError("Output contains no file changes")
    seen, total = set(), 0
    for item in changes:
        if not isinstance(item, dict) or set(item) != {
            "path",
            "before_sha256",
            "content_base64",
        }:
            raise ValueError("Unexpected file change fields")
        path = checked_path(item["path"])
        if path.casefold() in seen or path not in scope.data["write_paths"]:
            raise ValueError("Escaped, duplicate or unexpected patch path")
        seen.add(path.casefold())
        target = local_file(scope.root, path, missing=True)
        actual = digest(target.read_bytes()) if target.exists() else None
        if item["before_sha256"] != baseline[path] or actual != baseline[path]:
            raise ValueError("File changed since scope export")
        if (
            not isinstance(item["content_base64"], str)
            or len(item["content_base64"]) > MAX_FILE * 2
        ):
            raise ValueError("Oversized or invalid output")
        payload = base64.b64decode(item["content_base64"], validate=True)
        total += len(payload)
        if len(payload) > MAX_FILE or total > MAX_EXPORT:
            raise ValueError("Output size bound exceeded")
    return sorted(item["path"] for item in changes)


def verify_baseline(scope, baseline):
    contents = scope.files()
    current = {
        p: digest(b) if (scope.root / p).exists() else None for p, b in contents.items()
    }
    if current != baseline:
        raise ValueError("Scope input changed since export")


class Ownership:
    """Atomic per-branch and per-workspace reservations; expiry never grants takeover."""

    def __init__(self, directory: Path, clock=time.time):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory, self.clock = directory, clock
        self.db = directory / "ownership.sqlite3"
        self.startup_db = directory / "startup.sqlite3"
        with self.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS runs (
                token TEXT PRIMARY KEY, branch TEXT NOT NULL, workspace TEXT NOT NULL,
                owner TEXT NOT NULL, run_id TEXT NOT NULL, scope_hash TEXT NOT NULL,
                container TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL,
                evidence TEXT)""")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS branch_claim ON runs(branch) WHERE state='claimed'"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS workspace_claim ON runs(workspace) WHERE state='claimed'"
            )
            with self._startup_transaction() as startup:
                startup.execute("""CREATE TABLE IF NOT EXISTS startup_authority (
                    token TEXT PRIMARY KEY, attempted INTEGER NOT NULL CHECK(attempted IN (0, 1)))""")

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.db, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _startup_transaction(self):
        # Call only while holding the ownership write lock. This separate commit
        # survives rollback of the transaction that owns the Docker callback.
        connection = sqlite3.connect(self.startup_db, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def claim(self, scope: SessionScope, container: str, lease_seconds=300) -> str:
        if not math.isfinite(lease_seconds) or not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be 1 through 3600 seconds")
        token = uuid.uuid4().hex
        try:
            with self.transaction() as db:
                db.execute(
                    "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        token,
                        scope.data["branch"],
                        str(scope.root.resolve()).casefold(),
                        scope.data["owner"],
                        scope.data["run_id"],
                        scope.hash,
                        container,
                        self.clock() + lease_seconds,
                        "claimed",
                        None,
                    ),
                )
                with self._startup_transaction() as startup:
                    startup.execute(
                        "INSERT INTO startup_authority VALUES (?, 0)", (token,)
                    )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Branch or workspace already has a writer; expiry requires recovery"
            ) from exc
        return token

    def row(self, db, token):
        row = db.execute("SELECT * FROM runs WHERE token=?", (token,)).fetchone()
        if row is None or row["state"] != "claimed":
            raise ValueError("No active ownership for token")
        return row

    def heartbeat(self, token, lease_seconds=300):
        if not math.isfinite(lease_seconds) or not 1 <= lease_seconds <= 3600:
            raise ValueError("Invalid heartbeat lease")
        with self.transaction() as db:
            row = self.row(db, token)
            if row["expires"] <= self.clock():
                raise ValueError(
                    "Expired ownership must be recovered, never silently revived"
                )
            db.execute(
                "UPDATE runs SET expires=? WHERE token=?",
                (self.clock() + lease_seconds, token),
            )

    def start(self, token, start_container):
        # Recovery and start hold the same lock, eliminating expired-start/recovery races.
        with self.transaction() as db:
            row = self.row(db, token)
            if row["expires"] <= self.clock():
                raise ValueError("Expired ownership cannot start")
            with self._startup_transaction() as startup:
                authority = startup.execute(
                    "SELECT attempted FROM startup_authority WHERE token=?", (token,)
                ).fetchone()
                if authority is None:
                    raise ValueError(
                        "Startup history missing; explicit recovery required"
                    )
                if authority["attempted"] != 0:
                    raise ValueError(
                        "Startup authority already consumed; explicit recovery required"
                    )
                startup.execute(
                    "UPDATE startup_authority SET attempted=1 WHERE token=?", (token,)
                )
            # Commit consumed authority before the external side effect, without
            # releasing the ownership lock shared with recovery and other starts.
            start_container(row["container"])

    def finish(self, token, stopped, preserve, recovering=False):
        with self.transaction() as db:
            row = self.row(db, token)
            if recovering and row["expires"] > self.clock():
                raise ValueError("Live lease cannot be recovered")
            if not stopped(row["container"]):
                raise ValueError("Previous process is not confirmed stopped")
            evidence = preserve(row["container"])
            evidence = Path(evidence)
            if not evidence.is_file() or evidence.stat().st_size == 0:
                raise ValueError("Preserved output evidence is missing")
            db.execute(
                "UPDATE runs SET state=?, evidence=? WHERE token=?",
                (
                    "recovered" if recovering else "finished",
                    str(evidence.resolve()),
                    token,
                ),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check-output", help="Read-only eligibility check; never apply or accept"
    )
    check.add_argument("--scope", required=True, type=Path)
    check.add_argument("--baseline", required=True, type=Path)
    check.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        scope = SessionScope.load(wp.read_json(args.scope))
        result = verify_bundle(
            scope, wp.read_json(args.baseline), wp.read_json(args.bundle)
        )
        print(
            json.dumps({"eligible_paths": result, "accepted": False, "applied": False})
        )
        return 0
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as exc:
        print("SCOPE REFUSED: " + str(exc))
        return 1


if __name__ == "__main__":
    import cli_exit

    raise SystemExit(cli_exit.run(main))
