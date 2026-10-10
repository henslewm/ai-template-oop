# Session prompts

Copy the block for the session you are starting. Every session also gets
`CLAUDE.md` automatically and should be pointed at `contracts/`.

---

## Session 0: Architect (the contract)

> I am building an app with a separated UI and business-logic layer. The
> contract lives in `contracts/`, one module per feature, re-exported from
> `contracts/__init__.py`. Write (or amend) the abstract base classes, frozen
> dataclasses and exception hierarchy for `<feature>`. Complete type hints and
> docstrings that state every exception each method may raise. Interfaces
> return raw data or raise `contracts` exceptions; they never return display
> strings. Do not write implementations or UI code. Then add contract tests
> under `tests/test_contract_<feature>.py` that any implementation must pass.

---

## Session A: UI (the shell)

> You are building the UI for this application against `contracts/`.
>
> Constraints:
> - Do not write any business logic or data-processing code. No `sqlite3`,
>   `requests`, file I/O or computation in `src/ui/`.
> - Use dependency injection. `MainWindow` accepts instances of every
>   `contracts` ABC through its constructor and never instantiates a feature
>   class.
> - Every button handler parses input, makes exactly one interface call, and
>   renders the result or the exception. Exception-to-text lives only in
>   `src/ui/errors.py`.
> - Keep `src/ui/mocks.py` contract-complete so `python main.py --mock` and
>   the contract tests keep passing.
> - Run `python -m pytest` before you finish.

---

## Session B, C, ...: Feature (a worker)

> Write the concrete, production-ready implementation of
> `contracts.<Interface>` in `src/features/<feature>.py`.
>
> Constraints:
> - Strict OOP. One public class, `<Name>`, that implements the ABC exactly:
>   same method names, parameters, return types and exceptions. Private
>   helper methods, classes and functions are fine.
> - Do not write any UI code or display strings. Return the dataclasses and
>   raise the exceptions defined in `contracts/`. Wrap storage failures in
>   `StorageError`.
> - Validate domain rules (password policy, empty input) here; the UI handles
>   syntax.
> - Register your class in `IMPLEMENTATIONS` in `tests/conftest.py` and make
>   `python -m pytest` pass. Do not edit the contract tests to make them pass;
>   if the contract is wrong, say so and stop.
> - If you need something the contract does not give you, do not change your
>   own signature. Propose the change to `contracts/` in your final message.

---

## Session D: Integration (the wire-up)

> Wire the implementations together in `src/container/wiring.py` and
> `main.py`. The container is the only package that may import both
> `src.ui` and `src.features`. Add a builder per environment (`build_mock`,
> `build_production`, ...) rather than branching inside the UI or features.
> Run `python main.py --mock`, `python main.py`, and `python -m pytest`.

---

## Rules for maintaining this workflow

1. Never let the UI session write SQL, API calls or file-system operations.
   If it tries to `import sqlite3` or `import requests`, reject it and push
   that work behind an interface method.
2. Never let a feature session format strings for display. Feature objects
   return raw data or raise exceptions. The UI translates a
   `StorageError` into a status-bar message.
3. When a feature needs to change, update the contract first. Then hand the
   updated `contracts/` to the UI session and tell it to update its calls.
4. The contract tests are the acceptance gate. A feature class is done when
   it passes the same tests as the mock. The boundary linter is the
   structural gate. Both run under `python -m pytest`.
