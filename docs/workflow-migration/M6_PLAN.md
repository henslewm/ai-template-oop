# M6 design and implementation plan

Scope: AC-10, remaining integration/readiness of AC-11, and AC-12 only.
Destination authority is the owner request, CLAUDE.md, PROMPTS.md,
BRANCH_RETENTION.md and the frozen approved architecture. The pinned donor is
a reference read through git show only; its cleanup and autonomy do not transfer.

Entry is clean feature/workflow-migration at 34b5a3103b397bab6ae2e490a87a00aba6d118e3,
equal to both origin/main and origin/feature/workflow-migration after fetch
--no-prune and normal merge. PRs 6, 7 and 8 are merged. Live hosting reports
automatic branch deletion false and main unprotected. M6_PRESERVATION.json is a
new entry inventory, supplementing every unchanged historical raw-byte audit.

Design: add coordinator administration modules in scripts/, leaving M2-M5 and
application contracts untouched. Derived views never authorize execution.
Snapshot Journal heads/evidence, approval, task/revision, accounts, exact scope,
Git/index/worktree facts, ownership and consumed starts. Double observation
refuses concurrent changes; cross-store reads are observations, not a distributed
transaction. UTC time and conservative context estimates are labeled; actual
provider context consumption stays unknown without measurement. Bound output
and recent history, retaining exact digest references to full authority.

Explicit resume validates the whole supplied view against current observations
and returns the next operator action. It never calls launch, reconcile, reserve,
or changes ownership. Consumed, ambiguous and expired runs require existing
explicit M4/M5 recovery. Pending reviews and checks retain attempts and liability.
Missing context names exact path/symbol/reason; only a named architect-approved,
digest-bound proposal can derive the minimal read-only scope addition. It never
edits a running reservation or exports added contents automatically.

Readiness rechecks exact accepted submission and stopped evidence, candidate
feature/UI/base commits, scoped tree changes, interface revision, approval,
independent review and contract/boundary/affected checks. Approved interface
changes require linked UI and mocks evidence. Read-only GitHub observations bind
the exact PR head/base and live required checks (including rule sets), distinguish
unavailable from none configured, enforce review cap four and branch retention.
No merge/apply/push/deployment operation exists. A readiness result is a derived
observation and must be regenerated immediately before a separately authorized
integration. Accepted, integrated, VERIFIED dependencies and deployed stay distinct.

Implementation phases:

1. Add workflow_handoff.py with bounded startup/worker/coordinator views,
   freshness validation, explicit resume and minimal context proposals.
2. Add workflow_closeout.py with exact candidate/interface/check/review gates
   and a read-only live hosting adapter; retain every branch.
3. Add behavioral, negative, interrupted-run, concurrent-read, replay and two
   successive retained-branch release tests using disposable stores and repos.
4. Obtain separate fresh scoped review; triage findings and repair real defects.
5. Run complete split regression with the pinned image, approval/Journal/boundary
   gates, all existing preservation audits and scoped lint/format/type diagnostics.
   Record actual output, skips, source hashes and limits. Stop after M6.

Decision: additive modules and docs only. Reason: preserve reviewed M3 semantics,
M4/M5 receipts, byte snapshots, attempts and liability without a new hook.
Invalidates only if a demonstrated M6 requirement cannot use the existing APIs.

No real task/resource enablement, paid transport, unrestricted network exports,
canonical state mutation, hardware claim or inherited automatic merge authority.
