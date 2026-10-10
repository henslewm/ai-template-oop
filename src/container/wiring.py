"""Composition root.

Two builders, one per environment. Add a third (``build_staging``, ...) rather
than sprinkling ``if`` statements through the UI or the features.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contracts import DataProcessor, UserAuthenticator
from src.features import ProductionAuthenticator, SQLDataProcessor
from src.ui.mocks import MockAuthenticator, MockDataProcessor


@dataclass(frozen=True)
class Services:
    """Everything the UI needs, already constructed."""

    authenticator: UserAuthenticator
    processor: DataProcessor


def build_mock() -> Services:
    """In-memory services. Pre-seeded with ``demo`` / ``demo1234``."""
    auth = MockAuthenticator()
    return Services(authenticator=auth, processor=MockDataProcessor(auth))


def build_production(db_path: str | Path) -> Services:
    """SQLite-backed services sharing one database file."""
    auth = ProductionAuthenticator(db_path)
    return Services(authenticator=auth, processor=SQLDataProcessor(db_path, auth))
