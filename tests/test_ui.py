"""UI tests: input parsing, error translation, and a window smoke test.

Each window case drives handlers in a fresh process instead of running
``mainloop`` or reinitializing Tcl after destroying a root (Windows issue #4).
It is skipped only where no display is available. The whole module
is skipped where Tk is not installed: the GUI is an optional example (#28).
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

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


@contextmanager
def _window():
    auth = MockAuthenticator()
    try:
        win = MainWindow(authenticator=auth, processor=MockDataProcessor(auth))
    except tk.TclError as exc:
        message = str(exc)
        if message == "no display name and no $DISPLAY environment variable" or message.startswith(
            "couldn't connect to display "
        ):
            pytest.skip(f"Tk display unavailable: {exc}")
        raise
    try:
        win._root.withdraw()
        yield win
    finally:
        win.destroy()


def _run_window_case(case):
    # A child owns exactly one Tcl interpreter; do not retry bootstrap failures.
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import runpy
import sys
import pytest

namespace = runpy.run_path(sys.argv[1])
try:
    with namespace["_window"]() as window:
        namespace[sys.argv[2]](window)
except pytest.skip.Exception as exc:
    print(exc)
    sys.exit(77)
""",
            str(Path(__file__).resolve()),
            case,
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr


def test_login_process_logout_flow():
    _run_window_case("_check_login_process_logout_flow")


def _check_login_process_logout_flow(window):
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


def test_bad_login_stays_on_login_screen():
    _run_window_case("_check_bad_login_stays_on_login_screen")


def _check_bad_login_stays_on_login_screen(window):
    window._username.insert(0, DEMO_USERNAME)
    window._password.insert(0, "wrong")
    window._on_login()
    assert window._session is None
    assert "incorrect" in window._status.get()


@pytest.mark.parametrize(
    "message",
    [
        "no display name and no $DISPLAY environment variable",
        'couldn\'t connect to display ":99"',
    ],
)
def test_window_skips_only_unavailable_display(monkeypatch, message):
    def unavailable(**kwargs):
        raise tk.TclError(message)

    monkeypatch.setattr(sys.modules[__name__], "MainWindow", unavailable)
    with pytest.raises(pytest.skip.Exception, match="Tk display unavailable"):
        with _window():
            pytest.fail("An unavailable window must not be yielded")


@pytest.mark.parametrize(
    "message",
    [
        'invalid command name "tcl_findLibrary"',
        'couldn\'t read file "Python312/tcl/tcl8.6/auto.tcl": no such file or directory',
        'invalid command name "ttk::frame"',
    ],
)
def test_window_does_not_skip_bootstrap_or_application_errors(monkeypatch, message):
    error = tk.TclError(message)

    def broken(**kwargs):
        raise error

    monkeypatch.setattr(sys.modules[__name__], "MainWindow", broken)
    with pytest.raises(tk.TclError) as raised:
        with _window():
            pytest.fail("A broken window must not be yielded")
    assert raised.value is error


def test_window_is_destroyed_when_case_fails(monkeypatch):
    events = []

    class FakeWindow:
        def __init__(self, **kwargs):
            self._root = self

        def withdraw(self):
            events.append("withdraw")

        def destroy(self):
            events.append("destroy")

    monkeypatch.setattr(sys.modules[__name__], "MainWindow", FakeWindow)
    with pytest.raises(AssertionError, match="case failed"):
        with _window():
            raise AssertionError("case failed")
    assert events == ["withdraw", "destroy"]


@pytest.mark.parametrize("returncode", [0, 1, 77])
def test_window_case_propagates_child_outcome(monkeypatch, returncode):
    def run(command, **kwargs):
        assert command[:3] == [sys.executable, "-B", "-c"]
        assert Path(command[4]).is_absolute()
        assert command[5] == "_check_bad_login_stays_on_login_screen"
        assert kwargs["timeout"] == 60
        return subprocess.CompletedProcess(command, returncode, "child output", "child error")

    monkeypatch.setattr(subprocess, "run", run)
    if returncode == 77:
        with pytest.raises(pytest.skip.Exception, match="child output"):
            _run_window_case("_check_bad_login_stays_on_login_screen")
    elif returncode:
        with pytest.raises(AssertionError, match="child outputchild error"):
            _run_window_case("_check_bad_login_stays_on_login_screen")
    else:
        _run_window_case("_check_bad_login_stays_on_login_screen")
