# M6 handoff: shared resume views and retained-branch readiness

M5 implements independent acceptance only. Read M5_CLOSEOUT.md,
M5_VERIFICATION.json, M5_TYPING.json, M5_REVIEW.md, M5_OPERATIONS.md,
M5_SOURCE.json, M5_EVIDENCE.md, M5_PRESERVATION.json and the preservation tools. Delivery state
is dated in closeout; inspect its linked live PR and final coordinator comment
for the delivered head/merge and retained synchronization SHA. Do not infer
delivery from an old file. M6 has not been implemented.

The subsequent M1 AC-02/AC-03 acceptance-only campaign uses delivered M5
5f83ac755369f850af74ee8f17e6b566b871f769. Read M1_ACCEPTANCE.md,
M1_ACCEPTANCE_REVIEW.md, M1_ACCEPTANCE_FINAL_VERIFICATION.json and its linked
Docker evidence, M1_ACCEPTANCE_BASELINE.json and the new read-only
tools/check_m1_acceptance_preservation.py. M1_ACCEPTANCE_DECISIONS.json separately
closes AC-02 and AC-03 for the delivered software, supported by fresh scoped
review and final complete verification: 544 passed/1 tracked Tk skip, 46 approval
passes, and the skipped unchanged Tk case passed alone. All 13 real-Docker
campaign cases passed. Ruff/format/ty, ACTIVE/Journal/boundary and preservation
passed. BasedPyright remains non-green: existing 4 errors/1454 warnings; new
test/tools 0 errors/687 warnings. Consult the acceptance record and final PR
comment for actual delivery state. The source-changing pre-final run is retained separately
in M1_ACCEPTANCE_VERIFICATION.json and cannot replace final-source verification.
All delivered production source/config/existing tests/tools are unchanged.

Also read M5_HANDOFF.md and its final M4/M3 references, especially
M3_RESUME_VERIFICATION.json; CLAUDE.md, PROMPTS.md, BRANCH_RETENTION.md;
the frozen docs/workflow-migration/ARCHITECTURE.md and
config/workflow-bootstrap.json; M2_OPERATIONS.md; and the actual Journal,
scope/runtime, feedback/budget, M4 dispatch and M5 acceptance code and tests.

M5 records exact independent checks against an unapplied M4 replacement. It
binds task/revision/contract, artifact reference and bytes, feature/UI/base
commits, scope/interface, image/environment, archive/log and reviewer evidence.
Accepted is a separate fact from integrated, VERIFIED dependency or deployed.
Native worker PASS cannot accept, and native unproved APPROVE still refuses.
The only M3 code addition is a versioned lazy acceptance-proof hook; the original
source reconstructs byte for byte when that exact block is removed. Preserve
that audit and every old event's semantics, IDs, hashes, counts and costs.

One qualifying named architect review can satisfy both model and architect gates
when cross-family/tier requirements hold. This keeps M3's tier-4 cap of one and
reviewer lifetime cap of two. All reviews reserve/settle through M3 task/role/
project accounting. Resubmission invalidates all gates and retains attempts,
rejections, spend and liability. Check reruns after review/decision require a
resubmission. Exact duplicate checks/reports/synchronization replay durable
receipts, including after deadline and commit interruption.

Hardware/manual ingestion is disabled and such checks stay UNVERIFIED. Unit or
simulation PASS cannot establish hardware behavior. Paid workers, live provider
transport/usage, credentials, connectors and unrestricted networking remain
disabled. The ACTIVE fingerprint remains
8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481;
canonical project:workflow-migration remains sequence 2, head
5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7.
All real API caps remain USD 0. The coordinator and Docker/image/kernel remain
trusted; declared actor/model identities are not externally authenticated.

The protected original checkout remains on main at f624e207276372d9386b669bf087a66b44aba714
with its staged plan deletion. The pinned donor checkout remains at
d6e582b7edeae24345a175f36639230726dbdead with all eight untracked entries.
Neither checkout may be modified. Read the donor exclusively through `git show`.
Keep every branch, canonical store, ownership/start record and retained archive.

M6 scope is AC-10, the remaining integration/readiness part of AC-11, and AC-12:
bounded shared startup/worker/coordinator views derived from authoritative
Journals and exact Git/scope/evidence facts; explicit interrupted-run resume;
stale-view refusal; smallest approved missing-context proposals; and readiness
for a retained-branch integration. Views cannot become alternate authority or
automatically grant retries. Preserve M4/M5 consumed-start, exact stopped-output,
crash, replay and liability guarantees. Never use donor cleanup or automatic
branch deletion. Inspect live required checks and exact reviewed heads before
claiming readiness, and distinguish unavailable checks from green checks.

M1 AC-02/AC-03 evidence was open at M5 delivery. The separate acceptance-only
campaign adds paired real Docker isolation and actual process ownership/start/
crash/restart/recovery evidence; its separate supported closure decisions and
limits are recorded in M1_ACCEPTANCE.md. M5 implementation alone is insufficient.
Frozen acceptance statuses, approval, application contracts and canonical packet
files remain unchanged. Hardware remains UNVERIFIED. The separate Windows Tk
intermittent skip is tracked in issue #4 and must be reported honestly.

Copy/paste prompt for a new explicit request:

```text
Implement M6 only in
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration.
Read docs/workflow-migration/M6_HANDOFF.md and every listed reference, final M5
review/verification/typing/operations/preservation evidence, and the actual
M2/M3/M4/M5 controllers. Also read the subsequent M1_ACCEPTANCE.md,
M1_ACCEPTANCE_REVIEW.md and final verification/decision/preservation evidence.
Inspect current worktree, refs and live delivery state;
preserve all local work, both protected checkouts, every branch, canonical
control/ownership/start stores and archives. Fetch --no-prune and normally merge
current origin/main after inspecting/preserving work. Never reset, force-push,
prune/delete branches, enable paid workers or alter frozen approval/contracts/
packets. Default resources/harness stay disabled; real API budgets stay USD 0.

Implement bounded derived shared resume views and branch-preserving closeout
readiness for AC-10/remaining AC-11/AC-12. Use pinned donor
d6e582b7edeae24345a175f36639230726dbdead via git show only as an inspected
reference. Exclude donor cleanup/branch deletion and inherited auto-merge
authority. Bind views and readiness to current Journal heads, approval,
task/revision, scope/interface, exact candidate/feature/UI/base/evidence/image
and live required-check facts. Reject stale views. Resume must identify objective,
owned paths, base/diff/interface, pending dispatch/review/check, costs/liability,
context estimates, blockers and next explicit action without implicitly launching
or replenishing attempts. Preserve M3 historical semantics/caps, M4/M5 exact
output/proof bindings, consumed starts, crash recovery and idempotent receipts.

Acceptance, integration, VERIFIED dependencies and deployment remain separate.
No host execution of untrusted commands, output auto-apply, host credentials,
connectors, Git objects or bind mounts in exports. Missing hardware remains
unverified. Obtain fresh scoped review and meaningful behavioral/negative/
crash/concurrency/replay coverage. Run the complete split verification with
WORKFLOW_TEST_IMAGE=sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e:
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_approval.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B scripts/workflow_state.py verify
python -B tools/validate_boundaries.py
python -B tools/check_m4_preservation.py
python -B tools/check_m5_preservation.py
Run scoped lint/format/type checks, record actual results/skips/limitations,
preservation and current Git state. Preserve the separate M1 acceptance decisions
and frozen historical statuses; do not infer hardware, live rollout or deployment
from implementation alone. Stop after M6.
```
