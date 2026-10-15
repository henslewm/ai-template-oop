"""Pure lifecycle for the one approved maintenance preset; lifetime caps never reset."""

from __future__ import annotations

import copy

from scripts import workflow_budget as budget


def apply(state, event):
    kind, data = event["kind"], event["data"]
    if state is None:
        if kind != "INIT" or set(data) != {
            "version",
            "profile",
            "packet",
            "scope",
            "objective",
            "baseline",
        }:
            raise ValueError("Pilot must start with its bound preset")
        if data["version"] != "live-pilot-task-1":
            raise ValueError("Unknown pilot state version")
        return {
            **copy.deepcopy(data),
            "phase": "READY",
            "attempts": [],
            "reviews": [],
            "checks": None,
            "bundle": None,
            "blocker": None,
            "delivery": None,
        }
    state = copy.deepcopy(state)
    if kind == "ATTEMPT" and state["phase"] in {"READY", "REVIEW"}:
        role = "worker" if state["phase"] == "READY" else "reviewer"
        entries = state["attempts"] if role == "worker" else state["reviews"]
        if len(entries) >= 2 or data["role"] != role:
            raise ValueError("Lifetime attempt limit exhausted")
        expected_model = (
            "gpt-6-luna" if role == "worker" and not entries else "gpt-6.1-sol"
        )
        if data["model"] != expected_model:
            raise ValueError("Pilot model escalation path differs")
        if any(a["id"] == data["id"] for a in state["attempts"] + state["reviews"]):
            raise ValueError("Duplicate pilot attempt")
        entries.append(copy.deepcopy(data))
        state.update(
            phase="WORKER_RUNNING" if role == "worker" else "REVIEW_RUNNING",
            blocker=None,
        )
    elif kind == "WORKER_RESULT" and state["phase"] == "WORKER_RUNNING":
        state["attempts"][-1]["result"] = copy.deepcopy(data)
        if data["passed"]:
            state.update(phase="CHECKS", bundle=copy.deepcopy(data["bundle"]))
        else:
            state.update(
                phase="READY" if len(state["attempts"]) < 2 else "HELD",
                blocker=data["reason"],
            )
    elif kind == "CHECKS" and state["phase"] == "CHECKS":
        state["checks"] = copy.deepcopy(data)
        passed = bool(data["checks"]) and all(c["passed"] for c in data["checks"])
        if passed:
            state.update(phase="REVIEW", blocker=None)
        else:
            state["attempts"][-1]["result"]["passed"] = False
            state.update(
                phase="READY" if len(state["attempts"]) < 2 else "HELD",
                blocker="Independent checks failed; bounded repair required",
            )
    elif kind == "REVIEW" and state["phase"] == "REVIEW_RUNNING":
        state["reviews"][-1]["result"] = copy.deepcopy(data)
        report = data["report"]
        approved = report["verdict"] == "APPROVE"
        if approved and (
            report["bundle_sha256"] != data["bundle_sha256"]
            or not report["criteria"]
            or not all(c["met"] for c in report["criteria"])
        ):
            raise ValueError(
                "Independent approval does not bind all criteria and exact bundle"
            )
        if approved:
            state.update(phase="ACCEPTED", blocker=None)
        elif (
            report["verdict"] == "REJECT_BOUNDED"
            and len(state["attempts"]) < 2
            and len(state["reviews"]) < 2
        ):
            state["attempts"][-1]["result"]["passed"] = False
            state.update(phase="READY", blocker=report["summary"])
        else:
            state.update(phase="HELD", blocker=report["summary"])
    elif kind == "DELIVERY_PREPARED" and state["phase"] == "ACCEPTED":
        if state["delivery"] is not None and state["delivery"] != data:
            raise ValueError("Conflicting candidate delivery")
        state["delivery"] = copy.deepcopy(data)
    elif kind == "DELIVERY_HOLD" and state["phase"] == "ACCEPTED":
        state["blocker"] = data["reason"]
    elif kind == "DELIVERY" and state["phase"] in {"ACCEPTED", "DELIVERED"}:
        if state["delivery"] is not None and state["delivery"] != data:
            raise ValueError("Conflicting duplicate delivery")
        state.update(phase="DELIVERED", delivery=copy.deepcopy(data))
    elif kind == "RESUME_RECONCILED" and state["phase"] == "HELD":
        entries = state["attempts"] if data["role"] == "worker" else state["reviews"]
        if not entries or entries[-1]["id"] != data["dispatch_id"]:
            raise ValueError("Reconciliation must bind the current lifetime attempt")
        entries[-1].pop("result", None)
        state.update(
            phase="WORKER_RUNNING" if data["role"] == "worker" else "REVIEW_RUNNING",
            blocker=None,
        )
    elif kind == "HOLD" and state["phase"] != "DELIVERED":
        if state["phase"] in {"WORKER_RUNNING", "REVIEW_RUNNING"}:
            entries = (
                state["attempts"]
                if state["phase"] == "WORKER_RUNNING"
                else state["reviews"]
            )
            entries[-1]["result"] = {"passed": False, "reason": data["reason"]}
        state.update(phase="HELD", blocker=data["reason"])
    else:
        raise ValueError("Pilot transition refused; inspect existing evidence")
    return state


def paid_guard(account):
    totals = budget.totals(account)
    if totals["unknown"] or any(e["pending"] for e in account["entries"].values()):
        raise ValueError(
            "Unresolved paid request; inspect its saved response or reconcile provider usage. Never resend it"
        )
