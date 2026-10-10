"""SQLite-backed implementation of ``contracts.DataProcessor``.

Session validation is delegated to the injected ``UserAuthenticator`` rather
than re-implemented here, so this class works with *any* authenticator
(including the UI's mock) and never has to know how sessions are stored.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from contracts import (
    DataProcessor,
    EmptyInputError,
    ProcessingResult,
    Session,
    StorageError,
    UserAuthenticator,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    count      INTEGER NOT NULL,
    total      REAL    NOT NULL,
    mean       REAL    NOT NULL,
    minimum    REAL    NOT NULL,
    maximum    REAL    NOT NULL,
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS results_user_created ON results (user_id, id DESC);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SQLDataProcessor(DataProcessor):
    """Computes batch statistics and persists them per user.

    Args:
        db_path: SQLite file. May be the same file the authenticator uses.
        authenticator: Used to turn a ``Session`` into a ``User`` (and to
            reject sessions that are expired or logged out).
    """

    def __init__(self, db_path: str | Path, authenticator: UserAuthenticator) -> None:
        self._auth = authenticator
        try:
            self._db = sqlite3.connect(str(db_path))
            self._db.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Contract
    # ------------------------------------------------------------------ #

    def process(self, values: Sequence[float], session: Session) -> ProcessingResult:
        user = self._auth.current_user(session)  # raises SessionExpiredError
        if not values:
            raise EmptyInputError()

        stats = _Stats.of(values)
        created = _now()
        try:
            with self._db:
                cur = self._db.execute(
                    "INSERT INTO results (user_id, count, total, mean, minimum, maximum, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user.id, stats.count, stats.total, stats.mean, stats.minimum, stats.maximum,
                     created.isoformat()),
                )
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

        return ProcessingResult(
            record_id=int(cur.lastrowid),
            count=stats.count,
            total=stats.total,
            mean=stats.mean,
            minimum=stats.minimum,
            maximum=stats.maximum,
            created_at=created,
        )

    def history(self, session: Session, limit: int = 10) -> list[ProcessingResult]:
        user = self._auth.current_user(session)
        try:
            rows = self._db.execute(
                "SELECT id, count, total, mean, minimum, maximum, created_at"
                " FROM results WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user.id, max(0, limit)),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        return [self._row_to_result(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _row_to_result(row: tuple) -> ProcessingResult:
        rid, count, total, mean, minimum, maximum, created_at = row
        return ProcessingResult(
            record_id=int(rid),
            count=int(count),
            total=float(total),
            mean=float(mean),
            minimum=float(minimum),
            maximum=float(maximum),
            created_at=datetime.fromisoformat(created_at),
        )


class _Stats:
    """Pure computation, separated from persistence so it is trivially testable."""

    __slots__ = ("count", "total", "mean", "minimum", "maximum")

    def __init__(self, count: int, total: float, mean: float, minimum: float, maximum: float) -> None:
        self.count = count
        self.total = total
        self.mean = mean
        self.minimum = minimum
        self.maximum = maximum

    @classmethod
    def of(cls, values: Sequence[float]) -> "_Stats":
        floats = [float(v) for v in values]
        total = sum(floats)
        return cls(
            count=len(floats),
            total=total,
            mean=total / len(floats),
            minimum=min(floats),
            maximum=max(floats),
        )
