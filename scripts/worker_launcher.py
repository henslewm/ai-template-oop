"""Launch an exact prepared M4 reservation once through the Docker boundary."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import io
import math
from pathlib import Path
import sqlite3
import sys
import tarfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import execution_harness as h
from scripts import workflow_runtime as runtime
from scripts import workflow_state as ws


def startup_attempted(journal, token):
    path = journal.directory / "startup.sqlite3"
    h.read_file(path)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT attempted FROM startup_authority WHERE token=?", (token,)
        ).fetchone()
    h.require(row is not None, "Missing consumed-start history")
    return row[0]


def archive_files(raw, *, prefix):
    """Bounded comparison of an unstarted volume against its exact saved export."""
    h.require(len(raw) <= h.MAX_EXPORT * 2, "Container inputs exceed bound")
    files, seen, total = {}, set(), 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            for member in tar:
                h.require(len(seen) < 600, "Too many container input members")
                name = member.name.rstrip("/")
                if name == "." and member.isdir() and not prefix:
                    continue
                h.checked_path(name)
                h.require(name.casefold() not in seen, "Duplicate container input path")
                seen.add(name.casefold())
                if member.isdir():
                    continue
                h.require(
                    member.isfile() and member.size <= h.MAX_FILE,
                    "Linked or oversized container input",
                )
                total += member.size
                h.require(
                    total <= h.MAX_EXPORT + h.MAX_FILE * 2,
                    "Container input size exceeded",
                )
                h.require(
                    not prefix or name.startswith(prefix), "Escaped container input"
                )
                stream = tar.extractfile(member)
                if stream is None:
                    raise ValueError("Missing container input data")
                files[name[len(prefix) :]] = stream.read(h.MAX_FILE + 1)
    except (tarfile.TarError, EOFError) as exc:
        raise ValueError("Invalid container input archive") from exc
    return files


def prepared_run(
    journal, dispatch_id, *, config=None, timeout=None, launching=False, consumed=False
):
    """Read-only, repeated preflight; no ownership database is initialized."""
    h.require(
        timeout is None
        or type(timeout) in {int, float}
        and math.isfinite(timeout)
        and 0 < timeout <= 300,
        "Timeout must be positive and at most 300",
    )
    record, head = h.load(journal, dispatch_id)
    h.require(
        record["phase"] == ("LAUNCHING" if launching else "PREPARED"),
        "Run already launched or preparation incomplete",
    )
    saved = record["intent"]["harness_config"]
    h.config_valid(saved)
    h.require(
        saved["enabled"] and (config is None or config == saved),
        "Harness configuration changed or disabled",
    )
    state, attempt, scope, event = h.current(journal, record, scheduling=True)
    run = h.prepared_files(journal, record)
    runtime.check_state(scope, journal.directory)
    manifest = record["prepared"]["runtime"]
    h.require(
        h.parse(h.read_file(run / "runtime.json"), h.MAX_FILE) == manifest,
        "Runtime binding changed",
    )
    binding, harness = h.selected(saved, attempt["rates"])
    h.require(
        manifest["image"] == binding["image"]
        and manifest["argv"] == h.invocation(binding, harness)
        and manifest["dispatch_stream"] == h.stream_name(dispatch_id)
        and manifest["scope_sha256"] == scope.hash,
        "Image/invocation/scope binding changed",
    )
    raw_brief = h.read_file(run / "brief.json", h.MAX_FILE)
    h.require(
        raw_brief.decode() == event["data"]["options"]["context_envelope"]["brief"]
        and h.digest(raw_brief) == record["binding"]["brief_sha256"]
        and h.digest(h.read_file(run / "worker-rules.md"))
        == record["binding"]["rules_sha256"],
        "Changed brief/rules",
    )
    request = event["data"]["plan"]["routing"]["inputs"]["request"]
    window = binding["served_context_window"] or attempt["rates"]["context_window"]
    h.require(
        request["input_tokens"] + request["output_tokens"] <= window,
        "Context capacity changed",
    )
    h.require(
        not (run / "report.json").exists(),
        "Existing report; ingest or reconcile instead",
    )
    runtime.assert_boundary(
        manifest["container"], manifest["volume"], manifest["image"]
    )
    info = runtime.inspect(manifest["container"])
    h.require(
        info["State"]["Status"] == "created", "Worker container has already started"
    )
    h.require(
        info["Config"]["Entrypoint"] == manifest["argv"][:1]
        and info["Config"]["Cmd"] == manifest["argv"][1:],
        "Docker invocation changed",
    )
    actual = runtime.docker("cp", manifest["container"] + ":/session", "-")
    h.require(
        archive_files(actual, prefix="session/")
        == archive_files(h.read_file(run / "input.tar"), prefix=""),
        "Container export changed before launch",
    )
    rows = h.owner_rows(journal, scope)
    h.require(len(rows) == 1, "Exact ownership claim required")
    row = rows[0]
    h.require(
        row["state"] == "claimed"
        and row["token"] == manifest["ownership_token"]
        and row["container"] == manifest["container"]
        and row["owner"] == attempt["actor"]
        and row["expires"] > time.time(),
        "Ownership is stale or bound to another run",
    )
    h.require(
        startup_attempted(journal, row["token"]) == int(consumed),
        "Startup authority consumed or inconsistent",
    )
    remaining = (
        h.f.instant(attempt["deadline"]) - h.f.instant(h.f.wp.now())
    ).total_seconds()
    h.require(remaining > 0, "Reservation deadline expired")
    return {
        "record": record,
        "head": asdict(head),
        "run": run,
        "timeout": min(timeout if timeout is not None else 300, remaining),
        "deadline": attempt["deadline"],
    }


def launch(journal, dispatch_id, *, config=None, timeout=None):
    checked = prepared_run(journal, dispatch_id, config=config, timeout=timeout)
    h.advance(journal, dispatch_id, "LAUNCHING", {"dispatch_id": dispatch_id})

    def revalidate(consumed):
        prepared_run(
            journal,
            dispatch_id,
            config=config,
            timeout=timeout,
            launching=True,
            consumed=consumed,
        )

    # Never roll LAUNCHING back. A failed start (even before Docker observes it)
    # is reconciled explicitly, and the existing consumed-start store is final.
    runtime.execute(
        checked["run"],
        journal.directory,
        checked["timeout"],
        preflight=revalidate,
        absolute_deadline=checked["deadline"],
    )
    record, _ = h.load(journal, dispatch_id)
    stopped = h.stopped_record(journal, record)
    return {
        "dispatch_id": dispatch_id,
        "status": "STOPPED",
        "archive": stopped["archive"],
        "independent_acceptance": False,
        "next_action": "ingest or explicitly abandon",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=h.ROOT)
    parser.add_argument("command", choices=["preflight", "launch"])
    parser.add_argument("dispatch_id")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        journal = ws.Journal(args.root)
        config = (
            h.parse(h.read_file(args.config, h.MAX_FILE), h.MAX_FILE)
            if args.config
            else None
        )
        if args.command == "preflight":
            prepared_run(journal, args.dispatch_id, config=config, timeout=args.timeout)
            print("Prepared; no worker started and no work accepted.")
        else:
            import json

            print(
                json.dumps(
                    launch(
                        journal, args.dispatch_id, config=config, timeout=args.timeout
                    ),
                    indent=2,
                )
            )
        return 0
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error):
        print(
            "Launcher refused; inspect preserved coordinator state. No retry authorized."
        )
        return 1


if __name__ == "__main__":
    from scripts import cli_exit

    raise SystemExit(cli_exit.run(main))
