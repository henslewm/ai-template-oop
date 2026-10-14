#!/usr/bin/env python3
"""Make replayable routing decisions locally; never call models or authorize work."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from decimal import Decimal, DecimalException, localcontext
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import cli_exit
from scripts import work_packet as wp

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads(
    (ROOT / "config/model-router.schema.json").read_text(encoding="utf-8")
)
wp.Draft202012Validator.check_schema(SCHEMA)
ALGORITHM = "economic-router-1"
DESTINATION_ALGORITHM = "destination-economic-router-1"
RISK = {"low": 0, "medium": 1, "high": 3, "critical": 4}
COMPLEXITY = {"low": 0, "medium": 2, "high": 3}
TERMINAL = {"PASS", "BLOCKED", "ARCHITECTURE_CONFLICT"}


def digest(value):
    return hashlib.sha256(wp.canonical(value).encode("utf-8")).hexdigest()


def check_shape(name, value):
    wp.canonical(value)  # Reject nonfinite numbers even through the Python API.
    validator = wp.Draft202012Validator(
        {"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    )
    errors = wp.schema_errors(validator, value)
    if errors:
        raise ValueError("\n".join(errors))


def source_validate_config(config: dict[str, Any]):
    """Pinned source bounds for historical replay only."""
    check_shape("config", config)
    providers = [p["id"] for p in config["providers"]]
    resources = [r["id"] for r in config["resources"]]
    if len(set(providers)) != len(providers) or len(set(resources)) != len(resources):
        raise ValueError("Duplicate provider or resource identifier")
    for resource in config["resources"]:
        if resource["provider_id"] not in providers:
            raise ValueError("Resource references an unknown provider")
    for field, keys in (
        ("risk_floor", ["low", "medium", "high", "critical"]),
        ("complexity_floor", ["low", "medium", "high"]),
        ("min_acceptance", ["low", "medium", "high", "critical"]),
    ):
        values = [config["policy"][field][key] for key in keys]
        if values != sorted(values):
            raise ValueError(f"{field} must not decrease as risk/complexity increases")


def validate_config(config: dict[str, Any]):
    """Validate native configuration without granting execution authority."""
    source_validate_config(config)
    check_shape("destination_config", config)
    for field, floors in (("risk_floor", RISK), ("complexity_floor", COMPLEXITY)):
        if any(config["policy"][field][key] < floor for key, floor in floors.items()):
            raise ValueError("Routing policy lowers an approved floor")


def validate_inputs(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
):
    wp.canonical(packet)
    wp.require_valid(packet)
    source_validate_config(config)
    check_shape("request", request)
    revision = wp.current(packet)
    binding = request["binding"]
    expected = {
        "task_id": packet["task_id"],
        "revision": revision["version"],
        "contract_hash": revision["hash"],
        "role": binding["role"],
    }
    if binding != expected:
        raise ValueError(
            "Request history is bound to a different task or contract revision"
        )
    contract = revision["contract"]
    tiers = allowed_tiers(contract, binding["role"])
    attempts = request["attempts"]
    last_tier = -1
    terminal = False
    unavailable = set()
    decision_ids = set()
    for number, attempt in enumerate(attempts, 1):
        if attempt["sequence"] != number:
            raise ValueError("Attempt sequence must be consecutive from 1")
        if attempt["decision_id"] in decision_ids:
            raise ValueError("Attempt history repeats a routing decision")
        decision_ids.add(attempt["decision_id"])
        if terminal:
            raise ValueError("Attempt history continues after a terminal outcome")
        if attempt["tier"] not in tiers or attempt["tier"] < last_tier:
            raise ValueError(
                "Attempt tier violates the contract or descends after escalation"
            )
        if (
            number > 1
            and attempts[number - 2]["outcome"] == "NEEDS_ESCALATION"
            and attempt["tier"] <= last_tier
        ):
            raise ValueError("Attempt did not honor explicit escalation")
        if attempt["provider_id"] in unavailable:
            raise ValueError(
                "Attempt reused a provider already recorded unavailable in this history"
            )
        if attempt["outcome"] == "PROVIDER_UNAVAILABLE":
            unavailable.add(attempt["provider_id"])
        terminal = attempt["outcome"] in TERMINAL
        last_tier = attempt["tier"]
    if len(attempts) > attempt_limit(contract, config, binding["role"]):
        raise ValueError("History exceeds the total role attempt budget")
    keys = set()
    for item in request["observations"]:
        key = (item["resource_id"], item["task_class"], item["reasoning_effort"])
        if key in keys:
            raise ValueError("Duplicate observation aggregate")
        keys.add(key)
        if item["accepted"] > item["samples"] or item["regressions"] > item["samples"]:
            raise ValueError("Observation counts exceed samples")


def allowed_tiers(contract, role):
    if role == "reviewer":
        return [int(contract["routing"]["reviewer_tier"])]
    return [int(contract["routing"]["min_tier"])] + [
        int(t) for t in contract["escalation_path"]
    ]


def attempt_limit(contract, config: dict[str, Any], role):
    return int(
        config["policy"]["max_review_attempts"]
        if role == "reviewer"
        else contract["retry_budget"]["max_attempts"]
    )


def normalized(config: dict[str, Any], request: dict[str, Any]):
    config, request = copy.deepcopy(config), copy.deepcopy(request)
    config["providers"].sort(key=lambda p: p["id"])
    config["resources"].sort(key=lambda r: r["id"])
    for key in ("unavailable_providers", "unavailable_resources"):
        request[key].sort()
    request["observations"].sort(
        key=lambda r: (r["resource_id"], r["task_class"], r["reasoning_effort"])
    )
    return config, request


def dec(value):
    return Decimal(str(value))


def metered(resource: dict[str, Any]):
    """A resource that declares a nonzero API price, so an attempt on it may have charged."""
    return (
        dec(resource["input_million_usd"]) > 0
        or dec(resource["output_million_usd"]) > 0
    )


def number(value):
    return float(round(value, 12))


def score(
    resource: dict[str, Any], effort, request: dict[str, Any], policy: dict[str, Any]
):
    prior = resource["efforts"][effort]
    estimates = {key: dec(value) for key, value in prior.items()}
    matched = next(
        (
            item
            for item in request["observations"]
            if item["resource_id"] == resource["id"]
            and item["task_class"] == request["task_class"]
            and item["reasoning_effort"] == effort
        ),
        None,
    )
    source = {"kind": "configured_prior", "samples": 0}
    if matched:
        weight, samples = dec(policy["prior_samples"]), dec(matched["samples"])
        for key, field in (
            ("latency_seconds", "mean_latency_seconds"),
            ("context_churn_tokens", "mean_context_churn_tokens"),
            ("review_minutes", "mean_review_minutes"),
        ):
            estimates[key] = (
                estimates[key] * weight + dec(matched[field]) * samples
            ) / (weight + samples)
        for key, field in (
            ("acceptance_probability", "accepted"),
            ("regression_probability", "regressions"),
        ):
            estimates[key] = (estimates[key] * weight + dec(matched[field])) / (
                weight + samples
            )
        source = {
            "kind": "prior_plus_observations",
            "samples": matched["samples"],
            "source": matched["source"],
        }
    api = (
        (dec(request["input_tokens"]) + estimates["context_churn_tokens"])
        * dec(resource["input_million_usd"])
        + dec(request["output_tokens"]) * dec(resource["output_million_usd"])
    ) / dec(1_000_000)
    costs = {
        "api_usd": api,
        "time_usd": estimates["latency_seconds"] * dec(policy["wall_second_usd"]),
        "review_usd": estimates["review_minutes"] * dec(policy["review_minute_usd"]),
        "regression_usd": estimates["regression_probability"]
        * dec(policy["regression_usd"]),
    }
    total = sum(costs.values())
    expected = total / estimates["acceptance_probability"]
    trace = {
        "estimates": {key: number(value) for key, value in estimates.items()},
        "estimate_source": source,
        "cost_components": {key: number(value) for key, value in costs.items()},
        "estimated_attempt_cost_usd": number(total),
        "expected_cost_per_accepted_result_usd": number(expected),
    }
    return expected, api, estimates, trace


def source_route(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    """Pure offline selection. Full ordered role history is a caller-supplied assertion."""
    validate_inputs(packet, config, request)
    config, request = normalized(config, request)
    with localcontext() as context:
        # Schema-bounded cost / smoothed probability can need 41 display digits.
        context.prec = 80
        return _route(packet, config, request)


def _route(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    contract = wp.current(packet)["contract"]
    policy, binding, attempts = (
        config["policy"],
        request["binding"],
        request["attempts"],
    )
    role = binding["role"]
    limit = attempt_limit(contract, config, role)
    effort = contract["routing"]["reasoning_effort"]
    risk_floor = int(policy["risk_floor"][contract["risk"]])
    complexity_floor = int(policy["complexity_floor"][contract["complexity"]])
    tiers = allowed_tiers(contract, role)
    floor = max(min(tiers), risk_floor, complexity_floor)
    # A null cost is unknown, not zero: only known costs are summed, and an unknown one bars metered resources.
    spent = sum(
        (dec(a["api_cost_usd"]) for a in attempts if a["api_cost_usd"] is not None),
        dec(0),
    )
    # Whether an abandoned attempt could have charged is settled when it is recorded, from the
    # prices saved with its dispatch (ADR-097); a later re-pricing of the same resource id cannot clear it.
    unknown = [a for a in attempts if a["api_cost_usd"] is None]
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "algorithm_version": ALGORITHM,
        "policy_version": policy["version"],
        "binding": binding,
        "packet_hash": digest(packet),
        "config_hash": digest(config),
        "request_hash": digest(request),
        "status": "STOP",
        "reason_codes": [],
        "selected": None,
        "attempt_number": len(attempts) + 1,
        "remaining_attempts": limit - len(attempts),
        "recorded_api_spend_usd": number(spent),
        "recorded_elapsed_seconds": sum(a["elapsed_seconds"] for a in attempts),
        "role_api_budget_usd": policy["role_api_budget_usd"],
        "allowed_tiers": tiers,
        "risk_floor": risk_floor,
        "complexity_floor": complexity_floor,
        "reasoning_effort": effort,
        "candidates": [],
        "execution_authorized": False,
    }
    result["input_hash"] = digest(
        {key: result[key] for key in ("packet_hash", "config_hash", "request_hash")}
    )
    if unknown:
        result["unknown_api_cost_attempts"] = [a["decision_id"] for a in unknown]

    def finish(reason, selected=None):
        result["reason_codes"] = [reason]
        if selected:
            result["status"], result["selected"] = "ROUTED", selected
        result["decision_id"] = digest(result)
        return result

    if attempts and attempts[-1]["outcome"] in TERMINAL:
        return finish(
            {
                "PASS": "PASS_REQUIRES_ACCEPTANCE_GATES",
                "BLOCKED": "TASK_BLOCKED",
                "ARCHITECTURE_CONFLICT": "ARCHITECTURE_CHANGE_GATE",
            }[attempts[-1]["outcome"]]
        )
    if packet["state"] not in (
        {"READY", "IN_PROGRESS"} if role == "worker" else {"REVIEW"}
    ):
        return finish("PACKET_NOT_READY_FOR_ROLE")
    if len(attempts) >= limit:
        return finish("ATTEMPT_BUDGET_EXHAUSTED")
    if spent >= dec(policy["role_api_budget_usd"]) and spent > 0:
        return finish("API_BUDGET_EXHAUSTED")
    last = attempts[-1] if attempts else None
    if last:
        floor = max(floor, int(last["tier"]))
        failures = sum(
            a["outcome"] == "FAIL" and a["tier"] == last["tier"] for a in attempts
        )
        if (
            last["outcome"] == "NEEDS_ESCALATION"
            or failures >= policy["failures_per_tier"]
        ):
            floor = max(floor, int(last["tier"]) + 1)
    result["effective_floor"] = floor
    if not any(t >= floor for t in tiers):
        return finish("AUTHORIZED_TIER_PATH_EXHAUSTED")
    unavailable = set(request["unavailable_providers"])
    unavailable.update(
        a["provider_id"] for a in attempts if a["outcome"] == "PROVIDER_UNAVAILABLE"
    )
    provider_map = {p["id"]: p for p in config["providers"]}
    choices = []
    for resource in config["resources"]:
        excluded = []
        if not resource["enabled"]:
            excluded.append("DISABLED")
        if resource["tier"] not in tiers:
            excluded.append("TIER_NOT_AUTHORIZED")
        if resource["tier"] < floor:
            excluded.append("BELOW_EFFECTIVE_FLOOR")
        if resource["provider_id"] in unavailable:
            excluded.append("PROVIDER_UNAVAILABLE")
        if resource["id"] in request["unavailable_resources"]:
            excluded.append("RESOURCE_UNAVAILABLE")
        row = {
            "resource_id": resource["id"],
            "tier": resource["tier"],
            "reason_codes": excluded,
        }
        if effort not in resource["efforts"]:
            excluded.append("UNSUPPORTED_EFFORT")
        else:
            expected, api, estimates, values = score(resource, effort, request, policy)
            row.update(values)
            if estimates["acceptance_probability"] < dec(
                policy["min_acceptance"][contract["risk"]]
            ):
                excluded.append("BELOW_RELIABILITY_FLOOR")
            if dec(request["input_tokens"]) + dec(request["output_tokens"]) + estimates[
                "context_churn_tokens"
            ] > dec(resource["context_window"]):
                excluded.append("CONTEXT_CAPACITY_EXCEEDED")
            if spent + api > dec(policy["role_api_budget_usd"]):
                excluded.append("ESTIMATED_API_BUDGET_EXCEEDED")
            if unknown and metered(resource):
                excluded.append("PRIOR_API_COST_UNKNOWN")
            if not excluded:
                # On an observed outage, exhaust eligible equivalent-tier alternatives first.
                fallback_priority = (
                    0
                    if not last
                    or last["outcome"] != "PROVIDER_UNAVAILABLE"
                    or resource["tier"] == last["tier"]
                    else 1
                )
                choices.append((fallback_priority, expected, resource["id"], resource))
        row["eligible"] = not excluded
        result["candidates"].append(row)
    if not choices:
        return finish("NO_ELIGIBLE_RESOURCE")
    resource = min(choices, key=lambda item: item[:3])[3]
    selected = {
        "resource_id": resource["id"],
        "provider_id": resource["provider_id"],
        "adapter": provider_map[resource["provider_id"]]["adapter"],
        "model": resource["model"],
        "tier": resource["tier"],
        "reasoning_effort": effort,
    }
    if not last:
        reason = "INITIAL_ECONOMIC_SELECTION"
    elif resource["tier"] > last["tier"]:
        reason = "ESCALATED_WITHIN_CONTRACT"
    elif last["outcome"] == "PROVIDER_UNAVAILABLE":
        reason = "EQUIVALENT_TIER_FALLBACK"
    else:
        reason = "BOUNDED_RETRY_SELECTION"
    return finish(reason, selected)


def record(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    return {
        "inputs": {
            "packet": copy.deepcopy(packet),
            "config": copy.deepcopy(config),
            "request": copy.deepcopy(request),
        },
        "decision": route(packet, config, request),
    }


def source_record(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    return {
        "inputs": {
            "packet": copy.deepcopy(packet),
            "config": copy.deepcopy(config),
            "request": copy.deepcopy(request),
        },
        "decision": source_route(packet, config, request),
    }


def verify(recorded: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(recorded, dict)
        or set(recorded) != {"inputs", "decision"}
        or not isinstance(recorded["inputs"], dict)
        or set(recorded["inputs"]) != {"packet", "config", "request"}
    ):
        raise ValueError("Invalid routing ledger record")
    expected = route(**recorded["inputs"])
    if wp.canonical(expected) != wp.canonical(recorded["decision"]):
        raise ValueError("Routing decision does not reproduce from its saved inputs")
    return expected


def route(
    packet: dict[str, Any], config: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    """Destination policy; selection is metadata only, never launch authority."""
    validate_config(config)
    validate_inputs(packet, config, request)
    policy = config["policy"]
    for field, floors in (("risk_floor", RISK), ("complexity_floor", COMPLEXITY)):
        if any(policy[field][key] < floor for key, floor in floors.items()):
            raise ValueError("Routing policy lowers an approved floor")
    if policy["max_review_attempts"] > 2 or policy["failures_per_tier"] > 2:
        raise ValueError("Routing policy exceeds approved review/failure bounds")
    contract = wp.current(packet)["contract"]
    cap = min(2, attempt_limit(contract, config, request["binding"]["role"]))
    if len(request["attempts"]) > cap:
        raise ValueError("History exceeds destination lifetime attempt cap")
    decision = source_route(packet, config, request)
    decision["algorithm_version"] = DESTINATION_ALGORITHM
    decision["remaining_attempts"] = cap - len(request["attempts"])
    if len(request["attempts"]) >= cap:
        decision.update(
            status="STOP", reason_codes=["ATTEMPT_BUDGET_EXHAUSTED"], selected=None
        )
    decision.pop("decision_id")
    decision["decision_id"] = digest(decision)
    return decision


def verify_source(recorded: dict[str, Any]) -> dict[str, Any]:
    """Pinned historical decisions only; never an authority for a new dispatch."""
    exact_inputs = {"packet", "config", "request"}
    if (
        set(recorded) != {"inputs", "decision"}
        or set(recorded["inputs"]) != exact_inputs
    ):
        raise ValueError("Invalid source routing record")
    expected = source_route(**recorded["inputs"])
    if wp.canonical(expected) != wp.canonical(recorded["decision"]):
        raise ValueError("Source routing decision does not reproduce")
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    config_parser = commands.add_parser("validate-config")
    config_parser.add_argument("config", type=Path)
    router = commands.add_parser("route")
    router.add_argument("packet", type=Path)
    router.add_argument("--config", required=True, type=Path)
    router.add_argument("--request", required=True, type=Path)
    router.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New immutable local task-ledger record",
    )
    checker = commands.add_parser("verify")
    checker.add_argument("record", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-config":
            validate_config(wp.read_json(args.config))
            print(
                "Routing configuration is valid; this does not check live availability or credentials."
            )
            return 0
        if args.command == "verify":
            decision = verify(wp.read_json(args.record))
        else:
            saved = record(
                wp.read_json(args.packet),
                wp.read_json(args.config),
                wp.read_json(args.request),
            )
            wp.write_new(
                args.output,
                json.dumps(saved, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            )
            decision = saved["decision"]
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        return 0 if args.command == "verify" or decision["status"] == "ROUTED" else 2
    except (OSError, ValueError, TypeError, DecimalException) as exc:
        print(f"Model routing failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli_exit.run(main))
