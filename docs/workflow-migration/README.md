# Offline packet scope and ownership controls

Status: implemented and tested locally; uncommitted, unintegrated, undeployed.
Destination base: `a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4`.
Worktree: `ai-template-oop-workflow-migration`, branch `feature/workflow-migration`.

The destination-specific architecture and bootstrap proposal is now prepared in
`ARCHITECTURE.md`, `BOOTSTRAP_REVIEW.md` and `config/workflow-bootstrap.json`.
Validate it with `python -B scripts/validate_workflow_approval.py --fingerprint
--check-source --check-preserved --check-baseline`. It remains AWAITING_APPROVAL with autonomy off;
the proposal does not activate controllers or resolve the startup-token retry
blocker recorded in HANDOFF.md. Its acceptance criteria remain pending.

This is a coordinator-operated, offline implementation of packet scope and local
ownership. It does not replace the source routing, feedback, acceptance or
metered-launch controllers. It does not apply returned edits or approve work.

## Enforced boundary

Docker Desktop's Linux engine runs an immutable image as UID/GID 1000, with
network disabled, a read-only root, all capabilities dropped and
no-new-privileges. It receives one fresh Docker-managed volume containing only
the approved packet, scope, baseline and enumerated files. There are no host
bind mounts, Git objects, sockets, host credentials or repository connectors.

Directories and immutable input files are root-owned. Only explicitly named
owned files are writable. Shell commands run inside the same container.
Scratch space is bounded tmpfs; memory, CPUs, process count, log rotation and
file size are bounded. A fixed, offline root initializer assigns writable-file
ownership before the worker is created; it receives no host files or tools.

These controls assume a trusted Docker Desktop daemon, coordinator, runtime
image and Linux kernel. They are not a proof against kernel vulnerabilities or
a hostile host administrator. Cross-machine and cross-account coordination
is not implemented.

## Packet and scope

The canonical packet and its original schema are unchanged. Scope is a
separate immutable session manifest bound to the current packet revision hash,
base commit, interface-file digest, branch and workspace. It is not another
task or budget ledger. Source dependency gating still requires VERIFIED
dependencies; risk/review floors are unchanged.

Manifest version 1.0 requires exactly these fields:

- `schema_version`: `1.0`.
- `role`: `feature` or `ui`; `feature_id`, `owner`, `run_id`.
- `branch`: retained `feature/...` or `ui/...`; `workspace`: absolute checkout root.
- `base_commit`: full current SHA; `packet_revision_hash`: canonical packet revision hash.
- `interface_revision`: SHA256 of canonical JSON mapping each supplied
  `contracts/...` path to that file's SHA256. This is distinct from the
  canonical packet revision and its application interface version.
- `read_paths` and `write_paths`: exact POSIX relative file paths, no patterns.

Feature writes are limited to its named implementation, feature-owned tests
and handoff paths; UI writes are limited to UI, UI tests and UI handoffs.
Contracts are always immutable. Sibling-feature implementation reads/writes,
linked files, Git/governance paths and path escapes are refused. No exception
or contract-change approval API is shipped. The owner must approve any future
change to those policies.

Tracked dirty workspaces and stale base/packet/interface/context revisions are
refused. Declared new files require an existing parent directory and become
empty writable placeholders. Up to eight writable files and 128 supplied
files are supported; per-file content is bounded at 2 MiB and initial export
content at 16 MiB. Parent directories are immutable, so editor operations that
replace files by rename are unavailable; direct writes work. Adding directories
or deleting files is not supported.

A returned patch is a JSON file-replacement bundle, not arbitrary unified Git
patch text. It names the scope hash/base and exact paths, original hashes and
base64 content. Links, deletions, duplicate/unexpected paths, changed inputs
and stale bases are refused. Validation never applies or accepts output.

## Ownership and recovery

All worktrees sharing a Git common directory resolve to one host-only control
directory under LOCALAPPDATA/ai-template-workflow on Windows (the user's local
state directory on other hosts). Alternate state paths are refused. SQLite
transactions and unique indexes reserve both branch and workspace atomically.
They record owner, run, scope, container, lease and preservation evidence.

Each new claim also registers startup authority in `startup.sqlite3` in that
same canonical directory. While holding the ownership write lock, start commits
the consumed marker in this separate journal with SQLite synchronous=FULL before
calling Docker. Startup errors, interrupts, failed cleanup and coordinator exit
cannot roll that marker back with the ownership transaction. Repeat or racing
starts with the same token are refused without triggering another run's cleanup.
Retain both ownership and startup databases together; neither is worker-visible.

Existing tokens without startup journal history are refused rather than assumed
unused. They require explicit recovery under the same expired-lease,
confirmed-stopped and preserved-output checks, then a fresh preparation. Recovery
never restores the old token's startup authority. Journal entries left by failed
claim commits cannot authorize startup without an active ownership row.

The default lease is 300 seconds; heartbeat allows 1–3600 seconds. Expiry
never enables takeover or restart automatically. Start and recovery serialize
through the same database lock. Recovery requires an expired lease, confirmed
stopped container tree and a preserved opaque workspace archive. A previous
token is invalid afterwards. A normal finish also preserves output before
releasing ownership. No worker can reach this host database.

Preparation failures leave resources for inspection. Once execute attempts
startup, a Docker error or interrupt also triggers stop confirmation, log capture
and output preservation before ownership is released. If inspection, stopping,
logging or preservation fails, the claim remains for explicit recovery. Further
interrupts wait until cleanup finishes.
A coordinator must stop a live container before recovery; recovery itself
does not kill it. Containers, volumes and run evidence are retained; no
automatic cleanup or retention policy is shipped.

## Implemented commands

Run these from the migration worktree. These are regular Python commands,
not slash commands. Use only approved input files and the retained worker
workspace recorded in them; the coordinator migration worktree is not a
normal isolated worker workspace.

Read-only:

```powershell
python -B scripts/work_packet.py validate "C:\approved\packet.json"
python -B scripts/work_packet.py graph "C:\approved\packet.json"
python -B scripts/workflow_runtime.py state-directory --scope "C:\approved\scope.json"
python -B scripts/workflow_scope.py check-output --scope "C:\run\scope.json" --baseline "C:\run\baseline.json" --bundle "C:\run\bundle.json"
```

The packet graph invocation must include every dependency packet. Packet
validation establishes structure/history; it does not grant execution authority.

Coordinator writes/executes:

```powershell
$stateDirectory = python -B scripts/workflow_runtime.py state-directory --scope "C:\approved\scope.json"
$imageId = docker image inspect ai-template-workflow-runtime:phase1 --format '{{.Id}}'
python -B scripts/workflow_runtime.py prepare --scope "C:\approved\scope.json" --packet "C:\approved\packet.json" --state $stateDirectory --image $imageId -- python --version
# Use the actual run directory printed by prepare.
python -B scripts/workflow_runtime.py heartbeat --run "C:\actual-run" --state $stateDirectory --lease-seconds 300
python -B scripts/workflow_runtime.py execute --run "C:\actual-run" --state $stateDirectory --timeout 60
python -B scripts/workflow_runtime.py bundle --run "C:\actual-run" --state $stateDirectory
python -B scripts/workflow_runtime.py recover --run "C:\actual-run" --state $stateDirectory
```

Prepare writes exports, creates isolated Docker resources and reserves ownership;
it does not start the worker. Execute starts one container once, captures its
logs and preserves output after stopping. Bundle writes an unaccepted,
unapplied candidate. Recover writes ownership/evidence only after its checks.
Exit codes: 0 successful operation, 1 refused (including Docker command timeout),
2 worker failure/execution timeout,
130 coordinator interrupt. Inspect runtime state/evidence after any interrupt.

Handoff and missing-context requests remain documented procedures: ask the
coordinator for exact additional paths/symbols and a revised approved scope;
prepare a bounded handoff in an authorized path. There is no automatic
handoff/intake/approval/promotion operation.

## Setup and checks

The Windows coordinator requires Python 3.12+ for junction detection (older Windows interpreters are refused). Git, Docker Desktop Linux engine and JSON Schema are required; the existing application still supports Python 3.11+.
The dev dependency now includes the source-pinned jsonschema version.

```powershell
python -m pip install -e ".[dev]"
docker build -t ai-template-workflow-runtime:phase1 runtime/workflow
$env:WORKFLOW_TEST_IMAGE = docker image inspect ai-template-workflow-runtime:phase1 --format '{{.Id}}'
python -B -m pytest -q -p no:cacheprovider -o addopts=
python -B tools/validate_boundaries.py
```

The Python/Node base images are pinned by digest; Cline/jsonschema/pytest top-level
versions are pinned. Package transitive resolutions are not fully locked;
the inspected final local image ID is the tested runtime identity.
Network is used to build the image, never to run workers.

Python, POSIX shell, Cline 3.0.70 --version/--help and deterministic shell/Python
tasks were exercised. No API model call, Windows-native Codex/Claude executable,
hardware run, integration or deployment was exercised. PowerShell inside the
worker is not supplied. Before online AI workers, decide provider-only egress
and credential delivery, and integrate the existing routing/feedback/acceptance
controllers under their limits. Do not enable unrestricted network as a shortcut.

The presentation-only UI and feature ABCs are unchanged. Approved future
application I/O changes still require linked UI work. This implementation neither
creates a headless exception nor implements that later approval trigger.
