"""The one place where raw exceptions become human-readable text.

Feature modules raise ``contracts`` exceptions; this module decides what the
user sees. Keep it a flat table so the translation boundary is reviewable.
"""

from __future__ import annotations

from contracts import (
    AppError,
    EmptyInputError,
    InvalidCredentialsError,
    SessionExpiredError,
    StorageError,
    UserAlreadyExistsError,
    WeakPasswordError,
)

# Most specific type first; ``describe_error`` walks this in order.
_MESSAGES: list[tuple[type[BaseException], str]] = [
    (InvalidCredentialsError, "Username or password is incorrect."),
    (UserAlreadyExistsError, "That username is already taken."),
    (WeakPasswordError, "Password is too weak. Use at least 8 characters."),
    (SessionExpiredError, "Your session has expired. Please log in again."),
    (EmptyInputError, "Enter at least one number to process."),
    (StorageError, "Could not reach storage. Try again in a moment."),
    (AppError, "Something went wrong."),
    # Raised by the UI's own input parsing, not by a feature module.
    (ValueError, "Enter numbers separated by commas, e.g. 1, 2.5, 3"),
]


def describe_error(exc: BaseException) -> str:
    """Map an exception to a short message suitable for a status bar."""
    for exc_type, message in _MESSAGES:
        if isinstance(exc, exc_type):
            return message
    return "Unexpected error."
