# M5 handoff: independent acceptance (future work)

Stop boundary: M4 implements AC-07 only. M5 has not been implemented or accepted.
Remaining M1 AC-02/AC-03 independent worker/acceptance export evidence remains
open. Frozen acceptance statuses, foundation approval, contracts and packets
are unchanged. Never infer independent acceptance from a worker PASS or from
the M4 implementation tests.

Worktree: `C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration`.
Retained branch: `feature/workflow-migration`. Consult M4_CLOSEOUT.md and
M4_VERIFICATION.json for actual delivery SHA/PR state, fresh verification,
limitations and source hashes; inspect current Git/remote state before relying
on historical descriptions. The 18 M3 implementation/evidence/handoff files
remain byte-for-byte preserved; M4 may deliver them as the preserved dependency
baseline because they were uncommitted at entry. Both protected checkouts,
their indexes/local work, all branches and canonical state/archives survive.

Read M4_HANDOFF.md, M4_PLAN.md, M4_OPERATIONS.md, M4_REVIEW.md, M4_CLOSEOUT.md,
M4_VERIFICATION.json, M4_SOURCE.json, M4_PRESERVATION.json and the final
M4_PRESERVATION_CHECK.json. Read the listed M3 evidence, especially
M3_RESUME_VERIFICATION.json, and CLAUDE.md, PROMPTS.md, BRANCH_RETENTION.md,
frozen ARCHITECTURE.md and workflow-bootstrap.json. Read the actual M4/M3
controllers and runtime/scope/Journal code, not only these summaries.

M4 uses M3's Journal-native reservation and accounting, preserves the entire
context envelope, actor/resource/family/tier/config/rates/approval/head/deadline
bindings and consumed-start boundary, and atomically records a stopped result
with its task/role/project settlement and dispatch receipt. The receipt records
the M3 reduced state; a late ingested PASS can be a timeout failure. Exact
identical re-ingestion is idempotent. Changed/stale ingestion refuses.
Output stays an opaque stopped session tar plus a digest-bound replacement JSON;
it has not been applied to a worktree. Worker assertions are untrusted.

The actual ACTIVE receipt is Winston's 2026-10-14T02:07:06Z receipt with
fingerprint `8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
The canonical `project:workflow-migration` journal remains sequence 2, head
`5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7`.
Default resources and harness remain disabled; all real task/role/project API
budgets are USD 0. M4 refuses metered launch. Do not enable providers or paid
workers, initialize/replace control state, refresh frozen hashes, import donor
cleanup, apply output automatically, or alter a protected checkout.

The existing Windows Tk smoke test intermittently skips its second window;
the skipped case passes alone. This is tracked separately in
[issue #4](https://github.com/henslewm/ai-template-oop/issues/4). Preserve actual
skip/rerun evidence rather than suppressing it or changing application behavior
as part of M5. M4's final verification distinguishes this from its own cases.

M5 must adapt pinned donor `scripts/acceptance.py`, its schema and behavioral
tests from `d6e582b7edeae24345a175f36639230726dbdead`, using `git show` against
the donor object database. Acceptance is a separate Journal controller and a
fresh isolated Docker export, not a host subprocess or a reuse of the worker's
claims. Bind the exact candidate bytes/reference/digest, feature/UI/base commits,
task/revision/contract, interface/scope, image/environment and evidence.
Invalidate previous gates when any bound input changes while retaining review
attempts, failure history, spend and liability.

Enforce named actor independence, reviewer tier/family floors and cumulative
review caps. Preserve risk floors: low deterministic; medium also model review;
high also cross-family; critical also architect and user decision. Packet gates
may strengthen these. Actual missing hardware evidence remains unverified.
Use M3's reviewer reservations and budget streams, coordinator-bound usage and
the existing stopped-output/consumed-start boundary. Native M3 review currently
refuses APPROVE intentionally: an acceptance integration must be explicit,
digest-bound, idempotent and unable to reset the frozen M3 semantics/history.

Copy/paste next-session prompt (requires a new explicit M5 request):

```text
Implement M5 independent acceptance only in
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration.
Read docs/workflow-migration/M5_HANDOFF.md and every listed reference, including
the final M4 evidence and M3_RESUME_VERIFICATION.json. Inspect actual worktree,
delivery status and refs; preserve all local work, branches, both protected
checkouts, canonical stores and archives. Fetch --no-prune and normally merge
current origin/main after inspecting/preserving work. Never reset, force-push,
prune/delete branches, alter frozen approval/contracts/packets or enable paid
workers. Keep default resources/harness disabled and real API budgets USD 0.

Use pinned donor d6e582b7edeae24345a175f36639230726dbdead via git show, not its
working tree. Implement fresh Docker-isolated independent acceptance with exact
candidate/artifact/interface/scope/image/evidence/commit bindings, actor and
reviewer family/tier/risk floors, cumulative review attempts and M3 budget
semantics, and idempotent feedback synchronization. Worker PASS cannot accept.
No host untrusted command execution, credentials, connectors, Git objects or
bind mounts enter exports. Missing hardware stays unverified. Preserve M4 crash,
consumed-start, replay and exact stopped-output/report negative guarantees.

Add meaningful behavioral/negative/crash/concurrency/replay tests and obtain a
fresh scoped review. Rerun the complete split verification below, all M3/M4/M2
and existing regressions, scoped lint/format/type checks and preservation. Record
actual results, skips, limitations, current Git state and an M6 handoff. Do not
claim remaining M1 evidence closed by M5 implementation alone. Stop before M6.

$env:WORKFLOW_TEST_IMAGE = 'sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e'
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_approval.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B scripts/workflow_state.py verify
python -B tools/validate_boundaries.py
python -B tools/check_m4_preservation.py
```
