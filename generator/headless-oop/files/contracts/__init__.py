"""The Contract.

The single source of truth between the presentation shell and the features.
The CLI codes *against* these interfaces; features *implement* them; the
container wires them together. Change an interface here first.

Rules encoded by this package:
  * Interfaces return raw data (frozen dataclasses) or raise the exceptions
    defined here. They never return display strings.
  * The CLI parses user input into the typed arguments shown here and
    translates exceptions into something a human can read.
  * Feature implementations validate *domain* rules (e.g. password policy);
    the CLI validates *syntax* (e.g. "is this text a number?").
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
