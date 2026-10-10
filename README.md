# ai-template-oop

Contract-first boilerplate for building an app with several AI sessions in
parallel: one session owns the UI, one session per feature, one session wires
them together. The sessions never see each other's code. They share only the
abstract base classes in `contracts/`.

The demo app is a Tk window with login/register and a numeric batch
processor, backed by SQLite in production and by in-memory mocks during UI
development.

## Layout

```
contracts/            The Contract. ABCs, frozen dataclasses, exceptions. One module per feature.
  auth.py             UserAuthenticator, User, Session, auth exceptions
  data.py             DataProcessor, ProcessingResult, processing exceptions
  errors.py           AppError, StorageError
src/
  ui/                 The Shell. Layout, events, state. No business logic.
    main_window.py    MainWindow(authenticator, processor).start()
    errors.py         The only exception -> human text table
    mocks.py          Contract-complete in-memory implementations
  features/           The Workers. Concrete implementations of contracts/.
    auth.py           ProductionAuthenticator (SQLite, PBKDF2)
    data.py           SQLDataProcessor (SQLite)
  container/          The Wire-Up. The only package importing both ui and features.
    wiring.py         build_mock(), build_production(db_path)
main.py               Entry point. python main.py [--mock] [--db app.db]
tools/
  validate_boundaries.py   Import-boundary linter, also run by pytest
tests/
  conftest.py              IMPLEMENTATIONS table; every test runs per implementation
  test_contract_auth.py    Contract tests for UserAuthenticator
  test_contract_data.py    Contract tests for DataProcessor
  test_ui.py               Parsing, error text, window smoke test
  test_boundaries.py       Runs the linter
PROMPTS.md            Prompts for each session type
CLAUDE.md             Rules every session gets automatically
```

## Run

```
python main.py --mock     # in-memory services, log in with demo / demo1234
python main.py            # SQLite in ./app.db, register a user first
python -m pytest          # 50-ish tests: contracts x {mock, sql}, UI, linter
python tools/validate_boundaries.py
```

Requires Python 3.11+ with `tkinter` (included in the standard installers).
`pytest` is the only dev dependency.

## How the pattern works

1. **Contract first.** The architect session writes `contracts/` and the
   contract tests. Nothing else exists yet.
2. **UI in parallel.** The UI session receives feature objects through the
   `MainWindow` constructor and codes only against the ABCs. It ships its own
   mocks so the window runs on day one.
3. **Features in parallel.** Each feature session implements one ABC. It must
   pass the same contract tests the mock passes, which proves it is a
   drop-in replacement.
4. **Wire-up.** The integration session builds the objects in
   `src/container/` and injects them. `main.py` is the only place the UI and
   the features meet.

## Rules

- The UI never does work: no SQL, HTTP, file I/O or computation.
- Features never format for display: raw dataclasses or `contracts` exceptions only.
- Every public class in `src/features/` subclasses a `contracts` ABC. Private
  helpers (functions or classes) are fine.
- No module-level logic that does work at import time. Construction happens
  in the container.
- Change the contract first. A session that needs a new parameter edits
  `contracts/`, not its own signature.
- Timestamps are timezone-aware UTC.

The first four are enforced by `tools/validate_boundaries.py` where a static
check can; the rest are review criteria. See `CLAUDE.md` for the version the
sessions read.

## Adding a feature

1. Architect: add `contracts/<feature>.py`, re-export from
   `contracts/__init__.py`, write `tests/test_contract_<feature>.py`.
2. UI: add a mock in `src/ui/mocks.py`, add the widget flow, add the
   exception rows to `src/ui/errors.py`.
3. Feature: implement in `src/features/<feature>.py`, register in
   `tests/conftest.py`.
4. Integration: construct it in `src/container/wiring.py`, inject it in
   `MainWindow`.

## Design notes

- `DataProcessor` implementations take a `UserAuthenticator` so that session
  validation has one owner. The processor never looks inside a `Session`; it
  asks the authenticator.
- `Session` is opaque to the UI by contract. The UI stores it and passes it
  back, nothing more.
- Password hashing is stdlib PBKDF2-HMAC-SHA256 with a per-user salt. Swap
  the `_hash` helper for argon2 if you add the dependency.
