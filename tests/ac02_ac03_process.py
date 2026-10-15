"""Fresh-process fault driver for disposable AC-02/03 fixtures only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import acceptance_runtime as ar  # noqa: E402
from scripts import execution_harness as h  # noqa: E402
from scripts import worker_launcher as launcher  # noqa: E402
from scripts import workflow_runtime as runtime  # noqa: E402
from scripts import workflow_state as ws  # noqa: E402


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    root, state = Path(spec["root"]), Path(spec["state"])
    # These are the same explicit synthetic authorities as test_feedback's
    # fixture, restricted to its newly created repository and database.
    assert root.name == "repository" and root.parent == state.parent
    seams = pytest.MonkeyPatch()
    seams.setattr(ws, "control_directory", lambda _: state)
    seams.setattr(ws, "active_anchor", lambda *args: "a" * 64)
    seams.setattr(h.f, "active_anchor", lambda *args: "a" * 64)
    seams.setattr(runtime, "state_directory", lambda _: state)
    seams.setattr(h.f.wp, "now", lambda: spec["timestamp"])
    seams.setattr(runtime.wp, "now", lambda: spec["timestamp"])
    real_docker = runtime.docker
    trace = Path(spec["trace"])

    def docker(*args, **kwargs):
        if args[0] == "start" and "-a" not in args:
            # This callback occurs after the durable consumed-start commit.
            if spec["fault"] == "before_start_exit":
                os._exit(73)
            with trace.open("a", encoding="utf-8") as output:
                output.write("start\n")
                output.flush()
                os.fsync(output.fileno())
            if spec["fault"] == "start_refusal_log_failure":
                raise ValueError("Injected Docker refusal after consumed commit")
            result = real_docker(*args, **kwargs)
            if spec["fault"] == "after_start_exit":
                os._exit(74)
            return result
        if args[0] == "logs" and spec["fault"] == "start_refusal_log_failure":
            raise OSError("Injected logging failure after startup refusal")
        return real_docker(*args, **kwargs)

    seams.setattr(runtime, "docker", docker)
    Path(spec["ready"]).write_text("ready")
    deadline = time.monotonic() + 30
    while not Path(spec["gate"]).exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("Fresh process gate expired")
        time.sleep(0.01)
    journal = ws.Journal(root)
    try:
        if spec["action"] == "claim":
            scope = h.SessionScope.load(spec["scope"])
            print(h.Ownership(state).claim(scope, spec["container"]))
        elif spec["action"] == "execute":
            # Both executors complete the created-container observation before
            # either takes the shared ownership lock (stronger than launch CAS).
            original_inspect = runtime.inspect
            synchronized = False

            def inspect(container):
                nonlocal synchronized
                info = original_inspect(container)
                if not synchronized:
                    synchronized = True
                    Path(spec["observed"]).write_text("created")
                    until = time.monotonic() + 30
                    while not all(Path(p).exists() for p in spec["observations"]):
                        if time.monotonic() >= until:
                            raise RuntimeError("Created observation barrier expired")
                        time.sleep(0.01)
                return info

            seams.setattr(runtime, "inspect", inspect)

            def preflight(consumed):
                if spec["mode"] == "worker":
                    return launcher.prepared_run(
                        journal, spec["id"], launching=True, consumed=consumed
                    )
                return ar.preflight(
                    journal,
                    spec["stream"],
                    spec["id"],
                    launching=True,
                    consumed=consumed,
                )

            runtime.execute(
                Path(spec["run"]),
                state,
                60,
                preflight=preflight,
                absolute_deadline=spec["deadline"],
            )
        elif spec["mode"] == "worker":
            launcher.launch(journal, spec["id"])
        else:
            ar.launch_check(journal, spec["stream"], spec["id"])
    except (ValueError, OSError) as error:
        print(type(error).__name__ + ": " + str(error))
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
