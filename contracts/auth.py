"""Contract: user authentication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from contracts.errors import AppError


# --------------------------------------------------------------------------- #
# Data contracts (raw structures the UI renders)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class User:
    """A registered account. ``id`` is stable across logins."""

    id: int
    username: str
    created_at: datetime


@dataclass(frozen=True)
class Session:
    """Proof of a successful login.

    Opaque to the UI: pass it back to the authenticator/processor, never
    inspect ``token``. ``expires_at`` is timezone-aware UTC.
    """

    token: str
    user: User
    expires_at: datetime


# --------------------------------------------------------------------------- #
# Exceptions (raw error objects; the UI turns these into messages)
# --------------------------------------------------------------------------- #


class AuthError(AppError):
    """Base class for authentication failures."""


class InvalidCredentialsError(AuthError):
    """Username unknown or password wrong. Deliberately indistinguishable."""


class UserAlreadyExistsError(AuthError):
    """Registration attempted with a username that is taken."""


class WeakPasswordError(AuthError):
    """Password does not satisfy the implementation's policy."""


class SessionExpiredError(AuthError):
    """The supplied session is unknown, logged out, or past ``expires_at``."""


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #


class UserAuthenticator(ABC):
    """Creates accounts and exchanges credentials for sessions."""

    @abstractmethod
    def register(self, username: str, password: str) -> User:
        """Create a new account.

        Args:
            username: Already stripped of surrounding whitespace by the caller.
            password: Plain text; the implementation is responsible for hashing.

        Returns:
            The newly created user.

        Raises:
            UserAlreadyExistsError: ``username`` is taken.
            WeakPasswordError: ``password`` fails the implementation's policy.
            StorageError: The account could not be persisted.
        """

    @abstractmethod
    def login(self, username: str, password: str) -> Session:
        """Exchange credentials for a session.

        Raises:
            InvalidCredentialsError: Unknown user or wrong password.
            StorageError: The account store could not be read.
        """

    @abstractmethod
    def logout(self, session: Session) -> None:
        """Invalidate ``session``. Idempotent: logging out twice is not an error."""

    @abstractmethod
    def current_user(self, session: Session) -> User:
        """Resolve a session back to its user.

        Raises:
            SessionExpiredError: ``session`` is not (or no longer) valid.
        """
