# M3 handoff: routing, feedback and bounded budgets

Worktree: `C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration`.
Retained branch: `feature/workflow-migration`.
Reviewed M2 candidate base: `3fba5742044abcce7a664e3030e15a5db33f7b2b`; its tree
is identical to merged M1 main commit
`517a770dd7346fc5d6c530781719365fc9ff409e` (PR #2). Before M2 delivery, main was
normally merged into the retained branch at
`051a3a6b3c534eff232b604a87a7d5bb096a792a`, without changing that baseline tree.
Read `M2_CLOSEOUT.md` for the verification snapshot and authorized delivery scope.

M3 entry gate: the owner must first merge the M2 PR. Inspect the live PR to
confirm MERGED status and its actual head/merge SHA, and verify the merged commit
contains the M2 files. Fetch without pruning, inspect current refs and local
work, then deliberately merge current `origin/main` into the retained branch
without resetting, force-pushing, deleting branches or overwriting local work.
Do not start M3 if the M2 PR is still open or its merged contents are unverified.
Keep the original and donor checkouts unchanged. Record the actual M2 merge SHA
and M3 starting HEAD; do not substitute the historical candidate base above.

Read `CLAUDE.md`, `PROMPTS.md`, `BRANCH_RETENTION.md`, the frozen approved
`ARCHITECTURE.md`, `config/workflow-bootstrap.json`, `M2_PLAN.md`,
`M2_OPERATIONS.md`, `M2_ACCEPTANCE.md` and `M2_REVIEW.md`.

The ACTIVE receipt belongs to Winston at `2026-10-14T02:07:06Z` and retains
fingerprint `8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
The manifest and validator/tests are frozen approval material. Historical
criterion statuses remain pending by design; use the new milestone evidence,
not edits to those statuses, to describe implementation progress.

M2 adds the canonical `control.sqlite3` journal/bootstrap adapter in
`scripts/workflow_state.py`, with `Head`, `Evidence`, `Append`, atomic CAS
`append_many`, semantic replay/import, and verified backup/restore. The separate
ownership and consumed-start databases retain their runtime-only roles. Journal
reads do not initialize state. Use explicit `Journal.recover`/CLI `recover` if an
interrupted SQLite write left a hot rollback journal; recover verifies existing
state and never launches or initializes anything. Source imports preserve original bytes, hashes,
IDs, counters, costs and pending dispatches; no new INIT may reset old history.
The original protected checkout's staged plan deletion and the donor checkout's
eight untracked entries remain preserved. All retained branch refs must remain.

## Scope and evidence to earn

Implement M3 and AC-04, AC-05, AC-06 only. Adapt these files from the exact pinned
source commit `d6e582b7edeae24345a175f36639230726dbdead`, not its working tree:

- `scripts/model_router.py`, `config/model-router.schema.json` and router tests.
- `scripts/feedback.py`, `config/feedback.schema.json` and feedback tests.

Route/record/verify must preserve role/risk/complexity/reviewer floors, provider
eligibility, expected cost per accepted result, consecutive non-descending
escalation history and bounded context. Saved packet/config/rates/anchor and
history must reproduce each selected resource and reason. Resources default to
disabled, and destination task/role/project API budgets remain USD 0. Priors and
synthetic costs must remain clearly labeled; make no provider/model call.

Use the approved worker default of 2 attempts and reviewer overall cap of 2,
with tier caps `min(task cap, packet cap, policy cap)` and policy tiers
0..4 bounded at 3/3/2/2/1. Keep failure thresholds 2 per tier and 3 total,
one contract repair, three blocker resumptions, five architect diagnoses,
600-second attempt deadlines, five recent history entries and 40000 context
characters. Repair/resume/resubmission cannot replenish lifetime attempts or spend.

Reserve against task, role and project caps in a single `Journal.append_many`
transaction, comparing all relevant heads and enforcing one pending dispatch
per task/role. Preserve settled spend plus pending ceilings. Missing or unmeasured
metered cost remains held liability, including positive worker estimates and
abandoned possibly charged runs; explicit unmetered runs may cost zero. Usage
must bind to dispatch and saved rates; conservative cache accounting and upward
rounding remain. Tests may simulate costs in disposable fixtures.

Use `workflow_state.active_anchor` as the destination bootstrap adapter. Keep
controller semantics separate from storage. Pass semantic reducers for INIT and
append; historical replay must use stored-event semantics and new events the
stricter transition checks. One-time imports must not silently relabel source
anchors, policies or task identity to enable an incompatible task.

Port relevant pinned donor behavioral tests and add destination tests for
disabled resources, zero budgets, cumulative caps across revisions, repeated
failure fingerprints, context/provider/risk negatives, atomic reservations,
stale heads, unknown spend and exact decision replay. Run the M2 suite, approval
projection runner, actual ACTIVE validator and existing contract/boundary gates.

M1's existing scope/runtime regressions have been rerun with the pinned offline
Docker image. Full independent worker/acceptance export evidence remains separate
from M2 implementation verification. M3 must not claim M1/M5 acceptance or deployment.

## Copy/paste next-session prompt

```text
Implement and finish M3 in:
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration

Read docs/workflow-migration/M3_HANDOFF.md and its listed governing/evidence
files. Inspect the current worktree, refs, ACTIVE receipt and canonical journal
before changes. First confirm the owner-merged M2 PR and record its actual
head/merge SHA. Verify the M2 files on main, then synchronize the retained branch
with current main by a normal merge after inspecting and preserving local work.
Do not begin M3 while the M2 PR remains open or its merged contents are unverified.
Do not prune, reset, force-push, delete branches or modify either protected
checkout. Preserve all M2 additions, all branches, both protected checkouts
and their existing local work. Use donor commit
d6e582b7edeae24345a175f36639230726dbdead as the source reference.

Complete the planned router/feedback/budget controllers and AC-04/AC-05/AC-06.
Use workflow_state.Journal and atomic append_many for durable task/role/project
reservations. Preserve event hashes/IDs and lifetime counters/spend through
replay, repair, resume and resubmission. Bind packet/config/rates/approval and
enforce all approved risk/review/context/attempt/deadline/budget floors.

Keep live resources disabled and real API budgets at zero. Use deterministic
offline fixtures for costs and provider availability. Do not change the frozen
foundation, canonical packet files or application contracts, and do not launch
paid workers or begin M4. Verify the full M3 requirements with meaningful tests,
rerun M2/approval/contract/boundary regressions, and record concrete evidence.

When finished, provide a copy/paste M4 prompt and handoff identifying actual
files, current Git state, checks, remaining limitations and the next milestone.
```
