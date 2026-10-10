"""The main window: layout, event binding, and view state.

Everything the user can do here ends in exactly one call on an injected
``UserAuthenticator`` or ``DataProcessor``. This module parses input and
renders output; it never computes, stores, or fetches anything itself.

Feature calls run synchronously on the Tk thread. If an implementation turns
out to be slow (network, big DB) the fix is to push the call into a worker
thread *here*, not to make the feature module aware of Tk.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from contracts import (
    AppError,
    DataProcessor,
    ProcessingResult,
    Session,
    SessionExpiredError,
    UserAuthenticator,
)
from src.ui.errors import describe_error


def parse_numbers(text: str) -> list[float]:
    """Turn ``"1, 2.5 3"`` into ``[1.0, 2.5, 3.0]``. Raises ValueError on junk.

    Syntax validation belongs to the UI; *domain* validation (e.g. "no
    values") belongs to the processor, which raises ``EmptyInputError``.
    """
    tokens = [t for t in text.replace(",", " ").split() if t]
    return [float(t) for t in tokens]


class MainWindow:
    """Top-level application window.

    Args:
        authenticator: Any ``UserAuthenticator`` implementation.
        processor: Any ``DataProcessor`` implementation.
        title: Window title.
    """

    def __init__(
        self,
        authenticator: UserAuthenticator,
        processor: DataProcessor,
        title: str = "AI Template (OOP)",
    ) -> None:
        self._auth = authenticator
        self._proc = processor
        self._session: Session | None = None

        self._root = tk.Tk()
        self._root.title(title)
        self._root.minsize(520, 420)

        self._status = tk.StringVar(value="Not logged in.")
        self._build_login_frame()
        self._build_main_frame()
        self._build_status_bar()
        self._show_login()

    # ------------------------------------------------------------------ #
    # Public API (what main.py calls)
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Run the Tk event loop until the window closes."""
        self._root.mainloop()

    def destroy(self) -> None:
        """Tear the window down without running the loop (used by tests)."""
        self._root.destroy()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_login_frame(self) -> None:
        f = self._login_frame = ttk.Frame(self._root, padding=16)
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Username").grid(row=0, column=0, sticky="w", pady=4)
        self._username = ttk.Entry(f)
        self._username.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(f, text="Password").grid(row=1, column=0, sticky="w", pady=4)
        self._password = ttk.Entry(f, show="*")
        self._password.grid(row=1, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(f)
        buttons.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(buttons, text="Login", command=self._on_login).pack(side="left", padx=4)
        ttk.Button(buttons, text="Register", command=self._on_register).pack(side="left", padx=4)

        self._password.bind("<Return>", lambda _e: self._on_login())

    def _build_main_frame(self) -> None:
        f = self._main_frame = ttk.Frame(self._root, padding=16)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(4, weight=1)

        header = ttk.Frame(f)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self._whoami = ttk.Label(header, text="")
        self._whoami.grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Logout", command=self._on_logout).grid(row=0, column=1, sticky="e")

        ttk.Label(f, text="Numbers (comma or space separated)").grid(
            row=1, column=0, sticky="w", pady=(12, 2)
        )
        entry_row = ttk.Frame(f)
        entry_row.grid(row=2, column=0, sticky="ew")
        entry_row.columnconfigure(0, weight=1)
        self._numbers = ttk.Entry(entry_row)
        self._numbers.grid(row=0, column=0, sticky="ew")
        ttk.Button(entry_row, text="Process", command=self._on_process).grid(row=0, column=1, padx=(8, 0))
        self._numbers.bind("<Return>", lambda _e: self._on_process())

        self._result = ttk.Label(f, text="", justify="left")
        self._result.grid(row=3, column=0, sticky="w", pady=8)

        hist_box = ttk.LabelFrame(f, text="History (newest first)", padding=8)
        hist_box.grid(row=4, column=0, sticky="nsew")
        hist_box.columnconfigure(0, weight=1)
        hist_box.rowconfigure(0, weight=1)
        self._history = tk.Listbox(hist_box, height=8, activestyle="none")
        self._history.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(hist_box, orient="vertical", command=self._history.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._history.configure(yscrollcommand=scroll.set)
        ttk.Button(hist_box, text="Refresh", command=self._refresh_history).grid(
            row=1, column=0, columnspan=2, sticky="e", pady=(8, 0)
        )

    def _build_status_bar(self) -> None:
        bar = ttk.Label(self._root, textvariable=self._status, anchor="w", relief="sunken", padding=(8, 4))
        bar.pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ #
    # View state
    # ------------------------------------------------------------------ #

    def _show_login(self) -> None:
        self._main_frame.pack_forget()
        self._login_frame.pack(fill="both", expand=True)
        self._password.delete(0, "end")
        self._username.focus_set()

    def _show_main(self) -> None:
        assert self._session is not None
        self._login_frame.pack_forget()
        self._main_frame.pack(fill="both", expand=True)
        self._whoami.configure(text=f"Logged in as {self._session.user.username}")
        self._result.configure(text="")
        self._numbers.delete(0, "end")
        self._numbers.focus_set()
        self._refresh_history()

    def _set_status(self, text: str) -> None:
        self._status.set(text)

    def _fail(self, exc: BaseException) -> None:
        """Every error path funnels through here so messaging stays in one place."""
        self._set_status(describe_error(exc))
        if isinstance(exc, SessionExpiredError):
            self._session = None
            self._show_login()

    # ------------------------------------------------------------------ #
    # Event handlers: parse -> one interface call -> render
    # ------------------------------------------------------------------ #

    def _credentials(self) -> tuple[str, str]:
        return self._username.get().strip(), self._password.get()

    def _on_login(self) -> None:
        username, password = self._credentials()
        if not username or not password:
            self._set_status("Enter a username and password.")
            return
        try:
            self._session = self._auth.login(username, password)
        except AppError as exc:
            self._fail(exc)
            return
        self._set_status(f"Welcome, {self._session.user.username}.")
        self._show_main()

    def _on_register(self) -> None:
        username, password = self._credentials()
        if not username or not password:
            self._set_status("Enter a username and password.")
            return
        try:
            user = self._auth.register(username, password)
        except AppError as exc:
            self._fail(exc)
            return
        self._set_status(f"Account {user.username!r} created. You can log in now.")

    def _on_logout(self) -> None:
        if self._session is not None:
            self._auth.logout(self._session)  # idempotent by contract
        self._session = None
        self._set_status("Logged out.")
        self._show_login()

    def _on_process(self) -> None:
        if self._session is None:
            self._show_login()
            return
        try:
            values = parse_numbers(self._numbers.get())
        except ValueError as exc:
            self._fail(exc)
            return
        try:
            result = self._proc.process(values, self._session)
        except AppError as exc:
            self._fail(exc)
            return
        self._result.configure(text=self._format_result(result))
        self._set_status(f"Processed {result.count} value(s).")
        self._numbers.delete(0, "end")
        self._refresh_history()

    def _refresh_history(self) -> None:
        if self._session is None:
            return
        try:
            rows = self._proc.history(self._session, limit=20)
        except AppError as exc:
            self._fail(exc)
            return
        self._history.delete(0, "end")
        for r in rows:
            self._history.insert("end", self._format_history_row(r))

    # ------------------------------------------------------------------ #
    # Rendering helpers (display formatting lives in the UI, nowhere else)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_result(r: ProcessingResult) -> str:
        return (
            f"Record #{r.record_id}: count={r.count}  total={r.total:g}  "
            f"mean={r.mean:.4g}  min={r.minimum:g}  max={r.maximum:g}"
        )

    @staticmethod
    def _format_history_row(r: ProcessingResult) -> str:
        when = r.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return f"{when}  #{r.record_id}  n={r.count}  mean={r.mean:.4g}  [{r.minimum:g} .. {r.maximum:g}]"
