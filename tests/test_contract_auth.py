"""Contract tests for ``UserAuthenticator``. Run against every implementation."""

from __future__ import annotations

from datetime import timedelta, timezone

import pytest

from contracts import (
    InvalidCredentialsError,
    Session,
    SessionExpiredError,
    User,
    UserAlreadyExistsError,
    WeakPasswordError,
)


def test_register_returns_user(services):
    auth, _ = services
    user = auth.register("alice", "correct horse")
    assert isinstance(user, User)
    assert user.username == "alice"
    assert isinstance(user.id, int)
    assert user.created_at.tzinfo is not None, "created_at must be timezone-aware"


def test_login_returns_session_for_same_user(services):
    auth, _ = services
    user = auth.register("alice", "correct horse")
    session = auth.login("alice", "correct horse")
    assert isinstance(session, Session)
    assert session.user.id == user.id
    assert session.expires_at.tzinfo is not None
    assert session.expires_at.astimezone(timezone.utc) > user.created_at.astimezone(timezone.utc)


def test_current_user_resolves_session(services):
    auth, _ = services
    user = auth.register("alice", "correct horse")
    session = auth.login("alice", "correct horse")
    assert auth.current_user(session).id == user.id


def test_user_id_stable_across_logins(services):
    auth, _ = services
    auth.register("alice", "correct horse")
    first = auth.login("alice", "correct horse")
    second = auth.login("alice", "correct horse")
    assert first.user.id == second.user.id
    assert first.token != second.token


def test_duplicate_username_rejected(services):
    auth, _ = services
    auth.register("alice", "correct horse")
    with pytest.raises(UserAlreadyExistsError):
        auth.register("alice", "another password")


def test_weak_password_rejected(services):
    auth, _ = services
    with pytest.raises(WeakPasswordError):
        auth.register("alice", "short")


@pytest.mark.parametrize("username,password", [("alice", "wrong password"), ("nobody", "correct horse")])
def test_bad_credentials_indistinguishable(services, username, password):
    auth, _ = services
    auth.register("alice", "correct horse")
    with pytest.raises(InvalidCredentialsError):
        auth.login(username, password)


def test_logout_invalidates_and_is_idempotent(services):
    auth, _ = services
    auth.register("alice", "correct horse")
    session = auth.login("alice", "correct horse")
    auth.logout(session)
    auth.logout(session)  # second call must not raise
    with pytest.raises(SessionExpiredError):
        auth.current_user(session)


def test_expired_session_rejected(make_services):
    auth, _ = make_services(session_ttl=timedelta(0))
    auth.register("alice", "correct horse")
    session = auth.login("alice", "correct horse")
    with pytest.raises(SessionExpiredError):
        auth.current_user(session)


def test_unknown_session_rejected(services):
    auth, _ = services
    user = auth.register("alice", "correct horse")
    forged = Session(token="not-a-real-token", user=user, expires_at=user.created_at + timedelta(days=1))
    with pytest.raises(SessionExpiredError):
        auth.current_user(forged)
