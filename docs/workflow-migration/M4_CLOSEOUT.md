# M4 closeout: AC-07 implementation only

M4 Docker-only dispatch/report ingestion and launcher preflight are complete.
M5 is future work; remaining M1 AC-02/AC-03 independent export/ownership
acceptance is not closed. Frozen criterion statuses, approval, contracts and
canonical packets remain unchanged. Resources/harness remain disabled and all
real API budgets remain USD 0.

## Verification and review

The final corrected full invocation passed **463 cases with no skips** in
457.01 seconds, including 107 M4, 85 M3, 89 M2, 42 scope and 43 startup cases,
plus existing application/contract/packet regressions. The subsequent fresh
frozen approval projection passed **46 cases**. Thus **509 distinct cases passed**
in the complete split procedure. Earlier results were not substituted.
ACTIVE/source/fingerprint, canonical journal/evidence, boundary and preservation
checks passed after the full run. Scoped Ruff lint/format and ty passed.
The three native M4 modules have zero BasedPyright errors and
913 visible dynamic-boundary warnings.

A broader diagnostic on the two legacy scope/runtime modules still reports
16 existing implicit-script-import/generic-typing errors and
1439 warnings across all five files. This diagnostic is not reported as green.
No checker suppression, weakened configuration or repository-wide typing migration
was introduced. Ty passes all five implementation modules and the preservation
tool. No new numeric coverage measurement or global coverage gate is claimed;
behavioral/negative/crash/concurrency/replay tests are the evidence.

Fresh separate review is **PASS, F1-F5 closed** in M4_REVIEW.md. Corrections cover
receipt/M3-state agreement, invocation preflight, combined fixture collection,
remaining operator time, and legacy default-runtime timer compatibility.
The old startup test was preserved unchanged; its 43-case module and all M4
explicit-deadline delay cases were independently rechecked. Reviewed hashes match
the final source/config/test files exactly.

Earlier full runs are retained as historical evidence: 460 passed before the
remaining-time fix, then 461 passed/one compatibility failure/one Tk skip before
that compatibility correction. An earlier combined M4 invocation exposed fixture
setup errors, now fixed. The final 463-case run has no failures or skips. The
intermittent existing Windows Tk skip also passed alone and is tracked in
[issue #4](https://github.com/henslewm/ai-template-oop/issues/4); no UI code or test
was changed. M4_VERIFICATION.json records actual commands, outputs, times, hashes,
review, earlier runs, preserved state and limitations.

## Git delivery and preservation

M3 dependency baseline is `754b3a2b49f24f47b0f015e4e1eff4f90d08e0a1` on the
permanently retained `feature/workflow-migration` branch. Its 18 reviewed local
files were preserved byte for byte and committed separately. M4 implementation
commit is `8404a44eb9bad3c25627454cbafb311d2779b066`. The recorded evidence is a dated
pre-merge snapshot; the live PR and its final coordinator comment are the
authoritative delivered head/merge record:

[PR #5: Implement M4 Docker-only dispatch and report ingestion](https://github.com/henslewm/ai-template-oop/pull/5).

Fetch used `--no-prune`; current origin/main at verification was
`63b61ff9fcd1dba6676c6fd5dfb7561eaa92aed8`, already normally integrated. No reset,
force-push, prune, branch deletion or protected-checkout write occurred. Delivery
must retain the feature branch and synchronize it normally with merged main.

The preservation audit proves both protected HEADs, indexes and full statuses,
all **331 protected files**, all **18 original M3 files**, all **31 canonical
state/archive files** and all **14 retained scope-correction archive files**
match their entry inventories. Only the intended scope/runtime tracked code
changed; frozen approval, application contracts and packets match exactly.
The canonical project journal remains sequence 2 and head
`5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7`.
The actual receipt SHA256 remains
`33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f`,
with ACTIVE fingerprint
`8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.

## Remaining boundaries and next milestone

No paid worker, live provider/usage transport, host credential delivery,
application output apply, independent acceptance, deployment or hardware claim
was enabled. Actors are coordinator declarations; Docker/image/kernel and the
coordinator/host filesystem remain trusted. Approval replacement remains a
separate filesystem operation. Orphaned or missing manifests require explicit
operator inspection; they never authorize retry. Native M3 lifetime attempts,
replay, cost ceilings, held liability and conservative settlement remain intact.

M4_OPERATIONS.md documents the API, exact report/bundle contract and recovery.
The concrete next-session prompt is **M5_HANDOFF.md**. Stop before M5.
