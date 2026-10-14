"""Prepare an inert workflow review manifest from pinned local evidence; no activation."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import validate_workflow_approval as approval


def build():
    target = ROOT / approval.PACKAGE
    if target.exists():
        old = approval.read_json(approval.safe_file(ROOT, approval.PACKAGE))
        approval.check_receipt(old)
        approval.require(old["state"] == "AWAITING_APPROVAL", "Never overwrite an approved foundation")
    source = ROOT / "../universal-ai-project-template"
    dependencies = {}
    for path in sorted(approval.EXISTING_SOURCE | approval.NEW_SOURCE | approval.REFERENCES):
        dependencies[path] = {
            "git_blob": approval.git(source, "rev-parse", f"{approval.SOURCE_PIN}:{path}").decode().strip(),
            "sha256_lf": approval.content_digest(approval.git(source, "show", f"{approval.SOURCE_PIN}:{path}")),
            "disposition": "preserve_exact" if path in approval.EXISTING_SOURCE else "adapt" if path in approval.NEW_SOURCE else "reference_only",
        }
    files = set(approval.git(ROOT, "ls-files").decode().splitlines()) | approval.REQUIRED_BINDINGS | {
        "tests/test_workflow_runtime_startup.py",
    }
    files.discard(approval.PACKAGE)
    bindings = {path: approval.content_digest(approval.safe_file(ROOT, path).read_bytes()) for path in sorted(approval.REQUIRED_BINDINGS)}
    baseline = {path: approval.content_digest(approval.safe_file(ROOT, path).read_bytes()) for path in sorted(files - set(bindings))}
    criteria = [
        ("AC-01", "Foundation approval binds destination, source, policies and files; inactive or stale approval refuses dispatch.",
         ["Positive package validation and exact fingerprint", "Inactive, forged, altered-file, altered-policy and changed-anchor refusals", "Owner receipt only after explicit later approval"]),
        ("AC-02", "Retain Docker read/write/network isolation for worker and acceptance exports.",
         ["Denied host/sibling/Git/socket/credential/link/network access and immutable writes", "Allowed scoped task succeeds", "Image ID and Docker inspect evidence for both worker and acceptance"]),
        ("AC-03", "Only one branch/workspace owner and one consumed start survive failure, races and recovery.",
         ["Startup refusal plus failed logging cannot reuse token", "Concurrent execute permits at most one Docker start", "Restart after consumed-start commit refuses retry", "Expiry recovery requires stopped tree and preserved output; old token refused"]),
        ("AC-04", "Routing preserves role/risk/complexity floors, eligibility, expected-cost ranking and context bounds.",
         ["Source routing tests ported with disabled resources", "Risk/tier/provider-unavailable/context-negative cases", "Decision replay reproduces selected resource and reasons from saved config"]),
        ("AC-05", "Attempts, repeated failures, repairs, resumptions and review caps remain cumulative and bounded.",
         ["Worker cap 2 and reviewer cap 2; tier caps and deadlines enforced", "Contract repair/resume/resubmission never reset counts", "Repeated worker and reviewer fingerprints escalate or hold; exhausted budgets refuse"]),
        ("AC-06", "Budget accounting retains settled spend and pending liability and refuses unknown metered cost.",
         ["Concurrent reservations fit task/role/project caps", "Missing/zero/positive unmeasured cost remains held; measured cache usage priced conservatively", "Abandoned possibly charged run never becomes free", "Zero budgets and disabled resources prevent live API calls"]),
        ("AC-07", "Dispatch and ingestion bind one reservation to the exact scoped run and report.",
         ["Duplicate reservation/start/RESULT and changed brief/binding/deadline refusals", "Wrong dispatch/check IDs/types/oversized report/path escape/link/stale bundle refusals", "Crash between reserve/render/claim/start/result reconciles without implicit launch"]),
        ("AC-08", "Independent acceptance checks the current candidate and preserves source gate floors.",
         ["Worker PASS cannot accept; same actor and reviewer-tier/family shortfalls refused", "Fresh isolated deterministic checks bound to candidate/image", "Changed artifact/reference/commit/interface invalidates earlier gates", "Hardware evidence missing means unverified; feedback sync is bound and idempotent"]),
        ("AC-09", "One canonical durable journal survives Windows interruption across all repository worktrees.",
         ["Thread/process append collision and actual process-kill/restart tests", "Alternate-state, gap, digest mismatch and stale stream-head refusals", "One-time source chain import retains IDs/head/counts/spend", "Backup/restore verifies journal and referenced evidence before dispatch"]),
        ("AC-10", "A fresh session resumes from bounded coordinator/worker handoffs without widening scope.",
         ["Clean-start and interrupted-run resume identify objective/scope/base/diff/interface/pending spend/blocker/next action", "Stale derived view refused; exact missing-context proposal yields smallest revised scope", "UTC timestamps and measured/estimated/unknown context usage accurately labeled"]),
        ("AC-11", "Acceptance, integration and deployment remain distinct; interfaces and live required checks gate promotion.",
         ["Exact feature/UI/base candidate identities and contract/boundary tests", "Approved interface change links UI and mocks; internal-only change requires no UI work", "Changed head invalidates checks; missing/failing live required checks block promotion", "No deployment or hardware success inferred from tests"]),
        ("AC-12", "Closeout preserves original/source work and every permanent feature branch locally and on origin.",
         ["No donor cleanup/delete/reset/force-push/rename path imported", "Before authorized merge verify delete_branch_on_merge=false and exact reviewed head", "Two successive releases from retained branch preserve history and avoid duplicate changes", "Protected statuses/indexes and unrelated branch refs preserved"]),
    ]
    milestones = [
        ("M1", "Isolation maintainer", [], ["AC-02", "AC-03"], ["scripts/workflow_scope.py", "scripts/workflow_runtime.py", "tests/test_workflow_runtime_startup.py"]),
        ("M2", "Coordinator and journal maintainer", ["M1"], ["AC-01", "AC-09"], ["scripts/validate_workflow_approval.py", "scripts/workflow_state.py", "config/workflow-bootstrap.json", "tests/test_workflow_state.py"]),
        ("M3", "Routing and feedback maintainer", ["M2"], ["AC-04", "AC-05", "AC-06"], ["scripts/model_router.py", "scripts/feedback.py", "config/model-router.schema.json", "config/feedback.schema.json", "tests/test_model_router.py", "tests/test_feedback.py"]),
        ("M4", "Execution maintainer", ["M3"], ["AC-02", "AC-03", "AC-07"], ["scripts/execution_harness.py", "scripts/worker_launcher.py", "config/execution-harness.schema.json", "tests/test_execution_harness.py", "tests/test_worker_launcher.py"]),
        ("M5", "Independent acceptance owner", ["M4"], ["AC-08", "AC-11"], ["scripts/acceptance.py", "config/acceptance.schema.json", "tests/test_acceptance.py"]),
        ("M6", "Coordinator and integrator", ["M5"], ["AC-10", "AC-11", "AC-12"], ["scripts/workflow_handoff.py", "scripts/workflow_closeout.py", "docs/workflow-migration/README.md", "tests/test_workflow_closeout.py"]),
    ]
    return {
        "schema_version": "destination-workflow-approval/1.0",
        "state": "AWAITING_APPROVAL", "autonomy_enabled": False,
        "approval": {"approved": False, "approved_by": None, "approved_at": None, "architecture_fingerprint": None, "decision": None},
        "destination": {"repository": "ai-template-oop", "branch": "feature/workflow-migration", "base_commit": approval.BASE},
        "source": {"repository": "henslewm/universal-ai-project-template", "commit": approval.SOURCE_PIN, "checkout": "../universal-ai-project-template"},
        "authority": {
            "approval_scope": "bounded_offline_implementation", "live_workers_enabled": False,
            "provider_egress": "none", "credential_delivery": "none", "publication_authorized": False,
            "merge_authorized": False, "delegation_authorized": False, "activation_requires": "explicit_owner_receipt",
            "contract_changes_require": "owner_and_linked_ui",
        },
        "components": {
            "bootstrap": "Destination receipt and document/config hashes replace donor ACTIVE approval; validator is read-only.",
            "routing": "Adapt model_router route/record/verify; retain floors, expected cost ranking and context headroom; all resources disabled.",
            "feedback": "Adapt replay/apply/reserve/complete/review/diagnose over canonical journal; lifetime IDs, failures and caps preserved.",
            "bounded_attempts": "Worker default 2, reviewer overall 2, tier min caps, deadline and explicit holds; no reset on repair or resubmission.",
            "budgets": "Live caps zero; later metered enablement needs new foundation. Hold unknown liability and reserve all cost caps atomically.",
            "dispatch_report_ingestion": "Adapt harness prepare/validate/ingest and launcher preflight to Docker-only execution; bind exact reservation/scope/image/bundle.",
            "independent_acceptance": "Adapt acceptance gates and replay; rerun deterministic checks in separate Docker export; implementer cannot accept; exact candidate binding.",
            "durable_shared_state": "Separate control.sqlite3 journal from ownership.sqlite3; canonical Git-common identity, durable transactions, idempotent cross-store reconciliation and derived views.",
            "branch_preserving_closeout": "Adapt readiness only; exclude donor cleanup and auto-merge authority; permanent feature branches, exact heads and later owner merge gate.",
        },
        "policy": {
            "worker_max_attempts": 2, "reviewer_max_attempts": 2, "max_attempts_by_tier": {"0": 3, "1": 3, "2": 2, "3": 2, "4": 1},
            "repeated_failure_per_tier": 2, "repeated_failure_total": 3, "max_contract_repairs": 1,
            "max_blocker_resumptions": 3, "max_architect_diagnoses": 5, "attempt_timeout_seconds": 600,
            "automated_pr_review_max_rounds": 4, "max_context_chars": 40000, "max_history_entries": 5,
            "task_api_budget_usd": 0, "role_api_budget_usd": 0, "project_api_budget_usd": 0,
            "risk_floor": approval.RISK_FLOORS, "complexity_floor": {"low": 0, "medium": 2, "high": 3},
            "review_floors": approval.REVIEW_FLOORS, "resources_enabled": False, "unknown_cost_action": "HOLD",
            "budget_accounting": "settled_plus_pending_ceiling", "unmeasured_worker_cost": "unverified_liability",
        },
        "boundary": {
            "runtime": "Docker Desktop Linux", "network": "none", "uid_gid": "1000:1000", "read_only_root": True,
            "capabilities": "drop_all", "no_new_privileges": True, "host_bind_mounts": False, "git_objects": False,
            "host_credentials": False, "control_state_visible": False, "scope": "enumerated_files_only",
            "acceptance_execution": "separate_scoped_docker_export",
            "image": "sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e",
        },
        "state_layout": {
            "identity": "git_common_directory", "root": "LOCALAPPDATA/ai-template-workflow/<identity>",
            "ownership": "ownership.sqlite3", "task_review_project": "control.sqlite3", "evidence": "run-*/",
            "views": "derived_only", "alternate_state": "refused", "journal_durability": "sqlite_full_synchronous_transactions",
            "launch_authority": "commit_consumed_before_docker_start", "cross_store_recovery": "idempotent_reconciliation_no_implicit_restart",
            "branch_retention": "permanent_local_and_origin",
        },
        "source_dependencies": dependencies,
        "milestones": [{"id": ident, "owner": owner, "depends_on": depends, "criteria": gates, "paths": paths}
                       for ident, owner, depends, gates, paths in milestones],
        "acceptance_criteria": [{"id": ident, "requirement": requirement, "evidence": evidence, "status": "pending"}
                                for ident, requirement, evidence in criteria],
        "blockers": [
            "Launch prerequisite: durably consume startup authority; retry/race/restart defect remains unrepaired.",
            "Rollout prerequisite: implement journal, controllers, Docker dispatch and independent acceptance adapters in milestone order.",
            "Acceptance prerequisite: independent exact-candidate and Windows crash/concurrency evidence; historical tests are insufficient.",
            "Outside scope: real model resources, prices, provider-only egress, credentials, paid-worker authority and Git publication require a new owner-reviewed proposal.",
        ],
        "bound_files": bindings, "baseline_files": baseline,
        "preserved_state": {"refs": approval.refs(ROOT), "original": approval.checkout_snapshot(ROOT / "../ai-template-oop"),
                            "source": approval.checkout_snapshot(source)},
    }


def main():
    data = build()
    result = approval.validate(data, ROOT, check_source=True, check_preserved=True, check_baseline=True)
    # Exclusive temporary creation and atomic replacement cannot write an ACTIVE receipt.
    target = ROOT / approval.PACKAGE
    temporary = target.with_suffix(".json.preparing")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    temporary.replace(target)
    print("PREPARED AWAITING_APPROVAL; autonomy off")
    print(result)


if __name__ == "__main__":
    raise SystemExit(main())
