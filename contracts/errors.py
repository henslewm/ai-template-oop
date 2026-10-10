"""Exceptions shared by every feature contract."""


class AppError(Exception):
    """Base class for every error a feature module may raise.

    The UI catches this (and only this) at its call sites; anything else
    escaping a feature module is a bug in that module.
    """


class StorageError(AppError):
    """The backing store (DB, file, network) could not be read or written."""
