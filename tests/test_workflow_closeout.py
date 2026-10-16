"""M6 exact integration readiness and permanent branch retention scenarios."""

from __future__ import annotations

import copy
import os
import subprocess

import pytest

from scripts import workflow_closeout as c
from scripts import workflow_handoff as v
from scripts import acceptance as a
from scripts import execution_harness as h
from test_acceptance import (
    accepted_candidate as _accepted_candidate,
    candidate_fixture,
    check,
)
from test_execution_harness import execution as _execution, tar_bytes
from test_feedback import journal as _journal, start, stamp, options, result
from scripts import feedback as f
from scripts import worker_launcher as launcher

journal = _journal
execution = _execution
accepted_candidate = _accepted_candidate


def commit_candidate(e, tmp_path, *, base=None, payload=b"VALUE = 2\n"):
    root = e.journal.root
    base = base or e.scope.data["base_commit"]
    env = {
        **os.environ,
        "GIT_INDEX_FILE": str(tmp_path / ("index-" + h.digest(payload)[:12])),
    }

    def run(*args, data=None):
        return (
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    *args,
                ],
                input=data,
                env=env,
            )
            .decode()
            .strip()
        )

    run("read-tree", base)
    blob = run("hash-object", "-w", "--stdin", data=payload)
    run("update-index", "--cacheinfo", "100644," + blob + ",src/features/auth.py")
    tree = run("write-tree")
    return run(
        "commit-tree",
        tree,
        "-p",
        base,
        data=b"Explicit disposable integration candidate\n",
    )


def manifest(e, commit, *, update=None, directory="run-integration-proof"):
    accepted = a.load(e.journal, e.stream)[0]
    root = e.journal.directory / directory
    root.mkdir(exist_ok=True)

    def evidence(name, raw):
        p = root / name
        p.write_bytes(raw)
        return e.journal.evidence(
            p.relative_to(e.journal.directory).as_posix()
        ).__dict__

    value = {
        "binding": c.candidate_tree(e.journal, accepted["submission"], commit),
        "checks": [
            {
                "id": name,
                "status": "PASSED",
                "log": evidence(
                    name + ".log", b"Synthetic independent candidate check\n"
                ),
            }
            for name in ("contract", "boundary", "affected-runtime")
        ],
        "review": {
            "actor": "Independent",
            "head": commit,
            "verdict": "APPROVE",
            "report": evidence(
                "review.txt", b"Synthetic exact-head scoped independent review\n"
            ),
        },
        "interface_change": None,
    }
    if update:
        update(value)
    path = root / "manifest.json"
    path.write_bytes(h.json_bytes(value))
    return c.record_validation(
        e.journal, e.stream, commit, path.relative_to(e.journal.directory).as_posix()
    )


def live(e, commit):
    return {
        "repository": c.REPO,
        "delete_branch_on_merge": False,
        "number": 1,
        "state": "open",
        "draft": False,
        "head": commit,
        "branch": "feature/release",
        "head_repository": c.REPO,
        "base": e.scope.data["base_commit"],
        "base_branch": "main",
        "base_repository": c.REPO,
        "mergeable": True,
        "mergeable_state": "clean",
        "required": [],
        "required_policy": "NONE_CONFIGURED",
        "unsupported_rules": [],
        "statuses": [],
        "checks": [],
        "reviews": [],
        "unresolved": 0,
        "more_threads": False,
        "remote_branches": {
            "feature/release": commit,
            "feature/auth": e.scope.data["base_commit"],
            "main": e.scope.data["base_commit"],
        },
    }


@pytest.fixture
def ready(accepted_candidate, tmp_path, monkeypatch):
    e = accepted_candidate
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    # Fixture foundation is deliberately untracked by the inherited test setup.
    (e.journal.root / ".git/info/exclude").write_text("/config/\n")
    e.candidate = commit_candidate(e, tmp_path)
    v.git(e.journal.root, "branch", "feature/release", e.candidate)
    e.receipt = manifest(e, e.candidate)
    e.live = live(e, e.candidate)
    e.retained = {
        "local": {
            "feature/auth": e.scope.data["base_commit"],
            "feature/release": e.candidate,
        },
        "origin": copy.deepcopy(e.live["remote_branches"]),
    }
    monkeypatch.setattr(c, "hosting", lambda *args: copy.deepcopy(e.live))
    return e


def assess(e, **kwargs):
    kwargs.setdefault("retained", e.retained)
    return c.assess(e.journal, e.stream, e.candidate, e.receipt, 1, **kwargs)


def test_exact_candidate_ready_is_neither_integrated_verified_nor_deployed(ready):
    e = ready
    before = e.journal.verify()
    result = assess(e)
    assert result["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION", result
    assert result["required_policy"] == "NONE_CONFIGURED"
    assert result["accepted"] is True
    assert result["integrated"] == result["deployed"] == "NOT_ESTABLISHED"
    assert not result["merge_authorized"] and not result["execution_authorized"]
    assert result["validation"]["interface_changed"] is False
    assert e.journal.verify() == before
    assert (e.journal.root / "src/features/auth.py").read_bytes() == b"VALUE = 1\n"
    assert assess(e)["hosting_sha256"] == result["hosting_sha256"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ("delete", "AUTOMATIC_BRANCH_DELETION"),
        ("draft", "PR_NOT_READY"),
        ("unknown_policy", "LIVE_REQUIRED_POLICY_UNAVAILABLE"),
        ("missing", "REQUIRED_CHECK_MISSING"),
        ("pending", "REQUIRED_CHECK_MISSING"),
        ("failed", "REQUIRED_CHECK_MISSING"),
        ("wrong_app", "REQUIRED_CHECK_MISSING"),
        ("old_head", "REQUIRED_CHECK_MISSING"),
        ("threads", "REVIEW_THREADS"),
        ("more_threads", "REVIEW_THREADS"),
        ("changes_requested", "CHANGES_REQUESTED"),
        ("rounds", "REVIEW_ROUND_CAP"),
        ("unsupported", "UNSUPPORTED_LIVE_REQUIRED_RULE"),
    ],
)
def test_live_gates_hold_without_promotion(ready, change, reason):
    e = ready
    if change == "delete":
        e.live["delete_branch_on_merge"] = True
    elif change == "draft":
        e.live["draft"] = True
    elif change == "unknown_policy":
        e.live["required_policy"] = "UNAVAILABLE"
    elif change in {"missing", "pending", "failed", "wrong_app", "old_head"}:
        e.live.update(required=[("ci", 7)], required_policy="CONFIGURED")
        if change != "missing":
            e.live["checks"] = [
                {
                    "id": 1,
                    "name": "ci",
                    "head_sha": "0" * 40 if change == "old_head" else e.candidate,
                    "app": {"id": 8 if change == "wrong_app" else 7},
                    "status": "in_progress" if change == "pending" else "completed",
                    "conclusion": "failure" if change == "failed" else "success",
                }
            ]
    elif change == "threads":
        e.live["unresolved"] = 1
    elif change == "more_threads":
        e.live["more_threads"] = True
    elif change == "unsupported":
        e.live["unsupported_rules"] = ["workflows"]
    elif change == "changes_requested":
        e.live["reviews"] = [
            {
                "id": 1,
                "user": {"login": "reviewer"},
                "commit_id": e.candidate,
                "state": "CHANGES_REQUESTED",
                "body": "Finding",
            }
        ]
    else:
        e.live["reviews"] = [
            {
                "id": i,
                "user": {"login": "chatgpt-codex-connector[bot]"},
                "commit_id": e.candidate,
                "state": "COMMENTED",
                "body": "Round",
            }
            for i in range(5)
        ]
    before = e.journal.verify()
    result = assess(e)
    assert result["readiness"] == "HOLD" and any(
        reason in r for r in result["blockers"]
    )
    assert e.journal.verify() == before


def test_required_check_latest_rerun_and_app_binding(ready):
    e = ready
    e.live.update(required=[("ci", 7)], required_policy="CONFIGURED")
    e.live["checks"] = [
        {
            "id": i,
            "name": "ci",
            "head_sha": e.candidate,
            "app": {"id": 7},
            "status": "completed",
            "conclusion": conclusion,
        }
        for i, conclusion in [(1, "success"), (2, "failure")]
    ]
    assert assess(e)["readiness"] == "HOLD"
    e.live["checks"].append({**e.live["checks"][0], "id": 3})
    assert assess(e)["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION"


def test_prior_head_rejection_requires_explicit_resolution(ready):
    e = ready
    e.live["reviews"] = [
        {
            "id": 1,
            "user": {"login": "reviewer"},
            "commit_id": e.scope.data["base_commit"],
            "state": "CHANGES_REQUESTED",
            "body": "Body-only unresolved finding",
        }
    ]
    assert "OUTSTANDING_CHANGES_REQUESTED" in assess(e)["blockers"]
    e.live["reviews"].append({**e.live["reviews"][0], "id": 2, "state": "COMMENTED"})
    assert assess(e)["readiness"] == "HOLD"
    e.live["reviews"].append({**e.live["reviews"][0], "id": 3, "state": "DISMISSED"})
    assert assess(e)["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION"


def test_clean_automated_round_comments_count_toward_cap(ready):
    e = ready
    e.live["comments"] = [
        {
            "user": {"login": "chatgpt-codex-connector[bot]"},
            "body": "**Reviewed commit:** `" + e.candidate + "`",
        }
        for _ in range(5)
    ]
    result = assess(e)
    assert result["review_rounds"] == 5
    assert "REVIEW_ROUND_CAP_EXCEEDED" in result["blockers"]


def test_mutable_automated_summary_cannot_establish_round_cap(ready):
    e = ready
    e.live["comments"] = [
        {
            "user": {"login": "chatgpt-codex-connector[bot]"},
            "body": "<!-- codex-pull-request-review-summary -->\n| Review | Status | Commit | Review trigger |\n| Code Review | Completed | head | PR opened |",
            "created_at": "2026-10-14T22:00:00Z",
            "updated_at": "2026-10-14T22:05:00Z",
        }
    ]
    outcome = assess(e)
    assert outcome["readiness"] == "HOLD"
    assert (
        outcome["review_rounds"] is None
        and outcome["observed_immutable_review_rounds"] == 0
    )
    assert "AUTOMATED_REVIEW_HISTORY_UNVERIFIABLE" in outcome["blockers"]


@pytest.mark.parametrize(
    "change", ["head", "base", "remote", "cross_repo", "evidence", "local_branch"]
)
def test_changed_exact_binding_refuses(ready, change):
    e = ready
    if change == "head":
        e.live["head"] = e.scope.data["base_commit"]
    elif change == "base":
        e.live["base"] = "0" * 40
    elif change == "remote":
        e.live["remote_branches"]["feature/release"] = e.scope.data["base_commit"]
    elif change == "cross_repo":
        e.live["head_repository"] = "other/repo"
    elif change == "evidence":
        (e.journal.directory / "run-integration-proof/contract.log").write_bytes(
            b"changed"
        )
    else:
        v.git(
            e.journal.root,
            "branch",
            "--move",
            "feature/release",
            "feature/renamed-in-disposable-fixture",
        )
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        assess(e)


def test_live_unavailable_and_interleaved_head_change_refuse(ready, monkeypatch):
    e = ready
    monkeypatch.setattr(
        c, "hosting", lambda *args: (_ for _ in ()).throw(OSError("offline"))
    )
    with pytest.raises(OSError):
        assess(e)
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        result = copy.deepcopy(e.live)
        if calls > 1:
            result["head"] = "0" * 40
        return result

    monkeypatch.setattr(c, "hosting", changed)
    with pytest.raises(ValueError, match="changed"):
        assess(e)


@pytest.mark.parametrize(
    "kind", ["unreviewed", "same_actor", "missing_runtime", "failed_contract"]
)
def test_candidate_evidence_cannot_be_replaced_by_worker_pass(ready, kind):
    e = ready
    root = e.journal.directory / "run-other-proof"
    root.mkdir()
    original = h.parse(
        (e.journal.directory / "run-integration-proof/manifest.json").read_bytes(),
        40000,
    )
    if kind == "unreviewed":
        original["review"]["head"] = e.scope.data["base_commit"]
    elif kind == "same_actor":
        original["review"]["actor"] = "Implementer"
    elif kind == "missing_runtime":
        original["checks"].pop()
    else:
        original["checks"][0]["status"] = "FAILED"
    (root / "manifest.json").write_bytes(h.json_bytes(original))
    e.receipt = c.record_validation(
        e.journal, e.stream, e.candidate, "run-other-proof/manifest.json"
    )
    with pytest.raises(ValueError):
        assess(e)


def test_candidate_tree_extra_or_wrong_bytes_refuse(ready, tmp_path):
    e = ready
    bad = commit_candidate(e, tmp_path, payload=b"VALUE = 3\n")
    with pytest.raises(ValueError, match="exact accepted"):
        c.candidate_tree(e.journal, a.load(e.journal, e.stream)[0]["submission"], bad)


def test_retained_branch_names_and_history_are_checked(ready):
    e = ready
    previous = assess(e)["retained_refs"]
    assert assess(e, retained=previous)["branches_retained"]
    e.live["remote_branches"].pop("feature/auth")
    with pytest.raises(ValueError, match="disappeared"):
        assess(e, retained=previous)


def test_cli_has_no_merge_apply_push_cleanup_operation():
    for command in ("merge", "apply", "push", "clean-up", "delete"):
        with pytest.raises(SystemExit) as exc:
            c.main([command])
        assert exc.value.code == 2


def test_missing_retention_baseline_is_reported_as_hold(ready):
    outcome = assess(ready, retained=None)
    assert outcome["branches_retained"] == "BASELINE_REQUIRED"
    assert "RETAINED_BRANCH_BASELINE_REQUIRED" in outcome["blockers"]


def test_changed_valid_approval_and_stale_remote_main_refuse(ready, monkeypatch):
    e = ready
    e.live["remote_branches"]["main"] = e.candidate
    with pytest.raises(ValueError, match="base"):
        assess(e)
    e.live["remote_branches"]["main"] = e.scope.data["base_commit"]
    monkeypatch.setattr(v.ws, "active_anchor", lambda *args: "b" * 64)
    with pytest.raises(ValueError, match="anchor|approval"):
        assess(e)


@pytest.mark.parametrize(
    "approved", ["missing", "valid", "wrong_ui", "wrong_mocks", "unrelated"]
)
def test_interface_change_requires_exact_owner_ui_and_mocks(
    execution, tmp_path, monkeypatch, approved
):
    e = execution
    original_base = e.scope.data["base_commit"]
    (e.journal.root / "contracts/auth.py").write_bytes(
        b"class Interface: revised = True\n"
    )
    mocks = e.journal.root / "src/ui/mocks.py"
    mocks.parent.mkdir()
    mocks.write_bytes(b"class Mock: revised = True\n")
    if approved == "unrelated":
        (e.journal.root / "src/features/unrelated.py").write_bytes(
            b"UNACCEPTED = True\n"
        )
    v.git(e.journal.root, "add", "contracts", "src")
    v.git(
        e.journal.root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "Owner-approved interface and linked UI fixture",
    )
    base = v.git(e.journal.root, "rev-parse", "HEAD").decode().strip()
    e.scope = h.SessionScope.load(
        {
            **e.scope.data,
            "base_commit": base,
            "interface_revision": h.sha(
                {
                    "contracts/auth.py": h.digest(
                        (e.journal.root / "contracts/auth.py").read_bytes()
                    )
                }
            ),
        }
    )
    candidate_fixture(e)
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    foundation = e.journal.root / "config/workflow-bootstrap.json"
    package = f.wp.read_json(foundation)
    package["approval"] = {"approved_by": "Winston"}
    foundation.write_bytes(h.json_bytes(package))
    (e.journal.root / ".git/info/exclude").write_text("/config/\n")
    e.candidate = commit_candidate(e, tmp_path)
    v.git(e.journal.root, "branch", "feature/release", e.candidate)
    e.live = live(e, e.candidate)
    e.live["base"] = original_base
    e.live["remote_branches"]["main"] = original_base
    e.retained = {
        "local": {"feature/auth": base, "feature/release": e.candidate},
        "origin": copy.deepcopy(e.live["remote_branches"]),
    }
    monkeypatch.setattr(c, "hosting", lambda *args: copy.deepcopy(e.live))

    def add_approval(value):
        root = e.journal.directory / "run-interface-approval"
        root.mkdir()
        document = {
            "candidate": value["binding"],
            "interface_revision": e.scope.data["interface_revision"],
            "changed_paths": ["contracts/auth.py"],
            "owner": "Winston",
            "architect": "Architect",
            "ui_commit": base,
            "mocks_path": "src/ui/mocks.py",
            "linked_paths": ["contracts/auth.py", "src/ui/mocks.py"],
        }
        (root / "approval.json").write_bytes(h.json_bytes(document))
        value["interface_change"] = {
            "owner": "Winston",
            "architect": "Architect",
            "ui_commit": base,
            "mocks_path": "src/ui/mocks.py",
            "linked_paths": ["contracts/auth.py", "src/ui/mocks.py"],
            "approval": e.journal.evidence(
                "run-interface-approval/approval.json"
            ).__dict__,
        }
        if approved == "wrong_ui":
            value["interface_change"]["ui_commit"] = original_base
        if approved == "wrong_mocks":
            value["interface_change"]["mocks_path"] = "src/ui/other.py"

    e.receipt = manifest(
        e, e.candidate, update=add_approval if approved != "missing" else None
    )
    if approved == "valid":
        outcome = assess(e)
        assert outcome["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION", outcome
        assert outcome["validation"]["interface_changed"]
    else:
        with pytest.raises(ValueError):
            assess(e)


def test_two_successive_explicit_releases_keep_real_local_and_origin_branches(
    ready, tmp_path
):
    e = ready
    original = e.scope.data["base_commit"]
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", str(origin)], check=True, capture_output=True
    )
    v.git(e.journal.root, "remote", "add", "origin", str(origin))
    v.git(e.journal.root, "branch", "main", original)
    integrator = tmp_path / "integrator"
    v.git(e.journal.root, "worktree", "add", str(integrator), "main")

    def integrate_release(message):
        v.git(
            integrator,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "merge",
            "--no-ff",
            "feature/release",
            "-m",
            message,
        )
        merge = v.git(integrator, "rev-parse", "HEAD").decode().strip()
        v.git(integrator, "push", "origin", "main")
        v.git(e.journal.root, "fetch", "--no-prune", "origin")
        v.git(e.journal.root, "merge", "origin/main")
        v.git(e.journal.root, "push", "origin", "feature/auth")
        return merge

    v.git(
        e.journal.root,
        "push",
        "origin",
        original + ":refs/heads/main",
        "feature/auth",
        "feature/release",
    )
    first = assess(e)
    assert first["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION"
    first_commit = e.candidate
    # Only the explicit fixture integrator mutates Git; the product has no merge API.
    first_merge = integrate_release("Explicit first retained-branch integration")
    assert first_merge != first_commit
    assert v.git(e.journal.root, "show", "HEAD:src/features/auth.py") == b"VALUE = 2\n"
    assert v.build(e.journal, audience="startup")["content"]["tasks"]
    old_native = f.replay(e.journal, e.stream)[0]
    contract = copy.deepcopy(f.wp.current(old_native["packet"])["contract"])
    contract["validation"][0]["command"]["argv"] = [
        "python",
        "-c",
        "from pathlib import Path; assert Path('src/features/auth.py').read_bytes() == b'VALUE = 3\\n'",
    ]
    packet = f.wp.create(
        "RELEASE2",
        old_native["packet"]["domain_profile"],
        contract,
        "Architect",
        "Second retained branch release",
        stamp(20),
    )
    for target in ("ARCHITECTED", "READY"):
        packet = f.wp.transition(
            packet,
            target,
            "architect",
            "Architect",
            "Second fixture",
            ["Synthetic"],
            timestamp=stamp(20),
        )
    e.stream, _ = start(e.journal, name="RELEASE2", settings=e.routing, packet=packet)
    e.scope = h.SessionScope.load(
        {
            **e.scope.data,
            "base_commit": first_merge,
            "run_id": "fixture-two",
            "packet_revision_hash": f.wp.current(packet)["hash"],
        }
    )
    e.monkeypatch.setattr(f.wp, "now", lambda: stamp(30))

    def worker(files):
        public = h.parse(files["dispatch.json"], h.MAX_FILE)
        scope = h.SessionScope.load(h.parse(files["scope.json"], h.MAX_FILE))
        files["workspace/src/features/auth.py"] = b"VALUE = 3\n"
        bundle = h.runtime.bundle_from_archive(
            scope,
            h.parse(files["baseline.json"], h.MAX_FILE),
            tar_bytes(
                {n: raw for n, raw in files.items() if n.startswith("workspace/")},
                root="",
            ),
        )
        report = result(public, packet, outcome="PASS", passed=True)
        report["run"] = {
            "binding_sha256": public["binding_sha256"],
            "deadline": public["deadline"],
            "bundle_sha256": h.sha(bundle),
        }
        files["report.json"] = h.json_bytes(report)

    e.docker.worker = worker
    dispatch = h.dispatch(
        e.journal,
        e.stream,
        e.config,
        e.routing,
        options(),
        e.scope,
        timestamp=stamp(21),
    )
    launcher.launch(e.journal, dispatch["dispatch_id"])
    h.ingest(e.journal, dispatch["dispatch_id"])
    a.initialize(
        e.journal,
        e.stream,
        dispatch["dispatch_id"],
        e.acceptance_config,
        "Independent",
        "Architect",
        reference="second-stopped-replacement",
        commits={"feature": first_merge, "ui": first_merge, "base": first_merge},
        image=e.bindings["image"],
    )
    e.docker.worker = lambda files: None
    check(e)
    a.accept(e.journal, e.stream, "Independent")
    a.sync_feedback(e.journal, e.stream)
    e.candidate = commit_candidate(
        e, tmp_path, base=first_merge, payload=b"VALUE = 3\n"
    )
    v.git(e.journal.root, "switch", "feature/release")
    v.git(e.journal.root, "merge", "--ff-only", e.candidate)
    v.git(e.journal.root, "switch", "feature/auth")
    v.git(e.journal.root, "push", "origin", "feature/release")
    e.live = live(e, e.candidate)
    e.receipt = manifest(e, e.candidate, directory="run-second-integration-proof")
    second = assess(e, retained=first["retained_refs"])
    assert second["readiness"] == "READY_FOR_EXPLICIT_INTEGRATION", second
    second_merge = integrate_release("Explicit second retained-branch integration")
    assert second_merge != e.candidate
    refs = dict(
        row.split()[::-1]
        for row in v.git(e.journal.root, "ls-remote", "--heads", "origin")
        .decode()
        .splitlines()
    )
    assert {
        "refs/heads/feature/auth",
        "refs/heads/feature/release",
        "refs/heads/main",
    } <= refs.keys()
    assert refs["refs/heads/feature/release"] == e.candidate
    assert refs["refs/heads/main"] == refs["refs/heads/feature/auth"] == second_merge
    v.git(e.journal.root, "merge-base", "--is-ancestor", original, second_merge)
    v.git(e.journal.root, "merge-base", "--is-ancestor", first_commit, second_merge)
    assert (
        v.git(
            e.journal.root, "rev-list", "--count", original + ".." + second_merge
        ).strip()
        == b"4"
    )
    assert (
        v.git(
            e.journal.root,
            "rev-list",
            "--merges",
            "--count",
            original + ".." + second_merge,
        ).strip()
        == b"2"
    )
    assert v.git(e.journal.root, "show", "HEAD:src/features/auth.py") == b"VALUE = 3\n"
