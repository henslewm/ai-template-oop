"""Command-line shell: parse arguments, call interfaces, render results.

Every step ends in exactly one call on an injected ``UserAuthenticator`` or
``DataProcessor``. A command that needs a session logs in, performs its one
action and logs out again, because a CLI run holds no state between runs.
This module never computes, stores or fetches anything itself.
"""

from __future__ import annotations

import argparse
from typing import Sequence, TextIO

from contracts import AppError, DataProcessor, ProcessingResult, User, UserAuthenticator
from src.cli.errors import describe_error


def parse_numbers(text: str) -> list[float]:
    """Turn ``"1, 2.5 3"`` into ``[1.0, 2.5, 3.0]``. Raises ValueError on junk.

    Syntax validation belongs to the shell; *domain* validation (e.g. "no
    values") belongs to the processor, which raises ``EmptyInputError``.
    """
    tokens = [t for t in text.replace(",", " ").split() if t]
    return [float(t) for t in tokens]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Headless contract-first OOP sample."
    )
    storage = parser.add_mutually_exclusive_group()
    storage.add_argument(
        "--mock", action="store_true", help="in-memory services (demo / demo1234)"
    )
    storage.add_argument("--db", default="app.db", help="SQLite file (default: app.db)")
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="create an account")
    register.add_argument("username")
    register.add_argument("password")

    process = commands.add_parser("process", help="log in, summarise numbers, log out")
    process.add_argument("username")
    process.add_argument("password")
    process.add_argument("values", nargs="*", help='numbers, e.g. 1 2.5 or "1, 2.5"')

    history = commands.add_parser("history", help="log in, list results, log out")
    history.add_argument("username")
    history.add_argument("password")
    history.add_argument("--limit", type=int, default=10)
    return parser


class CommandLine:
    """Runs one parsed command against injected services.

    Args:
        authenticator: Any ``UserAuthenticator`` implementation.
        processor: Any ``DataProcessor`` implementation.
        out: Stream for results.
        err: Stream for human-readable errors.
    """

    def __init__(
        self,
        authenticator: UserAuthenticator,
        processor: DataProcessor,
        out: TextIO,
        err: TextIO,
    ) -> None:
        self._auth = authenticator
        self._proc = processor
        self._out = out
        self._err = err

    def execute(self, args: argparse.Namespace) -> int:
        """Return a process exit code: 0 on success, 1 on a reported error."""
        try:
            if args.command == "register":
                self._render_user(
                    self._auth.register(args.username.strip(), args.password)
                )
            elif args.command == "process":
                values = parse_numbers(" ".join(args.values))
                self._with_session(
                    args, lambda s: self._render_result(self._proc.process(values, s))
                )
            elif args.command == "history":
                self._with_session(
                    args,
                    lambda s: self._render_history(self._proc.history(s, args.limit)),
                )
            else:
                self._err.write(f"Unknown command: {args.command}\n")
                return 2
        except (AppError, ValueError) as exc:
            self._err.write(describe_error(exc) + "\n")
            return 1
        return 0

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _with_session(self, args: argparse.Namespace, action) -> None:
        session = self._auth.login(args.username.strip(), args.password)
        try:
            action(session)
        finally:
            self._auth.logout(session)

    def _render_user(self, user: User) -> None:
        self._out.write(f"registered {user.username} (id {user.id})\n")

    def _render_result(self, result: ProcessingResult) -> None:
        self._out.write(
            f"record {result.record_id}: count={result.count} total={result.total:g}"
            f" mean={result.mean:g} min={result.minimum:g} max={result.maximum:g}"
            f" at {result.created_at.isoformat()}\n"
        )

    def _render_history(self, results: Sequence[ProcessingResult]) -> None:
        if not results:
            self._out.write("no results\n")
        for result in results:
            self._render_result(result)
