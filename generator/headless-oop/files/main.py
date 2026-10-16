"""Entry point: the only place where the CLI and the features meet.

python main.py --mock process demo demo1234 1 2 3 10    # in-memory
python main.py register alice "correct horse"           # SQLite, ./app.db
python main.py process alice "correct horse" 4 5 6
python main.py --db other.db history alice "correct horse"
"""

from __future__ import annotations

import sys

from contracts import AppError
from src.cli import CommandLine, build_parser
from src.cli.errors import describe_error
from src.container import build_mock, build_production


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # 1. Instantiate the feature objects (The Workers)
    try:
        services = build_mock() if args.mock else build_production(args.db)
    except AppError as exc:
        sys.stderr.write(describe_error(exc) + "\n")
        return 1

    # 2. Inject them into the shell and run one command
    shell = CommandLine(
        authenticator=services.authenticator,
        processor=services.processor,
        out=sys.stdout,
        err=sys.stderr,
    )
    return shell.execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
