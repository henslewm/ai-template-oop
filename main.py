"""Entry point: the only place where the UI and the features meet.

    python main.py            # SQLite-backed, data in ./app.db
    python main.py --mock     # in-memory, pre-seeded demo/demo1234
    python main.py --db x.db  # SQLite-backed, custom file
"""

from __future__ import annotations

import argparse

from src.container import build_mock, build_production
from src.ui import MainWindow


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mock", action="store_true", help="use in-memory mock services")
    parser.add_argument("--db", default="app.db", help="SQLite file (default: app.db)")
    args = parser.parse_args(argv)

    # 1. Instantiate the feature objects (The Workers)
    services = build_mock() if args.mock else build_production(args.db)

    # 2. Inject them into the UI (The Shell)
    app = MainWindow(authenticator=services.authenticator, processor=services.processor)

    # 3. Run
    app.start()


if __name__ == "__main__":
    main()
