# Headless template: Tk demo removed

Recorded 2026-10-17 UTC. Owner decision on
[issue #28](https://github.com/henslewm/ai-template-oop/issues/28): option 1,
remove the Tk demo and keep the backend as a headless example.

This file is the current, unbound record of that change. It exists because
`CLAUDE.md` and `PROMPTS.md` are approval-bound (`config/workflow-bootstrap.json`
`bound_files`); editing them would withdraw the ACTIVE foundation approval, so
their stale lines are corrected here instead (`MASTER_INSTRUCTIONS.md`,
"Foundation gate").

## What changed

| Before | After |
| --- | --- |
| `src/ui/` (Tk `MainWindow`, `errors.py`, lazy `__init__.py`) | Removed |
| `src/ui/mocks.py` | Moved unchanged in behavior to `src/testing/fakes.py` (same layout the generator already produced) |
| `main.py` (Tk entry point) | Removed. A runnable headless CLI is what `tools/project_intake.py` / `tools/generate_example.py` generate |
| `tests/test_ui.py` | Removed. Plain `python -m pytest` no longer needs Tk to collect |
| Boundary rule `src/ui` | Replaced by `src/testing`: may not import `src.features`, `src.container`, I/O or UI toolkits; features may not import `src.testing` |
| Generator manifest copied `src/ui/mocks.py` and rewrote the conftest import | Copies `src/testing/fakes.py`; the conftest rewrite is gone because the root already imports `src.testing.fakes` |

The SQLite features, contracts, composition root and shared contract tests
are unchanged. The ACTIVE gate still validates: removed files were only in
`baseline_files`, which `--require-active` does not enforce.

## Read these frozen lines as corrected

| Frozen text | Read as |
| --- | --- |
| `CLAUDE.md` layout row `src/ui/` (UI session) | No UI layer ships. `src/testing/` holds the in-memory fakes; whoever changes a contract keeps them contract-complete |
| `CLAUDE.md` rule 2 "The UI never does work" | Still binding for any presentation layer a generated project adds (`src/presentation/` in generated output) |
| `CLAUDE.md` rule 6 "including the mocks" | The fakes in `src/testing/fakes.py` |
| `CLAUDE.md` commands `python main.py --mock`, `python main.py` | Removed. Run a generated project's `main.py` instead (`SOFTWARE_INTAKE.md`) |
| `CLAUDE.md` `python -m pytest` "contract tests + UI tests + boundary linter" | No UI tests. Prefer the focused command in `WINDOWS_QUICKSTART.md` step 2; the full suite is slow and includes Docker-gated tests |
| `PROMPTS.md` "Session A: UI" | Not used in this repository. Generated projects with a presentation layer may reuse it, substituting their own paths |
| `PROMPTS.md` Integration session `main.py`, `src.ui` | `src/container/` only; it is the only package that may import both `src.testing` and `src.features` |

## Not changed (follow-up candidates)

- `scripts/workflow_scope.py` and `scripts/workflow_closeout.py` still model a
  UI worker role with `src/ui/` roots and `src/ui/mocks.py` as the mocks path.
  They operate on scoped packets, not on the root tree, and their tests use
  synthetic paths. Retiring or renaming that role is a separate package.
- Historical records (M1–M6, `TK_INDEPENDENT_VERIFICATION.md`,
  `GENERATED_OOP_EXAMPLE*.md`) describe the tree as it was and are left as is.
- Issue #4 (intermittent Windows Tk skips) has no remaining subject.
