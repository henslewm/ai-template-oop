"""SQLite-backed implementation of ``contracts.UserAuthenticator``.

Passwords are salted and stretched with PBKDF2-HMAC-SHA256 (stdlib only).
Sessions live in a table so that any other feature holding the same database
path can validate them through ``current_user``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts import (
    InvalidCredentialsError,
    Session,
    SessionExpiredError,
    StorageError,
    User,
    UserAlreadyExistsError,
    UserAuthenticator,
    WeakPasswordError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash BLOB    NOT NULL,
    salt          BLOB    NOT NULL,
    iterations    INTEGER NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt_to_db(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _dt_from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ProductionAuthenticator(UserAuthenticator):
    """Account and session store on top of SQLite.

    Args:
        db_path: File to open or create. ``":memory:"`` works for tests but
            cannot then be shared with ``SQLDataProcessor``.
        session_ttl: How long a login stays valid.
        min_password_length: Domain rule behind ``WeakPasswordError``.
        pbkdf2_iterations: Work factor for password hashing. Lower it in
            tests if they feel slow; never below ~100k in production.
    """

    def __init__(
        self,
        db_path: str | Path,
        session_ttl: timedelta = timedelta(hours=8),
        min_password_length: int = 8,
        pbkdf2_iterations: int = 200_000,
    ) -> None:
        self._ttl = session_ttl
        self._min_len = min_password_length
        self._iterations = pbkdf2_iterations
        try:
            self._db = sqlite3.connect(str(db_path))
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Contract
    # ------------------------------------------------------------------ #

    def register(self, username: str, password: str) -> User:
        if len(password) < self._min_len:
            raise WeakPasswordError()
        salt = secrets.token_bytes(16)
        digest = self._hash(password, salt, self._iterations)
        created = _now()
        try:
            with self._db:
                cur = self._db.execute(
                    "INSERT INTO users (username, password_hash, salt, iterations, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (username, digest, salt, self._iterations, _dt_to_db(created)),
                )
        except sqlite3.IntegrityError as exc:
            raise UserAlreadyExistsError(username) from exc
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        return User(id=int(cur.lastrowid), username=username, created_at=created)

    def login(self, username: str, password: str) -> Session:
        try:
            row = self._db.execute(
                "SELECT id, username, password_hash, salt, iterations, created_at"
                " FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

        if row is None:
            # Burn the same work as a real check so timing does not leak
            # whether the username exists.
            self._hash(password, b"\x00" * 16, self._iterations)
            raise InvalidCredentialsError()

        user_id, name, stored_hash, salt, iterations, created_at = row
        if not hmac.compare_digest(self._hash(password, salt, iterations), stored_hash):
            raise InvalidCredentialsError()

        user = User(id=int(user_id), username=name, created_at=_dt_from_db(created_at))
        session = Session(token=secrets.token_urlsafe(32), user=user, expires_at=_now() + self._ttl)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                    (session.token, user.id, _dt_to_db(session.expires_at)),
                )
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        return session

    def logout(self, session: Session) -> None:
        try:
            with self._db:
                self._db.execute("DELETE FROM sessions WHERE token = ?", (session.token,))
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

    def current_user(self, session: Session) -> User:
        try:
            row = self._db.execute(
                "SELECT s.expires_at, u.id, u.username, u.created_at"
                " FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token = ?",
                (session.token,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        if row is None:
            raise SessionExpiredError()
        expires_at, user_id, username, created_at = row
        if _dt_from_db(expires_at) <= _now():
            self.logout(session)
            raise SessionExpiredError()
        return User(id=int(user_id), username=username, created_at=_dt_from_db(created_at))

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash(password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
