# M1 AC-02 and AC-03 independent acceptance

Scope: acceptance of the delivered M5 software baseline
5f83ac755369f850af74ee8f17e6b566b871f769, in the existing migration checkout.
**AC-02: independently accepted. AC-03: independently accepted.** These new
criterion-level closure decisions are supported by fresh separate review and
completed final-source verification. Machine-readable decisions and exact
evidence digests are in M1_ACCEPTANCE_DECISIONS.json. Actual remote delivery is
recorded in [PR #7](https://github.com/henslewm/ai-template-oop/pull/7) and its final coordinator comment; this evidence
does not itself claim a future push or merge has occurred.

The frozen requirements, their historical pending statuses, foundation approval,
contracts, packets and old evidence remain unchanged. This is a separate new
criterion-level decision against the delivered software, not a rewrite of the
historical M1 candidate record. M6 has not been implemented.

## Requirement-to-evidence map

| Frozen criterion evidence | New direct evidence |
| --- | --- |
| AC-02: denied host/sibling/Git/socket/credential/link/network access and immutable writes | `test_paired_real_exports_and_exact_candidate_acceptance` runs both production adapters with real Docker. Each export records 124 direct/link read/write denials over 31 targets, including Windows host strings and Linux Docker Desktop/WSL host aliases. Both deny inherited host-canary environment, public/host/socket connections, immutable metadata and workspace write/chmod, and immutable directory creation. Acceptance additionally denies candidate write/chmod. |
| AC-02: allowed scoped task succeeds | The real worker changes only its owned feature file and emits a bound report. Independent acceptance exports those stopped bytes into a separate read-only volume, verifies them, then accepts/synchronizes only the disposable task. The host source and six canaries retain their exact bytes. |
| AC-02: image ID and Docker inspect for both exports | The paired case saves complete image inspection, separate worker/acceptance container inspections, runtime ownership, logs and archive digests in `M1_ACCEPTANCE_FINAL_VERIFICATION_DOCKER.json`. Production boundary checks enforce no host binds, network none, UID/GID1000, exact image/environment, read-only root, capability/security/resource/file/log limits. |
| AC-03: startup refusal plus failed logging cannot reuse token | The worker and acceptance `start_refusal_log_failure` cases fault at the real adapter's start/log seams after the durable consumed-start commit. Each fresh-process restart refuses, the consumed bit remains one, and the claim remains held until explicit preserved recovery. The refusal itself is injected; Docker preparation and stop/archive observations are real. |
| AC-03: concurrent execute permits at most one Docker start | Separate worker and acceptance launch races and direct-execute races each use two fresh Python processes. Execute races force both created-container observations before the ownership lock. Each has one winner, one refusal, one start trace, one command execution marker, a stopped tree, a finished claim and consumed bit one. |
| AC-03: restart after consumed-start commit refuses retry | Both adapters undergo actual `os._exit` before Docker start and immediately after actual start. The latter leaves a real live container and held claim. Fresh processes refuse restart without another start call, and direct ownership start also refuses the old consumed authority. |
| AC-03: expiry recovery requires stopped tree and preserved output; old token refused | Both adapters reject live-tree and missing-output recovery. A fixture clock models expiry without editing stored leases/history. Recovery observes real stop and saves the opaque session tar; explicit abandonment retains exact archive bytes and the consumed bit. The recovered token cannot start again. |
| AC-03: exclusive branch/workspace ownership | Two fresh processes race distinct scope identities against one ownership SQLite database and a real prepared/stopped container. Independent branch-only and workspace-only collisions each permit exactly one active claim and no Docker start. |

`M1_ACCEPTANCE_REVIEW.md` is the separate reviewer judgement. It records actual
independent probe commands/results and exact reviewed source hashes. The
coordinator's final complete regression, static and preservation results are
separate gates in `M1_ACCEPTANCE_FINAL_VERIFICATION.json`.

## Final coordinator results

The complete final-source suite finished **544 passed, 1 skipped in 1382.64
seconds**. The only skip is the existing second Windows Tk window case at
tests/test_ui.py:85, tracked separately in issue #4. Its actual tk.tcl/
menubutton.tcl diagnostic is retained without suppression. The unchanged case
passed alone (**1 passed in 0.08 seconds**) in M1_ACCEPTANCE_UI_RECHECK.json.
The frozen approval-projection procedure passed **46 cases in 1.93 seconds**.
Thus 591 distinct regression cases passed across the complete split procedure
and isolated Tk recheck; the complete invocation still has its one reported
skip. No hardware skip or simulation result is relabeled as hardware evidence.

All **13** dedicated real-Docker campaign cases passed within that final suite.
The digest-bound Docker bundle contains both export inspections/logs and every
ownership, race, process-death, startup-refusal/logging-failure and recovery
case. All eleven before/after source hashes in the recorder match, and all
eleven separate review-table hashes match the current files. Reviewer probe
results remain additional evidence, not a substitute for this full run.

ACTIVE/source/fingerprint, canonical Journal/evidence, application boundary,
M4/M5/delivered-M5 preservation, Ruff lint/format and ty all passed. Scoped
BasedPyright remains **not green**: the three M5 acceptance modules retain
**4 import-cycle errors and 1454 warnings**; the four new test/tool files report
**0 errors and 687 warnings** with the actual Python environment. Both checker
invocations exit 1 and their actual errors/warning-rule summaries remain visible
in final verification. No checker suppression or configuration weakening was
introduced.

All 331 protected files, both protected HEADs/indexes/complete statuses, 31
canonical files and 14 archived files match their preserved baselines. All refs
survive. Of the 115 delivered files, only the requested M6_HANDOFF.md update
differs. Production source/config/existing tests/tools, frozen material and all
historical M3/M4/M5 evidence are unchanged. Canonical project sequence remains
2, head 5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7;
the ACTIVE fingerprint remains
8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481.

## Preservation and limits

The delivered production source/config/existing tests/tools require no change.
The fixes close evidence gaps through a dedicated real-Docker campaign, stronger
metadata/host-alias negatives, and a read-only delivered-baseline audit. All 115
entry raw hashes are retained in `M1_ACCEPTANCE_BASELINE.json`; independent
Git clean-filter object checks establish their identity with delivered 5f83ac7.
`check_m1_acceptance_preservation.py` permits only the requested M6 handoff
documentation update among those files and nests the unchanged M4/M5 audits.

The coordinator, Docker daemon, pinned image, kernel and filesystem are trusted.
Actor/model identities are declarations. The tested finite paths and fault
points are bounded adversarial evidence, not an exhaustive isolation/security
proof. Fixture approval, budgets and clocks are synthetic and confined to new
disposable repositories; no canonical authority is enabled or changed. Actual
default resources/harness remain disabled and real API caps remain USD 0.

Hardware/manual ingestion remains disabled and required hardware gates remain
UNVERIFIED. This acceptance cannot establish hardware behavior, live providers,
credentials/connectors, output application, task integration or deployment.
The separate Windows Tk intermittent case remains tracked in issue #4. Existing
M5 BasedPyright diagnostics remain visible; new owned-file diagnostics are also
reported separately, without checker suppression or a global typing migration.

The source-changing pre-final complete run is retained separately in
`M1_ACCEPTANCE_VERIFICATION.json`: 544 passed/1 Tk skip plus 46 approval passes,
with source_hashes_unchanged=false and a nonpassing aggregate field. Its owned
BasedPyright invocation also lacked the actual pytest Python environment and
records two missing-import errors/720 warnings. It cannot substitute for the
final-source run with the corrected environment and immutable source hashes.
The first development paired test failed only because its expected denial
count was 84 instead of 76; that assertion was corrected before the initial
13-case passing campaign. Later stronger probes increased the final count to
124 per export. New static errors were corrected through qualified fixture
imports, dispatch-ID narrowing, JSON annotations and the actual Python
environment, before the final source run.

## Dated Git delivery record

Entry was clean on retained feature/workflow-migration at delivered M5
5f83ac755369f850af74ee8f17e6b566b871f769. Initial and pre-delivery fetches used
--no-prune; normal merges of origin/main reported already up to date. No reset,
force-push, branch deletion or protected-checkout write occurred.

Implementation/evidence commit b5b198281e0a42a32e5da9f0c991c4d8a0da723f was
committed and pushed non-force. PR #7 is open and ready at preparation of this
following documentation-only record. Final local gates, exact reviewed source
and evidence bindings passed before its creation. Inspect the live final head
and coordinator comments for actual remote delivery and synchronization; this
dated pre-merge entry does not claim future actions have occurred.

Hosting inspection reports delete_branch_on_merge=false, rebase-only merge,
no branch protection/rulesets or required tests, and no repository test workflow.
The dynamic Copilot cloud agent and Dependency Graph workflows are not required
test passes. No manual bot/paid worker was enabled. Under the owner's explicit
commit/comment/push/delivery instruction, merge the exact final head using an
allowed method, preserve every branch, and normally synchronize afterward.

The protected local main stays f624e207276372d9386b669bf087a66b44aba714 with its
staged plan deletion. The donor stays d6e582b7edeae24345a175f36639230726dbdead
with all eight untracked entries. The final coordinator comment records actual
post-delivery ref and preservation checks. Stop before M6.
