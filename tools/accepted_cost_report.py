"""Compare total cost per accepted result for a matched task cohort."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys


SIDES = ("baseline", "pilot")
CATEGORIES = {"implementation", "review", "integration", "other"}
OUTCOMES = {"accepted", "failed", "abandoned", "other"}
FAILED_OUTCOMES = {"failed", "abandoned"}


def _exact(value, keys, name):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f"{name} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _cost(value, name):
    if value is None:
        return None
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be a non-negative number or null")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{name} must be a non-negative finite number or null")
    return amount


def _money(value):
    return None if value is None else format(value.normalize(), "f")


def _sum_costs(items):
    if any(value is None for value in items):
        return None
    return sum(items, Decimal(0))


def _side_summary(tasks, side):
    accepted = sum(task[side]["accepted"] for task in tasks)
    activities = [
        activity
        for task in tasks
        for activity in task[side]["activities"]
    ]
    costs = [activity["cost"] for activity in activities]
    total = _sum_costs(costs)
    failed = [
        activity["cost"]
        for activity in activities
        if activity["outcome"] in FAILED_OUTCOMES
    ]
    integration = [
        activity["cost"]
        for activity in activities
        if activity["category"] == "integration"
    ]
    return {
        "accepted_results": accepted,
        "activity_count": len(activities),
        "failed_attempt_count": sum(
            activity["outcome"] in FAILED_OUTCOMES for activity in activities
        ),
        "unknown_cost_items": sum(cost is None for cost in costs),
        "total_cost_usd": _money(total),
        "failed_attempt_cost_usd": _money(_sum_costs(failed)),
        "integration_cost_usd": _money(_sum_costs(integration)),
        "cost_per_accepted_result_usd": _money(
            total / accepted if total is not None and accepted else None
        ),
    }


def summarize(record):
    """Validate a measurement manifest and return exact, unknown-aware totals."""
    _exact(record, {"version", "cohort", "provenance", "tasks"}, "record")
    if type(record["version"]) is not int or record["version"] != 1:
        raise ValueError("Unsupported measurement version")
    if not isinstance(record["cohort"], str) or not record["cohort"].strip():
        raise ValueError("cohort must identify the fixed task set")
    provenance = _exact(
        record["provenance"], {"kind", "evidence_ref"}, "provenance"
    )
    if not isinstance(provenance["kind"], str) or provenance["kind"] not in {
        "real",
        "fixture",
        "mixed",
    }:
        raise ValueError("provenance.kind must be real, fixture, or mixed")
    if (
        not isinstance(provenance["evidence_ref"], str)
        or not provenance["evidence_ref"].strip()
        or len(provenance["evidence_ref"]) > 256
        or any(not char.isprintable() for char in provenance["evidence_ref"])
    ):
        raise ValueError("provenance.evidence_ref must be a short printable reference")
    if not isinstance(record["tasks"], list) or not record["tasks"]:
        raise ValueError("tasks must be a non-empty, predeclared matched cohort")

    tasks = []
    identifiers = set()
    for index, raw_task in enumerate(record["tasks"]):
        task = _exact(raw_task, {"id", *SIDES}, f"tasks[{index}]")
        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"tasks[{index}].id must be non-empty")
        if task_id in identifiers:
            raise ValueError(f"duplicate task id: {task_id}")
        identifiers.add(task_id)
        parsed = {"id": task_id}
        for side in SIDES:
            data = _exact(task[side], {"accepted", "activities"}, f"{task_id}.{side}")
            if type(data["accepted"]) is not bool:
                raise ValueError(f"{task_id}.{side}.accepted must be boolean")
            if not isinstance(data["activities"], list) or not data["activities"]:
                raise ValueError(f"{task_id}.{side}.activities must not be empty")
            parsed_activities = []
            has_integration = False
            for activity_index, raw_activity in enumerate(data["activities"]):
                activity = _exact(
                    raw_activity,
                    {"category", "outcome", "cost_usd"},
                    f"{task_id}.{side}.activities[{activity_index}]",
                )
                if (
                    not isinstance(activity["category"], str)
                    or activity["category"] not in CATEGORIES
                ):
                    raise ValueError(
                        f"{task_id}.{side} has an unknown activity category"
                    )
                if (
                    not isinstance(activity["outcome"], str)
                    or activity["outcome"] not in OUTCOMES
                ):
                    raise ValueError(
                        f"{task_id}.{side} has an unknown activity outcome"
                    )
                has_integration |= activity["category"] == "integration"
                parsed_activities.append(
                    {
                        "category": activity["category"],
                        "outcome": activity["outcome"],
                        "cost": _cost(
                            activity["cost_usd"],
                            f"{task_id}.{side}.activities[{activity_index}].cost_usd",
                        ),
                    }
                )
            if not has_integration:
                raise ValueError(
                    f"{task_id}.{side} must explicitly record integration cost "
                    "(use zero or null when appropriate)"
                )
            parsed[side] = {
                "accepted": data["accepted"],
                "activities": parsed_activities,
            }
        tasks.append(parsed)

    baseline = _side_summary(tasks, "baseline")
    pilot = _side_summary(tasks, "pilot")
    baseline_cost = baseline["cost_per_accepted_result_usd"]
    pilot_cost = pilot["cost_per_accepted_result_usd"]
    savings = savings_percent = None
    if baseline_cost is not None and pilot_cost is not None:
        baseline_amount = Decimal(baseline_cost)
        pilot_amount = Decimal(pilot_cost)
        savings = _money(baseline_amount - pilot_amount)
        if baseline_amount > 0:
            savings_percent = format(
                (baseline_amount - pilot_amount) * 100 / baseline_amount, "f"
            )

    return {
        "version": 1,
        "cohort": record["cohort"],
        "task_ids": [task["id"] for task in tasks],
        "provenance": {
            "kind": provenance["kind"],
            "evidence_ref": provenance["evidence_ref"],
            "status": "declared_not_verified",
            "non_fixture_declared": provenance["kind"] == "real",
        },
        "baseline": baseline,
        "pilot": pilot,
        "comparison": {
            "savings_per_accepted_result_usd": savings,
            "savings_percent": savings_percent,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="matched-cohort JSON manifest")
    args = parser.parse_args(argv)
    try:
        raw = args.manifest.read_bytes()
        record = json.loads(raw)
        report = summarize(record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    report["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
