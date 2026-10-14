"""Read-only validation of the destination workflow foundation; never activate it."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "config/workflow-bootstrap.json"
SOURCE_PIN = "d6e582b7edeae24345a175f36639230726dbdead"
BASE = "a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4"
FIELDS = {
    "schema_version", "state", "autonomy_enabled", "approval", "destination",
    "source", "authority", "components", "policy", "boundary", "state_layout",
    "source_dependencies", "milestones", "acceptance_criteria", "blockers",
    "bound_files", "baseline_files", "preserved_state",
}
RECEIPT_FIELDS = {"state", "autonomy_enabled", "approval"}
COMPONENTS = {"bootstrap", "routing", "feedback", "bounded_attempts", "budgets",
              "dispatch_report_ingestion", "independent_acceptance",
              "durable_shared_state", "branch_preserving_closeout"}
EXISTING_SOURCE = {
    "scripts/work_packet.py", "scripts/cli_exit.py", "scripts/software_hardware.py",
    "config/work-packet.schema.json", "config/domains/software-hardware.schema.json",
    "examples/work-packets/software-hardware.contract.json", "tests/test_work_packet.py",
    "requirements-work-packets.txt",
}
NEW_SOURCE = {
    "scripts/model_router.py", "scripts/feedback.py", "scripts/execution_harness.py",
    "scripts/worker_launcher.py", "scripts/acceptance.py", "scripts/validate_bootstrap.py",
    "scripts/cli_colors.py", "scripts/progress.py",
    "config/model-router.schema.json", "config/feedback.schema.json",
    "config/execution-harness.schema.json", "config/acceptance.schema.json",
}
REFERENCES = {
    "scripts/bootstrap_gate.py", "config/bootstrap.schema.json", "scripts/closeout.py",
    "templates/harness/BOUNDED_WORKER_RULES.md", "templates/acceptance/REVIEWER_RULES.md",
    "tests/test_model_router.py", "tests/test_feedback.py", "tests/test_execution_harness.py",
    "tests/test_worker_launcher.py", "tests/test_acceptance.py", "tests/test_bootstrap.py",
    "tests/test_bootstrap_gate.py", "tests/test_closeout.py",
}
REQUIRED_BINDINGS = EXISTING_SOURCE | {
    "CLAUDE.md", "PROMPTS.md", "BRANCH_RETENTION.md", "pyproject.toml",
    "docs/workflow-migration/ARCHITECTURE.md", "docs/workflow-migration/BOOTSTRAP_REVIEW.md",
    "scripts/validate_workflow_approval.py", "tests/test_workflow_approval.py",
    "tools/prepare_workflow_approval.py",
}
REQUIRED_BASELINE = {
    "scripts/workflow_scope.py", "scripts/workflow_runtime.py", "runtime/workflow/Dockerfile",
    "runtime/workflow/probe.py", "tools/validate_boundaries.py", "tests/test_workflow_scope.py",
    "tests/test_workflow_runtime_startup.py", "docs/workflow-migration/HANDOFF.md",
}
RISK_FLOORS = {"low": 0, "medium": 1, "high": 3, "critical": 4}
REVIEW_FLOORS = {
    "low": ["deterministic"],
    "medium": ["deterministic", "model_review"],
    "high": ["cross_family_review", "deterministic", "model_review"],
    "critical": ["architect_review", "cross_family_review", "deterministic", "model_review", "user_decision"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, fields, where):
    require(isinstance(value, dict) and set(value) == set(fields), f"Invalid fields in {where}")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def hex_digest(value, size):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value) is not None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def fingerprint(data):
    return hashlib.sha256(canonical({k: v for k, v in data.items() if k not in RECEIPT_FIELDS})).hexdigest()


def content_digest(content):
    """Normalize text line endings only; preserve all other bytes."""
    return hashlib.sha256(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    def invalid_constant(_value):
        raise ValueError("Nonfinite JSON number")
    require(path.stat().st_size <= 4 * 1024 * 1024, "Approval JSON exceeds size limit")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 approval JSON") from exc


def relative_path(value):
    require(text(value) and "\\" not in value and ":" not in value, "Invalid relative file path")
    path = PurePosixPath(value)
    require(bool(path.parts) and not path.is_absolute() and path.as_posix() == value
            and all(part not in {".", "..", ".git", ".agents", ".codex", ".aws"} for part in path.parts),
            "Escaped or protected file path")
    return path


def safe_file(root, relative):
    path = relative_path(relative)
    target = root
    for part in path.parts:
        target = target / part
        require(not target.is_symlink() and not getattr(target, "is_junction", lambda: False)(),
                "Linked approval input refused")
    require(target.resolve().is_relative_to(root.resolve()) and target.is_file(),
            f"Bound file missing or escaped: {relative}")
    require(target.stat().st_size <= 4 * 1024 * 1024, "Bound file exceeds size limit")
    return target


def git(root, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                            capture_output=True, timeout=30, check=False)
    require(result.returncode == 0, "Read-only Git inspection failed")
    return result.stdout


def refs(root):
    output = git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes")
    return dict(line.split(" ", 1) for line in output.decode().splitlines())


def checkout_snapshot(root):
    index = Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
    return {"status": git(root, "status", "--porcelain=v2", "--branch").decode().splitlines(),
            "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest()}


def check_receipt(data):
    exact(data["approval"], {"approved", "approved_by", "approved_at", "architecture_fingerprint", "decision"}, "approval")
    require(type(data["autonomy_enabled"]) is bool, "autonomy_enabled must be boolean")
    receipt = data["approval"]
    if data["state"] == "AWAITING_APPROVAL":
        require(data["autonomy_enabled"] is False and receipt["approved"] is False and receipt == {
            "approved": False, "approved_by": None, "approved_at": None,
            "architecture_fingerprint": None, "decision": None,
        }, "Inactive foundation requires autonomy off and an empty approval receipt")
    elif data["state"] == "ACTIVE":
        require(data["autonomy_enabled"] is True and receipt["approved"] is True
                and text(receipt["approved_by"]), "ACTIVE requires an identified approving owner")
        current = fingerprint(data)
        require(receipt["architecture_fingerprint"] == current and receipt["decision"] == "APPROVE " + current,
                "Approval fingerprint or literal decision differs from current foundation")
        try:
            require(isinstance(receipt["approved_at"], str), "Approval timestamp must be a UTC string")
            instant = datetime.fromisoformat(receipt["approved_at"].replace("Z", "+00:00"))
            require(instant.utcoffset() == timedelta(0), "Approval timestamp must be timezone-aware UTC")
        except (TypeError, ValueError) as exc:
            raise ValueError("Approval timestamp must be timezone-aware UTC") from exc
    else:
        raise ValueError("Unsupported foundation state")


def check_policy(policy):
    required = {
        "worker_max_attempts", "reviewer_max_attempts", "max_attempts_by_tier",
        "repeated_failure_per_tier", "repeated_failure_total", "max_contract_repairs",
        "max_blocker_resumptions", "max_architect_diagnoses", "attempt_timeout_seconds",
        "automated_pr_review_max_rounds", "max_context_chars", "max_history_entries",
        "task_api_budget_usd", "role_api_budget_usd", "project_api_budget_usd",
        "risk_floor", "complexity_floor", "review_floors", "resources_enabled",
        "unknown_cost_action", "budget_accounting", "unmeasured_worker_cost",
    }
    exact(policy, required, "policy")
    limits = {
        "worker_max_attempts": 2, "reviewer_max_attempts": 2,
        "repeated_failure_per_tier": 2, "repeated_failure_total": 3,
        "max_contract_repairs": 1, "max_blocker_resumptions": 3,
        "max_architect_diagnoses": 5, "attempt_timeout_seconds": 600,
        "automated_pr_review_max_rounds": 4, "max_context_chars": 40000,
        "max_history_entries": 5,
    }
    for key, ceiling in limits.items():
        require(type(policy[key]) is int and 0 < policy[key] <= ceiling, f"Invalid bounded limit: {key}")
    tiers = policy["max_attempts_by_tier"]
    exact(tiers, {str(t) for t in range(5)}, "tier caps")
    for tier, ceiling in enumerate((3, 3, 2, 2, 1)):
        require(type(tiers[str(tier)]) is int and 0 < tiers[str(tier)] <= ceiling, "Invalid tier attempt cap")
    for key in ("task_api_budget_usd", "role_api_budget_usd", "project_api_budget_usd"):
        require(type(policy[key]) in (int, float) and policy[key] == 0, "Metered budgets must remain zero")
    require(canonical(policy["risk_floor"]) == canonical(RISK_FLOORS)
            and canonical(policy["complexity_floor"]) == canonical({"low": 0, "medium": 2, "high": 3})
            and policy["review_floors"] == REVIEW_FLOORS, "Inherited routing/review floors changed")
    require(policy["resources_enabled"] is False and policy["unknown_cost_action"] == "HOLD"
            and policy["budget_accounting"] == "settled_plus_pending_ceiling"
            and policy["unmeasured_worker_cost"] == "unverified_liability", "Unsafe dispatch or cost policy")


def check_plan(data):
    exact(data["components"], COMPONENTS, "components")
    require(all(text(v) for v in data["components"].values()), "Every component needs a destination adaptation")
    criteria = data["acceptance_criteria"]
    require(isinstance(criteria, list) and len(criteria) == 12, "Twelve acceptance criteria required")
    identifiers = set()
    for criterion in criteria:
        exact(criterion, {"id", "requirement", "evidence", "status"}, "acceptance criterion")
        require(text(criterion["id"]) and criterion["id"] not in identifiers, "Duplicate criterion ID")
        identifiers.add(criterion["id"])
        require(text(criterion["requirement"]) and isinstance(criterion["evidence"], list)
                and criterion["evidence"] and all(text(e) for e in criterion["evidence"])
                and criterion["status"] == "pending", "Acceptance evidence must be specified and remain pending")
    require(identifiers == {f"AC-{i:02d}" for i in range(1, 13)}, "Missing required acceptance criterion")
    milestones = data["milestones"]
    require(isinstance(milestones, list) and len(milestones) == 6, "Six ordered milestones required")
    prior = set()
    for milestone in milestones:
        exact(milestone, {"id", "owner", "depends_on", "criteria", "paths"}, "milestone")
        require(milestone["id"] == f"M{len(prior) + 1}" and text(milestone["owner"]), "Invalid milestone identity")
        require(isinstance(milestone["depends_on"], list) and set(milestone["depends_on"]) <= prior,
                "Milestone dependency is missing, forward or cyclic")
        require(isinstance(milestone["criteria"], list) and milestone["criteria"]
                and set(milestone["criteria"]) <= identifiers, "Milestone must reference acceptance criteria")
        require(isinstance(milestone["paths"], list) and milestone["paths"], "Milestone needs owned paths")
        for path in milestone["paths"]:
            relative_path(path)
        prior.add(milestone["id"])
    require(isinstance(data["blockers"], list) and data["blockers"] and all(text(v) for v in data["blockers"]),
            "Operational prerequisites must remain explicit")


def validate(data, root, *, check_source=False, check_preserved=False, check_baseline=False, require_active=False):
    exact(data, FIELDS, "foundation")
    require(data["schema_version"] == "destination-workflow-approval/1.0", "Unsupported package version")
    exact(data["destination"], {"repository", "branch", "base_commit"}, "destination")
    require(data["destination"] == {"repository": "ai-template-oop", "branch": "feature/workflow-migration", "base_commit": BASE},
            "Destination repository, retained branch or base differs")
    if check_baseline:
        require(git(root, "rev-parse", "HEAD").decode().strip() == BASE
                and git(root, "branch", "--show-current").decode().strip() == data["destination"]["branch"],
                "Wrong destination branch or base")
    exact(data["source"], {"repository", "commit", "checkout"}, "source")
    require(data["source"] == {"repository": "henslewm/universal-ai-project-template", "commit": SOURCE_PIN,
                               "checkout": "../universal-ai-project-template"}, "Source identity differs from pinned design")
    require(canonical(data["authority"]) == canonical({
        "approval_scope": "bounded_offline_implementation", "live_workers_enabled": False,
        "provider_egress": "none", "credential_delivery": "none", "publication_authorized": False,
        "merge_authorized": False, "delegation_authorized": False,
        "activation_requires": "explicit_owner_receipt", "contract_changes_require": "owner_and_linked_ui",
    }), "Foundation authority was expanded")
    require(canonical(data["boundary"]) == canonical({
        "runtime": "Docker Desktop Linux", "network": "none", "uid_gid": "1000:1000",
        "read_only_root": True, "capabilities": "drop_all", "no_new_privileges": True,
        "host_bind_mounts": False, "git_objects": False, "host_credentials": False,
        "control_state_visible": False, "scope": "enumerated_files_only",
        "acceptance_execution": "separate_scoped_docker_export",
        "image": "sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e",
    }), "Existing Docker isolation boundary was changed")
    require(canonical(data["state_layout"]) == canonical({
        "identity": "git_common_directory", "root": "LOCALAPPDATA/ai-template-workflow/<identity>",
        "ownership": "ownership.sqlite3", "task_review_project": "control.sqlite3",
        "evidence": "run-*/", "views": "derived_only", "alternate_state": "refused",
        "journal_durability": "sqlite_full_synchronous_transactions",
        "launch_authority": "commit_consumed_before_docker_start",
        "cross_store_recovery": "idempotent_reconciliation_no_implicit_restart",
        "branch_retention": "permanent_local_and_origin",
    }), "Ownership, journal, recovery or retention boundary changed")
    check_policy(data["policy"])
    check_plan(data)
    bindings = data["bound_files"]
    require(isinstance(bindings, dict) and REQUIRED_BINDINGS <= set(bindings) and PACKAGE not in bindings,
            "Required approval-bound files are missing or recursively bound")
    folded = set()
    for path, expected in bindings.items():
        require(path.casefold() not in folded and hex_digest(expected, 64), "Duplicate or invalid bound digest")
        folded.add(path.casefold())
        require(content_digest(safe_file(root, path).read_bytes()) == expected, f"Approval-bound file changed: {path}")
    baseline = data["baseline_files"]
    require(isinstance(baseline, dict) and REQUIRED_BASELINE <= set(baseline)
            and not (set(baseline) & set(bindings)) and PACKAGE not in baseline, "Invalid destination baseline inventory")
    for path, expected in baseline.items():
        relative_path(path)
        require(path.casefold() not in folded and hex_digest(expected, 64), "Duplicate or invalid baseline digest")
        folded.add(path.casefold())
        if check_baseline:
            require(content_digest(safe_file(root, path).read_bytes()) == expected, f"Destination baseline changed: {path}")
    dependencies = data["source_dependencies"]
    exact(dependencies, EXISTING_SOURCE | NEW_SOURCE | REFERENCES, "pinned source dependency closure")
    source_root = root / data["source"]["checkout"]
    for path, record in dependencies.items():
        relative_path(path)
        exact(record, {"git_blob", "sha256_lf", "disposition"}, "source dependency")
        require(hex_digest(record["git_blob"], 40) and hex_digest(record["sha256_lf"], 64), "Invalid source blob/digest")
        expected_disposition = "preserve_exact" if path in EXISTING_SOURCE else "adapt" if path in NEW_SOURCE else "reference_only"
        require(record["disposition"] == expected_disposition, "Source dependency disposition changed")
        if path in EXISTING_SOURCE:
            local = safe_file(root, path).read_bytes()
            # Git object IDs describe normalized imported text, not working-tree CRLF bytes.
            normalized = local.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            blob = hashlib.sha1(b"blob " + str(len(normalized)).encode() + b"\0" + normalized).hexdigest()
            require(blob == record["git_blob"] and content_digest(local) == record["sha256_lf"],
                    f"Imported source file differs: {path}")
        if check_source:
            require(git(source_root, "rev-parse", f"{SOURCE_PIN}:{path}").decode().strip() == record["git_blob"],
                    f"Pinned source blob differs: {path}")
            require(content_digest(git(source_root, "show", f"{SOURCE_PIN}:{path}")) == record["sha256_lf"],
                    f"Pinned source content differs: {path}")
    preserved = data["preserved_state"]
    exact(preserved, {"refs", "original", "source"}, "preserved state")
    require(isinstance(preserved["refs"], dict) and preserved["refs"]
            and all(k.startswith(("refs/heads/", "refs/remotes/")) and hex_digest(v, 40)
                    for k, v in preserved["refs"].items()), "Invalid preserved branch inventory")
    for name in ("original", "source"):
        exact(preserved[name], {"status", "index_sha256"}, "protected checkout snapshot")
        require(isinstance(preserved[name]["status"], list) and all(text(v) for v in preserved[name]["status"])
                and hex_digest(preserved[name]["index_sha256"], 64), "Invalid protected checkout snapshot")
    if check_preserved:
        require(refs(root) == preserved["refs"], "Retained local/cached remote branch refs changed")
        require(checkout_snapshot(root / "../ai-template-oop") == preserved["original"], "Original checkout/index changed")
        require(checkout_snapshot(source_root) == preserved["source"], "Source checkout/index changed")
    check_receipt(data)
    require(not require_active or data["state"] == "ACTIVE", "Foundation is not ACTIVE; autonomy remains off")
    return fingerprint(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fingerprint", action="store_true")
    parser.add_argument("--check-source", action="store_true")
    parser.add_argument("--check-preserved", action="store_true")
    parser.add_argument("--check-baseline", action="store_true")
    parser.add_argument("--require-active", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        require(sys.version_info >= (3, 12) or sys.platform != "win32", "Windows validation requires Python 3.12+ for junction checks")
        data = read_json(safe_file(root, PACKAGE))
        result = validate(data, root, check_source=args.check_source, check_preserved=args.check_preserved,
                          check_baseline=args.check_baseline, require_active=args.require_active)
        print("FOUNDATION VALID: " + data["state"] + "; live workers and publication disabled")
        if args.fingerprint:
            print(result)
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError):
        # Report only controlled validation errors; never dump manifest values or external stderr.
        message = sys.exc_info()[1]
        print("FOUNDATION INVALID: " + (str(message) if isinstance(message, ValueError) else "Input or read-only inspection failed"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
