# M4 Docker dispatch and report operations

M4 owns AC-07 implementation only. `execution_harness.py` prepares and ingests;
`worker_launcher.py` performs read-only preflight and explicit launch;
`dispatch_state.py` reduces the dispatch journal. All worker execution goes
through the existing `workflow_runtime` and `workflow_scope` Docker boundary.
No host worker subprocess or credential/environment forwarding is present.

The actual ACTIVE foundation still disables resources and sets all real API
caps to USD 0. The router and new harness defaults are disabled. These commands
describe the API; they do not enable a worker against canonical state. Every
enabled test resource and nonzero simulated budget lives only in disposable
offline fixtures. Metered launch is refused even in an otherwise enabled policy.

## Durable sequence and bindings

Use an existing `workflow_state.Journal(root)`. Do not initialize or replace the
canonical journal, ownership/startup stores or approval receipt. M3 task INIT
and accounts must already exist. `dispatch(journal, task_stream, harness_config,
router_config, options, scope)` performs static preflight and renders the actual
bounded brief before calling M3's native `reserve`. The saved context envelope
contains the full context, rendered brief/rules, declared overhead, output and
growth headroom. It counts metadata conservatively and checks the served window.

The reservation freezes scope/branch/base/interface, packet/revision/contract,
actor, resource/family/tier, saved rates/config/approval and absolute deadline.
The dispatch stream also binds the task and budget heads, immutable image,
brief/rules, baseline and exact export. No packet schema, application interface
or frozen foundation file is changed. M3 still owns lifetime attempts and costs.

`dispatch:<decision_id>` progresses PREPARING -> PREPARED -> LAUNCHING -> STOPPED
-> CLOSED. The runtime records container/volume names before Docker mutations.
PREPARED registers immutable host inputs as Journal evidence. The Docker volume
contains only packet/scope/baseline, brief/rules/dispatch metadata, a writable
report placeholder and enumerated workspace files. No control database, ownership
token, Git objects, credentials, connector or host mount is exported.

`prepared_run` writes nothing. `launch` first wins a Journal CAS and then repeats
all approval/head/config/context/bytes/base/interface/ownership/deadline checks,
including exact volume bytes and Docker boundary/argv, before consumption and
inside the existing consumed-start boundary immediately before Docker start.
Only one contender can launch. A failed or interrupted LAUNCHING record is never
rolled back into reusable authority. Operator bounds only shorten the runtime
and reservation deadline; startup and teardown count. The worker remains network
none, UID/GID 1000, read-only root, capabilities dropped, no-new-privileges, private
process namespace and bounded memory/CPU/PIDs/files/logs/tmpfs.

The runtime confirms the whole container stopped and durably preserves opaque
session output before ownership release. M4 leaves `runtime.json` immutable and
writes the execution outcome separately. Generic runtime execute/recover/bundle
commands cannot substitute for M4's Journal launcher/reconciliation/ingestion.

## Report and replacement contract

The report has M3's exact result fields plus `run`, containing exactly
`binding_sha256`, `deadline`, and `bundle_sha256`. `dispatch.json` supplies the
first two. The last is SHA256 of the canonical replacement bundle (the existing
scope/base/changes envelope), derived from exact stopped workspace bytes.
The complete report field/check lists are in the immutable brief.

`ingest(journal, dispatch_id, usage=None, usage_evidence=())` reads only the archive
already bound by ownership and the STOPPED event. It checks bounded bytes/types,
strict JSON, every required check ID exactly once, PASS consistency, actual exit
status/time, exact immutable inputs and scoped replacements. It refuses escaped,
case-colliding, linked, missing, unexpected or oversized tar entries, stale
base/interface/scope, wrong binding/hash/deadline and credential-like report,
output or log content. It never extracts archive members on the host.

The coordinator preserves a replacement JSON artifact; it does not apply it.
One `append_many` transaction commits the M3 task, role and project outcomes plus
the dispatch receipt. M3 reducers determine all pricing, unknown liability,
overrun holds, attempt/failure history and status. The receipt reflects that
reduced status, including a late-ingestion timeout. A worker PASS can reach only
independent acceptance pending; M5 must implement independent acceptance.
Identical re-ingestion (including concurrent callers and restart after commit)
returns the durable receipt. Changed report/archive/bundle/usage or stale scope
refuses. Re-ingestion never creates another RESULT or replenishes an attempt.

Worker null/zero/positive cost assertions cannot settle metered liability.
Optional coordinator usage must bind the dispatch, saved rates and registered
evidence digest; M3 conservatively prices it and preserves truthful overruns.
The CLI intentionally has no arbitrary worker-supplied usage-file option.

## Explicit recovery and limitations

`reconcile(journal, task_stream, reason, stop=False)` explicitly abandons a pending
attempt after inspecting actual Journal, Docker, ownership and preservation
facts. `stop=True` explicitly permits stopping a still-live container first.
The equivalent CLI accepts `reconcile <task_stream> --reason <specific reason>`
and optional `--stop`. It never renders, launches or retries a worker.

A reservation before dispatch INIT can be abandoned because no Docker operation
precedes INIT. A claim surviving a manifest-token write is located by exact
scope/run identity. Consumed authority remains consumed. Missing/ambiguous state,
an unavailable Docker observation, a live container, missing start history or
failed preservation holds ownership/liability for inspection. Missing runtime
manifests and orphaned evidence require explicit operator investigation rather
than deletion or inferred completion. If SQLite has a hot rollback journal, use
the existing explicit Journal recover operation before verifying/reconciling.

The coordinator, Docker daemon/image/kernel and host filesystem remain trusted.
Actor names are coordinator declarations, not authentication. Approval-file
replacement is a separate filesystem operation; repeated checks do not claim an
atomic transaction with arbitrary external editors. No live provider, trusted
live usage transport, deployment, automatic output apply, M1 independent export
acceptance or M5 acceptance is enabled by M4.
