"""Trusted pilot bootstrap/inspection. The worker builds the separate user shell."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import execution_harness as h
from scripts import pilot_authority as authority
from scripts import workflow_closeout as closeout
from scripts import workflow_state as ws


def activate(root, commit, number, report_path):
    journal = ws.Journal(root)
    if journal.db.exists():
        raise ValueError(
            "Activation requires a fresh independent pilot journal; existing state cannot be reset"
        )
    if (journal.directory / authority.PROFILE).exists():
        raise ValueError(
            "Pilot approval already exists; never replace authority or budgets"
        )
    pull = closeout.gh(f"repos/{closeout.REPO}/pulls/{number}")
    if (
        not pull["merged"]
        or pull["head"]["sha"] != commit
        or pull["base"]["ref"] != "main"
        or not pull["merge_commit_sha"]
    ):
        raise ValueError(
            "Activate only the exact reviewed bootstrap head after its PR is merged"
        )
    report = ws._json(h.read_file(report_path))
    if (
        report.get("head") != commit
        or report.get("verdict") != "APPROVE"
        or report.get("actor") in {None, "", "Bootstrap implementer"}
        or report.get("blocking_findings") != []
    ):
        raise ValueError(
            "Independent review must approve the exact bootstrap head with no blocking findings"
        )
    # Both the reviewed objects and executing checkout must match before receipt creation.
    ws.approval.git(root, "fetch", "origin")
    integrated = pull["merge_commit_sha"]
    if closeout.tree(root, commit) != closeout.tree(root, integrated):
        raise ValueError(
            "Integrated bootstrap tree differs from the reviewed candidate"
        )
    implementation = authority.inventory(root, commit)
    if implementation != authority.inventory(root):
        raise ValueError("Executing implementation differs from the reviewed bootstrap")
    body = {
        "version": "live-pilot-1",
        "approved_by": "Winston",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "foundation": ws.active_anchor(root),
        "identity": journal.identity,
        "implementation_commit": integrated,
        "implementation": implementation,
        "review": {
            "head": commit,
            "actor": report["actor"],
            "verdict": "APPROVE",
            "report_sha256": h.digest(ws.approval.canonical(report)),
            "pr": number,
        },
        "image": authority.IMAGE,
        "read_paths": authority.READ_PATHS,
        "write_paths": authority.WRITE_PATHS,
        "provider": authority.PROVIDER,
        "limits": authority.LIMITS,
        "project": authority.PROJECT,
        "objective": authority.OBJECTIVE,
        "delivery": {
            "repository": closeout.REPO,
            "base": "main",
            "publish": True,
            "merge_after_gates": True,
            "retain_branches": True,
        },
    }
    profile = {**body, "fingerprint": h.digest(ws.approval.canonical(body))}
    target = journal.directory / authority.PROFILE
    target.parent.mkdir(parents=True, exist_ok=True)
    h.write_once(target.parent / "review.json", ws.approval.canonical(report))
    h.write_once(target, authority.profile_bytes(profile))
    authority.load_profile(root)
    return {"profile": str(target), "fingerprint": profile["fingerprint"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    approval = commands.add_parser("activate")
    approval.add_argument("--commit", required=True)
    approval.add_argument("--pr", type=int, required=True)
    approval.add_argument("--review-report", type=Path, required=True)
    commands.add_parser("status")
    commands.add_parser("run")
    commands.add_parser("reconcile-checks")
    recovery = commands.add_parser("reconcile-provider")
    recovery.add_argument("--dispatch-id", required=True)
    recovery.add_argument("--response-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "activate":
            result = activate(
                args.root.resolve(), args.commit, args.pr, args.review_report
            )
        else:
            from dataclasses import asdict
            from scripts.pilot_controller import Operator

            service = Operator(args.root)
            if args.command == "reconcile-checks":
                authority.load_profile(args.root)
                service._checks(reconcile=True)
                print(json.dumps(asdict(service.status()), indent=2))
                return 0
            if args.command == "reconcile-provider":
                print(
                    json.dumps(
                        asdict(
                            service.reconcile_provider(
                                args.dispatch_id,
                                ws._json(h.read_file(args.response_file)),
                            )
                        ),
                        indent=2,
                    )
                )
                return 0
            result = asdict(
                service.start(authority.OBJECTIVE)
                if args.command == "run"
                else service.status()
            )
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        # Never echo provider HTTP errors, credentials, or external stderr.
        print(
            "Pilot blocked: "
            + (
                str(exc)
                if isinstance(exc, ValueError)
                else "Prerequisite or read-only inspection failed"
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
