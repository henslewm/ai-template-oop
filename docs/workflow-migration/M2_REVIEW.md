# Fresh M2 implementation review

**Current status: PASS for the scoped M2 correctness re-review. F1–F3 are
closed and O1 is strengthened and closed. No remaining correctness blocker
was identified in the reviewed implementation.**

This status supersedes the initial verdict below. The appended follow-up records
the repaired snapshot and independent verification. The main agent's refreshed
full-suite and coverage runs were still in progress when this follow-up was
prepared; this status does not certify those results or full M1/M5 runtime
acceptance.

## Initial review (superseded; retained for audit)

Review date: 2026-10-14. Scope: `ARCHITECTURE.md`, `M2_PLAN.md`, AC-01 and
AC-09 in `config/workflow-bootstrap.json`, `scripts/workflow_state.py`,
`tests/test_workflow_state.py`, and `tools/check_workflow_approval.py`.
The final source reread includes `Append` and `Journal.append_many`.

**Initial verdict (superseded): changes required before declaring M2 implementation complete.**
Two P1 findings affect interruption recovery and the integrity of restored
authority. One P2 finding permits a scheduling event to commit after approval
revocation during validation. A separate, non-blocking P2 API observation
identifies the limits of the imported replay-state digest.

## Verified findings

### F1 — P1: a cache-spilling interruption prevents read/replay recovery

Source: `scripts/workflow_state.py:285` (read connections use `mode=ro`),
`:294` (transaction and integrity check), and `:463` (public read path).
Existing interruption coverage starts at `tests/test_workflow_state.py:524`.

SQLite's rollback-journal recovery can require writing the existing database.
A process killed after an uncommitted event has spilled dirty pages leaves a
hot journal. The read-only connection used by `read`, `verify`, and therefore
`replay` cannot perform that recovery. A coordinator that first replays its
history on restart is held despite an intact, recoverable committed history.
The public CLI provides initialize/restore/verify, but no explicit recovery
operation for this condition; initialize and restore refuse an existing file.

Verified on this Windows host with Python 3.12 and a disposable database:
initialize a stream, insert an uncommitted HOLD containing a 3 MiB string through
the actual `_connection(write=True)` and `_insert` paths, signal completion of
the insert, then kill that test process. No cache-size override was needed.
The rollback journal remained, with size 17,936 bytes. A subsequent public
`read` raised `sqlite3.OperationalError: attempt to write a readonly database`.
Opening the same disposable database through `_connection(write=True)` recovered
it; read then returned the original sequence 1. The uncommitted event was
correctly rolled back, so this finding concerns the supported recovery path,
not loss of committed events.

Missing AC-09 evidence: process-kill/restart with a valid event large enough to
spill SQLite's page cache. The existing kill test uses a small event and does
not exercise a hot-journal recovery that needs database writes.

Required correction: provide a controlled recovery path for the existing
canonical journal before replay, retaining missing-state refusal, identity and
chain/evidence checks, and no implicit launch. This can be an explicit recovery
operation; it need not make ordinary inspection create storage. Add the
cache-spill kill/reopen regression.

### F2 — P1: restore installs different bytes from those bound by the manifest

Source: `scripts/workflow_state.py:865` (source database selection/digest check),
`:878` (head verification), `:930` (staged copy), and `:941` (final verification).

Restore hashes and verifies the backup database, closes its verification
connections, copies evidence, then rereads the source database to populate the
staged authoritative file. That second read is not bound to the checked digest.
The final `self.verify()` checks structural integrity and evidence, but does not
compare installed heads or database bytes with the trusted manifest. A concurrent
change to the backup can therefore substitute a different valid history.

Verified with disposable state and an externally supplied manifest digest:
back up a sequence-1 stream with evidence; while restore writes the target
evidence, append a structurally valid HOLD to the backup database using the
actual journal API; then let restore finish. Restore returned success, installed
sequence 2, and the installed database SHA256 differed from the manifest's
`database_sha256`. The manifest still bound sequence 1. The timing hook simulated
another writer and did not alter the restore implementation.

Missing AC-09 requirement: the journal actually installed must be the journal
whose externally bound digest and heads were verified before scheduling.

Required correction: stage the exact verified bytes or verify a private staged
copy, and check its digest, heads, identity, and evidence before atomic
installation. Do not reread an independently mutable source for installation.
Add a regression changing the source between validation and staging, requiring
refusal before installing mismatched authoritative state.

### F3 — P2: scheduling approval can expire during validation and still commit

Source: `scripts/workflow_state.py:640` (batch transaction), `:655` (scheduling
anchor check), `:662` (semantic replay), `:675` (insert), and `:308` (commit after
the connection context yields). Single-stream `append` delegates to this path.

`append_many` validates ACTIVE approval before running the request's reducer
and validating/inserting its evidence. It never rechecks scheduling approval
after this work. Revocation or a changed foundation during that interval does
not cause the transaction to roll back.

Verified with an isolated copy of the foundation: a pure reducer paused while
processing a DISPATCH; another thread changed only that fixture's receipt to
AWAITING_APPROVAL; then the reducer resumed. `append_many` returned sequence 2,
and `active_anchor` immediately refused the now-inactive foundation. The reducer
did not modify the receipt or event. The supplied batch approval test covers
approval already inactive before validation, which is a different case.

Missing AC-01/M2_PLAN guarantee: new scheduling events require current ACTIVE
approval matching the stream anchor, including changes during validation.
This observation does not demonstrate a worker launch: this module has no launch
operation, and later runtime preflight remains a separate gate.

Required correction: revalidate anchors for every scheduling request after
reducers/evidence work and immediately before commit; roll back the entire batch
on a changed or revoked foundation. If the intended guarantee includes strictly
serialized concurrent approval replacement, define the shared synchronization
boundary. Preserve the existing ability to record outcome-only events after
revocation. Add a revocation-during-validation regression.

## API observation

### O1 — P2, non-blocking: the imported replay-state digest is informational

Source: `scripts/workflow_state.py:436` (import receipt checks), `:474` (replay),
`:662` (append semantic replay), and `:741` (receipt construction).

Import stores `state_sha256`, but later `_read` only checks that it has digest
syntax. Neither `replay` nor append semantic validation compares the reducer's
state at the imported `count` with that digest. The API consequently delegates
preservation of source replay semantics entirely to the supplied reducer.

Verified with the supplied synthetic three-event pattern: the import reducer
produced attempts 3, spend 1.0, and pending dispatch-2. A different pure reducer
replayed the same bytes as attempts 1, spend 0.25, and the same pending ID. Replay
returned successfully even though its state digest differed from the receipt.
This is not evidence of an incorrect pinned donor reducer, changed donor bytes,
or a storage operation resetting counters. The plan explicitly delegates
controller semantics to reducers and requires the digest to be recorded; it does
not explicitly require every later reducer result to equal it. Accordingly this
observation alone does not block M2.

Before relying on this API, state clearly whether the receipt digest is audit
information or an enforced compatibility boundary. A verified semantic replay
path could check the digest at the imported prefix before applying destination
events. Any deliberate change of semantic state representation needs explicit
verification that lifetime counts, spend, and pending liabilities survive. This
review does not require implementing M3 policies or controllers.

## Implementation and requirement assessment

| Area | Assessment |
| --- | --- |
| AC-01 foundation inspection | Existing validator is reused read-only; ACTIVE, exact binding, and expected-anchor checks are present. F3 leaves a revocation interval during scheduling validation. |
| AC-09 canonical storage | Git common-directory identity and runtime state resolution are reused; alternate state is refused. Constructor/inspection does not initialize a journal. |
| Atomicity and concurrency | FULL synchronous write transactions, immutable event/evidence/import rows, expected-head checks under BEGIN IMMEDIATE, and rollback are present. Batch CAS updates share one transaction. |
| History/evidence refusal | Reads validate six-field envelopes, sequence/previous/hash, UTC ordering, stored heads, canonical/original consistency, and evidence inventory/size/digest. Writes verify all streams before mutation. |
| One-time source import | Complete enumerated chains undergo structural checks and caller-supplied semantic replay before an atomic import; original bytes, IDs, hashes, and receipt are retained. Existing-stream replacement and repeated INIT are refused. O1 limits later semantic verification. |
| Windows interruption | Small-event committed/uncommitted kill tests are present. F1 leaves the public replay path unable to recover a hot rollback journal after cache spill. |
| Backup/restore | Consistent SQLite backup, evidence collection, externally bound manifest, identity/head/evidence checks, and no-overwrite installation are present. F2 breaks binding between checked and installed database bytes. |
| Frozen approval regression helper | `tools/check_workflow_approval.py:24` first validates ACTIVE state; lines 25–60 run unchanged approval tests on a disposable inactive projection. It checks fingerprint equivalence and original receipt preservation. No issue found in this helper's intended scope. |

The reviewed `Append` request is keyword-only and carries stream, kind, data,
expected head, timestamp, evidence, and optional reducer. `append_many` accepts
1–16 distinct streams, returns heads in request order, rejects INIT, and commits
all requested changes or none. This is an appropriate storage primitive for
future task/role/project reservation records. It does not itself enforce cap
policy, dispatch identity/idempotence, controller semantics, or cross-database
ownership/start authority. These are deliberate consumer boundaries, not missing
M2 controllers. Sequential reads may observe different committed versions; CAS
refusal requires replaying/recomputing the complete proposed batch before retry.

## Verification provenance and acceptance limits

Reviewer-executed checks used temporary fixture copies/databases only. The six
supplied batch cases were invoked directly against isolated fixtures: successful
three-stream commit; later stale-head, reducer, and inactive-approval rollback;
eight concurrent contenders with one complete winner; and empty/duplicate-stream
refusal. All six passed. Direct invocation avoided the test fixture's Git
initialization and worktree mutations. Four additional targeted probes verified
F1, F2, F3, and O1. Only a disposable Python test process was killed; no worker
was launched, and no live host journal was read or written.

The owner supplied prior evidence of 73 M2 tests including real Windows kills,
process contenders, and pinned donor feedback replay; 46 frozen approval tests
on an inactive projection; 42 existing scope/Docker checks; passing ty/Ruff; and
BasedPyright with zero errors and dynamic warnings. Those full-suite results
were not rerun or independently recertified here. CLI roundtrip coverage and
operational documentation were assigned to the main agent and were not
duplicated by this review. The added BOM/CRLF compatibility and controlled
invalid-Git CLI refusal were inspected in the current source/tests.

Final reread snapshot (raw SHA256):

| File | SHA256 |
| --- | --- |
| `scripts/workflow_state.py` | `5c877d5da10407810984926c581171145de1c2eae9a3a3c2eaa7771edc4c273b` |
| `tests/test_workflow_state.py` | `11e6e129cfa0a1fc621e1f970d4d171d28cccb2a08eb9b5e146a7b82982887f5` |
| `tools/check_workflow_approval.py` | `f25a57337cc7d146c9ea7ec9138150994aa68be3565e7a79d9b302272049eeaa` |

The ACTIVE fingerprint remains
`8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
The frozen package, validator, and approval tests retained their observed raw
hashes throughout review, and read-only Git diff inspection showed no tracked
changes. This reviewer edited only this report, performed no Git mutations,
and did not read or write live host databases.

Closing F1–F3 and recording their regression evidence is necessary for this
review's M2 implementation verdict to pass. It would establish implementation
verification for the scoped journal/bootstrap work; it would not establish full
M1 Docker runtime acceptance, M5 independent acceptance, live dispatch authority,
provider access, publication, integration, or merge acceptance. No unrelated
toolchain migration is required.

## Follow-up review after repairs — 2026-10-14

**Follow-up verdict: PASS for scoped M2 implementation correctness.** The
repaired versions of the earlier probes now produce the required results.
F1–F3 no longer block this review, and the O1 semantic compatibility check is
now enforced when a reducer is supplied. No additional correctness blocker was
found while rereading the updated journal, batch-append API, restore/recovery
paths, CLI recovery branch, and repair regressions.

| Item | Repair and independently verified result | Current source |
| --- | --- | --- |
| F1 — closed | Public `recover` opens only existing state with the canonical journal's writable transaction, lets SQLite recover hot rollback pages, and verifies all stored history/evidence. A real Windows kill after an uncommitted 3 MiB insert again made ordinary read refuse; public recovery returned the original committed head, and the next append succeeded. Missing state remained absent, and a corrupted stored head was refused. | `scripts/workflow_state.py:474`; CLI branch at `:1050`; regression at `tests/test_workflow_state.py:1139`. |
| F2 — closed | Restore captures database bytes once, checks the trusted digest, verifies a private copy, and stages those same bytes. It checks the staged digest and installed heads/digest. Repeating the original source-mutation timing hook changed the backup to sequence 2 while restore copied evidence, but restore installed the exact manifest-bound sequence 1 bytes and head. | `scripts/workflow_state.py:894`, `:902`, `:968`, and `:986`; regression at `tests/test_workflow_state.py:1217`. |
| F3 — closed within the stated synchronization boundary | Scheduling anchors are collected and revalidated after every batch insert/reducer/evidence operation, immediately before transaction exit. A separate thread revoked a fixture receipt while a pure reducer paused; the entire mixed outcome/scheduling batch rolled back. An outcome-only HOLD remained recordable afterward. Create and import also have final anchor checks. | `scripts/workflow_state.py:672`, `:708`, `:608`, and `:804`; regression at `tests/test_workflow_state.py:1261`. |
| O1 — strengthened and closed | `_reduce_events` checks semantic state against the receipt at the imported prefix before continuing into later events. The original counter/spend-resetting reducer probe now refuses replay and append. A batch containing an earlier sibling-stream insert also rolled back on this refusal. The original reducer accepted a later RESULT and retained attempts 3, spend 1.5, and no pending dispatch. | `scripts/workflow_state.py:486`, `:491`, and `:696`; regression at `tests/test_workflow_state.py:1297`. |

The reviewer independently reran these targeted scenarios in one successful
standalone invocation against disposable fixture copies and SQLite databases.
The only process killed was the disposable Python interruption-test process.
No Git mutation, worker launch, other-checkout operation, or live host database
access was needed. The review still writes only this report. The new repair
regressions were also inspected; the owner separately reported six targeted
regressions passing in 3.34 seconds and passing Ruff/ty checks. Full-suite and
coverage refreshes remain the main agent's verification work and were not
duplicated or claimed as independently passed here.

The remaining approval limitation is explicit: receipt replacement is a
filesystem operation, not part of SQLite's transaction. A replacement after the
last anchor check is not serialized with commit. The repaired code catches the
tested change during validation and provides a final check, but does not promise
an atomic transaction with arbitrary receipt editors. This is an accepted
boundary for this journal-only milestone, not proof that a reservation permits
execution after revocation. A later launch preflight must freshly validate the
current foundation and the other required authority. No launch operation exists
in this module. The generic API still requires controllers to supply their pure
reducers for semantic validation; `read`, `verify`, and `recover` verify stored
history and evidence rather than implement budget/controller policy.

`Append`/`append_many` retains the reviewed single-transaction, distinct-stream
CAS boundary, and semantic/approval failures roll back earlier inserts in the
same batch. Recovery does not initialize missing state or issue scheduling
authority. Restore retains the no-overwrite rule and exact repository identity,
history, evidence, and manifest bindings. AC-01/AC-09 implementation correctness
has no unresolved finding from this re-review; final refreshed regression
evidence must be recorded separately before milestone closeout.

Follow-up reread snapshot (raw SHA256):

| File | SHA256 |
| --- | --- |
| `scripts/workflow_state.py` | `6c87c02e3c467ec8a3cf2af48720ea59d7ecb7285620d91e0e28be05c7495050` |
| `tests/test_workflow_state.py` | `fda5387e288fee28660e703f9d20dfe356beef9ce90c290aa6275cd3071906e7` |
| `tools/check_workflow_approval.py` | `f25a57337cc7d146c9ea7ec9138150994aa68be3565e7a79d9b302272049eeaa` |

Read-only ACTIVE validation again returned
`8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
The frozen package, validator, and approval tests retain the raw hashes observed
in the initial review; read-only Git diff inspection reports no tracked changes.
This follow-up establishes scoped implementation review, not full M1 Docker
runtime acceptance, M5 independent acceptance, live activation, publication,
integration, or merge acceptance. No unrelated toolchain change is required.
