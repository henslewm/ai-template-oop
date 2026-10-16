# B02 handoff: one runnable generated OOP software project

Owner: Claude Code, sole implementation owner. Branch `feature/b02-generated-project`,
base `29a0c25`. Candidate source commit: `b8e9b50`; this handoff and the backlog
row follow in the next commit. Status: **implemented and locally verified; awaiting
independent review.** Not pushed, published or merged. No paid call, worker or
activation was used.

## Owned paths

| Path | Role |
| --- | --- |
| `tools/generate_project.py` | Generator entrypoint (`--dest`, `--slug`) |
| `generator/headless-oop/manifest.json` | Explicit manifest: `copy` (verbatim from template) and `assets` |
| `generator/headless-oop/files/**` | Headless sample assets (CLI, composition root, conftest, tests, boundary checker, README) |
| `tests/test_generate_project.py` | Focused generation tests |

Root application files, `contracts/`, `src/`, approval-bound files and frozen
approval material are unchanged.

## What generation does

1. Refuses a bad slug, a destination inside the template, a non-directory or a
   non-empty directory, all before writing anything.
2. Runs `git init -b main` and byte-copies the manifest entries. The verbatim copies are
   the auth/data/errors contracts, `src/features/{__init__,auth,data}.py`,
   `src/container/__init__.py`, the shared `tests/test_contract_{auth,data}.py` and
   `tests/test_boundaries.py`. The fakes are **relocated**: `src/ui/mocks.py` →
   `src/features/in_memory.py`. `src/ui/errors.py` → `src/cli/errors.py`.
3. Assets add a contracts `__init__` without the workflow operator export, plus a
   `wiring.py` importing the relocated fakes. They also add a thin `src/cli/app.py`
   (parse, call one interface method per step, render, translate errors) and `main.py`,
   along with conftest and CLI/headless tests. The boundary checker gains a `src/cli`
   layer rule and forbids UI toolkits in every layer.
4. Calls `project_authority.initialize` (B01) for a fresh UUID. The project stays
   `AWAITING_APPROVAL`: no approval package, decision, runtime state, key or receipt
   is copied. The only host write is the B01 registration
   `<LOCALAPPDATA>/ai-template-workflow/<hash>/project-authority/identity.json`.
5. Writes `GENERATION.json`: template commit, uncommitted template sources, project
   identity and per-file raw SHA-256 with source path.

## Acceptance evidence

| # | Requirement | Evidence |
| - | --- | --- |
| 1 | Refuse non-empty dest; fresh identity, nothing inherited; distinct UUIDs | `test_refuses_unusable_destinations_without_side_effects`; `test_two_outputs_have_fresh_distinct_unapproved_identities` asserts the exact output file set, no approval package, AWAITING_APPROVAL and host files = registrations only. Proof run: UUIDs `ee901c12-…` and `c75c9a20-…`, refusal exit 1 |
| 2 | Thin CLI over typed interfaces, logic in features, composition root, shared assertions | Verbatim feature/contract-test copies (hash-checked in the test); `src/cli` may not import features/container/I/O (validator plus negative fixture) |
| 3 | Documented command runs; both variants and boundary checks pass without Tk | `test_generated_project_runs_cli_and_both_implementation_variants`; generated `tests/test_headless.py` runs the CLI and checks under a Tk-blocking import hook |
| 4 | Worker scope / reviewer separation | No worker was used. The reviewer regenerates independently (below). Tests do not accept the package |
| 5 | Identities, commands, results, limits | This document |

## Proof run (from committed `b8e9b50`, `LOCALAPPDATA` = scratchpad)

- Generation of A and B: exit 0, 25 files each. `GENERATION.json` `template.commit` = `b8e9b50c11e08790164769c242d1c4174af21396`, `uncommitted_sources: []`.
- `project_admin.py --root <A> status` returns `AWAITING_APPROVAL`. A second generation into A returns `GENERATION REFUSED … not empty`, exit 1.
- In A, `python main.py --mock process demo demo1234 1 2 3 10` exits 0 and prints `record 1: count=4 total=16 mean=4 min=1 max=10 at …+00:00`.
- `-k mock` contract tests: **20 passed**; `-k sql`: **20 passed**; full generated suite: **55 passed**; `tools/validate_boundaries.py`: `Boundaries OK.`
- Host focused run (generation, boundaries, contracts, headless imports, project authority): **81 passed**. `ruff check`/`ruff format` are clean on the authored files. The derived `wiring.py`, `conftest.py` and validator keep host formatting.

Raw SHA-256 at `b8e9b50`:

| Path | SHA-256 |
| --- | --- |
| `tools/generate_project.py` | `971165244055f46cbae0a02d7ce97195b59be65c74cd2460a1360e1438171b84` |
| `generator/headless-oop/manifest.json` | `b088a9f733d6cc63ec0b0175a730045b64cbaefb0436de381432ca7df1d5a7ec` |
| `tests/test_generate_project.py` | `b265959a61b56b4bf9348647d3a21791ae54e0f1a25e7755ca6595c9244d1b1a` |
| `generator/headless-oop/files/src/cli/app.py` | `201bb296bbad104d67c1a590faf7b95bbb6c2446821760cbf2b04279c2e14ca5` |

## Reviewer commands

Windows Python 3.12+ with the template's dev dependencies (`pytest`, `jsonschema`).
Point `LOCALAPPDATA` at a throwaway directory so registrations stay out of the real host state.

```powershell
$T = Join-Path $env:TEMP "b02-review-$(Get-Random)"
$env:LOCALAPPDATA = "$T\host state"
python -B tools/generate_project.py --dest "$T\out" --slug review-sample
python -B tools/generate_project.py --dest "$T\out" --slug again          # expect exit 1
python -B tools/project_admin.py --root "$T\out" status                    # AWAITING_APPROVAL
Push-Location "$T\out"
python main.py --mock process demo demo1234 1 2 3 10                       # count=4 total=16 mean=4 min=1 max=10
python -m pytest -p no:cacheprovider -rA -k mock tests/test_contract_auth.py tests/test_contract_data.py   # 20 passed
python -m pytest -p no:cacheprovider -rA -k sql  tests/test_contract_auth.py tests/test_contract_data.py   # 20 passed
python -m pytest -p no:cacheprovider                                       # 55 passed
python tools/validate_boundaries.py                                        # Boundaries OK.
Pop-Location
python -B -m pytest -q -p no:cacheprovider -o addopts= tests/test_generate_project.py tests/test_boundaries.py tests/test_contract_auth.py tests/test_contract_data.py tests/test_headless_imports.py tests/test_project_authority.py   # 81 passed
```

## Limits and known issues

- **Pre-existing, not B02:** `tests/test_workflow_approval.py` gives **4 failed, 42 passed**
  (inactive package, `<lambda>17`, receipt fields, CLI activation: receipt state is
  `ACTIVE` where tests expect `AWAITING_APPROVAL`). The identical result reproduces at
  clean `29a0c25` with B02 files moved aside. B01 recorded 46 passed; this needs a
  separately scoped look and was not changed here.
- The generated project cannot `review`/`activate` itself. B01's inventory requires the
  workflow controller scripts, whose closure needs jsonschema and schemas. Activation, if
  ever wanted, runs host tooling with `--root`.
- The host generator imports `project_authority` → `workflow_state` → `work_packet`, so it
  needs the template's dev dependency `jsonschema`. The generated project needs only `pytest`.
- Each generation leaves a B01 host registration under `LOCALAPPDATA`; B01 provides no cleanup.
- The relocated `in_memory.py` docstring still says "UI": it is a verbatim, hash-traceable copy.
- The refusal message's "partial output left in place" line also prints for pre-write refusals.
- CLI passwords are positional arguments (visible in shell history); the README says so.
- Out of scope: Tk/UI removal from the template (B03), CI (B05), hardware generation (B07).
