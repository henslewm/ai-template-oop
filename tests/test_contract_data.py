"""Contract tests for ``DataProcessor``. Run against every implementation."""

from __future__ import annotations

from datetime import timedelta

import pytest

from contracts import EmptyInputError, ProcessingResult, SessionExpiredError


@pytest.fixture
def logged_in(services):
    auth, proc = services
    auth.register("alice", "correct horse")
    return auth, proc, auth.login("alice", "correct horse")


def test_process_computes_statistics(logged_in):
    _, proc, session = logged_in
    result = proc.process([1.0, 2.0, 3.0, 10.0], session)
    assert isinstance(result, ProcessingResult)
    assert result.count == 4
    assert result.total == 16.0
    assert result.mean == 4.0
    assert result.minimum == 1.0
    assert result.maximum == 10.0
    assert result.created_at.tzinfo is not None


def test_process_single_value(logged_in):
    _, proc, session = logged_in
    result = proc.process([7.5], session)
    assert (result.count, result.total, result.mean, result.minimum, result.maximum) == (1, 7.5, 7.5, 7.5, 7.5)


def test_empty_input_rejected(logged_in):
    _, proc, session = logged_in
    with pytest.raises(EmptyInputError):
        proc.process([], session)


def test_record_ids_unique_and_increasing(logged_in):
    _, proc, session = logged_in
    a = proc.process([1.0], session)
    b = proc.process([2.0], session)
    assert b.record_id > a.record_id


def test_history_newest_first_and_limited(logged_in):
    _, proc, session = logged_in
    ids = [proc.process([float(i)], session).record_id for i in range(5)]
    rows = proc.history(session, limit=3)
    assert [r.record_id for r in rows] == ids[::-1][:3]
    assert [r.record_id for r in proc.history(session)] == ids[::-1]


def test_history_round_trips_values(logged_in):
    _, proc, session = logged_in
    stored = proc.process([2.0, 4.0], session)
    (fetched,) = proc.history(session)
    assert fetched == stored


def test_history_is_per_user(services):
    auth, proc = services
    auth.register("alice", "correct horse")
    auth.register("bob", "battery staple")
    alice = auth.login("alice", "correct horse")
    bob = auth.login("bob", "battery staple")
    proc.process([1.0], alice)
    proc.process([2.0], bob)
    proc.process([3.0], bob)
    assert [r.total for r in proc.history(alice)] == [1.0]
    assert [r.total for r in proc.history(bob)] == [3.0, 2.0]


def test_logged_out_session_rejected(logged_in):
    auth, proc, session = logged_in
    auth.logout(session)
    with pytest.raises(SessionExpiredError):
        proc.process([1.0], session)
    with pytest.raises(SessionExpiredError):
        proc.history(session)


def test_expired_session_rejected(make_services):
    auth, proc = make_services(session_ttl=timedelta(0))
    auth.register("alice", "correct horse")
    session = auth.login("alice", "correct horse")
    with pytest.raises(SessionExpiredError):
        proc.process([1.0], session)
