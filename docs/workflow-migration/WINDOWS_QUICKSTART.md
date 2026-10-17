# Windows quickstart: existing offline operator workflow

This is the current starting point after M1–M6 and the Tk-independent fix.
Use PowerShell, Python **3.12+**, Git, and Docker Desktop's Linux engine.
Tk is not needed; the demo window was removed (`HEADLESS_TEMPLATE.md`). The walkthrough uses no model, provider,
credential, hardware ingestion or deployment. Dependency installation needs
package-index access; the worker and acceptance containers have network disabled.

The shipped ACTIVE receipt still disables live workers/resources and sets real
API budgets to USD 0. Do not edit it to run this walkthrough. Fixture authority
exists only inside pytest's new temporary repository and state. This proves
operation of the existing controllers, not general project activation or the
completion of the broader reusable headless template.

## 1. Install in an independent clean clone

Run this from a scratch parent directory. Choose a new destination name; do not
reuse a protected checkout or use `git worktree add` for this exercise. Worktrees
share canonical state through their Git common directory; independent clones do
not. The commands assume `python` selects Python 3.12 or newer.

```powershell
git clone --branch main --single-branch https://github.com/henslewm/ai-template-oop.git ai-template-operator
if ($LASTEXITCODE) { throw 'clone failed' }
Set-Location ai-template-operator
git status --short --branch
git rev-parse HEAD
python --version
python -m venv .venv
if ($LASTEXITCODE) { throw 'venv failed' }
$Python = (Resolve-Path .venv/Scripts/python.exe).Path
& $Python -m pip install -e '.[dev]'
if ($LASTEXITCODE) { throw 'install failed' }
& $Python -m pip check
if ($LASTEXITCODE) { throw 'dependency check failed' }
git status --short
```

The last command should be empty. Editable installation produces `src/*.egg-info`;
it and `.venv` are ignored. No PowerShell activation-policy change is needed.
Run the scripts from the repository root; this is a source-checkout workflow,
not a standalone installed CLI distribution.

## 2. Inspect authority and run focused non-GUI checks

```powershell
& $Python -B scripts/validate_workflow_approval.py --fingerprint --require-active
if ($LASTEXITCODE) { throw 'approval check failed' }
& $Python -B scripts/workflow_state.py foundation
if ($LASTEXITCODE) { throw 'foundation check failed' }
& $Python -B scripts/workflow_state.py directory
if ($LASTEXITCODE) { throw 'state resolution failed' }
& $Python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_contract_auth.py tests/test_contract_data.py tests/test_boundaries.py tests/test_headless_imports.py
if ($LASTEXITCODE) { throw 'focused checks failed' }
& $Python -B tools/check_workflow_approval.py
if ($LASTEXITCODE) { throw 'approval projection failed' }
```

The foundation fingerprint is
`8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
`foundation` and `directory` do not initialize state. The frozen approval runner
uses an inactive disposable projection and verifies the real ACTIVE receipt is
unchanged. Do not execute `tests/test_workflow_approval.py` directly against ACTIVE.

Skip `--check-source` in a portable clone: it requires the recorded sibling donor
repository and pinned commit. If separately inspecting that donor, read only
`git show d6e582b7edeae24345a175f36639230726dbdead:<path>` and pinned object metadata.
The `--check-preserved` and `--check-baseline` flags and historical preservation
tools describe original frozen checkouts, indexes and milestone snapshots; they
are not portable setup checks. Do not refresh those baselines to make a clone pass.

## 3. Confirm the immutable local runtime image

```powershell
docker version
if ($LASTEXITCODE) { throw 'Docker Linux engine unavailable' }
$env:WORKFLOW_TEST_IMAGE = 'sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e'
docker image inspect $env:WORKFLOW_TEST_IMAGE --format '{{.Id}} {{.Os}}/{{.Architecture}}'
if ($LASTEXITCODE) { throw 'Required trusted local image is missing' }
```

Expected: the same full SHA256, `linux/amd64`. This image must already be loaded
from a trusted artifact. It is a local image identity, not a promised publicly
pullable registry reference. [The runtime Dockerfile](../../runtime/workflow/Dockerfile)
records its build inputs; rebuilding is not demonstrated here and need not
reproduce this exact image. Missing Docker/image is a blocker to the real proof.
Do not treat an image-related skip as success or substitute a mutable tag.

## 4. Execute one disposable operator task

Use a **new** proof directory on every invocation. Pytest clears an existing
`--basetemp` directory, so never point it at earlier evidence or live state.

```powershell
$ProofRoot = Join-Path $env:TEMP ('ai-template-operator-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $ProofRoot) { throw 'Proof directory must be new' }
& $Python -B -m pytest -q -s -rs -p no:cacheprovider -o addopts= tests/test_operator_workflow.py --basetemp=$ProofRoot
if ($LASTEXITCODE) { throw 'Operator proof failed; preserve its state for inspection' }
$Proof = Join-Path $ProofRoot 'test_offline_operator_workflow0/operator-proof.json'
if (-not (Test-Path -LiteralPath $Proof)) { throw 'Proof absent (possibly skipped)' }
Get-Content -LiteralPath $Proof | ConvertFrom-Json | Select-Object authority,hosting,image,native_status,attempts,accounting,hardware
```

Expected: **1 passed**, no skips; authority `DISPOSABLE_FIXTURE_ONLY`, native status
`ACCEPTED`, one worker attempt, zero settled cost/liability and hardware
`UNVERIFIED_ON_HARDWARE`. This is a deterministic file-replacement fixture, not an
AI coding task. The test composes existing APIs; no new controller is introduced.

| Stage | Existing operation and demonstrated outcome |
| --- | --- |
| Packet and scope | `work_packet.create/transition` prepares `OPERATOR` in READY; `feedback.initialize` binds it to accounts. `SessionScope.load` binds current branch/base, packet revision, interface digest, exact reads and only `src/features/auth.py` as writable. |
| Preparation | `execution_harness.dispatch` reserves once and prepares the exact export. Harness/router enablement, clock and approval anchor are fixture-only substitutions inherited from the existing test fixtures. |
| Handoff/resume | `workflow_handoff.build` saves PREPARED facts. A new `Journal` instance reloads the disk view; `resume` returns `INSPECT_THEN_EXPLICIT_LAUNCH_OR_ABANDON`, with no execution or retry authority and unchanged journal heads. After launch the old view refuses as stale. |
| Offline worker | `worker_launcher.prepared_run/launch` runs Python in Docker, changes fixture `VALUE = 1` to `VALUE = 2`, and emits the exact bound report. `execution_harness.ingest` records `INDEPENDENT_ACCEPTANCE_PENDING`; the host fixture stays `VALUE = 1`. |
| Independent acceptance | `acceptance.initialize` binds exact input commits and unapplied replacement. Early `accept` refuses. `acceptance_runtime.prepare_check/launch_check/ingest_check` then executes contract, boundary and affected-runtime checks in three distinct read-only candidate exports. The independent named fixture actor accepts; `sync_feedback` records ACCEPTED and replays identically. |
| Readiness inspection | A trusted test helper prepares an exact Git candidate object without applying it. `candidate_tree/record_validation/assess` bind the three real stopped check logs and a **synthetic independent review declaration**. Hosting facts are **simulated**, with no live PR, check, review or branch push. Missing retention baseline yields HOLD; supplying the observed baseline yields `READY_FOR_EXPLICIT_INTEGRATION`. Merge/execution authority stays false; integration/deployment remain `NOT_ESTABLISHED`. |

The exported packet/scope, saved view, `operator-proof.json`, real SQLite stores,
stopped archives, replacement and digest-bound logs remain under `$ProofRoot`.
Successful completion removes only the proof's four stopped Docker container
pairs and volumes. It retains disk evidence and all fixture branches. A failed
preparation may retain Docker objects/ownership for explicit inspection; do not
delete state or retry a consumed start to bypass the existing recovery rules.
The proof's prepared handoff is intentionally stale after execution, and its
readiness result is historical fixture evidence, not current live authority.

The fixture checks test this tiny candidate and isolation boundary. The actual
application's ABC/mock/SQL/boundary checks run separately in step 2. Actor names,
the fixture anchor and host observations are coordinator declarations; this
does not authenticate a real independent human reviewer or prove live hosting.

## 5. Use the existing operations for real coordinator work

The following inspection commands are safe to consult in a source checkout:

```powershell
& $Python -B scripts/work_packet.py --help
& $Python -B scripts/feedback.py --help
& $Python -B scripts/execution_harness.py --help
& $Python -B scripts/worker_launcher.py --help
& $Python -B scripts/acceptance.py --help
& $Python -B scripts/workflow_handoff.py --help
& $Python -B scripts/workflow_closeout.py --help
```

For an already provisioned authorized Journal, use the existing CLI forms:

```powershell
& $Python -B scripts/workflow_state.py verify
& $Python -B scripts/workflow_handoff.py view --audience startup
# For an existing task/saved view, replace these example paths/identity:
& $Python -B scripts/workflow_handoff.py view --task task:EXAMPLE --audience coordinator
& $Python -B scripts/workflow_handoff.py resume C:\path\to\saved-view.json
```

An absent journal is expected in a new clone. Do not initialize canonical state
or copy fixture policy into it just to make examples work. Real execution still
requires separate owner enablement; the shipped foundation does not provide it.
Initialization/account provisioning and packet preparation are explicit Python
coordinator APIs, not an automatic one-command project bootstrap.

Continue with the stage-specific references when operating beyond the proof:

- [M2 operations](M2_OPERATIONS.md): canonical Journal, explicit initialization,
  verify/recover, evidence, export, backup and restore.
- [M3 operations](M3_OPERATIONS.md): account/task initialization, reservation,
  lifetime attempts, settlement and unknown-cost holds.
- [M4 operations](M4_OPERATIONS.md): dispatch, explicit launch, exact stopped
  output ingestion and reconciliation; never automatic application.
- [M5 operations](M5_OPERATIONS.md): independent checks, risk/review gates,
  acceptance and synchronization; manual/hardware ingestion stays disabled.
- [M6 operations](M6_OPERATIONS.md): fresh bounded views (300-second expiry),
  resume, approved context and exact-candidate/live-host readiness requirements.
- [Tk-independent verification](TK_INDEPENDENT_VERIFICATION.md): non-GUI import
  scope and separate GUI checks. This quickstart does not launch the Tk demo.
- [Recorded quickstart verification](WINDOWS_QUICKSTART_VERIFICATION.md): actual
  environment, commands, results, limits and preservation for this delivery.

Live readiness requires a separate exact candidate, real independent scoped
review, observed checks, current GitHub PR/rules/review threads and a retained-ref
baseline. A simulated READY or worker PASS cannot replace those facts. Keep
automatic branch deletion disabled; never delete permanent branches, reset them
or force-push. Merge only through currently supported hosting rules, then normally
synchronize the retained feature branch. Readiness itself never merges or deploys.
