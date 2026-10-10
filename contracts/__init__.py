"""The Contract.

This package is the single source of truth shared by every parallel AI
session. The UI session codes *against* these interfaces; feature sessions
*implement* them; the container wires them together. Nobody edits their own
copy -- changes land here first, then propagate to the other sessions.

Rules encoded by this package:
  * Interfaces return raw data (frozen dataclasses) or raise the exceptions
    defined here. They never return display strings.
  * The UI parses user input into the typed arguments shown here and
    translates exceptions into something a human can read.
  * Feature implementations validate *domain* rules (e.g. password policy);
    the UI validates *syntax* (e.g. "is this text a number?").
  * One module per feature. Add ``contracts/<feature>.py`` and re-export it
    here when a new feature is born.
"""

from contracts.auth import (
    AuthError,
    InvalidCredentialsError,
    Session,
    SessionExpiredError,
    User,
    UserAlreadyExistsError,
    UserAuthenticator,
    WeakPasswordError,
)
from contracts.data import (
    DataProcessor,
    EmptyInputError,
    ProcessingError,
    ProcessingResult,
)
from contracts.errors import AppError, StorageError

__all__ = [
    # errors
    "AppError",
    "StorageError",
    # auth
    "User",
    "Session",
    "AuthError",
    "InvalidCredentialsError",
    "UserAlreadyExistsError",
    "WeakPasswordError",
    "SessionExpiredError",
    "UserAuthenticator",
    # data
    "ProcessingResult",
    "ProcessingError",
    "EmptyInputError",
    "DataProcessor",
]
