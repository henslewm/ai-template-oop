#!/usr/bin/env python3
"""Reserve bounded worker attempts and replay their local evidence; no model calls."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import cli_exit
from scripts import model_router as router
from scripts import work_packet as wp
from scripts import workflow_budget as budget
from scripts.workflow_state import Journal, Append, Head, active_anchor

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = wp.read_json(ROOT / "config/feedback.schema.json")
wp.Draft202012Validator.check_schema(SCHEMA)
ACTIVE = {"READY", "IN_PROGRESS"}
PROTECTED = (
    "parent",
    "scope",
    "non_goals",
    "interface",
    "dependencies",
    "architecture_boundaries",
    "domain",
    "risk",
)


def shape(name, value):
    wp.canonical(value)
    validator = wp.Draft202012Validator(
        {"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    )
    errors = wp.schema_errors(validator, value)
    if errors:
        raise ValueError("\n".join(errors))


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"Expected fields: {', '.join(sorted(keys))}")


def instant(value):
    if not isinstance(value, str) or not wp.valid_timestamp(value):
        raise ValueError("Invalid event timestamp")
    return datetime.fromisoformat(value.upper().replace("Z", "+00:00"))


def binding(packet: dict[str, Any]):
    revision = wp.current(packet)
    return {
        "task_id": packet["task_id"],
        "revision": revision["version"],
        "contract_hash": revision["hash"],
        "role": "worker",
    }


def graph_check(packet: dict[str, Any], graph):
    if not isinstance(graph, list):
        raise ValueError("A complete packet graph is required")
    for item in graph:
        wp.require_valid(item)
        if item["domain_profile"] != packet["domain_profile"]:
            raise ValueError("Graph contains a different domain profile")
    matches = [item for item in graph if item["task_id"] == packet["task_id"]]
    if len(matches) != 1 or wp.canonical(matches[0]) != wp.canonical(packet):
        raise ValueError("Graph must contain the exact current packet once")
    wp.graph_order(graph)


def current_graph(state: dict[str, Any], packet: dict[str, Any] | None = None):
    chosen: dict[str, Any] = state["packet"] if packet is None else packet
    return [
        chosen if item["task_id"] == chosen["task_id"] else item
        for item in state["graph"]
    ]


def tier_counts(state: dict[str, Any]):
    return {str(t): sum(a["tier"] == t for a in state["attempts"]) for t in range(5)}


def failure_groups(state: dict[str, Any]):
    groups = {}
    for attempt in state["attempts"]:
        if not attempt.get("fingerprint"):
            continue
        key = attempt["fingerprint"]
        group = groups.setdefault(
            key,
            {
                "fingerprint": key,
                "count": 0,
                "tiers": {},
                "first_evidence": attempt["result"]["evidence"],
                "latest_evidence": [],
            },
        )
        group["count"] += 1
        tier = str(int(attempt["tier"]))
        group["tiers"][tier] = group["tiers"].get(tier, 0) + 1
        group["latest_evidence"] = attempt["result"]["evidence"]
    return [groups[key] for key in sorted(groups)]


def worker_context(state: dict[str, Any]):
    failures = [a for a in state["attempts"] if a.get("fingerprint")]
    context = {
        "binding": binding(state["packet"]),
        "contract": wp.current(state["packet"])["contract"],
        "controller_status": state["status"],
        "architect_guidance": state["latest_diagnosis"],
        "remaining_task_attempts": state["total_cap"] - len(state["attempts"]),
        "tier_counts": tier_counts(state),
        "tier_caps": state["caps"],
        "failure_groups": failure_groups(state),
        "recent_failures": [
            {
                "attempt_id": a["id"],
                "fingerprint": a["fingerprint"],
                "summary": a["result"]["summary"],
                "validation": a["result"]["validation"],
            }
            for a in failures[-int(state["policy"]["max_history_entries"]) :]
        ],
        # Present only once a rejection exists, so ledgers recorded before this key reproduce.
        **(
            {
                "review_rejections": [
                    {
                        "review_id": r["review_id"],
                        "fingerprint": r["fingerprint"],
                        "summary": r["summary"],
                        "contract_failures": r["contract_failures"],
                    }
                    for r in state["review_rejections"][
                        -int(state["policy"]["max_history_entries"]) :
                    ]
                ]
            }
            if state["review_rejections"]
            else {}
        ),
        "worker_rule": "Execution requires a matching reserved dispatch. Execute only this contract. Report unrelated discoveries as issue proposals. Do not revise scope or accept your own result.",
    }
    if len(wp.canonical(context)) > state["policy"]["max_context_chars"]:
        raise ValueError("CONTEXT_LIMIT_REQUIRES_DECOMPOSITION")
    return context


def history(state: dict[str, Any]):
    revision = wp.current(state["packet"])["version"]
    relevant = [a for a in state["attempts"] if a["revision"] == revision]
    return [
        {
            "sequence": index,
            "resource_id": a["resource_id"],
            "provider_id": a["provider_id"],
            "tier": a["tier"],
            "outcome": a["routing_outcome"],
            "api_cost_usd": a["result"]["api_cost_usd"],
            "elapsed_seconds": a["elapsed_seconds"],
            "decision_id": a["id"],
            "config_hash": a["config_hash"],
            "evidence": a["result"]["evidence"],
        }
        for index, a in enumerate(relevant, 1)
    ]


def source_plan(
    state: dict[str, Any], config: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    if state["pending"]:
        raise ValueError(
            "A reserved dispatch is pending; reconcile it before another attempt"
        )
    if state["status"] not in ACTIVE:
        raise ValueError(f"Controller hold: {state['status']}")
    router.source_validate_config(config)
    if config["policy"] != state["router_policy"]:
        raise ValueError(
            "Routing policy is frozen for this task; resource mappings may change"
        )
    exact(
        options,
        {
            "task_class",
            "input_tokens",
            "output_tokens",
            "unavailable_providers",
            "unavailable_resources",
        },
    )
    graph_check(state["packet"], current_graph(state))
    result: dict[str, Any] = {
        "status": "NEEDS_ARCHITECT",
        "reason": "TOTAL_ATTEMPT_LIMIT",
        "routing": None,
        "context": None,
    }
    if len(state["attempts"]) >= state["total_cap"]:
        return result
    try:
        result["context"] = worker_context(state)
    except ValueError:
        result["reason"] = "CONTEXT_LIMIT_REQUIRES_DECOMPOSITION"
        return result
    request: dict[str, Any] = {
        "schema_version": "1.0",
        "binding": binding(state["packet"]),
        **copy.deepcopy(options),
        "attempts": history(state),
        "observations": [],
    }
    # Validate caller filters before combining them with immutable controller limits.
    router.check_shape("request", request)
    config = copy.deepcopy(config)
    earlier = [
        a for a in state["attempts"] if a["revision"] != request["binding"]["revision"]
    ]
    old_spend = sum(
        (
            router.dec(a["result"]["api_cost_usd"])
            for a in earlier
            if a["result"]["api_cost_usd"] is not None
        ),
        router.dec(0),
    )
    # An unknown cost on an earlier revision cannot be carried in the router's current-revision
    # history, so its consequence is applied here: no metered resource while that spend is unknown.
    unknown_earlier = any(a["result"]["api_cost_usd"] is None for a in earlier)
    remaining = router.dec(config["policy"]["role_api_budget_usd"]) - old_spend
    if remaining < 0 or (remaining == 0 and old_spend > 0):
        result["reason"] = "CUMULATIVE_API_LIMIT"
        return result
    config["policy"]["role_api_budget_usd"] = float(remaining)
    counts = tier_counts(state)
    exhausted = [
        r["id"]
        for r in config["resources"]
        if counts[str(int(r["tier"]))] >= state["caps"][str(int(r["tier"]))]
    ]
    if unknown_earlier:
        exhausted = sorted(
            set(exhausted) | {r["id"] for r in config["resources"] if router.metered(r)}
        )
    request["unavailable_resources"] = sorted(
        set(request["unavailable_resources"] + exhausted)
    )
    routed = router.source_record(state["packet"], config, request)
    result["routing"] = routed
    if routed["decision"]["status"] == "ROUTED":
        result.update(status="DISPATCH", reason="BOUNDED_DISPATCH")
    else:
        result["reason"] = routed["decision"]["reason_codes"][0]
        if result["reason"] == "NO_ELIGIBLE_RESOURCE":
            # Exhausted tiers need architect resolution; temporary filters may be reconciled.
            result["status"] = "NEEDS_ARCHITECT" if exhausted else "BLOCKED"
    return result


def normalize(text):
    return " ".join(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text).split())


def failure_fingerprint(contract, result: dict[str, Any], timed_out=False):
    actual = {item["check_id"]: item for item in result["validation"]}
    failures = []
    for check in sorted(contract["validation"], key=lambda item: item["id"]):
        item = actual.get(check["id"])
        if item is None:
            failures.append({"check_id": check["id"], "code": "MISSING_VALIDATION"})
        elif not item["passed"]:
            failures.append(
                {
                    "check_id": check["id"],
                    "code": normalize(item["failure_code"]),
                    "expected": normalize(item["expected"]),
                    "actual": normalize(item["actual"]),
                }
            )
    return router.digest(
        {
            "failures": failures,
            "scope": result["scope_status"],
            "architecture_conflict": result["architecture_conflict"],
            "timed_out": timed_out,
            "outcome": result["outcome"] if not failures else "OBJECTIVE_FAILURE",
        }
    )


def move(state: dict[str, Any], target, actor, reason, evidence, timestamp):
    packet = state["packet"]
    state["packet"] = wp.transition(
        packet,
        target,
        "worker",
        actor,
        reason,
        evidence,
        current_graph(state),
        timestamp,
    )


def apply_result(
    state: dict[str, Any],
    result: dict[str, Any],
    timestamp,
    abandoned=False,
    cost_unknown=False,
):
    shape("result", result)
    if not state["pending"] or result["dispatch_id"] != state["pending"]:
        raise ValueError("Result does not match the pending dispatch")
    attempt = state["attempts"][-1]
    # ADR-097: an unknown cost is recorded only on a resource that was metered at dispatch; an unmetered
    # one is known to cost nothing. ADR-101 (OL-041): besides an abandonment, `execution_harness.ingest`
    # records a metered worker's reported zero as unknown through its own RESULT_COST_UNKNOWN event,
    # because a worker cannot measure its own spend. A plain RESULT always states a number.
    if abandoned:
        # ABANDON is the only provenance allowed an unknown cost, so it carries exactly the
        # no-report shape `execution_harness.abandon` writes; it can never record a pass.
        if (
            result["outcome"] != "FAIL"
            or result["scope_status"] != "unknown"
            or result["validation"]
            or result["architecture_conflict"]
            or result["discoveries"]
            or not all(
                item.startswith("attempt-abandoned: ") for item in result["evidence"]
            )
        ):
            raise ValueError(
                "An abandonment records outcome FAIL, scope unknown, no validation, no discoveries "
                "and attempt-abandoned evidence only"
            )
        expected = None if attempt.get("api_metered", True) else 0
        if result["api_cost_usd"] != expected:
            raise ValueError(
                "An abandoned attempt records an unknown (null) cost on a metered resource and 0 on an unmetered one"
            )
    elif cost_unknown:
        if result["api_cost_usd"] is not None:
            raise ValueError("A cost-unknown result records null")
        if not attempt.get("api_metered", True):
            raise ValueError(
                "An unknown (null) cost is recorded only on a metered resource; an unmetered one costs nothing"
            )
    elif result["api_cost_usd"] is None:
        raise ValueError(
            "An unknown (null) cost is recorded only by abandoning the attempt or by ingesting a metered zero"
        )
    contract = wp.current(state["packet"])["contract"]
    checks = {check["id"] for check in contract["validation"]}
    ids = [check["check_id"] for check in result["validation"]]
    if len(ids) != len(set(ids)) or set(ids) - checks:
        raise ValueError(
            "Validation IDs must be unique and belong to the current contract"
        )
    if any(
        not item["passed"] and not normalize(item["failure_code"])
        for item in result["validation"]
    ):
        raise ValueError("Failed validations require a stable failure code")
    elapsed = (instant(timestamp) - instant(attempt["issued_at"])).total_seconds()
    if elapsed < 0:
        raise ValueError("Result predates dispatch")
    timed_out = instant(timestamp) > instant(attempt["deadline"])
    passed = set(ids) == checks and all(item["passed"] for item in result["validation"])
    outcome = result["outcome"]
    status, reason = "IN_PROGRESS", "BOUNDED_RETRY"
    if result["architecture_conflict"] or outcome == "ARCHITECTURE_CONFLICT":
        status, reason, outcome = (
            "ARCHITECTURE_HOLD",
            "ARCHITECT_DIAGNOSIS_REQUIRED",
            "ARCHITECTURE_CONFLICT",
        )
    elif result["scope_status"] != "within":
        status, reason, outcome = "NEEDS_ARCHITECT", "SCOPE_REVIEW_REQUIRED", "BLOCKED"
    elif timed_out:
        outcome, reason = "FAIL", "ATTEMPT_TIMEOUT"
    elif outcome == "BLOCKED":
        status, reason = "BLOCKED", "WORKER_BLOCKED"
    elif outcome == "PASS" and passed:
        status, reason = "REVIEW_PENDING", "OBJECTIVE_CHECKS_PASSED"
    elif outcome == "PASS":
        outcome, reason = "FAIL", "PASS_CONTRADICTED_BY_VALIDATION"
    attempt.update(
        result=copy.deepcopy(result),
        elapsed_seconds=elapsed,
        resolved_at=timestamp,
        routing_outcome=outcome,
        fingerprint=None,
    )
    if (
        outcome in {"FAIL", "NEEDS_ESCALATION", "ARCHITECTURE_CONFLICT"}
        or result["scope_status"] != "within"
    ):
        attempt["fingerprint"] = failure_fingerprint(contract, result, timed_out)
    groups = failure_groups(state)
    group = next(
        (g for g in groups if g["fingerprint"] == attempt["fingerprint"]), None
    )
    if group and status == "IN_PROGRESS":
        if group["count"] >= state["policy"]["repeated_failure_total"]:
            status, reason, outcome = (
                "NEEDS_ARCHITECT",
                "REPEATED_FAILURE_TASK_LIMIT",
                "NEEDS_ESCALATION",
            )
        elif (
            group["tiers"].get(str(int(attempt["tier"])), 0)
            >= state["policy"]["repeated_failure_per_tier"]
        ):
            reason, outcome = "REPEATED_FAILURE_TIER_LIMIT", "NEEDS_ESCALATION"
    attempt["routing_outcome"] = outcome
    actor = "worker:" + attempt["resource_id"]
    if status == "ARCHITECTURE_HOLD":
        move(
            state, "ARCHITECTURE_CONFLICT", actor, reason, result["evidence"], timestamp
        )
    elif status == "NEEDS_ARCHITECT":
        move(state, "ESCALATED", actor, reason, result["evidence"], timestamp)
    elif status == "BLOCKED":
        move(state, "BLOCKED", actor, reason, result["evidence"], timestamp)
    elif outcome != "PROVIDER_UNAVAILABLE":
        move(state, "VALIDATING", actor, reason, result["evidence"], timestamp)
        move(
            state,
            "REVIEW" if status == "REVIEW_PENDING" else "IN_PROGRESS",
            actor,
            reason,
            result["evidence"],
            timestamp,
        )
    state.update(status=status, reason=reason, pending=None)
    state["discoveries"].extend(
        {"attempt_id": attempt["id"], **item} for item in result["discoveries"]
    )


def source_apply(
    state: dict[str, Any] | None, event: dict[str, Any], stored=False
) -> dict[str, Any]:
    data, timestamp = event["data"], event["timestamp"]
    if state is None:
        if event["kind"] != "INIT":
            raise ValueError("Ledger must start with INIT")
        exact(
            data, {"packet", "graph", "policy", "router_config", "anchor", "architect"}
        )
        wp.require_valid(data["packet"])
        graph_check(data["packet"], data["graph"])
        shape("policy", data["policy"])
        router.source_validate_config(data["router_config"])
        if (
            data["packet"]["state"] != "READY"
            or not isinstance(data["anchor"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", data["anchor"])
            or not isinstance(data["architect"], str)
            or not data["architect"].strip()
        ):
            raise ValueError(
                "INIT needs a READY packet, approval anchor and architect identity"
            )
        contract = wp.current(data["packet"])["contract"]
        cap = int(contract["retry_budget"]["max_attempts"])
        overrides = contract["retry_budget"].get("max_attempts_by_tier", {})
        return {
            "packet": copy.deepcopy(data["packet"]),
            "graph": copy.deepcopy(data["graph"]),
            "policy": copy.deepcopy(data["policy"]),
            "router_policy": data["router_config"]["policy"],
            "anchor": data["anchor"],
            "architect": data["architect"],
            "total_cap": cap,
            "caps": {
                str(t): min(
                    cap,
                    int(
                        overrides.get(
                            str(t), data["policy"]["max_attempts_by_tier"][str(t)]
                        )
                    ),
                )
                for t in range(5)
            },
            "repairs": 0,
            "resumptions": 0,
            "diagnoses": 0,
            "latest_diagnosis": None,
            "attempts": [],
            "pending": None,
            "status": "READY",
            "reason": "INITIALIZED",
            "discoveries": [],
            "review_rejections": [],
        }
    if event["kind"] in {"DISPATCH", "HALT"}:
        exact(data, {"config", "options", "plan"})
        expected = plan(state, data["config"], data["options"])
        if wp.canonical(expected) != wp.canonical(data["plan"]):
            raise ValueError("Recorded dispatch plan does not reproduce")
        if event["kind"] == "HALT":
            if expected["status"] == "DISPATCH":
                raise ValueError("HALT cannot contain a dispatch")
            state.update(status=expected["status"], reason=expected["reason"])
            return state
        if expected["status"] != "DISPATCH":
            raise ValueError("Dispatch violates a controller limit")
        decision = expected["routing"]["decision"]
        routed = next(
            r
            for r in data["config"]["resources"]
            if r["id"] == decision["selected"]["resource_id"]
        )
        attempt: dict[str, Any] = {
            "id": decision["decision_id"],
            **decision["selected"],
            "revision": binding(state["packet"])["revision"],
            "api_metered": router.metered(routed),
            "contract_hash": binding(state["packet"])["contract_hash"],
            "config_hash": decision["config_hash"],
            "issued_at": timestamp,
            "deadline": (
                instant(timestamp)
                + timedelta(seconds=int(state["policy"]["attempt_timeout_seconds"]))
            ).isoformat(),
            "result": None,
            "routing_outcome": None,
            "fingerprint": None,
        }
        if state["packet"]["state"] == "READY":
            move(
                state,
                "IN_PROGRESS",
                "worker:" + attempt["resource_id"],
                "Dispatch reserved",
                [attempt["id"]],
                timestamp,
            )
        state["attempts"].append(attempt)
        state.update(
            status="IN_PROGRESS", reason="DISPATCH_RESERVED", pending=attempt["id"]
        )
    elif event["kind"] in {"RESULT", "RESULT_COST_UNKNOWN", "ABANDON"}:
        apply_result(
            state,
            data,
            timestamp,
            abandoned=event["kind"] == "ABANDON",
            cost_unknown=event["kind"] == "RESULT_COST_UNKNOWN",
        )
        state["attempts"][-1]["result_event_sequence"] = event["sequence"]
    elif event["kind"] == "APPROVAL_HOLD":
        exact(data, {"reason"})
        if (
            state["pending"]
            or state["status"] not in ACTIVE
            or not isinstance(data["reason"], str)
            or not data["reason"].strip()
        ):
            raise ValueError("Approval hold requires an unreserved active controller")
        state["packet"] = wp.transition(
            state["packet"],
            "NEEDS_DECISION",
            "architect",
            state["architect"],
            "Current bootstrap approval is unavailable or changed",
            [data["reason"]],
            timestamp=timestamp,
        )
        state.update(status="NEEDS_DECISION", reason="CURRENT_APPROVAL_REQUIRED")
    elif event["kind"] == "DIAGNOSIS":
        exact(data, {"actor", "diagnosis", "verified_anchor"})
        diagnosis = data["diagnosis"]
        shape("diagnosis", diagnosis)
        if state["pending"] or state["status"] not in {
            "NEEDS_ARCHITECT",
            "ARCHITECTURE_HOLD",
            "BLOCKED",
        }:
            raise ValueError("Architect diagnosis requires a resolved controller hold")
        if (
            data["actor"] != state["architect"]
            or diagnosis["architecture_fingerprint"] != state["anchor"]
        ):
            raise ValueError(
                "Architect identity or architecture binding differs from INIT"
            )
        classification = diagnosis["classification"]
        if (
            state["diagnoses"] >= state["policy"]["max_architect_diagnoses"]
            and classification != "ARCHITECTURE_CHANGE"
        ):
            raise ValueError("Architect diagnosis budget exhausted")
        recovered = diagnosis.get("resolved_providers", [])
        if recovered and classification != "RESUME_WORK":
            raise ValueError(
                "Provider recovery is only allowed in an explicit blocker resumption"
            )
        if (
            classification != "REPAIR_CONTRACT"
            and diagnosis["revised_contract"] is not None
        ):
            raise ValueError(
                "Only a contract-repair diagnosis may provide a replacement contract"
            )
        if classification == "ARCHITECTURE_CHANGE":
            state["packet"] = wp.transition(
                state["packet"],
                "NEEDS_DECISION",
                "architect",
                data["actor"],
                diagnosis["reason"],
                diagnosis["evidence"],
                timestamp=timestamp,
            )
            state.update(
                status="NEEDS_DECISION", reason="EXPLICIT_USER_APPROVAL_REQUIRED"
            )
        elif classification == "BLOCKED":
            # A deferral cannot downgrade an architecture/scope/repetition hold.
            state["reason"] = "ARCHITECT_BLOCKED"
        elif classification == "RESUME_WORK":
            if (
                state["status"] != "BLOCKED"
                or data["verified_anchor"] != state["anchor"]
            ):
                raise ValueError(
                    "Only ordinary resolved blockers may resume under unchanged ACTIVE approval"
                )
            if state["resumptions"] >= state["policy"]["max_blocker_resumptions"]:
                raise ValueError("Blocker resumption budget exhausted")
            unavailable = {
                a["provider_id"]
                for a in state["attempts"]
                if a["routing_outcome"] == "PROVIDER_UNAVAILABLE"
            }
            if set(recovered) - unavailable:
                raise ValueError(
                    "Recovered providers must have recorded unavailable attempts"
                )
            for attempt in state["attempts"]:
                if (
                    attempt["provider_id"] in recovered
                    and attempt["routing_outcome"] == "PROVIDER_UNAVAILABLE"
                ):
                    attempt["routing_outcome"] = "PROVIDER_RECOVERED"
            if (
                state["attempts"]
                and state["attempts"][-1]["routing_outcome"] == "BLOCKED"
            ):
                # Preserve the raw result; this event explicitly records the blocker resolution.
                state["attempts"][-1]["routing_outcome"] = "FAIL"
            packet = state["packet"]
            if packet["state"] == "BLOCKED":
                for target in ("ARCHITECTED", "READY"):
                    packet = wp.transition(
                        packet,
                        target,
                        "architect",
                        data["actor"],
                        diagnosis["reason"],
                        diagnosis["evidence"],
                        current_graph(state, packet),
                        timestamp,
                    )
            state.update(
                packet=packet,
                status="READY",
                reason="BLOCKER_RESOLVED",
                resumptions=state["resumptions"] + 1,
            )
        else:
            if data["verified_anchor"] != state["anchor"]:
                raise ValueError(
                    "Contract repair requires unchanged current ACTIVE approval"
                )
            if (
                state["repairs"] >= state["policy"]["max_contract_repairs"]
                or len(state["attempts"]) >= state["total_cap"]
            ):
                raise ValueError("Contract repair/task attempt budget exhausted")
            revised = diagnosis["revised_contract"]
            profile = state["packet"]["domain_profile"]
            errors = wp.validate_contract(revised, profile, domain_rules=False)
            if errors:
                raise ValueError("\n".join(errors))
            # A stored repair predating the profile's domain rules replays marked (ADR-041); a new
            # repair that fails them is refused.
            shortfall = wp.domain_errors(revised, profile)
            if shortfall and not stored:
                raise ValueError("\n".join(shortfall))
            old = wp.current(state["packet"])["contract"]
            if any(old[field] != revised[field] for field in PROTECTED):
                raise ValueError(
                    "Contract repair changes a protected scope/interface/architecture field"
                )
            if old.get("review") != revised.get("review"):
                # Risk is protected above for the same reason: a repair exists to fix wording,
                # never to lower the acceptance gates the original risk classification requires.
                raise ValueError(
                    "Contract repair cannot change the assigned acceptance gates"
                )
            if revised["retry_budget"] != old["retry_budget"]:
                raise ValueError("Contract repair cannot change or reset retry limits")
            packet = wp.revise(
                state["packet"],
                revised,
                data["actor"],
                diagnosis["reason"],
                timestamp,
                domain_rules=not stored,
            )
            for target in ("ARCHITECTED", "READY"):
                graph = current_graph(state, packet)
                packet = wp.transition(
                    packet,
                    target,
                    "architect",
                    data["actor"],
                    diagnosis["reason"],
                    diagnosis["evidence"],
                    graph,
                    timestamp,
                )
            state.update(
                packet=packet,
                status="READY",
                reason="CONTRACT_REPAIRED",
                repairs=state["repairs"] + 1,
            )
            if shortfall:
                state.setdefault("domain_shortfall", []).append(
                    {"revision": wp.current(packet)["version"], "errors": shortfall}
                )
        if classification != "ARCHITECTURE_CHANGE":
            state["diagnoses"] += 1
        state["latest_diagnosis"] = {
            "event_sequence": event["sequence"],
            "classification": classification,
            "reason": diagnosis["reason"],
            "evidence": diagnosis["evidence"],
        }
    elif event["kind"] == "REVIEW":
        exact(data, {"decision"})
        apply_review(state, data["decision"], timestamp, stored)
    else:
        raise ValueError("Unknown ledger event kind")
    return state


def rejection_fingerprint(failures):
    normalized = sorted(
        (
            {
                "kind": f["kind"],
                "failed_ref": normalize(f["failed_ref"]),
                "what_failed": normalize(f["what_failed"]),
            }
            for f in failures
        ),
        key=lambda item: (item["kind"], item["failed_ref"], item["what_failed"]),
    )
    return router.digest({"review_failures": normalized})


def apply_review(
    state: dict[str, Any], decision: dict[str, Any], timestamp, stored=False
):
    """Record an independent acceptance decision; the gates themselves live in the acceptance ledger.

    A new decision must carry its binding. A REVIEW event already stored in a ledger written
    before the binding was required replays under the legacy shape, because hash-chained
    history cannot be amended; the boundary is the presence of the binding fields, and only
    replay of stored events may cross it.
    """
    legacy = (
        stored and "binding" not in decision and "result_dispatch_id" not in decision
    )
    shape("review_decision_legacy" if legacy else "review_decision", decision)
    if state["pending"] or state["status"] != "REVIEW_PENDING":
        raise ValueError(
            "A review decision requires an unreserved controller awaiting review"
        )
    verdict, actor = decision["verdict"], decision["reviewer"]["actor"]
    if (verdict == "REJECT_BOUNDED") != bool(decision["contract_failures"]):
        raise ValueError("Exactly a bounded rejection names contract failures")
    if not legacy:
        # A decision is evidence about one task revision and one worker result. Recording another
        # ledger's decision here would let a mix-up of ledger paths accept work nobody reviewed.
        expected = binding(state["packet"])
        if any(
            decision["binding"][key] != expected[key]
            for key in ("task_id", "revision", "contract_hash")
        ):
            raise ValueError(
                "Acceptance decision is bound to a different task, revision or contract than this ledger"
            )
        reviewed = state["attempts"][-1]["result"] if state["attempts"] else None
        if (
            reviewed is None
            or reviewed["dispatch_id"] != decision["result_dispatch_id"]
        ):
            raise ValueError(
                "Acceptance decision reviewed a different worker result than the one awaiting review"
            )
    contract = wp.current(state["packet"])["contract"]
    known = {entry["id"] for entry in contract["acceptance_criteria"]} | {
        check["id"] for check in contract["validation"]
    }
    scope_refs = (
        set(contract["scope"]["allowed"])
        | set(contract["scope"]["prohibited"])
        | set(contract["architecture_boundaries"])
    )
    for failure in decision["contract_failures"]:
        refs = scope_refs if failure["kind"] == "scope" else known
        if failure["failed_ref"] not in refs:
            raise ValueError(
                "A contract failure must name an existing criterion, validation or scope rule"
            )
    if verdict == "APPROVE":
        state["packet"] = wp.transition(
            state["packet"],
            "ACCEPTED",
            "reviewer",
            actor,
            decision["summary"],
            decision["evidence"],
            current_graph(state),
            timestamp,
        )
        state.update(status="ACCEPTED", reason="INDEPENDENT_ACCEPTANCE_RECORDED")
    elif verdict == "REJECT_BOUNDED":
        fingerprint = rejection_fingerprint(decision["contract_failures"])
        repeated = any(
            r["fingerprint"] == fingerprint for r in state["review_rejections"]
        )
        state["review_rejections"].append(
            {
                "review_id": decision["review_id"],
                "fingerprint": fingerprint,
                "summary": decision["summary"],
                "evidence": decision["evidence"],
                "contract_failures": copy.deepcopy(decision["contract_failures"]),
            }
        )
        if state["attempts"] and state["attempts"][-1]["routing_outcome"] == "PASS":
            # Preserve the raw result; the rejection overturns the objective PASS, so the
            # router may route the bounded corrective attempt within the same frozen budget.
            state["attempts"][-1].update(
                routing_outcome="FAIL", fingerprint=fingerprint
            )
        if repeated:
            state["packet"] = wp.transition(
                state["packet"],
                "ESCALATED",
                "reviewer",
                actor,
                decision["summary"],
                decision["evidence"],
                timestamp=timestamp,
            )
            state.update(status="NEEDS_ARCHITECT", reason="REPEATED_REVIEW_REJECTION")
        else:
            state["packet"] = wp.transition(
                state["packet"],
                "IN_PROGRESS",
                "reviewer",
                actor,
                decision["summary"],
                decision["evidence"],
                current_graph(state),
                timestamp,
            )
            state.update(status="IN_PROGRESS", reason="REVIEW_REJECTED")
    elif verdict == "NEEDS_EVIDENCE":
        state["reason"] = "REVIEW_NEEDS_EVIDENCE"
    elif verdict == "NEEDS_ESCALATION":
        state["packet"] = wp.transition(
            state["packet"],
            "ESCALATED",
            "reviewer",
            actor,
            decision["summary"],
            decision["evidence"],
            timestamp=timestamp,
        )
        state.update(status="NEEDS_ARCHITECT", reason="REVIEW_ESCALATED")
    else:
        state["packet"] = wp.transition(
            state["packet"],
            "ARCHITECTURE_CONFLICT",
            "reviewer",
            actor,
            decision["summary"],
            decision["evidence"],
            timestamp=timestamp,
        )
        state.update(status="ARCHITECTURE_HOLD", reason="ARCHITECT_DIAGNOSIS_REQUIRED")


VERSION = "destination-feedback-1"
LIMITS = {
    "max_attempts_by_tier": {"0": 3, "1": 3, "2": 2, "3": 2, "4": 1},
    "repeated_failure_per_tier": 2,
    "repeated_failure_total": 3,
    "max_contract_repairs": 1,
    "max_blocker_resumptions": 3,
    "max_architect_diagnoses": 5,
    "attempt_timeout_seconds": 600,
    "max_context_chars": 40000,
    "max_history_entries": 5,
}
REVIEW_FLOORS = {
    "low": {"deterministic"},
    "medium": {"deterministic", "model_review"},
    "high": {"deterministic", "model_review", "cross_family_review"},
    "critical": {
        "deterministic",
        "model_review",
        "cross_family_review",
        "architect_review",
        "user_decision",
    },
}


def check_policy(policy: dict[str, Any]):
    shape("policy", policy)
    for key, limit in LIMITS.items():
        if isinstance(limit, dict):
            if any(policy[key][tier] > count for tier, count in limit.items()):
                raise ValueError("Policy exceeds approved tier caps")
        elif policy[key] > limit:
            raise ValueError("Policy exceeds approved " + key)


def accounting(state: dict[str, Any]):
    entries = state["attempts"] + state.get("review_attempts", [])
    return budget.totals(
        {"entries": {a["id"]: a["accounting"] for a in entries if "accounting" in a}}
    )


def actor_identity(value: str) -> str:
    """Conservative comparison of coordinator-declared names, never authentication."""
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("Actor identity must be nonblank and have no outer whitespace")
    return " ".join(value.split()).casefold()


def plan(
    state: dict[str, Any],
    config: dict[str, Any],
    options: dict[str, Any],
    role="worker",
) -> dict[str, Any]:
    if state.get("controller_version") != VERSION:
        return source_plan(state, config, options)
    if role not in {"worker", "reviewer"}:
        raise ValueError("Unknown controller role")
    attempts = state["attempts"] if role == "worker" else state["review_attempts"]
    expected_status = ACTIVE if role == "worker" else {"REVIEW_PENDING"}
    if (
        state["pending"]
        or state.get("review_pending")
        or state["status"] not in expected_status
    ):
        raise ValueError("Controller hold or pending dispatch")
    if config["policy"] != state["router_policy"]:
        raise ValueError("Routing policy is frozen for this task")
    exact(
        options,
        {
            "task_class",
            "input_tokens",
            "output_tokens",
            "unavailable_providers",
            "unavailable_resources",
            "context_envelope",
        }
        | ({"reviewer_actor"} if role == "reviewer" else set()),
    )
    if role == "reviewer" and (
        not isinstance(options["reviewer_actor"], str)
        or not options["reviewer_actor"].strip()
        or actor_identity(options["reviewer_actor"])
        == actor_identity(state["destination"]["implementer"])
    ):
        raise ValueError("Named independent reviewer required before reservation")
    envelope = options["context_envelope"]
    exact(envelope, {"brief", "rules", "overhead_tokens"})
    if any(not isinstance(envelope[k], str) for k in ("brief", "rules")):
        raise ValueError("Rendered brief and rules required")
    overhead = envelope["overhead_tokens"]
    if type(overhead) is not int or not 0 <= overhead <= 10**9:
        raise ValueError("Invalid context overhead")
    result: dict[str, Any] = {
        "status": "NEEDS_ARCHITECT",
        "reason": "TOTAL_ATTEMPT_LIMIT",
        "routing": None,
        "context": None,
    }
    cap = state["total_cap"] if role == "worker" else state["review_cap"]
    if len(attempts) >= cap:
        return result
    graph_check(state["packet"], current_graph(state))
    try:
        context = worker_context(state)
    except ValueError:
        result["reason"] = "CONTEXT_LIMIT_REQUIRES_DECOMPOSITION"
        return result
    rendered = wp.canonical(context) + envelope["brief"] + envelope["rules"]
    if len(rendered) > state["policy"]["max_context_chars"]:
        result["reason"] = "CONTEXT_LIMIT_REQUIRES_DECOMPOSITION"
        return result
    result["context"] = context
    history_items = [
        {
            "sequence": n,
            "resource_id": a["resource_id"],
            "provider_id": a["provider_id"],
            "tier": a["tier"],
            "outcome": "FAIL"
            if a["revision"] != binding(state["packet"])["revision"]
            and a["routing_outcome"] in {"BLOCKED", "ARCHITECTURE_CONFLICT"}
            else a["routing_outcome"],
            "api_cost_usd": None
            if a["accounting"]["unknown"]
            else a["accounting"]["settled"],
            "elapsed_seconds": a["elapsed_seconds"],
            "decision_id": a["id"],
            "config_hash": a["config_hash"],
            "evidence": a["result"]["evidence"],
        }
        for n, a in enumerate(attempts, 1)
    ]
    request: dict[str, Any] = {
        "schema_version": "1.0",
        "binding": {**binding(state["packet"]), "role": role},
        **{
            k: copy.deepcopy(v)
            for k, v in options.items()
            if k not in {"context_envelope", "reviewer_actor"}
        },
        "attempts": history_items,
        "observations": [],
    }
    router.check_shape("request", request)
    # One byte per token is a conservative bound for rendered UTF-8 context;
    # output and harness overhead are reserved separately. No tokenizer guesses.
    request["input_tokens"] = max(
        request["input_tokens"], len(rendered.encode("utf-8")) + overhead
    )
    counts = {str(t): sum(a["tier"] == t for a in attempts) for t in range(5)}
    exhausted = {
        r["id"]
        for r in config["resources"]
        if counts[str(r["tier"])] >= state["caps"][str(r["tier"])]
    }
    if accounting(state)["unknown"]:
        exhausted |= {r["id"] for r in config["resources"] if router.metered(r)}
    contract = wp.current(state["packet"])["contract"]
    gates = REVIEW_FLOORS[contract["risk"]] | set(
        contract.get("review", {}).get("required_gates", [])
    )
    if role == "reviewer" and "cross_family_review" in gates:
        worker_family = state["attempts"][-1]["model_family"]
        exhausted |= {
            r["id"]
            for r in config["resources"]
            if r.get("model_family", r["provider_id"]) == worker_family
        }
    if attempts:
        last = attempts[-1]
        exhausted |= {r["id"] for r in config["resources"] if r["tier"] < last["tier"]}
    request["unavailable_resources"] = sorted(
        set(request["unavailable_resources"]) | exhausted
    )
    routed = router.record(state["packet"], config, request)
    result["routing"] = routed
    if routed["decision"]["status"] == "ROUTED":
        result.update(status="DISPATCH", reason="BOUNDED_DISPATCH")
    else:
        result["reason"] = routed["decision"]["reason_codes"][0]
        if result["reason"] == "NO_ELIGIBLE_RESOURCE" and not exhausted:
            result["status"] = "BLOCKED"
    return result


def apply(
    state: dict[str, Any] | None, event: dict[str, Any], stored=False
) -> dict[str, Any]:
    """Historical source semantics and stricter versioned destination events."""
    state = copy.deepcopy(state)
    event = copy.deepcopy(event)
    if state is None:
        if "destination" not in event["data"]:
            if not stored:
                raise ValueError("New INIT requires destination bindings")
            return source_apply(None, event, stored=True)
        destination = event["data"].pop("destination")
        exact(destination, {"version", "project", "implementer", "budgets"})
        if destination["version"] != VERSION or not destination["implementer"].strip():
            raise ValueError("Invalid destination identity")
        actor_identity(destination["implementer"])
        router.check_shape("identifier", destination["project"])
        exact(destination["budgets"], {"task", "role", "project"})
        for amount in destination["budgets"].values():
            budget.money(amount)
        check_policy(event["data"]["policy"])
        # Validate immutable routing floors even with no resource available.
        packet = event["data"]["packet"]
        config = event["data"]["router_config"]
        request: dict[str, Any] = {
            "schema_version": "1.0",
            "binding": binding(packet),
            "task_class": "policy-check",
            "input_tokens": 0,
            "output_tokens": 1,
            "unavailable_providers": [],
            "unavailable_resources": [],
            "attempts": [],
            "observations": [],
        }
        router.route(packet, config, request)
        state = source_apply(None, event, stored=stored)
        contract = wp.current(packet)["contract"]
        state.update(
            controller_version=VERSION,
            destination=destination,
            total_cap=min(2, state["total_cap"]),
            review_cap=min(2, config["policy"]["max_review_attempts"]),
            review_attempts=[],
            review_pending=None,
        )
        state["caps"] = {
            str(t): min(
                state["total_cap"],
                contract["retry_budget"]
                .get("max_attempts_by_tier", {})
                .get(str(t), 20),
                state["policy"]["max_attempts_by_tier"][str(t)],
            )
            for t in range(5)
        }
        return state
    if state.get("controller_version") != VERSION:
        if not stored:
            raise ValueError(
                "Imported source history is incompatible with new destination scheduling"
            )
        return source_apply(state, event, stored=True)
    kind, data = event["kind"], event["data"]
    # BEGIN M5 explicit acceptance integration
    if (
        kind == "REVIEW"
        and data.get("acceptance_version") == "destination-acceptance-1"
    ):
        from scripts.acceptance import apply_feedback

        return apply_feedback(state, event)
    # END M5 explicit acceptance integration
    if kind in {"DISPATCH", "HALT", "REVIEW_DISPATCH"}:
        role = "reviewer" if kind == "REVIEW_DISPATCH" else "worker"
        exact(data, {"config", "options", "plan"})
        expected = plan(state, data["config"], data["options"], role)
        if wp.canonical(expected) != wp.canonical(data["plan"]):
            raise ValueError("Recorded dispatch plan does not reproduce")
        if kind == "REVIEW_DISPATCH":
            if expected["status"] != "DISPATCH":
                raise ValueError("Reviewer dispatch violates a limit")
            decision = expected["routing"]["decision"]
            attempt: dict[str, Any] = {
                "id": decision["decision_id"],
                **decision["selected"],
                "config_hash": decision["config_hash"],
                "issued_at": event["timestamp"],
                "deadline": (
                    instant(event["timestamp"])
                    + timedelta(seconds=state["policy"]["attempt_timeout_seconds"])
                ).isoformat(),
                "result": None,
                "routing_outcome": None,
                "revision": binding(state["packet"])["revision"],
            }
            state["review_attempts"].append(attempt)
            state["review_pending"] = attempt["id"]
        else:
            state = source_apply(state, event, stored=stored)
            if kind == "HALT":
                return state
            attempt = state["attempts"][-1]
        resource = next(
            r for r in data["config"]["resources"] if r["id"] == attempt["resource_id"]
        )
        attempt["rates"] = copy.deepcopy(resource)
        attempt["model_family"] = resource.get("model_family", resource["provider_id"])
        attempt["actor"] = (
            data["options"]["reviewer_actor"]
            if role == "reviewer"
            else state["destination"]["implementer"]
        )
        request = expected["routing"]["inputs"]["request"]
        attempt["token_ceiling"] = {
            k: request[k] for k in ("input_tokens", "output_tokens")
        }
        attempt["ceiling"] = budget.ceiling(
            resource, request["input_tokens"], request["output_tokens"]
        )
        attempt["api_metered"] = router.metered(resource)
        if budget.money(accounting(state)["committed"]) + budget.money(
            attempt["ceiling"]
        ) > budget.money(state["destination"]["budgets"]["task"]):
            raise ValueError("Task budget cap exceeded")
        attempt["accounting"] = {
            "settled": 0,
            "liability": attempt["ceiling"],
            "unknown": False,
        }
        return state
    if kind in {"RESULT", "RESULT_COST_UNKNOWN", "ABANDON"}:
        usage = data.pop("usage", None)
        shape("result", data)
        attempt = state["attempts"][-1]
        raw = copy.deepcopy(data)
        measured = budget.measurement(attempt, usage) if usage is not None else None
        unknown = attempt["api_metered"] and measured is None
        claim = 0 if raw["api_cost_usd"] is None else raw["api_cost_usd"]
        budget.money(claim)
        data["api_cost_usd"] = (
            None if unknown else measured if measured is not None else 0
        )
        if kind == "ABANDON" and usage is not None:
            raise ValueError(
                "Abandonment cannot carry measured usage; reconcile afterward"
            )
        event["kind"] = (
            "ABANDON"
            if kind == "ABANDON"
            else "RESULT_COST_UNKNOWN"
            if unknown
            else "RESULT"
        )
        state = source_apply(state, event, stored=stored)
        attempt = state["attempts"][-1]
        attempt.update(
            raw_result=raw,
            usage=usage,
            accounting={
                "settled": 0 if unknown else data["api_cost_usd"],
                "liability": max(attempt["ceiling"], claim) if unknown else 0,
                "unknown": unknown,
            },
        )
        if (
            measured is not None
            and usage is not None
            and budget.exceeds(attempt, usage, measured)
        ):
            state.update(
                status="NEEDS_DECISION", reason="MEASURED_USAGE_EXCEEDS_RESERVATION"
            )
        return state
    if kind == "COST_RECONCILED":
        exact(data, {"dispatch_id", "usage"})
        reconciled_attempt = next(
            (
                a
                for a in state["attempts"] + state["review_attempts"]
                if a["id"] == data["dispatch_id"]
            ),
            None,
        )
        if (
            reconciled_attempt is None
            or not reconciled_attempt["accounting"]["unknown"]
        ):
            raise ValueError("Reconciliation requires an unknown liability")
        attempt = reconciled_attempt
        settled = budget.measurement(attempt, data["usage"])
        attempt.update(
            usage=copy.deepcopy(data["usage"]),
            accounting={"settled": settled, "liability": 0, "unknown": False},
        )
        if budget.exceeds(attempt, data["usage"], settled):
            state.update(
                status="NEEDS_DECISION", reason="MEASURED_USAGE_EXCEEDS_RESERVATION"
            )
        return state
    if kind == "REVIEW" and "dispatch_id" in data:
        exact(data, {"dispatch_id", "decision", "usage"})
        if data["dispatch_id"] != state["review_pending"]:
            raise ValueError("Reviewer result differs from pending dispatch")
        attempt = state["review_attempts"][-1]
        decision = data["decision"]
        shape("review_decision", decision)
        reviewer = decision["reviewer"]
        contract = wp.current(state["packet"])["contract"]
        if (
            reviewer["actor"] == state["destination"]["implementer"]
            or reviewer["tier"] < contract["routing"]["reviewer_tier"]
        ):
            raise ValueError("Independent reviewer identity/tier floor required")
        if (
            reviewer["tier"] != attempt["tier"]
            or reviewer["model_family"] != attempt["model_family"]
            or reviewer["actor"] != attempt["actor"]
        ):
            raise ValueError("Reviewer declaration differs from saved reservation")
        gates = REVIEW_FLOORS[contract["risk"]] | set(
            contract.get("review", {}).get("required_gates", [])
        )
        if (
            "cross_family_review" in gates
            and reviewer["model_family"] == state["attempts"][-1]["model_family"]
        ):
            raise ValueError("Cross-family reviewer required")
        if instant(event["timestamp"]) > instant(attempt["deadline"]):
            raise ValueError("Reviewer attempt deadline expired; abandon explicitly")
        if decision["verdict"] == "APPROVE":
            raise ValueError("M5 independent acceptance is required; M3 cannot accept")
        state = source_apply(
            state,
            {**event, "kind": "REVIEW", "data": {"decision": decision}},
            stored=False,
        )
        attempt = state["review_attempts"][-1]
        measured = (
            budget.measurement(attempt, data["usage"])
            if data["usage"] is not None
            else None
        )
        unknown = attempt["api_metered"] and measured is None
        attempt.update(
            result={"evidence": decision["evidence"]},
            routing_outcome="FAIL",
            elapsed_seconds=(
                instant(event["timestamp"]) - instant(attempt["issued_at"])
            ).total_seconds(),
            usage=data["usage"],
            accounting={
                "settled": 0 if unknown else measured or 0,
                "liability": attempt["ceiling"] if unknown else 0,
                "unknown": unknown,
            },
        )
        state["review_pending"] = None
        if measured is not None and budget.exceeds(attempt, data["usage"], measured):
            state.update(
                status="NEEDS_DECISION", reason="MEASURED_USAGE_EXCEEDS_RESERVATION"
            )
        return state
    if kind == "REVIEW":
        raise ValueError("Reviewer decision requires a lifetime reservation")
    if kind == "REVIEW_ABANDONED":
        exact(data, {"dispatch_id", "reason"})
        if (
            data["dispatch_id"] != state["review_pending"]
            or not isinstance(data["reason"], str)
            or not data["reason"].strip()
        ):
            raise ValueError("Reviewer abandonment requires the pending dispatch")
        attempt = state["review_attempts"][-1]
        attempt.update(
            result={"evidence": ["attempt-abandoned: " + data["reason"]]},
            routing_outcome="FAIL",
            elapsed_seconds=(
                instant(event["timestamp"]) - instant(attempt["issued_at"])
            ).total_seconds(),
            accounting={
                "settled": 0,
                "liability": attempt["ceiling"] if attempt["api_metered"] else 0,
                "unknown": attempt["api_metered"],
            },
        )
        if attempt["elapsed_seconds"] < 0:
            raise ValueError("Reviewer abandonment predates dispatch")
        state["review_pending"] = None
        return state
    if kind == "DIAGNOSIS":
        if (
            state["review_pending"]
            or state["diagnoses"] >= state["policy"]["max_architect_diagnoses"]
        ):
            raise ValueError("Diagnosis budget exhausted or review pending")
        if data["diagnosis"]["classification"] == "REPAIR_CONTRACT":
            revised = data["diagnosis"]["revised_contract"]
            old = wp.current(state["packet"])["contract"]
            if any(
                revised[k] != old[k]
                for k in ("routing", "escalation_path", "complexity")
            ):
                raise ValueError("Contract repair cannot change routing or complexity")
    return source_apply(state, event, stored=stored)


def reducer(expected=None):
    return lambda state, event: apply(
        state, event, stored=expected is None or event["sequence"] <= expected.sequence
    )


def replay(journal, stream) -> tuple[dict[str, Any], int, str | None]:
    state, head = journal.replay(stream, reducer())
    return state, head.sequence, head.hash


def initialize(
    journal,
    stream,
    packet: dict[str, Any],
    graph,
    policy: dict[str, Any],
    config: dict[str, Any],
    architect,
    *,
    project,
    implementer,
    caps=None,
    timestamp=None,
):
    if stream != "task:" + packet["task_id"]:
        raise ValueError("Task must use its canonical identity stream")
    for existing in journal.verify():
        events, _ = journal.read(existing)
        prior_packet = events[0]["data"].get("packet")
        if prior_packet is not None and prior_packet["task_id"] == packet["task_id"]:
            raise ValueError(
                "Task identity already exists; lifetime history cannot reset"
            )
    anchor = active_anchor(journal.root)
    foundation = wp.read_json(journal.root / "config/workflow-bootstrap.json")["policy"]
    caps = caps or {
        "task": foundation["task_api_budget_usd"],
        "role": foundation["role_api_budget_usd"],
        "project": foundation["project_api_budget_usd"],
    }
    if any(
        budget.money(caps[k]) > budget.money(foundation[k + "_api_budget_usd"])
        for k in caps
    ):
        raise ValueError("Budget exceeds ACTIVE foundation")
    if not foundation["resources_enabled"] and any(
        r["enabled"] for r in config["resources"]
    ):
        raise ValueError("ACTIVE foundation disables resources")
    destination = {
        "version": VERSION,
        "project": project,
        "implementer": implementer,
        "budgets": caps,
    }
    data = {
        "packet": packet,
        "graph": graph,
        "policy": policy,
        "router_config": config,
        "anchor": anchor,
        "architect": architect,
        "destination": destination,
    }
    journal.create(
        stream,
        family="feedback",
        binding=binding(packet),
        data=data,
        timestamp=timestamp,
        reducer=reducer(Head()),
    )
    return replay(journal, stream)[0]


def accounts(state: dict[str, Any], role):
    project = state["destination"]["project"]
    return ("role-budget:" + project + ":" + role, "project-budget:" + project)


def initialize_accounts(journal, project, caps, *, timestamp=None):
    """Explicit once-only provisioning; refuses existing accounts, never resets."""
    anchor = active_anchor(journal.root)
    foundation = wp.read_json(journal.root / "config/workflow-bootstrap.json")["policy"]
    for role in ("worker", "reviewer", None):
        key = "project" if role is None else "role"
        if budget.money(caps[key]) > budget.money(foundation[key + "_api_budget_usd"]):
            raise ValueError("Account cap exceeds ACTIVE foundation")
        stream = (
            "project-budget:" + project
            if role is None
            else "role-budget:" + project + ":" + role
        )
        account_binding = {"project": project, **({"role": role} if role else {})}
        journal.create(
            stream,
            family="project",
            binding=account_binding,
            data={
                "budget_version": "destination-budget-1",
                "binding": account_binding,
                "cap": caps[key],
                "anchor": anchor,
            },
            timestamp=timestamp,
            reducer=budget.apply,
        )


def append(journal, stream, kind, data, *, expected, timestamp=None, evidence=()):
    if kind not in {"HALT", "DIAGNOSIS", "APPROVAL_HOLD"}:
        raise ValueError(
            "Accounting events require atomic task/role/project controllers"
        )
    journal.append(
        stream,
        kind,
        data,
        expected=expected,
        timestamp=timestamp,
        evidence=evidence,
        reducer=reducer(expected),
    )
    return replay(journal, stream)[0]


def reserve(
    journal,
    stream,
    config: dict[str, Any],
    options: dict[str, Any],
    *,
    role="worker",
    timestamp=None,
    expected=None,
):
    timestamp = timestamp or wp.now()
    state, sequence, last = replay(journal, stream)
    head = Head(sequence, last)
    if expected is not None and head != expected:
        raise ValueError("Stale task head")
    if state.get("controller_version") != VERSION:
        raise ValueError("Imported source history cannot be relabeled for scheduling")
    active_anchor(journal.root, state["anchor"])
    foundation = wp.read_json(journal.root / "config/workflow-bootstrap.json")["policy"]
    if not foundation["resources_enabled"] and any(
        r["enabled"] for r in config["resources"]
    ):
        raise ValueError("ACTIVE foundation disables resources")
    proposed = plan(state, config, options, role)
    if proposed["status"] != "DISPATCH":
        if role == "worker":
            append(
                journal,
                stream,
                "HALT",
                {"config": config, "options": options, "plan": proposed},
                expected=head,
                timestamp=timestamp,
            )
        return {**proposed, "dispatch_id": None, "deadline": None}
    kind = "DISPATCH" if role == "worker" else "REVIEW_DISPATCH"
    data = {"config": config, "options": options, "plan": proposed}
    simulated = apply(
        state,
        {
            "kind": kind,
            "data": data,
            "timestamp": timestamp or wp.now(),
            "sequence": head.sequence + 1,
        },
    )
    attempt = (
        simulated["attempts"] if role == "worker" else simulated["review_attempts"]
    )[-1]
    reservation = {
        "dispatch_id": attempt["id"],
        "task_id": state["packet"]["task_id"],
        "role": role,
        "ceiling": attempt["ceiling"],
        "metered": attempt["api_metered"],
    }
    requests = [
        Append(
            stream=stream,
            kind=kind,
            data=data,
            expected=head,
            timestamp=timestamp,
            reducer=reducer(head),
        )
    ]
    for account in accounts(state, role):
        account_state, account_head = journal.replay(account, budget.apply)
        if (
            account_state["anchor"] != state["anchor"]
            or account_state["binding"]["project"] != state["destination"]["project"]
        ):
            raise ValueError("Budget account binding differs")
        key = "role" if "role" in account_state["binding"] else "project"
        if budget.money(account_state["cap"]) != budget.money(
            state["destination"]["budgets"][key]
        ):
            raise ValueError("Task and account caps differ")
        requests.append(
            Append(
                stream=account,
                kind="RESERVE",
                data=reservation,
                expected=account_head,
                timestamp=timestamp,
                reducer=budget.apply,
            )
        )
    journal.append_many(tuple(requests))
    return {**proposed, "dispatch_id": attempt["id"], "deadline": attempt["deadline"]}


def finish(journal, stream, kind, data, *, timestamp=None, evidence=()):
    timestamp = timestamp or wp.now()
    state, sequence, last = replay(journal, stream)
    head = Head(sequence, last)
    usage = data.get("usage")
    if usage is not None and usage["evidence_sha256"] not in {
        e.sha256 for e in evidence
    }:
        raise ValueError("Measured usage requires coordinator Journal evidence")
    event = {
        "kind": kind,
        "data": data,
        "timestamp": timestamp or wp.now(),
        "sequence": sequence + 1,
    }
    simulated = apply(state, event)
    dispatch_id = data["dispatch_id"]
    attempt = next(
        a
        for a in simulated["attempts"] + simulated["review_attempts"]
        if a["id"] == dispatch_id
    )
    role = (
        "worker"
        if any(a["id"] == dispatch_id for a in simulated["attempts"])
        else "reviewer"
    )
    outcome = {"dispatch_id": dispatch_id, **attempt["accounting"]}
    requests = [
        Append(
            stream=stream,
            kind=kind,
            data=data,
            expected=head,
            timestamp=timestamp,
            evidence=evidence,
            reducer=reducer(head),
        )
    ]
    for account in accounts(state, role):
        _, account_head = journal.replay(account, budget.apply)
        requests.append(
            Append(
                stream=account,
                kind="COST_RECONCILED" if kind == "COST_RECONCILED" else "RESULT",
                data=outcome,
                expected=account_head,
                timestamp=timestamp,
                evidence=evidence,
                reducer=budget.apply,
            )
        )
    journal.append_many(tuple(requests))
    return replay(journal, stream)[0]


def complete(journal, stream, result: dict[str, Any], **kwargs):
    return finish(journal, stream, "RESULT", result, **kwargs)


def abandon(journal, stream, result: dict[str, Any], **kwargs):
    return finish(journal, stream, "ABANDON", result, **kwargs)


def review(journal, stream, result: dict[str, Any], **kwargs):
    return finish(journal, stream, "REVIEW", result, **kwargs)


def reconcile(journal, stream, dispatch_id, usage, **kwargs):
    return finish(
        journal,
        stream,
        "COST_RECONCILED",
        {"dispatch_id": dispatch_id, "usage": usage},
        **kwargs,
    )


def diagnose(journal, stream, diagnosis: dict[str, Any], actor, *, timestamp=None):
    state, sequence, last = replay(journal, stream)
    anchor = (
        active_anchor(journal.root, state["anchor"])
        if diagnosis["classification"] in {"RESUME_WORK", "REPAIR_CONTRACT"}
        else None
    )
    return append(
        journal,
        stream,
        "DIAGNOSIS",
        {"actor": actor, "diagnosis": diagnosis, "verified_anchor": anchor},
        expected=Head(sequence, last),
        timestamp=timestamp,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("stream")
    for key in ("packet", "policy", "config"):
        init.add_argument("--" + key, required=True, type=Path)
    init.add_argument("--graph", required=True, nargs="+", type=Path)
    for key in ("architect", "project", "implementer"):
        init.add_argument("--" + key, required=True)
    account = commands.add_parser("accounts")
    account.add_argument("--project", required=True)
    nxt = commands.add_parser("next")
    nxt.add_argument("stream")
    nxt.add_argument("--role", choices=("worker", "reviewer"), default="worker")
    nxt.add_argument("--config", required=True, type=Path)
    nxt.add_argument("--options", required=True, type=Path)
    for key in ("complete", "abandon", "review", "reconcile", "diagnose"):
        command = commands.add_parser(key)
        command.add_argument("stream")
        command.add_argument("input", type=Path)
        command.add_argument("--evidence", action="append", default=[])
        if key == "diagnose":
            command.add_argument("--actor", required=True)
    for key in ("status", "context", "render", "packet"):
        command = commands.add_parser(key)
        command.add_argument("stream")
    args = parser.parse_args(argv)
    try:
        journal = Journal(args.root)
        if args.command == "accounts":
            foundation = wp.read_json(journal.root / "config/workflow-bootstrap.json")[
                "policy"
            ]
            initialize_accounts(
                journal,
                args.project,
                {
                    "role": foundation["role_api_budget_usd"],
                    "project": foundation["project_api_budget_usd"],
                },
            )
            print("Budget accounts created; no execution authority")
            return 0
        if args.command == "init":
            state = initialize(
                journal,
                args.stream,
                wp.read_json(args.packet),
                [wp.read_json(p) for p in args.graph],
                wp.read_json(args.policy),
                wp.read_json(args.config),
                args.architect,
                project=args.project,
                implementer=args.implementer,
            )
        elif args.command == "next":
            decision = reserve(
                journal,
                args.stream,
                wp.read_json(args.config),
                wp.read_json(args.options),
                role=args.role,
            )
            print(json.dumps(decision, indent=2, ensure_ascii=False))
            return 0 if decision["status"] == "DISPATCH" else 2
        elif args.command in {"complete", "abandon", "review", "reconcile", "diagnose"}:
            data = wp.read_json(args.input)
            evidence = tuple(journal.evidence(p) for p in args.evidence)
            if args.command == "diagnose":
                state = diagnose(journal, args.stream, data, args.actor)
            elif args.command == "reconcile":
                state = reconcile(
                    journal,
                    args.stream,
                    data["dispatch_id"],
                    data["usage"],
                    evidence=evidence,
                )
            else:
                state = {"complete": complete, "abandon": abandon, "review": review}[
                    args.command
                ](journal, args.stream, data, evidence=evidence)
        else:
            state = replay(journal, args.stream)[0]
        if args.command == "render":
            print(render(state), end="")
        else:
            value = (
                worker_context(state)
                if args.command == "context"
                else state["packet"]
                if args.command == "packet"
                else summary(state)
            )
            print(json.dumps(value, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, router.DecimalException) as exc:
        print(f"Feedback control refused: {exc}", file=sys.stderr)
        return 1


def summary(state: dict[str, Any]):
    return {
        **(
            {
                "accounting": accounting(state),
                "review_attempts": state["review_attempts"],
                "review_pending": state["review_pending"],
            }
            if state.get("controller_version") == VERSION
            else {}
        ),
        "binding": binding(state["packet"]),
        "status": state["status"],
        "reason": state["reason"],
        "pending_dispatch": state["pending"],
        "total_attempts": len(state["attempts"]),
        "total_cap": state["total_cap"],
        "tier_counts": tier_counts(state),
        "tier_caps": state["caps"],
        "contract_repairs": state["repairs"],
        "blocker_resumptions": state["resumptions"],
        "failure_groups": failure_groups(state),
        "architect_diagnoses": state["diagnoses"],
        "remaining_architect_diagnoses": state["policy"]["max_architect_diagnoses"]
        - state["diagnoses"],
        "latest_diagnosis": state["latest_diagnosis"],
        "review_rejections": state["review_rejections"],
        "domain_shortfall": state.get("domain_shortfall"),
        "attempts": state["attempts"],
        "issue_proposals": state["discoveries"],
    }


def render(state: dict[str, Any]):
    def reference(text):
        return {
            "preview": text[:200],
            "sha256": router.digest(text),
            "truncated": len(text) > 200,
        }

    def evidence(items):
        return {
            "count": len(items),
            "first_references": [reference(item) for item in items[:2]],
        }

    view = {
        key: value
        for key, value in summary(state).items()
        if key
        not in {
            "attempts",
            "failure_groups",
            "issue_proposals",
            "latest_diagnosis",
            "review_rejections",
        }
    }
    view["review_rejections"] = [
        {
            "review_id": r["review_id"],
            "fingerprint": r["fingerprint"],
            "summary": reference(r["summary"]),
        }
        for r in state["review_rejections"]
    ]
    view["attempts"] = [
        {
            "attempt_id": a["id"],
            "tier": a["tier"],
            "resource_id": a["resource_id"],
            "routing_outcome": a["routing_outcome"],
            "fingerprint": a["fingerprint"],
            "record": f"{int(a['result_event_sequence']):08d}.json"
            if a.get("result_event_sequence")
            else "pending",
            "summary": reference(a["result"]["summary"]) if a["result"] else None,
            "evidence": evidence(a["result"]["evidence"]) if a["result"] else None,
        }
        for a in state["attempts"]
    ]
    view["failure_groups"] = [
        {"fingerprint": g["fingerprint"], "count": g["count"], "tiers": g["tiers"]}
        for g in failure_groups(state)
    ]
    view["issue_proposal_count"] = len(state["discoveries"])
    if state["latest_diagnosis"]:
        diagnosis = state["latest_diagnosis"]
        view["latest_diagnosis"] = {
            "classification": diagnosis["classification"],
            "record": f"{int(diagnosis['event_sequence']):08d}.json",
            "reason": reference(diagnosis["reason"]),
            "evidence": evidence(diagnosis["evidence"]),
        }
    body = json.dumps(view, indent=2, ensure_ascii=False, allow_nan=False)
    if len(body) > 60000:
        raise ValueError(
            "Feedback comment exceeds the export limit; use immutable event references"
        )
    fence = "`" * max(
        3, 1 + max((len(run) for run in re.findall(r"`+", body)), default=0)
    )
    return f"# Feedback ledger - {state['packet']['task_id']}\n\nRecorded local evidence; external outcomes require their own verification.\n\n{fence}json\n{body}\n{fence}\n"


if __name__ == "__main__":
    raise SystemExit(cli_exit.run(main))
