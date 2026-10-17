"""Shared fixtures.

The key idea: ``make_services`` is parametrised over *every* implementation
(mock and production). Each ``test_contract_*`` test therefore runs once per
implementation with identical assertions. If a feature session's class
passes, it is substitutable for the in-memory fake callers were built against.

To add an implementation, append one entry to ``IMPLEMENTATIONS``.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Callable

import pytest

from contracts import DataProcessor, UserAuthenticator
from src.features import ProductionAuthenticator, SQLDataProcessor
from src.testing.fakes import MockAuthenticator, MockDataProcessor

ServicesFactory = Callable[..., tuple[UserAuthenticator, DataProcessor]]


def _mock(_tmp: Path, ttl: timedelta) -> tuple[UserAuthenticator, DataProcessor]:
    auth = MockAuthenticator(session_ttl=ttl, seed_demo=False)
    return auth, MockDataProcessor(auth)


def _sql(tmp: Path, ttl: timedelta) -> tuple[UserAuthenticator, DataProcessor]:
    db = tmp / "test.db"
    auth = ProductionAuthenticator(db, session_ttl=ttl, pbkdf2_iterations=1_000)  # fast for tests
    return auth, SQLDataProcessor(db, auth)


IMPLEMENTATIONS = {"mock": _mock, "sql": _sql}


@pytest.fixture(params=list(IMPLEMENTATIONS), ids=list(IMPLEMENTATIONS))
def make_services(request: pytest.FixtureRequest, tmp_path: Path) -> ServicesFactory:
    """Factory: ``make_services(session_ttl=...)`` -> (authenticator, processor)."""
    builder = IMPLEMENTATIONS[request.param]

    def factory(session_ttl: timedelta = timedelta(hours=1)) -> tuple[UserAuthenticator, DataProcessor]:
        return builder(tmp_path, session_ttl)

    return factory


@pytest.fixture
def services(make_services: ServicesFactory) -> tuple[UserAuthenticator, DataProcessor]:
    return make_services()
