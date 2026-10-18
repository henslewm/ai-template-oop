"""Cooperative, host-local Git integration ownership; never rewrites worker files.

SQLite serializes independent clones for the current Windows account. Tokens
identify cooperating sessions, not security principals. Historical offline
approval controllers remain disabled; this is the standing interactive policy.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote
import uuid


def run(root, *args):
    return subprocess.run(args, cwd=root, capture_output=True, text=True,
                          check=True, timeout=60).stdout.strip()


def git(root, *args):
    return run(root, "git", "--no-optional-locks", *args)


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical_database(repository_id):
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state"))
    return base / "ai-template-sessions" / str(repository_id) / "coordination.sqlite3"


class Coordinator:
    def __init__(self, root, *, database=None, clock=time.time):
        self.root = Path(root).resolve()
        self.config = json.loads((self.root / "config/session-coordination.json").read_text())
        self.database = Path(database) if database else canonical_database(self.config["repository_id"])
        self.clock = clock

    @contextmanager
    def connection(self, *, write=False, initialize=False):
        if initialize:
            self.database.parent.mkdir(parents=True, exist_ok=True)
        require(self.database.exists() or initialize, "Run init before registering a session")
        # Read-only status must not create a database, journal or state directory.
        mode = "rwc" if initialize else ("rw" if write else "ro")
        db = sqlite3.connect(self.database.resolve().as_uri() + "?mode=" + mode,
                             uri=True, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone():
                binding = db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
                require(binding is None or binding[0] == json.dumps(self.config, sort_keys=True),
                        "Existing registry policy differs; inspect before migration")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def identity(self):
        repo = self.config["repository"]
        origin = git(self.root, "remote", "get-url", "origin")
        require(origin in {f"https://github.com/{repo}.git", f"git@github.com:{repo}.git"},
                "Origin must match the configured repository")
        observed = json.loads(run(self.root, "gh", "api", f"repos/{repo}"))
        require(observed["id"] == self.config["repository_id"], "Repository identity changed")

    def target(self, branch):
        require(branch in self.config["shared_targets"], "Not a configured shared target")
        git(self.root, "fetch", "--no-prune", "--no-tags", "origin", "refs/heads/" + branch)
        return git(self.root, "rev-parse", "FETCH_HEAD")

    def init(self):
        self.identity()
        heads = {name: self.target(name) for name in self.config["shared_targets"]}
        with self.connection(write=True, initialize=True) as db:
            for statement in (
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, branch TEXT NOT NULL, workspace TEXT NOT NULL, heartbeat REAL NOT NULL, closed INTEGER NOT NULL DEFAULT 0)",
                "CREATE UNIQUE INDEX IF NOT EXISTS branch_owner ON sessions(branch) WHERE closed=0",
                "CREATE UNIQUE INDEX IF NOT EXISTS workspace_owner ON sessions(workspace) WHERE closed=0",
                "CREATE UNIQUE INDEX IF NOT EXISTS integration_owner ON sessions(role) WHERE role='integrator' AND closed=0",
                "CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, head TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, token TEXT NOT NULL, pr INTEGER NOT NULL, head TEXT NOT NULL, base TEXT NOT NULL, target TEXT NOT NULL, review TEXT NOT NULL, state TEXT NOT NULL, result TEXT)",
                "CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY, target TEXT NOT NULL, head TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(target,head))",
                "CREATE TABLE IF NOT EXISTS acks (token TEXT NOT NULL, notice INTEGER NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL, PRIMARY KEY(token,notice))",
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)",
            ):
                db.execute(statement)
            binding = json.dumps(self.config, sort_keys=True)
            old = db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
            require(old is None or old[0] == binding, "Existing registry policy differs; inspect before migration")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('config',?)", (binding,))
            for name, head in heads.items():
                db.execute("INSERT OR IGNORE INTO targets VALUES (?,?)", (name, head))
        return self.status()

    def event(self, db, kind, **payload):
        db.execute("INSERT INTO events(at,kind,payload) VALUES (?,?,?)",
                   (self.clock(), kind, json.dumps(payload, sort_keys=True)))

    def session(self, db, token, *, integrator=False, workspace=False):
        row = db.execute("SELECT * FROM sessions WHERE token=? AND closed=0", (token,)).fetchone()
        require(row is not None, "Unknown or closed session")
        require(0 <= self.clock() - row["heartbeat"] <= self.config["stale_seconds"],
                "Stale session or clock rollback; inspect and recover explicitly")
        if integrator:
            require(row["role"] == "integrator", "Integration ownership required")
        if workspace:
            require(row["workspace"] == self.workspace(), "This session owns a different checkout")
            require(row["branch"] == git(self.root, "branch", "--show-current"),
                    "Owned checkout changed branches")
        return dict(row)

    def workspace(self):
        return os.path.normcase(str(self.root))

    def register(self, name, role):
        require(role in {"worker", "integrator"} and name.strip(), "Name and valid role required")
        branch = git(self.root, "branch", "--show-current")
        require(branch.startswith("feature/"), "Use a retained feature branch")
        token = uuid.uuid4().hex
        with self.connection(write=True) as db:
            db.execute("INSERT INTO sessions(token,name,role,branch,workspace,heartbeat) VALUES (?,?,?,?,?,?)",
                       (token, name, role, branch, self.workspace(), self.clock()))
            self.event(db, "REGISTER", name=name, role=role, branch=branch)
        return {"token": token, "branch": branch, "role": role}

    def heartbeat(self, token):
        with self.connection(write=True) as db:
            self.session(db, token, workspace=True)
            db.execute("UPDATE sessions SET heartbeat=? WHERE token=?", (self.clock(), token))
        return {"heartbeat": "renewed"}

    def status(self):
        if not self.database.exists():
            return {"initialized": False, "scope": "current Windows account"}
        with self.connection() as db:
            sessions = [{k: r[k] for k in ("name", "role", "branch", "heartbeat", "closed")}
                        for r in db.execute("SELECT * FROM sessions")]
            for row in sessions:
                row["stale"] = not 0 <= self.clock() - row["heartbeat"] <= self.config["stale_seconds"]
            return {"initialized": True, "scope": "current Windows account", "sessions": sessions,
                    "requests": [dict(r) for r in db.execute("SELECT id,pr,head,base,target,state,result FROM requests")],
                    "notices": [json.loads(r[0]) for r in db.execute("SELECT payload FROM notices ORDER BY id")],
                    "acks": [dict(r) for r in db.execute("SELECT notice,state,detail FROM acks")]}

    def notice(self, db, target, before, head, *, pr=None):
        if before == head:
            return
        paths = git(self.root, "diff", "--name-only", before, head).splitlines()
        payload = {"target": target, "before": before, "head": head, "pr": pr,
                   "paths": paths, "contract_impact": any(p.startswith("contracts/") for p in paths),
                   "diff": f"https://github.com/{self.config['repository']}/compare/{before}...{head}"}
        db.execute("INSERT OR IGNORE INTO notices(target,head,payload) VALUES (?,?,?)",
                   (target, head, json.dumps(payload, sort_keys=True)))
        db.execute("UPDATE targets SET head=? WHERE name=?", (head, target))

    def observe(self, token):
        self.heartbeat(token)
        for target in self.config["shared_targets"]:
            head = self.target(target)
            with self.connection(write=True) as db:
                before = db.execute("SELECT head FROM targets WHERE name=?", (target,)).fetchone()[0]
                self.notice(db, target, before, head)
        with self.connection() as db:
            return [dict(r) | {"payload": json.loads(r["payload"])} for r in db.execute(
                "SELECT n.*,a.state AS acknowledgment FROM notices n LEFT JOIN acks a ON a.notice=n.id AND a.token=? WHERE a.state IS NULL OR a.state!='synchronized' ORDER BY n.id", (token,))]

    def ack(self, token, notice_id, state, detail=""):
        require(state in {"seen", "deferred", "blocked", "synchronized"}, "Invalid acknowledgment")
        with self.connection(write=True) as db:
            self.session(db, token, workspace=True)
            notice = db.execute("SELECT * FROM notices WHERE id=?", (notice_id,)).fetchone()
            require(notice is not None, "Unknown notice")
            if state == "synchronized":
                git(self.root, "merge-base", "--is-ancestor", notice["head"], "HEAD")
            db.execute("INSERT INTO acks VALUES (?,?,?,?) ON CONFLICT(token,notice) DO UPDATE SET state=excluded.state,detail=excluded.detail",
                       (token, notice_id, state, detail))
        return {"notice": notice_id, "state": state}

    def sync(self, token, *, apply=False):
        notices = self.observe(token)
        if not apply:
            return notices
        # No stash, reset, rebase or operation on another session's checkout.
        with self.connection(write=True) as db:
            self.session(db, token, workspace=True)
            require(not git(self.root, "status", "--porcelain"), "Dirty checkout; preserve work before sync")
            for target in self.config["shared_targets"]:
                head = db.execute("SELECT head FROM targets WHERE name=?", (target,)).fetchone()[0]
                git(self.root, "merge", "--no-edit", head)
        for notice in notices:
            self.ack(token, notice["id"], "synchronized")
        return {"synchronized": git(self.root, "rev-parse", "HEAD")}

    def hosting(self, number):
        from scripts import workflow_closeout
        return workflow_closeout.hosting(self.root, number)

    def gates(self, number, head, review):
        from scripts import pilot_delivery
        live = self.hosting(number)
        blockers = pilot_delivery._hosting_holds(live, head, review)
        require(live["repository"] == live["head_repository"] == live["base_repository"] == self.config["repository"],
                "Cross-repository integration refused")
        require(live["base_branch"] in self.config["shared_targets"] and live["branch"].startswith("feature/"),
                "Only retained feature PRs into configured shared targets")
        require(live["head"] == head == live["remote_branches"].get(live["branch"]), "PR head changed")
        require(live["base"] == live["remote_branches"].get(live["base_branch"]), "PR base changed")
        require(live["state"] == "open" and not live["draft"] and live["mergeable"] is True
                and live["mergeable_state"] in {"clean", "unstable"}, "PR not ready")
        require(not blockers, "Integration held: " + "; ".join(blockers))
        require(any(c["head_sha"] == head and c["status"] == "completed" and c["conclusion"] == "success"
                    for c in live["checks"]) or any(s["state"] == "success" for s in live["statuses"]),
                "Successful hosting validation required")
        require(isinstance(review, dict) and isinstance(review.get("implementer"), str)
                and review["implementer"].strip(), "Named implementation actor required")
        git(self.root, "fetch", "--no-prune", "--no-tags", "origin")
        git(self.root, "merge-base", "--is-ancestor", live["base"], head)
        return live

    def submit(self, token, number, head, review):
        self.identity()
        live = self.gates(number, head, review)
        request = uuid.uuid4().hex
        with self.connection(write=True) as db:
            owner = self.session(db, token, workspace=True)
            if owner["role"] == "worker":
                require(owner["branch"] == live["branch"] and git(self.root, "rev-parse", "HEAD") == head,
                        "Workers submit only their own exact checkout head")
                require(not git(self.root, "status", "--porcelain"), "Dirty checkout; preserve work before submission")
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,NULL)",
                       (request, token, number, head, live["base"], live["base_branch"], json.dumps(review), "ready"))
            self.event(db, "SUBMIT", request=request, head=head, base=live["base"])
        return {"request": request}

    def integrate(self, token, request):
        self.identity()
        with self.connection() as db:
            self.session(db, token, integrator=True, workspace=True)
            row = db.execute("SELECT * FROM requests WHERE id=?", (request,)).fetchone()
            require(row is not None, "Unknown integration request")
            saved = dict(row)
        if saved["state"] == "merged":
            return {"merged": saved["result"]}
        require(saved["state"] == "ready", "Uncertain integration: recover; do not retry the merge")
        live = self.gates(saved["pr"], saved["head"], json.loads(saved["review"]))
        require(live["base"] == saved["base"], "Base advanced; synchronize, revalidate and resubmit")
        # Commit intent separately so a process death cannot erase an uncertain call.
        with self.connection(write=True) as db:
            self.session(db, token, integrator=True, workspace=True)
            require(not db.execute("SELECT 1 FROM requests WHERE state='intent'").fetchone(),
                    "Uncertain earlier integration must be reconciled first")
            changed = db.execute("UPDATE requests SET state='intent' WHERE id=? AND state='ready'", (request,)).rowcount
            require(changed == 1, "Request already consumed")
            self.event(db, "MERGE_INTENT", request=request, owner=token)
        # Hold SQLite's writer transaction throughout the external command. A
        # heartbeat/recovery cannot replace ownership while the command runs.
        with self.connection(write=True) as db:
            self.session(db, token, integrator=True, workspace=True)
            second = self.gates(saved["pr"], saved["head"], json.loads(saved["review"]))
            require(second == live, "Hosting facts changed; reconcile intent before retry")
            run(self.root, "gh", "pr", "merge", "--repo", self.config["repository"], str(saved["pr"]),
                "--rebase", "--match-head-commit", saved["head"])
            return self.reconcile(db, saved)

    def reconcile(self, db, saved):
        repo = self.config["repository"]
        pull = json.loads(run(self.root, "gh", "api", f"repos/{repo}/pulls/{saved['pr']}"))
        require(pull["head"]["sha"] == saved["head"] and pull["base"]["ref"] == saved["target"],
                "Uncertain PR identity changed; preserve intent")
        require(pull["merged"] and pull["merge_commit_sha"],
                "Merge not confirmed; preserve intent until old command is verified stopped")
        merged = pull["merge_commit_sha"]
        target = self.target(saved["target"])
        git(self.root, "merge-base", "--is-ancestor", merged, target)
        require(git(self.root, "rev-parse", saved["head"] + "^{tree}") == git(self.root, "rev-parse", merged + "^{tree}"),
                "Integrated tree differs from reviewed candidate")
        self.notice(db, saved["target"], saved["base"], merged, pr=saved["pr"])
        if target != merged:
            self.notice(db, saved["target"], merged, target)
        db.execute("UPDATE requests SET state='merged',result=? WHERE id=?", (merged, saved["id"]))
        self.event(db, "MERGED", request=saved["id"], head=merged)
        return {"merged": merged}

    def close(self, token):
        with self.connection(write=True) as db:
            self.session(db, token, workspace=True)
            require(not db.execute("SELECT 1 FROM requests WHERE state='intent'").fetchone(), "Reconcile uncertain merge before closing")
            db.execute("UPDATE sessions SET closed=1 WHERE token=?", (token,))
            self.event(db, "CLOSE", token=token)
        return {"closed": True, "branches_retained": True}

    def recover(self, token, evidence):
        require(isinstance(evidence, str) and len(evidence.strip()) >= 20,
                "Record how the old session and all merge commands were verified stopped")
        with self.connection(write=True) as db:
            old = db.execute("SELECT * FROM sessions WHERE token=? AND closed=0", (token,)).fetchone()
            require(old is not None, "Unknown active owner")
            require(self.clock() - old["heartbeat"] > self.config["stale_seconds"], "Live owner cannot be recovered")
            for row in db.execute("SELECT * FROM requests WHERE state='intent'").fetchall():
                saved = dict(row)
                pull = json.loads(run(self.root, "gh", "api", f"repos/{self.config['repository']}/pulls/{saved['pr']}"))
                if pull["merged"]:
                    self.reconcile(db, saved)
                else:
                    require(pull["state"] in {"open", "closed"}, "Unknown hosting outcome")
                    db.execute("UPDATE requests SET state='abandoned' WHERE id=?", (saved["id"],))
            db.execute("UPDATE sessions SET closed=1 WHERE token=?", (token,))
            self.event(db, "RECOVER", token=token, evidence=evidence)
        return {"recovered": True, "next": "Register a new session; no ownership transferred automatically"}


def guarded_pilot_merge(root, number, head, review):
    """Separately activated pilot must use the same designated local integrator."""
    token = os.environ.get("AI_TEMPLATE_INTEGRATION_TOKEN")
    require(token, "Register the pilot checkout as integrator and set AI_TEMPLATE_INTEGRATION_TOKEN")
    coordinator = Coordinator(root)
    request = coordinator.submit(token, number, head, review)["request"]
    return coordinator.integrate(token, request)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        commands.add_parser(name)
    register = commands.add_parser("register")
    register.add_argument("--name", required=True)
    register.add_argument("--role", choices=("worker", "integrator"), default="worker")
    for name in ("heartbeat", "watch", "sync", "ack", "submit", "integrate", "close", "recover"):
        command = commands.add_parser(name)
        command.add_argument("--token", required=True)
        if name == "watch":
            command.add_argument("--once", action="store_true")
        if name == "sync":
            command.add_argument("--apply", action="store_true")
        if name == "ack":
            command.add_argument("--notice", type=int, required=True)
            command.add_argument("--state", choices=("seen", "deferred", "blocked", "synchronized"), required=True)
            command.add_argument("--detail", default="")
        if name == "submit":
            command.add_argument("--pr", type=int, required=True)
            command.add_argument("--head", required=True)
            command.add_argument("--review-file", type=Path, required=True)
        if name == "integrate":
            command.add_argument("--request", required=True)
        if name == "recover":
            command.add_argument("--stopped-evidence", required=True)
    args = parser.parse_args(argv)
    coordinator = Coordinator(args.root)
    try:
        if args.command == "register":
            result = coordinator.register(args.name, args.role)
        elif args.command == "submit":
            raw = args.review_file.read_bytes()
            review = json.loads(raw)
            review["report_sha256"] = hashlib.sha256(raw).hexdigest()
            result = coordinator.submit(args.token, args.pr, args.head, review)
        elif args.command == "integrate":
            result = coordinator.integrate(args.token, args.request)
        elif args.command == "recover":
            result = coordinator.recover(args.token, args.stopped_evidence)
        elif args.command == "sync":
            result = coordinator.sync(args.token, apply=args.apply)
        elif args.command == "ack":
            result = coordinator.ack(args.token, args.notice, args.state, args.detail)
        elif args.command == "watch":
            while True:
                try:
                    print(json.dumps(coordinator.observe(args.token), indent=2), flush=True)
                except sqlite3.OperationalError as error:
                    if "locked" not in str(error):
                        raise
                    print("Integration transaction busy; polling again", flush=True)
                if args.once:
                    return 0
                time.sleep(coordinator.config["heartbeat_seconds"])
        else:
            method = getattr(coordinator, args.command)
            result = method(args.token) if hasattr(args, "token") else method()
        print(json.dumps(result, indent=2))
        return 0
    except KeyboardInterrupt:
        print("Watcher stopped; session ownership retained until close/recovery", file=sys.stderr)
        return 130
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(f"Coordination held: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
