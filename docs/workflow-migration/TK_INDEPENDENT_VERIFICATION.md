# Tk-independent non-UI verification

This bounded follow-up removes an inherited test-collection dependency on Tk.
It does not complete the broader headless-template migration.

`src.ui` previously imported `main_window` eagerly. Loading the shared mocks
from `tests/conftest.py` therefore required `tkinter` even for unrelated
contract and workflow tests. The package now loads the window class when
`MainWindow` is explicitly requested. Its existing public re-export, the demo
entrypoint, application ABCs, mocks and production behavior remain compatible.
The explicit `__all__` and type-checking import preserve the declared export.

The new regression uses fresh Python subprocesses that reject every Tk import.
It checks collection of all non-UI regressions, excluding the separate frozen
approval module, and executes the shared mock/SQL contract and boundary tests.
The complete Docker campaigns are collected but not executed by this regression.
Both cases failed at the original eager import before the production fix and
passed afterward. This is controlled import-denial evidence on Windows Python
3.12.10, not a claim that Tk was physically uninstalled.

## Verification

Commands ran from the retained migration worktree unless noted otherwise:

| Check | Actual result |
| --- | --- |
| `python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_headless_imports.py tests/test_contract_auth.py tests/test_contract_data.py tests/test_boundaries.py tests/test_ui.py` | 57 passed in 2.68 seconds, including both existing window cases. |
| Same command in a tracked-files-only export with the new regression included | 56 passed, 1 existing Tk skip in 2.88 seconds. The skip reports unavailable Tcl `auto.tcl`; this intermittent case remains tracked in issue #4. |
| `python -B tools/check_workflow_approval.py` | 46 passed locally; 46 passed in the export. Actual ACTIVE receipt SHA256 remained `33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f`. |
| `python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active` | Passed; fingerprint remains `8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`. |
| `python -B tools/validate_boundaries.py` | Passed. |
| `python -B main.py --help` | Passed through the compatible public window import. |
| `ruff check src/ui/__init__.py tests/test_headless_imports.py` | Passed. |
| `ruff format --check src/ui/__init__.py tests/test_headless_imports.py` | Passed. |
| `uvx --offline ty check src/ui/__init__.py tests/test_headless_imports.py` in the export | Passed. |
| `python -B -m pip install --dry-run --no-deps --no-build-isolation -e .` in the export | Editable metadata preparation passed. This did not install dependencies or prove a clean-machine installation. |
| `git diff --check` | Passed. |

The export uses the same installed interpreter/dependencies. It contains
tracked working files and the new regression, excluding the absent local plan
and untracked original-goals brief. It is not a new activated project.

## Preservation and scope

Exactly two existing tracked files change: the UI package initializer and the
root README. The new regression and this evidence note are additive. All
approval-bound files and all six frozen M6 source hashes still match. Both
protected checkout HEADs, worktree/index entries and raw indexes match the frozen
approval record. The original checkout's upstream behind-count reflects later
authorized main deliveries; that tracking count is not a protected-file change.
The staged plan and untracked original-goals brief are excluded from delivery.

Historical M1-M6 evidence and raw-byte preservation baselines are not rewritten.
Their unchanged-file audits describe their original milestone snapshots; this
authorized follow-up records its own two-file delta. No broad Docker campaign,
worker, live provider or hardware check ran for this package. The existing
M6 BasedPyright diagnostics are not claimed resolved by the scoped ty result.

The README now documents focused checks, explicit non-UI collection, separate
GUI coverage, the frozen approval projection, declared dependencies and the
Windows workflow Python minimum. Full headless cleanup, project generation,
platform entrypoints, CI and consolidated fresh-checkout setup remain separate
work packages. No resources or approval boundaries are enabled or widened.
