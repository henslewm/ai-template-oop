"""In-memory stand-ins so callers can be built and tested before any feature
session has delivered a real implementation.

These are *contract-complete*: they pass the same ``tests/test_contract_*``
suite as the production classes, so swapping one for the other is safe.

Pre-seeded account: username ``demo`` / password ``demo1234``.
"""

from __future__ import annotations

import itertools
import secrets
from datetime import datetime, timedelta, timezone
from typing import Sequence

from contracts import (
    DataProcessor,
    EmptyInputError,
    InvalidCredentialsError,
    ProcessingResult,
    Session,
    SessionExpiredError,
    User,
    UserAlreadyExistsError,
    UserAuthenticator,
    WeakPasswordError,
)

MIN_PASSWORD_LENGTH = 8
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MockAuthenticator(UserAuthenticator):
    def __init__(self, session_ttl: timedelta = timedelta(hours=1), seed_demo: bool = True) -> None:
        self._ttl = session_ttl
        self._ids = itertools.count(1)
        self._users: dict[str, tuple[User, str]] = {}  # username -> (user, password)
        self._sessions: dict[str, Session] = {}
        if seed_demo:
            self.register(DEMO_USERNAME, DEMO_PASSWORD)

    def register(self, username: str, password: str) -> User:
        if username in self._users:
            raise UserAlreadyExistsError(username)
        if len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError()
        user = User(id=next(self._ids), username=username, created_at=_now())
        self._users[username] = (user, password)
        return user

    def login(self, username: str, password: str) -> Session:
        entry = self._users.get(username)
        if entry is None or entry[1] != password:
            raise InvalidCredentialsError()
        session = Session(token=secrets.token_hex(16), user=entry[0], expires_at=_now() + self._ttl)
        self._sessions[session.token] = session
        return session

    def logout(self, session: Session) -> None:
        self._sessions.pop(session.token, None)

    def current_user(self, session: Session) -> User:
        live = self._sessions.get(session.token)
        if live is None or live.expires_at <= _now():
            self._sessions.pop(session.token, None)
            raise SessionExpiredError()
        return live.user


class MockDataProcessor(DataProcessor):
    """Keeps results in memory, keyed by user id.

    Takes the authenticator so it can reject logged-out or expired sessions
    exactly like the production class does.
    """

    def __init__(self, authenticator: UserAuthenticator) -> None:
        self._auth = authenticator
        self._ids = itertools.count(1)
        self._records: dict[int, list[ProcessingResult]] = {}

    def process(self, values: Sequence[float], session: Session) -> ProcessingResult:
        user = self._auth.current_user(session)  # raises SessionExpiredError
        if not values:
            raise EmptyInputError()
        total = float(sum(values))
        result = ProcessingResult(
            record_id=next(self._ids),
            count=len(values),
            total=total,
            mean=total / len(values),
            minimum=float(min(values)),
            maximum=float(max(values)),
            created_at=_now(),
        )
        self._records.setdefault(user.id, []).append(result)
        return result

    def history(self, session: Session, limit: int = 10) -> list[ProcessingResult]:
        user = self._auth.current_user(session)
        return list(reversed(self._records.get(user.id, [])))[:limit]
