# M4 handoff: Docker dispatch and report ingestion

M3 AC-04/AC-05/AC-06 implementation is complete locally. Read M3_ACCEPTANCE.md,
M3_REVIEW.md, M3_OPERATIONS.md, M3_CLOSEOUT.md, M3_VERIFICATION.json,
M3_RESUME_VERIFICATION.json and M3_PRESERVATION.json.
M3 does not close remaining M1 AC-02/AC-03 evidence or M5 independent acceptance.

Worktree: C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration.
Retained branch: feature/workflow-migration.
Current HEAD: ef6ae42bdef7ef32793764400761383fe650bea7, the normal synchronization
merge of M2 PR #3 (merge 63b61ff9fcd1dba6676c6fd5dfb7561eaa92aed8) into retained
M2 head a56743f20517577363bf5affccf3a27f66136c5a. M3 files are new and uncommitted;
no M3 push, PR or merge has occurred. Inspect actual current local work and refs
before delivery or M4 changes. Preserve it rather than resetting the branch.

The owner most recently reconfirmed M3 only and stop before M4. A stale saved
M4 goal is not authority to continue. Partial M4 edits made under that mistaken
scope were archived and reversed; M3's nine reviewed hashes match exactly and
no active M4 adapter remains. M3_CLOSEOUT.md records the archive. Begin M4 only
under a new explicit owner request, such as the prompt below.

The ACTIVE foundation and canonical journal remain unchanged: fingerprint
8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481;
project:workflow-migration sequence 2, head
5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7.
Do not initialize, replace or delete existing state or archived evidence.
All resources remain disabled and live API budgets remain USD 0.

M4 owns AC-07: adapt scripts/execution_harness.py, scripts/worker_launcher.py,
config/execution-harness.schema.json and relevant tests from the exact pinned
donor d6e582b7edeae24345a175f36639230726dbdead. Read with git show, not the donor
working tree. Do not import the donor host subprocess launch path. Use the
existing workflow_scope/workflow_runtime Docker boundary and consumed-start
authority. No host credentials, Git objects, control databases, connectors or
host bind mounts enter worker or acceptance exports. Keep network none,
UID/GID1000, read-only root, dropped capabilities and resource bounds.

Use M3's Journal-native reserve and atomic accounting. Bind task/role/dispatch,
packet/revision/contract, exact branch/base/interface/scope, actor, selected
resource/family/tier, saved config/rates/approval, ledger heads, image,
brief/rules/export hashes, absolute deadline and replacement bundle. Preserve
M3's full context envelope, lifetime attempts, held costs and conservative usage
rules. A saved reservation alone is not launch authority. A preparation failure
consumes the attempt and is explicitly abandoned; missing usage remains held.

Validate untrusted reports and exact stopped output without self-acceptance:
bounded bytes/types, duplicate/unknown/missing check IDs, contradictory PASS,
escaped or linked paths, immutable input changes, stale base/interface/scope,
wrong dispatch/bundle/hash/deadline and credential-like content all refuse.
No automatic output apply/promote. Bind coordinator usage to dispatch and saved
rates; worker cost assertions cannot settle metered liability. PASS advances
only to independent acceptance pending. M5 implements acceptance.

Reconcile reserve/render/claim/consumed-start/result crashes explicitly. Never
implicitly launch or restart a possibly consumed run. Duplicate identical
ingestion must be idempotent; conflicting or stale ingestion refuses. Preserve
stopped output/evidence before releasing ownership; orphaned state holds.
Existing M1/M2 authority limitations remain real, not inferred accepted by M4.

## Copy/paste next-session prompt

```text
Implement and finish M4 only (AC-07) in:
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration

Read docs/workflow-migration/M4_HANDOFF.md and all its listed M3 evidence,
plus CLAUDE.md, PROMPTS.md, BRANCH_RETENTION.md, frozen ARCHITECTURE.md,
workflow-bootstrap.json, M2_OPERATIONS.md and the existing scope/runtime code.
Inspect local work, current refs and actual delivery status first. M3's files
were locally verified but uncommitted at handoff; preserve all of them. Do not
assume a M3 PR/main merge exists. Fetch without pruning and deliberately merge
current origin/main only after preserving and inspecting work. Never reset,
force-push, prune/delete branches or alter either protected checkout. Retain
the original staged plan deletion and donor's eight untracked entries.

Revalidate the actual ACTIVE receipt and existing canonical journal. Preserve
all control/ownership/start state and archives. Use pinned donor commit
d6e582b7edeae24345a175f36639230726dbdead, never its working tree.

Adapt Docker-only dispatch/report ingestion and launcher preflight using the
M3 Journal-native reservations and existing consumed-start boundary. Follow
every exact binding, context/deadline/cap, report-negative, stopped-output,
unknown-cost and crash/idempotence requirement in M4_HANDOFF.md. Do not import
host subprocess workers or enable provider access. Keep resources disabled,
real API budgets zero, and fixtures deterministic and offline. Do not change
frozen approval material, application contracts or canonical packet files.

Add meaningful M4 positive/negative/crash/concurrency/replay tests and obtain
fresh scoped review. Rerun M3, M2 and existing regressions with:
$env:WORKFLOW_TEST_IMAGE = 'sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e'
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_approval.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B scripts/workflow_state.py verify
python -B tools/validate_boundaries.py
Run scoped lint, formatting and type checks. Record actual results, skips,
findings and preservation. Do not substitute M3's results for fresh checks.

Finish with concrete evidence, current Git state, remaining limitations and
a copy/paste M5 handoff. Do not claim M1 AC-02/AC-03 or M5 independent acceptance
closed by M4. Stop before M5. Do not launch paid workers.
```
