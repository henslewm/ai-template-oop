"""Initialize, review and explicitly approve an offline project's current implementation."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import project_authority as authority


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser(
        "init", help="Create fresh identity; never inherit approval"
    )
    initialize.add_argument("--slug", required=True)
    commands.add_parser("review", help="Prepare the exact offline approval package")
    commands.add_parser("status", help="Read-only project authority inspection")
    for command in ("activate", "revoke"):
        decision = commands.add_parser(command)
        decision.add_argument("--owner", required=True)
        decision.add_argument(
            "--decision",
            help="Literal APPROVE/REVOKE <review fingerprint>; prompted if omitted",
        )
    args = parser.parse_args(argv)
    try:
        root = args.root
        if args.command == "init":
            result = {
                "state": "AWAITING_APPROVAL",
                "project": authority.initialize(root, args.slug),
            }
        elif args.command == "review":
            fingerprint = authority.review(root)
            result = {
                "fingerprint": fingerprint,
                "decision": "APPROVE " + fingerprint,
                "note": "Review does not approve. All live capabilities remain disabled.",
            }
        elif args.command == "status":
            result = authority.status(root)
        else:
            decision = (
                args.decision
                if args.decision is not None
                else input("Literal owner decision: ")
            )
            fingerprint = authority.decide(
                root, args.owner, decision, revoke=args.command == "revoke"
            )
            result = {
                "fingerprint": fingerprint,
                "state": "REVOKED" if args.command == "revoke" else "ACTIVE_OFFLINE",
            }
        print(json.dumps(result, indent=2))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        EOFError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            "PROJECT AUTHORITY HELD: "
            + (
                str(exc)
                if isinstance(exc, ValueError)
                else "Missing, malformed or inaccessible input; inspect project status"
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
