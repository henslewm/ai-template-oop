"""UI tests: input parsing, error translation, and a window smoke test.

The window test drives handlers directly instead of running ``mainloop``.
It is skipped where no display is available (headless CI). The whole module
is skipped where Tk is not installed: the GUI is an optional example (#28).
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter", reason="Tk is not installed; the GUI is optional")

from contracts import AppError, EmptyInputError, InvalidCredentialsError, SessionExpiredError
from src.ui.errors import describe_error
from src.ui.main_window import MainWindow, parse_numbers
from src.ui.mocks import DEMO_PASSWORD, DEMO_USERNAME, MockAuthenticator, MockDataProcessor


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1, 2.5, 3", [1.0, 2.5, 3.0]),
        ("1 2 3", [1.0, 2.0, 3.0]),
        ("  4,,5 ", [4.0, 5.0]),
        ("", []),
        ("-1e3", [-1000.0]),
    ],
)
def test_parse_numbers(text, expected):
    assert parse_numbers(text) == expected


def test_parse_numbers_rejects_junk():
    with pytest.raises(ValueError):
        parse_numbers("1, two, 3")


@pytest.mark.parametrize(
    "exc,fragment",
    [
        (InvalidCredentialsError(), "incorrect"),
        (SessionExpiredError(), "expired"),
        (EmptyInputError(), "at least one"),
        (AppError(), "Something went wrong"),
        (ValueError("x"), "separated by commas"),
        (RuntimeError("x"), "Unexpected"),
    ],
)
def test_describe_error(exc, fragment):
    assert fragment in describe_error(exc)


@pytest.fixture
def window():
    auth = MockAuthenticator()
    try:
        win = MainWindow(authenticator=auth, processor=MockDataProcessor(auth))
    except tk.TclError as exc:  # no display
        pytest.skip(f"Tk unavailable: {exc}")
    win._root.withdraw()
    yield win
    win.destroy()


def test_login_process_logout_flow(window):
    window._username.insert(0, DEMO_USERNAME)
    window._password.insert(0, DEMO_PASSWORD)
    window._on_login()
    assert window._session is not None
    assert "Welcome" in window._status.get()

    window._numbers.insert(0, "1, 2, 3")
    window._on_process()
    assert "Processed 3" in window._status.get()
    assert window._history.size() == 1

    window._numbers.insert(0, "not a number")
    window._on_process()
    assert "separated by commas" in window._status.get()

    window._on_logout()
    assert window._session is None


def test_bad_login_stays_on_login_screen(window):
    window._username.insert(0, DEMO_USERNAME)
    window._password.insert(0, "wrong")
    window._on_login()
    assert window._session is None
    assert "incorrect" in window._status.get()
