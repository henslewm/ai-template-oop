# Session rules

This repo is built by several AI sessions working in parallel. Before you edit
anything, know which session you are. The prompts in `PROMPTS.md` say so.

## Layout

| Path             | Owner session | May import                              |
| ---------------- | ------------- | --------------------------------------- |
| `contracts/`     | Architect     | stdlib only                             |
| `src/ui/`        | UI            | `contracts`, `src.ui`, toolkit          |
| `src/features/`  | Feature       | `contracts`, `src.features`, stdlib I/O |
| `src/container/` | Integration   | anything                                |
| `tests/`         | anyone        | anything                                |

`tools/validate_boundaries.py` enforces the import rules and runs as part of
`pytest`. Do not work around it; if the rule is wrong, change the rule.

## Rules

1. Change the contract first. If you need a new parameter, return field or
   exception, edit `contracts/` and say so in your final message. Never widen
   your own class's public signature beyond what the ABC declares.
2. The UI never does work. No SQL, HTTP, file I/O, or computation. Parse the
   input, call one interface method, render the result or the error.
3. Features never format for display. Return frozen dataclasses or raise a
   `contracts` exception. No strings meant for humans.
4. Every public class in `src/features/` subclasses a `contracts` ABC. Private
   helper classes and private module-level helpers are fine.
5. No module-level code that does work at import time (opens files, connects,
   reads env). Construction happens in `src/container/`.
6. Every implementation, including the mocks, passes `tests/test_contract_*`.
   Add your implementation to `IMPLEMENTATIONS` in `tests/conftest.py`.
7. Timestamps are timezone-aware UTC.

## Review criteria (not linted)

- No placeholder comments (`# TODO: implement`), no silently omitted branches.
- No `print` in `src/`; errors travel as exceptions.

## Commands

```
python main.py --mock     # run the UI with in-memory services (demo / demo1234)
python main.py            # run with SQLite (app.db)
python -m pytest          # contract tests + UI tests + boundary linter
python tools/validate_boundaries.py
```
