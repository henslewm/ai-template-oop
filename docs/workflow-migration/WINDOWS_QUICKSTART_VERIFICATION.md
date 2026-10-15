# Windows operator quickstart verification

This bounded follow-up proves the existing M2–M6 path without changing any
controller, application interface, approval-bound file or historical evidence.
The only demonstrated setup defect was untracked `src/ai_template_oop.egg-info/`
after the documented editable install. Adding `*.egg-info/` to `.gitignore`
keeps generated installation metadata out of worktree-cleanliness checks.
No setup dependency or controller capability was missing in the exercised path.

## Environment and isolation

Observed 2026-10-15 UTC (2026-10-14 America/New_York). Initial source was fetched
main `b482b96823e0cef06ad7c93a3b44d99ddd1fa99e`; retained migration HEAD was
`9ed60b9e7a03f90ae50f72ded0d48dd39513d143`. Original `main` checkout retained its
local divergent commit and staged deletion; it was not synchronized or edited.

An independent `git clone --no-hardlinks --no-checkout` of the retained repository
was checked out at exact main into
`C:\Users\hensl\AppData\Local\Temp\operator-workflow-29lg7q3j\clean`.
It had no tracked/untracked work before setup. A new virtual environment at
`..\venv` used no system site packages. Delivery edits were isolated on
`feature/operator-quickstart` there. The new test creates a further disposable
fixture Git repository and real SQLite journals under pytest's new basetemp;
fixture authority never touches the source clone's ACTIVE receipt or canonical
state. The clone's `foundation`/`directory` inspections create no storage.

| Component | Observed identity |
| --- | --- |
| Host | Windows 11 `10.0.26300`, AMD64; PowerShell 7.6.6 |
| Python | CPython 3.12.10, MSC v.1943, 64 bit |
| Git | 2.55.0.windows.5 |
| New venv | pip 25.0.1, pytest 9.1.1, jsonschema 4.26.0 |
| Docker | Desktop 4.94.0 (241994), engine 29.8.2, API 1.56, Linux amd64 |
| Kernel | `6.18.54.1-microsoft-standard-WSL2` |
| Image | `sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e`, locally inspected as linux/amd64 |

Installed transitive packages: attrs 26.1.0, colorama 0.4.6, iniconfig 2.3.1,
jsonschema-specifications 2025.9.1, packaging 26.3, pluggy 1.6.0, Pygments 2.21.0,
referencing 0.37.0, rpds-py 2026.9.1, typing_extensions 4.16.0. Package installation
used normal cache/index access. There were no provider/model calls; all four
task/check containers used the existing network-none boundary.

## Actual commands and outcomes

Commands below ran from the independent clone. `$Python` represents the exact
new `..\venv\Scripts\python.exe`; `WORKFLOW_TEST_IMAGE` was the full image ID above.
Logs and original preservation snapshots are retained in the temporary parent.

| Command | Result |
| --- | --- |
| `python -m venv venv` (temporary parent), then `& '../venv/Scripts/python.exe' -m pip install -e '.[dev]'` (clone) | Actual editable install and dependency installation succeeded; metadata artifact exposed the ignore defect. |
| `& $Python -m pip check` | No broken requirements. |
| `& $Python -B scripts/validate_workflow_approval.py --fingerprint --require-active` | ACTIVE valid; fingerprint `8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`; live workers/publication disabled. |
| `& $Python -B scripts/workflow_state.py foundation` and `directory` | Correct fingerprint and distinct clone-specific canonical path; no initialization. |
| `& $Python -B -m pytest -q -s -rs -p no:cacheprovider -o addopts= tests/test_operator_workflow.py --basetemp='../proof-initial'` | **1 passed in 60.60s**; no skips. Basetemp was new. |
| `& $Python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_contract_auth.py tests/test_contract_data.py tests/test_boundaries.py tests/test_headless_imports.py` | **43 passed in 3.08s**; no skips. |
| `& $Python -B tools/check_workflow_approval.py` | **46 passed in 1.97s**; actual clone ACTIVE receipt preserved. |
| `& $Python -B tools/validate_boundaries.py` | Boundaries OK. |
| Same operator test without `WORKFLOW_TEST_IMAGE`, new `--basetemp='../proof-no-image'` | **1 explicit skip in 0.74s**; this is intentionally not worker/acceptance proof. The quickstart checks that a proof artifact exists. |
| `ruff check tests/test_operator_workflow.py` and `ruff format --check tests/test_operator_workflow.py` | Passed. |
| `uvx --offline ty check --python '../venv/Scripts/python.exe' tests/test_operator_workflow.py` | Passed. A first check against the ambient environment reported the positional `pytest.skip` argument; using `reason=` and the actual venv resolved the scoped check. |
| `git diff --check` | Passed. |

The initial real proof's `operator-proof.json` records one settled unmetered
worker attempt, no liability/unknown usage, three distinct stopped check log
references, exact packet/scope/input commits/replacement/candidate bindings,
resumed prepared action, and `ACCEPTED` synchronization. The host fixture file
remained `VALUE = 1`. Checks observed `VALUE = 2` in fresh immutable exports.
All four Docker boundaries/stopped states were inspected before removing only
the proof's own stopped container pairs/volumes. Disk evidence remains.

The integration assessment first returned HOLD for the absent retention
baseline, then `READY_FOR_EXPLICIT_INTEGRATION` after supplying the observed
fixture baseline. Check logs are real; the independent review declaration and
hosting facts are **synthetic fixture inputs**. No live task PR, independent
human review or real hosting approval is claimed by this result. Integration
and deployment remained `NOT_ESTABLISHED`; merge/execution authority was false.

## Preservation and limits

The clone's raw receipt SHA256 is
`28803d74d76b27272145cad0f0cc000ba50723cee463ce8f7af39564140cb5d2`.
The original retained checkout's raw receipt is
`33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f`.
These different checkout byte representations validate to the same frozen
fingerprint; neither receipt was rewritten. No foundation/baseline was refreshed.

The staged `Original_plan.md` blob/absent working file, untracked original-goals
brief, native index, protected checkout indexes/HEADs/status and canonical state
were inventoried separately from delivery. Donor working files were not read;
only Git/index metadata was inspected. Permanent branches remain retained.

Broad M1–M6 campaigns, GUI execution, image rebuild, full repository typing,
live provider transport, physical hardware and deployment were deliberately
not run. No old acceptance status is upgraded. Missing trusted local image or
Docker blocks the real proof; no portable image distribution is established.
The shipped zero-budget/disabled policy still blocks real project execution
until separately enabled by the owner. Existing BasedPyright diagnostics and
the tracked intermittent GUI/Tcl issue are outside this package.
