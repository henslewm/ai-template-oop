# M5 independent acceptance operations

The independent controller is `scripts/acceptance.py`, its Docker adapter is
`scripts/acceptance_runtime.py`, and pinned donor report consistency rules live
in `scripts/acceptance_report.py`. The donor schema is adapted to destination
review/time/context bounds. The default foundation still disables resources and
all real task/role/project API budgets remain USD 0. Model reports are bounded
coordinator inputs; this implementation adds no model/provider transport.

Use the existing `workflow_state.Journal(root)`. Never initialize or replace
canonical stores to make an acceptance command run. All verification uses
disposable repositories, Journals, ownership/start stores and offline resources.
`python -B scripts/acceptance.py --help` lists the explicit CLI stages.

## Candidate and independent checks

`initialize(journal, task_stream, worker_dispatch_id, config, controller,
architect, reference=..., commits={feature,ui,base}, image=...)` starts one
`acceptance:<task_id>` Journal stream. It requires the exact closed M4 worker
receipt awaiting review, validates the stopped archive and replacement bundle,
and freezes the original packet/graph, task/revision/contract, worker actor and
family/tier, scope/interface/base, exact artifact reference and digest, three
existing Git commit identities, immutable image and image environment digest.
No candidate is applied to the host worktree. Commit identities describe inputs
to acceptance; an uncommitted replacement remains a separately bound artifact.
They are not a claim that a feature/UI integration commit has been produced.

`prepare_check`, `launch_check`, and `ingest_check` run one architect-declared
validation in a fresh volume/container. Python and POSIX shell entry points are
supported, within the existing network-none, UID/GID1000, read-only root,
capability/resource/log limits. The candidate overlays the exact original export.
All workspace inputs are root-owned and immutable, and the entire acceptance
session is mounted read-only. Writable tmpfs remains private. No credentials,
connector, Git objects, host bind mount, database or ownership token is exported.
Only fixed trusted preparation code runs as root in the setup container.

Each command runs directly as the Docker entry point. The coordinator observes
the exit code and bounds the absolute deadline, verifies the exact preserved
session archive and log, and records the digest-bound effective check outcome.
A command-written report is refused. Candidate changes, missing/linked/escaped
or extra files, immutable changes, secret-like output and wrong bindings refuse.
Stopped output stays opaque; archive members are never extracted on the host.
Zero exit after the deadline cannot pass. Identical ingestion replays its durable
effective result even after the deadline or feedback synchronization.

Check runs progress PREPARING → PREPARED → LAUNCHING → STOPPED → CLOSED. Intent
precedes external effects. Existing ownership and durable consumed-start logic
remain authoritative, and interrupted runs never restart implicitly. There are
at most two explicit check preparations per validation/submission. Starting a
rerun invalidates that validation's prior PASS. Pending runs block review and
acceptance. After review or a user decision exists, rerunning checks requires an
explicit resubmission that invalidates all gates.

`reconcile_check(..., reason, stop=False)` explicitly abandons a pending check
after observing stop and preserving any claimed output. `stop=True` permits a
live container to be stopped first. Missing manifests/containers, ambiguous
ownership, failed Docker observations and missing preservation hold for operator
inspection. Consumed authority remains consumed. Recovery never retries.

## Review, decision and synchronization

Risk floors cannot be waived: low requires independent deterministic checks;
medium also requires model review; high also requires cross-family review;
critical also requires the named architect and a separate user decision. Packet
and configuration gates can strengthen these. Actors compare normalized names,
and result spelling/family/tier must match the native reservation exactly.

`prepare_review` renders the actual bounded candidate/check/context envelope and
uses M3 `reserve(..., role='reviewer')`. M3 owns lifetime review counts, tier
ceilings, rates, deadlines, context accounting and all task/role/project budgets.
The minimum of native and acceptance caps applies; resubmission cannot replenish
attempts. Metered review is refused. A qualifying named architect review can
also satisfy model review, including cross-family and tier floors; this permits
critical acceptance with M3's tier-4 cap of one, without granting a second use.

`ingest_review` validates every criterion exactly once, binding the complete
report to its reserved actor and review ID. Donor verdict consistency and
contract-reference rules apply. One transaction records the acceptance report,
native reviewer result and both budget settlements. An APPROVE report records
native NEEDS_EVIDENCE until all acceptance gates have passed. A rejection uses
M3's existing corrective-failure/fingerprint behavior. Duplicate identical
reports and usage replay the same outcome; changed input refuses. Coordinator
usage must carry registered evidence and saved-rate/dispatch bindings. M3's
unknown liability, conservative pricing and overrun holds remain unchanged.

An interruption after native reservation but before REVIEW_OPEN leaves an
orphaned native review reservation. `abandon_review` explicitly closes it with
the lifetime attempt retained. Opened reviews are abandoned atomically across
acceptance, task and budget streams. No lost result becomes a free retry.

`accept` requires every gate, no pending run/review or unknown cost, current
authority and the bound independent controller. Accepted gates become immutable.
`resubmit` revalidates an actual candidate and invalidates all earlier gates,
while retaining every review, native attempt, failure, settled cost and liability.
An artifact reference change is itself a new binding, even with identical bytes.

`sync_feedback` embeds the exact hash-chained acceptance proof and native head
in a versioned REVIEW event. The additive native hook validates the proof and
native result/reviewer settlements before applying ACCEPTED. Unproved native
APPROVE still refuses. Task acceptance and the synchronization receipt commit in
one CAS transaction. Exact duplicate and racing synchronizations return the
same receipt. Stale/cross-task proofs refuse. M3 source/history semantics remain
unchanged outside this hook; preservation reconstructs and hashes the original
M3 source after removing exactly that block, without refreshing its baseline.

## Limits

Hardware/manual evidence ingestion is deliberately disabled. Every such required
validation remains UNVERIFIED and blocks acceptance. Unit/simulation success
never upgrades the packet's declared hardware status. No physical hardware was
verified. Actors and reviewer/model declarations are coordinator assertions,
not external authentication. The coordinator, Docker daemon/image/kernel and
host filesystem are trusted; pure replay verifies records, not the truth of an
external observation fabricated by a trusted host administrator. Approval-file
replacement remains a separate filesystem operation from SQLite transactions.

M5 records independent acceptance only. It does not apply output, create an
integration candidate, authorize deployment, implement shared resume/closeout
views, or close the remaining M1 AC-02/AC-03 evidence. Frozen statuses stay
pending. M6 requires a new explicit implementation request.
