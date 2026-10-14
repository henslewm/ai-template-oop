# M3 offline controller operations

The coordinator modules are `scripts/model_router.py`, `scripts/feedback.py`
and `scripts/workflow_budget.py`. Defaults live in `config/model-router.json`
and `config/feedback.json`. Every resource is disabled, credentials are absent,
and task/role/project API caps remain USD 0. Routing records are metadata and
always carry `execution_authorized=false`. No transport or worker is launched.

## Durable API

Use the existing `workflow_state.Journal(root)`; never initialize, replace or
delete a live database to use these examples. The canonical M2 project journal
remains at sequence 2. M3 verification uses disposable state exclusively.

`initialize_accounts(journal, project, caps)` explicitly creates separate
worker-role, reviewer-role and project budget streams. It refuses existing
accounts rather than resetting spend. Administrative recovery of interrupted
provisioning must inspect existing streams and create only a verified missing
account with the same binding and caps; it must not delete successful writes.

`initialize(journal, 'task:<task_id>', packet, graph, policy, config, architect,
project=..., implementer=...)` creates one destination task INIT. The task ID
and canonical stream are immutable. Aliases, repeated identities and INIT reset
are refused. Current ACTIVE approval sets maximum budgets and resource policy.
The two caps may be lowered by a packet; tier caps take every applicable minimum.

`reserve(journal, stream, config, options, role='worker')` reads and replays
state, checks current approval and availability, computes a reproducible plan,
and atomically appends task DISPATCH plus role/project RESERVE. All three heads
must match. One contender wins; callers must replay and recompute after a stale
head, never reuse a failed batch. A reservation consumes a lifetime attempt.

Options contain task_class, input_tokens, output_tokens, unavailable_providers,
unavailable_resources and context_envelope. The envelope contains actual rendered
brief and rules strings and overhead_tokens. Context accounting includes the
controller context, UTF-8 bytes conservatively bounded at one byte per input
token, harness overhead and reserved output. More than 40000 characters holds.
Reviewer options also require reviewer_actor: a named actor independent of the
recorded implementer. Risk and packet cross-family gates filter resources before
selection. Actor, actual model family and tier are frozen in the reservation.

`complete`, `abandon`, `review`, `reconcile` and `finish` append outcomes to all
three streams in one transaction. Duplicate or mismatched outcomes refuse.
The single-stream `append` helper allows only HALT, DIAGNOSIS and APPROVAL_HOLD;
it cannot bypass budget accounting. Diagnoses preserve attempts, identities,
failure fingerprints, reviewer history, settled spend and held liability.

Native review records can reject, request evidence or escalate. They cannot
APPROVE: M5 owns independent acceptance. A reviewer outcome needs its pending
dispatch and exact worker-result binding. Timeout requires explicit abandonment,
which consumes the attempt and retains possibly charged metered liability.

## Accounting and replay

Accounts retain settled spend plus every pending ceiling and unknown liability.
Missing metered measurements, null/zero/positive worker estimates and abandoned
possibly charged runs remain unknown. Repricing cannot clear an old liability.
Explicit unmetered resources settle at zero, preserving the original claim.

Measured usage carries dispatch_id, rates_hash, input_tokens, output_tokens,
cached_input_tokens and evidence_sha256. Supply matching coordinator Journal
Evidence to the outcome API. Rates come from the saved dispatch, never current
configuration. Input is fully charged without an inferred cache discount and
money rounds upward to a USD millionth. Truthful usage beyond the reserved token
or monetary ceiling is recorded and holds NEEDS_DECISION. No hard live cap is
asserted without an enforceable transport ceiling and trustworthy measurement;
both are later enablement work and real metered launch remains disabled.

New destination events use `destination-feedback-1`. `replay` calls stored
semantics; appending supplies a reducer that treats only prior sequence numbers
as stored and the proposal as new. Pinned source imports retain original bytes,
hashes, source anchor, policy, packet, cap, attempts, costs and pending dispatch.
An incompatible imported task is inspection-only for new scheduling; it is never
silently relabeled with a destination INIT. Generic Journal read/verify needs
the controller reducer to perform semantic replay.

## CLI and next boundary

`python -B scripts/model_router.py` exposes validate-config, route and verify.
`python -B scripts/feedback.py --help` lists explicit Journal commands and
read-only status/context/render/packet views. A missing journal is refused;
CLI use does not initialize storage automatically. Use `workflow_state.recover`
only after an actual interrupted SQLite rollback requires it.

M4 must adapt Docker dispatch/report ingestion to these exact reservations,
deadlines, rates, actor bindings and heads. A saved reservation alone does not
authorize a launch. M1 AC-02/AC-03 acceptance gaps and M5 independent acceptance
remain separate; neither is closed by M3 implementation verification.
