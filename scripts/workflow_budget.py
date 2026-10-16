"""Pure budget semantics for atomic Journal batches; no provider access."""

from __future__ import annotations

import copy
from decimal import Decimal, ROUND_CEILING
from typing import Any

from scripts import model_router as router

UNIT = Decimal("0.000001")


def money(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Invalid budget amount")
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > 1000000:
        raise ValueError("Invalid budget amount")
    return amount


def upward(value: Decimal) -> float:
    return float(value.quantize(UNIT, rounding=ROUND_CEILING))


def ceiling(resource: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    for count in (input_tokens, output_tokens):
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 0 <= count <= 10**9
        ):
            raise ValueError("Invalid token ceiling")
    return upward(
        (
            money(resource["input_million_usd"]) * input_tokens
            + money(resource["output_million_usd"]) * output_tokens
        )
        / 1000000
    )


def measurement(attempt: dict[str, Any], usage: dict[str, Any]) -> float:
    required = {
        "dispatch_id",
        "rates_hash",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "evidence_sha256",
    }
    if not isinstance(usage, dict) or set(usage) != required:
        raise ValueError("Invalid measured usage")
    if usage["dispatch_id"] != attempt["id"] or usage["rates_hash"] != router.digest(
        attempt["rates"]
    ):
        raise ValueError("Usage dispatch or saved rates differ")
    cache = usage["cached_input_tokens"]
    if (
        isinstance(cache, bool)
        or not isinstance(cache, int)
        or not 0 <= cache <= usage["input_tokens"]
    ):
        raise ValueError("Invalid cached usage")
    router.check_shape("sha256", usage["evidence_sha256"])
    # Do not infer a cache discount. Charge the complete input at the saved rate.
    return ceiling(attempt["rates"], usage["input_tokens"], usage["output_tokens"])


def totals(state: dict[str, Any]) -> dict[str, Any]:
    settled = sum((money(e["settled"]) for e in state["entries"].values()), Decimal(0))
    liability = sum(
        (money(e["liability"]) for e in state["entries"].values()), Decimal(0)
    )
    return {
        "settled": upward(settled),
        "liability": upward(liability),
        "committed": upward(settled + liability),
        "unknown": sorted(k for k, v in state["entries"].items() if v["unknown"]),
    }


def exceeds(attempt: dict[str, Any], usage: dict[str, Any], settled: float) -> bool:
    return money(settled) > money(attempt["ceiling"]) or any(
        usage[key] > attempt["token_ceiling"][key] for key in attempt["token_ceiling"]
    )


def apply(state: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
    """Versioned role/project accounts. Outcomes never erase unknown liability."""
    data = event["data"]
    if state is None:
        if event["kind"] != "INIT" or set(data) != {
            "budget_version",
            "binding",
            "cap",
            "anchor",
        }:
            raise ValueError("Budget INIT binding required")
        if data["budget_version"] != "destination-budget-1":
            raise ValueError("Incompatible budget semantics")
        money(data["cap"])
        router.check_shape("sha256", data["anchor"])
        return {**copy.deepcopy(data), "entries": {}}
    state = copy.deepcopy(state)
    if event["kind"] == "RESERVE":
        if set(data) != {"dispatch_id", "task_id", "role", "ceiling", "metered"}:
            raise ValueError("Invalid budget reservation")
        router.check_shape("sha256", data["dispatch_id"])
        router.check_shape("identifier", data["task_id"])
        if (
            data["role"] not in {"worker", "reviewer"}
            or type(data["metered"]) is not bool
        ):
            raise ValueError("Invalid reservation role or metering")
        if data["dispatch_id"] in state["entries"]:
            raise ValueError("Duplicate dispatch budget reservation")
        if state["binding"].get("role", data["role"]) != data["role"]:
            raise ValueError("Budget role binding differs")
        if any(
            e["pending"]
            and e["task_id"] == data["task_id"]
            and e["role"] == data["role"]
            for e in state["entries"].values()
        ):
            raise ValueError("One pending dispatch per task/role")
        current = totals(state)
        if data["metered"] and current["unknown"]:
            raise ValueError("Unknown spend remains held")
        if money(current["committed"]) + money(data["ceiling"]) > money(state["cap"]):
            raise ValueError("Budget cap exceeded")
        state["entries"][data["dispatch_id"]] = {
            **data,
            "pending": True,
            "settled": 0,
            "liability": data["ceiling"],
            "unknown": False,
        }
    elif event["kind"] in {"RESULT", "COST_RECONCILED"}:
        if set(data) != {"dispatch_id", "settled", "liability", "unknown"}:
            raise ValueError("Invalid budget outcome")
        entry = state["entries"].get(data["dispatch_id"])
        if entry is None or (event["kind"] == "RESULT" and not entry["pending"]):
            raise ValueError("Budget outcome has no pending reservation")
        if event["kind"] == "COST_RECONCILED" and (
            entry["pending"] or not entry["unknown"]
        ):
            raise ValueError("Reconciliation requires unknown resolved liability")
        money(data["settled"])
        money(data["liability"])
        if type(data["unknown"]) is not bool:
            raise ValueError("Invalid unknown-cost flag")
        if data["unknown"]:
            if (
                not entry["metered"]
                or money(data["settled"]) != 0
                or money(data["liability"]) < money(entry["liability"])
            ):
                raise ValueError("Unknown liability cannot be settled or reduced")
        elif money(data["liability"]) != 0:
            raise ValueError("Measured outcome must release the liability")
        if not entry["metered"] and money(data["settled"]) != 0:
            raise ValueError("Explicit unmetered run costs zero")
        entry.update(data, pending=False)
    else:
        raise ValueError("Unknown budget event")
    return state
