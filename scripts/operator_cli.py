"""Parse operator commands and render the trusted facade's compact view."""

import sys
from pathlib import Path

from contracts.operator import OperatorService, OperatorView
from scripts.operator_service import open_service


USAGE = ('Usage: .\\start.ps1 "objective" | status | resume [--run]')


def _one_line(value) -> str:
    """Keep untrusted summaries from changing terminal state or output structure."""
    return " ".join("".join(char if char.isprintable() else " " for char in str(value)).split())


def _parse(argv):
    if argv == ["status"]:
        return "status", None
    if argv == ["resume"]:
        return "resume", False
    if argv == ["resume", "--run"]:
        return "resume", True
    if (len(argv) == 1 and argv[0].strip()
            and not argv[0].startswith("-")
            and argv[0] not in {"status", "resume"}):
        return "start", argv[0]
    raise ValueError('Pass one quoted objective, status, resume, or resume --run.')


def _render(view: OperatorView) -> None:
    print(f"Objective: {_one_line(view.objective)}")
    print(f"Progress: {_one_line(view.progress)}")
    print(f"Settled USD: {view.settled_usd:.4f}")
    print(f"Pending liability USD: {view.liability_usd:.4f}")
    print(f"Failed attempt cost USD: {view.failed_attempt_usd:.4f}")
    print(f"Context bytes: {view.context_bytes}")
    print(f"Accepted changes: {view.accepted_changes}")
    accepted_cost = view.cost_per_accepted_change_usd
    print("Cost per accepted change USD: " + (
        "unknown" if accepted_cost is None else f"{accepted_cost:.4f}"
    ))
    print("Blockers:")
    if view.blockers:
        for blocker in view.blockers:
            print(f"  - {_one_line(blocker)}")
    else:
        print("  none")
    print(f"Next action: {_one_line(view.next_action)}")


def main(argv=None, *, service: OperatorService | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--help"], ["-h"]):
        print(USAGE)
        return 0
    try:
        command, value = _parse(args)
    except ValueError as exc:
        print(f"Argument error: {exc} {USAGE}", file=sys.stderr)
        return 2
    try:
        if service is None:
            service = open_service(Path(__file__).resolve().parents[1])
        if command == "status":
            view = service.status()
        elif command == "resume":
            view = service.resume(run=value)
        else:
            view = service.start(value)
        _render(view)
        return 0
    except Exception as exc:
        detail = _one_line(exc) or type(exc).__name__
        print(
            f"Operator error: {detail}. Check local setup and inspect with "
            ".\\start.ps1 status before retrying.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
