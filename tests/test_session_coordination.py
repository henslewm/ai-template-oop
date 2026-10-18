"""Independent-clone contention, preservation and uncertain merge recovery."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import session_coordination as sc

ROOT = Path(__file__).resolve().parents[1]


def command(root, *args):
    return subprocess.run(args, cwd=root, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def clients(tmp_path):
    config = (ROOT / "config/session-coordination.json").read_bytes()
    repos = []
    for name in ("one", "two"):
        root = tmp_path / name
        root.mkdir()
        command(root, "git", "init", "-b", "feature/" + name)
        command(root, "git", "config", "user.name", "Fixture")
        command(root, "git", "config", "user.email", "fixture@example.invalid")
        (root / "config").mkdir()
        (root / "config/session-coordination.json").write_bytes(config)
        (root / "source.txt").write_text("original\n")
        command(root, "git", "add", ".")
        command(root, "git", "commit", "-m", "fixture")
        repos.append(root)
    database = tmp_path / "shared/registry.sqlite3"
    clock = [1000.0]
    objects = [sc.Coordinator(root, database=database, clock=lambda: clock[0]) for root in repos]
    for obj in objects:
        obj.identity = lambda: None
        obj.target = lambda branch, obj=obj: sc.git(obj.root, "rev-parse", "HEAD")
    objects[0].init()
    return objects, clock


def test_status_never_initializes(tmp_path):
    db = tmp_path / "absent/registry.sqlite3"
    coordinator = sc.Coordinator(ROOT, database=db)
    assert coordinator.status()["initialized"] is False
    assert not db.parent.exists()


def test_independent_clones_share_single_integration_owner(clients):
    (first, second), clock = clients
    token = first.register("first", "integrator")["token"]
    with pytest.raises(sc.sqlite3.IntegrityError):
        second.register("second", "integrator")
    clock[0] += 301
    # Expiry itself never releases the original owner.
    with pytest.raises(sc.sqlite3.IntegrityError):
        second.register("second", "integrator")
    with pytest.raises(ValueError, match="Stale"):
        first.heartbeat(token)
    first.recover(token, "Inspected old process exit and no merge command exists")
    assert second.register("second", "integrator")["role"] == "integrator"


def test_real_processes_contend_atomically(clients):
    (first, second), _ = clients
    script = (
        "import sys; from scripts.session_coordination import Coordinator; "
        "Coordinator(sys.argv[1],database=sys.argv[2]).register(sys.argv[3],'integrator')"
    )
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(obj.root),
                                  str(obj.database), str(i)], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for i, obj in enumerate((first, second))]
    results = [p.communicate(timeout=15) for p in processes]
    assert sorted(p.returncode for p in processes) == [0, 1], results
    assert sum(not r["closed"] for r in first.status()["sessions"]) == 1


def test_duplicate_checkout_and_branch_claims_rejected(clients):
    (first, second), _ = clients
    first.register("first", "worker")
    with pytest.raises(sc.sqlite3.IntegrityError):
        first.register("same workspace", "worker")
    command(second.root, "git", "branch", "-m", "feature/one")
    with pytest.raises(sc.sqlite3.IntegrityError):
        second.register("same branch", "worker")


def test_worker_token_cannot_integrate_or_mutate_other_checkout(clients):
    (first, second), _ = clients
    token = first.register("first", "worker")["token"]
    with pytest.raises(ValueError, match="Integration ownership"):
        first.integrate(token, "unknown")
    with pytest.raises(ValueError, match="different checkout"):
        second.heartbeat(token)


def test_clock_rollback_and_live_recovery_refuse(clients):
    (first, _), clock = clients
    token = first.register("first", "integrator")["token"]
    with pytest.raises(ValueError, match="Live owner"):
        first.recover(token, "Inspected old process exit and no merge command exists")
    clock[0] -= 1
    with pytest.raises(ValueError, match="clock rollback"):
        first.heartbeat(token)


def add_notice(first):
    before = sc.git(first.root, "rev-parse", "HEAD")
    (first.root / "source.txt").write_text("new main\n")
    command(first.root, "git", "commit", "-am", "new main")
    head = sc.git(first.root, "rev-parse", "HEAD")
    with first.connection(write=True) as db:
        first.notice(db, "main", before, head, pr=12)
        first.notice(db, "main", before, head, pr=12)
    return before, head


def test_notices_are_idempotent_and_offline_ack_catches_up(clients):
    (first, second), _ = clients
    token = second.register("offline", "worker")["token"]
    _, head = add_notice(first)
    with first.connection() as db:
        assert db.execute("SELECT count(*) FROM notices").fetchone()[0] == 1
    notice = first.status()["notices"][0]
    assert notice["head"] == head and notice["paths"] == ["source.txt"]
    second.ack(token, 1, "deferred", "Saving edits")
    with pytest.raises(subprocess.CalledProcessError):
        second.ack(token, 1, "synchronized")
    assert first.status()["acks"][0]["state"] == "deferred"


def test_dirty_sync_preserves_files_and_index(clients):
    (first, _), _ = clients
    token = first.register("dirty", "worker")["token"]
    (first.root / "source.txt").write_text("my edits\n")
    (first.root / "notes.txt").write_text("untracked work\n")
    index = Path(sc.git(first.root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    before = hashlib.sha256(index.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Dirty"):
        first.sync(token, apply=True)
    assert (first.root / "source.txt").read_text() == "my edits\n"
    assert (first.root / "notes.txt").read_text() == "untracked work\n"
    assert hashlib.sha256(index.read_bytes()).hexdigest() == before


def test_clean_sync_and_acknowledgment(clients):
    (first, _), _ = clients
    token = first.register("clean", "worker")["token"]
    _, head = add_notice(first)
    result = first.sync(token, apply=True)
    assert result["synchronized"] == head
    assert first.status()["acks"][0]["state"] == "synchronized"


def ready(first):
    head = sc.git(first.root, "rev-parse", "HEAD")
    return {"repository": "henslewm/ai-template-oop", "head_repository": "henslewm/ai-template-oop",
            "base_repository": "henslewm/ai-template-oop", "head": head, "base": head,
            "base_branch": "main", "branch": "feature/one", "remote_branches": {"feature/one": head, "main": head},
            "state": "open", "draft": False, "mergeable": True, "mergeable_state": "clean",
            "checks": [{"id": 1, "head_sha": head, "name": "validate", "app": {"id": 1},
                        "status": "completed", "conclusion": "success"}],
            "statuses": [], "required": [], "required_policy": "NONE_CONFIGURED",
            "reviews": [], "comments": [], "delete_branch_on_merge": False,
            "unsupported_rules": [], "unresolved": 0, "more_threads": False}


def review(head):
    return {"head": head, "actor": "independent", "implementer": "first", "verdict": "APPROVE",
            "blocking_findings": [], "report_sha256": "a" * 64}


@pytest.mark.parametrize("mutation,match", [
    (lambda live: live.update(head="b" * 40), "head changed"),
    (lambda live: live["remote_branches"].update(main="b" * 40), "base changed"),
    (lambda live: live["checks"][0].update(conclusion="failure"), "held"),
    (lambda live: live["checks"][0].update(status="in_progress"), "held"),
    (lambda live: live.update(unresolved=1), "held"),
    (lambda live: live.update(checks=[]), "validation required"),
])
def test_hosting_readiness_holds(clients, monkeypatch, mutation, match):
    (first, _), _ = clients
    live = ready(first)
    head = live["head"]
    mutation(live)
    first.hosting = lambda number: live
    with pytest.raises(ValueError, match=match):
        first.gates(12, head, review(head))


def test_stale_or_self_review_refuses(clients):
    (first, _), _ = clients
    live = ready(first)
    first.hosting = lambda number: live
    proof = review(live["head"])
    proof["actor"] = proof["implementer"]
    with pytest.raises(ValueError, match="INDEPENDENT_EXACT_REVIEW_REQUIRED"):
        first.gates(12, live["head"], proof)


def prepare_request(first):
    token = first.register("first", "integrator")["token"]
    before = sc.git(first.root, "rev-parse", "HEAD")
    (first.root / "source.txt").write_text("reviewed candidate\n")
    command(first.root, "git", "commit", "-am", "candidate")
    head = sc.git(first.root, "rev-parse", "HEAD")
    live = ready(first)
    live["base"] = before
    live["remote_branches"]["main"] = before
    first.gates = lambda *args: live.copy()
    request = first.submit(token, 12, head, review(head))["request"]
    return token, request, head, live


def test_base_advance_invalidates_saved_readiness(clients):
    (first, _), _ = clients
    token, request, _, live = prepare_request(first)
    live["base"] = "b" * 40
    with pytest.raises(ValueError, match="Base advanced"):
        first.integrate(token, request)
    assert first.status()["requests"][0]["state"] == "ready"


def test_crash_after_merge_keeps_intent_then_reconciles_once(clients, monkeypatch):
    (first, _), clock = clients
    token, request, head, _ = prepare_request(first)
    native = sc.run
    calls = []
    def crash(root, *args):
        if args[:3] == ("gh", "pr", "merge"):
            calls.append(args)
            raise subprocess.TimeoutExpired(args, 60)
        return native(root, *args)
    monkeypatch.setattr(sc, "run", crash)
    with pytest.raises(subprocess.TimeoutExpired):
        first.integrate(token, request)
    assert first.status()["requests"][0]["state"] == "intent"
    with pytest.raises(ValueError, match="Uncertain"):
        first.integrate(token, request)
    def reconciled(root, *args):
        if args[:2] == ("gh", "api"):
            return json.dumps({"head": {"sha": head}, "base": {"ref": "main"},
                               "merged": True, "merge_commit_sha": head})
        return native(root, *args)
    monkeypatch.setattr(sc, "run", reconciled)
    clock[0] += 301
    first.recover(token, "Old process and merge subprocess exited; verified GitHub outcome")
    assert len(calls) == 1
    assert first.status()["requests"][0]["state"] == "merged"
    assert first.status()["requests"][0]["result"] == head
    assert len(first.status()["notices"]) == 1
    new_token = first.register("replacement", "integrator")["token"]
    assert first.integrate(new_token, request) == {"merged": head}
    assert len(first.status()["notices"]) == 1


def test_writer_lock_prevents_recovery_during_merge(clients):
    (first, second), clock = clients
    token = first.register("first", "integrator")["token"]
    clock[0] += 301
    with first.connection(write=True):
        with pytest.raises(sc.sqlite3.OperationalError, match="locked"):
            second.recover(token, "Verified old process stopped; fixture holds writer transaction")
    assert not first.status()["sessions"][0]["closed"]


def test_registry_policy_drift_refuses_init(clients):
    (first, _), _ = clients
    first.config["shared_targets"] = ["main", "ui"]
    with pytest.raises(ValueError, match="policy differs"):
        first.init()


def test_recovering_unrelated_worker_preserves_live_merge_intent(clients):
    (first, second), clock = clients
    worker = second.register("stopped worker", "worker")["token"]
    token, request, _, _ = prepare_request(first)
    with first.connection(write=True) as db:
        db.execute("UPDATE requests SET state='intent' WHERE id=?", (request,))
    clock[0] += 301
    with first.connection(write=True) as db:
        db.execute("UPDATE sessions SET heartbeat=? WHERE token=?", (clock[0], token))
    second.recover(worker, "Worker process exited; unrelated integrator is still running")
    assert first.status()["requests"][0]["state"] == "intent"
    assert not first.status()["sessions"][1]["closed"]


def test_target_uses_pinned_remote_object_not_fetch_head(clients, monkeypatch):
    (first, _), _ = clients
    calls = []
    def observed(root, *args):
        calls.append(args)
        if args[0] == "ls-remote":
            return "a" * 40 + "\trefs/heads/main"
        assert args == ("fetch", "--no-prune", "--no-tags", "--no-write-fetch-head", "origin", "a" * 40)
        return ""
    monkeypatch.setattr(sc, "git", observed)
    assert sc.Coordinator.target(first, "main") == "a" * 40
    assert len(calls) == 2


def test_successful_merge_is_exact_head_guarded_and_idempotent(clients, monkeypatch):
    (first, _), _ = clients
    token, request, head, _ = prepare_request(first)
    native = sc.run
    merges = []
    def hosted(root, *args):
        if args[:3] == ("gh", "pr", "merge"):
            merges.append(args)
            assert args[-3:] == ("--rebase", "--match-head-commit", head)
            return ""
        if args[:2] == ("gh", "api"):
            return json.dumps({"head": {"sha": head}, "base": {"ref": "main"},
                               "merged": True, "merge_commit_sha": head})
        return native(root, *args)
    monkeypatch.setattr(sc, "run", hosted)
    assert first.integrate(token, request) == {"merged": head}
    assert first.integrate(token, request) == {"merged": head}
    assert len(merges) == 1
    assert len(first.status()["notices"]) == 1


def test_independent_clone_fetches_notice_and_synchronizes_own_branch(clients, tmp_path):
    (first, _), _ = clients
    clone = tmp_path / "real clone"
    command(first.root, "git", "clone", "--no-hardlinks", str(first.root), str(clone))
    command(clone, "git", "checkout", "-b", "feature/clone-worker")
    command(clone, "git", "config", "user.name", "Fixture")
    command(clone, "git", "config", "user.email", "fixture@example.invalid")
    worker = sc.Coordinator(clone, database=first.database, clock=first.clock)
    def fetch_target(branch):
        head = sc.git(first.root, "rev-parse", "HEAD")
        sc.git(clone, "fetch", "--no-write-fetch-head", "origin", head)
        return head
    worker.target = fetch_target
    token = worker.register("clone worker", "worker")["token"]
    old = sc.git(clone, "rev-parse", "HEAD")
    (first.root / "contracts").mkdir()
    (first.root / "contracts/change.txt").write_text("interface change\n")
    command(first.root, "git", "add", "contracts/change.txt")
    command(first.root, "git", "commit", "-m", "contract update")
    head = sc.git(first.root, "rev-parse", "HEAD")
    observed = worker.sync(token)
    assert observed[0]["payload"]["contract_impact"] is True
    assert sc.git(clone, "rev-parse", "HEAD") == old
    assert worker.sync(token, apply=True)["synchronized"] == head
    assert sc.git(first.root, "rev-parse", "HEAD") == head
    assert worker.status()["acks"][0]["state"] == "synchronized"


def test_delayed_observation_cannot_regress_newer_recorded_target(clients):
    (first, _), _ = clients
    before, newer = add_notice(first)
    with first.connection(write=True) as db:
        first.notice(db, "main", newer, before)  # delayed watcher captured old head
        assert db.execute("SELECT head FROM targets WHERE name='main'").fetchone()[0] == newer
        assert db.execute("SELECT count(*) FROM notices").fetchone()[0] == 1


def test_divergent_target_observation_preserves_known_history(clients):
    (first, _), _ = clients
    before, newer = add_notice(first)
    command(first.root, "git", "checkout", "-b", "feature/divergent", before)
    (first.root / "other.txt").write_text("divergent\n")
    command(first.root, "git", "add", "other.txt")
    command(first.root, "git", "commit", "-m", "divergent")
    divergent = sc.git(first.root, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="diverged"):
        with first.connection(write=True) as db:
            first.notice(db, "main", newer, divergent)
    with first.connection() as db:
        assert db.execute("SELECT head FROM targets WHERE name='main'").fetchone()[0] == newer
        assert db.execute("SELECT count(*) FROM notices").fetchone()[0] == 1


def test_confirmed_merge_enriches_watch_notice_without_duplicate(clients):
    (first, _), _ = clients
    before = sc.git(first.root, "rev-parse", "HEAD")
    (first.root / "source.txt").write_text("merged\n")
    command(first.root, "git", "commit", "-am", "merged")
    head = sc.git(first.root, "rev-parse", "HEAD")
    with first.connection(write=True) as db:
        first.notice(db, "main", before, head)
        first.notice(db, "main", before, head, pr=12)
        assert db.execute("SELECT count(*) FROM notices").fetchone()[0] == 1
    assert first.status()["notices"][0]["pr"] == 12


def test_pilot_requires_designated_integration_token(monkeypatch):
    monkeypatch.delenv("AI_TEMPLATE_INTEGRATION_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Register the pilot"):
        sc.guarded_pilot_merge(ROOT, 12, "a" * 40, {})
