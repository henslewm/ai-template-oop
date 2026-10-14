"""Pure M4 journal transitions. No scheduling, Docker, accounting or acceptance."""

from __future__ import annotations

import copy
from typing import Any

from scripts import feedback as feedback

VERSION = "destination-dispatch-1"


def apply(state: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
    kind, data = event["kind"], event["data"]
    if state is None:
        if kind != "INIT":
            raise ValueError("Dispatch starts with INIT")
        feedback.exact(
            data, {"version", "task_stream", "dispatch_id", "binding", "intent"}
        )
        if data["version"] != VERSION:
            raise ValueError("Unsupported dispatch version")
        return {
            **copy.deepcopy(data),
            "phase": "PREPARING",
            "prepared": None,
            "stopped": None,
            "receipt": None,
        }
    state = copy.deepcopy(state)
    if kind == "PREPARED" and state["phase"] == "PREPARING":
        feedback.exact(data, {"run", "files", "runtime"})
        state.update(phase="PREPARED", prepared=copy.deepcopy(data))
    elif kind == "LAUNCHING" and state["phase"] == "PREPARED":
        feedback.exact(data, {"dispatch_id"})
        if data["dispatch_id"] != state["dispatch_id"]:
            raise ValueError("Wrong launch dispatch")
        state["phase"] = "LAUNCHING"
    elif kind == "RECOVERY" and state["phase"] in {
        "PREPARING",
        "PREPARED",
        "LAUNCHING",
    }:
        feedback.exact(data, {"archive", "runtime", "exit_code", "finished_at"})
        feedback.instant(data["finished_at"])
        state.update(phase="STOPPED", stopped=copy.deepcopy(data))
    elif kind in {"RESULT", "ABANDON"} and state["phase"] != "CLOSED":
        feedback.exact(
            data, {"dispatch_id", "ingestion_sha256", "status", "bundle_sha256"}
        )
        if data["dispatch_id"] != state["dispatch_id"]:
            raise ValueError("Wrong result dispatch")
        if kind == "RESULT" and state["phase"] != "STOPPED":
            raise ValueError("Result requires preserved stopped output")
        state.update(phase="CLOSED", receipt=copy.deepcopy(data))
    else:
        raise ValueError("Dispatch transition refused; reconcile explicitly")
    return state
