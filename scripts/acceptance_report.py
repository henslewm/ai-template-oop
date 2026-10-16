"""Pinned donor reviewer report validation; no execution or journal authority."""

from __future__ import annotations

from scripts import work_packet as wp
from scripts.execution_harness import require, secret_free

SCHEMA = wp.read_json(wp.ROOT / "config/acceptance.schema.json")


def shape(name, value):
    wp.canonical(value)
    validator = wp.Draft202012Validator(
        {"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    )
    if wp.schema_errors(validator, value):
        raise ValueError("Invalid acceptance report field types")


def report_valid(report, contract, opened, policy):
    """The complete reviewer report contract; shared by the ledger and the ledger-free verifier."""
    shape("report", report)
    require(
        len(wp.canonical(report).encode("utf-8")) <= policy["review_report_max_bytes"],
        "Reviewer report exceeds its configured bound",
    )
    secret_free(report, "Reviewer report")
    require(
        report["review_id"] == opened["review_id"],
        "Report does not match the opened review",
    )
    require(
        report["reviewer"] == opened["reviewer"],
        "Report reviewer identity differs from the opened review",
    )
    criteria = {entry["id"] for entry in contract["acceptance_criteria"]}
    found = [finding["criterion_id"] for finding in report["criteria"]]
    require(
        len(set(found)) == len(found) and set(found) == criteria,
        "Report exactly one finding per contract acceptance criterion and no other id",
    )
    statuses = {
        finding["criterion_id"]: finding["status"] for finding in report["criteria"]
    }
    verdict = report["verdict"]
    failures, missing, escalation = (
        report["contract_failures"],
        report["missing_evidence"],
        report["escalation_reason"],
    )
    validations = {check["id"]: check for check in contract["validation"]}
    scope_refs = (
        set(contract["scope"]["allowed"])
        | set(contract["scope"]["prohibited"])
        | set(contract["architecture_boundaries"])
    )
    for failure in failures:
        refs = (
            scope_refs
            if failure["kind"] == "scope"
            else (criteria if failure["kind"] == "criterion" else set(validations))
        )
        require(
            failure["failed_ref"] in refs,
            "A contract failure must name an existing criterion, validation or scope rule",
        )
    if verdict == "APPROVE":
        require(
            all(status == "met" for status in statuses.values()),
            "APPROVE requires every acceptance criterion to be met",
        )
        require(
            not failures and not missing and not escalation.strip(),
            "APPROVE carries no failures, missing evidence or escalation",
        )
    elif verdict == "REJECT_BOUNDED":
        require(
            bool(failures), "A bounded rejection must name specific contract failures"
        )
        require(
            "cannot_determine" not in statuses.values(),
            "Undeterminable criteria are NEEDS_EVIDENCE, not a bounded rejection",
        )
        require(
            "not_met" in statuses.values()
            or any(f["kind"] == "scope" for f in failures),
            "A bounded rejection requires an unmet criterion or a scope failure",
        )
        require(
            not missing and not escalation.strip(),
            "A bounded rejection carries no missing evidence or escalation",
        )
    elif verdict == "NEEDS_EVIDENCE":
        require(bool(missing), "NEEDS_EVIDENCE must name the missing evidence")
        require(
            "cannot_determine" in statuses.values(),
            "NEEDS_EVIDENCE requires at least one undeterminable criterion",
        )
        for item in missing:
            check = validations.get(item["validation_id"])
            require(
                check is not None
                and item["evidence_required"] in check["evidence_required"],
                "Missing evidence must reference a contract validation's declared evidence",
            )
        require(
            not failures and not escalation.strip(),
            "NEEDS_EVIDENCE carries no contract failures or escalation",
        )
    else:
        require(
            bool(escalation.strip()), f"{verdict} requires a stated escalation reason"
        )
        require(
            not failures and not missing,
            f"{verdict} carries no failures or missing evidence",
        )
    return report
