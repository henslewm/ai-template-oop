# M5 closeout: independent acceptance only

M5 implementation and exact-source scoped review are complete. The final full
split procedure passed 578 distinct cases. M6 remains future work. Remaining
M1 AC-02/AC-03 evidence and criterion decisions stay open; M5_EVIDENCE.md records
what this milestone adds and what remains missing. Frozen criterion statuses,
foundation approval, application contracts and canonical packets are unchanged.

## Result and verification

Independent checks run in fresh Docker exports of the exact stopped M4 candidate.
The acceptance session is read-only, candidate inputs are root-owned, and the
coordinator observes actual check exits and preserves exact archive/log evidence.
Candidate/reference/commit/interface/scope/image/environment/evidence changes
invalidate gates. Actor, reviewer family/tier/risk floors, cumulative attempts,
M3 accounting, consumed starts, stopped-output negatives and idempotent feedback
synchronization remain enforced. Worker PASS cannot accept or apply output.

Final complete command from the owner request: **532 passed, no skips**, in
**1018.62 seconds**, followed by **46 approval-projection cases** in **2.08
seconds**. The full run freshly includes 69 M5, 107 M4, 85 M3, 89 M2, 42 scope
and 43 startup cases plus existing application/contract/packet regressions.
No older milestone result substitutes for this run. The intermittent Tk issue
did not skip in this final invocation; its historical issue #4 remains separate.

ACTIVE/source/fingerprint, canonical journal/evidence, application boundary,
M4/M5 preservation, scoped Ruff lint/format and ty checks passed. The eight
tested source/tool files remained byte-identical throughout verification. All
ten final reviewed source/config/test/tool hashes match the delivered source.
M5_VERIFICATION.json records actual commands, outputs, timestamps and hashes.

Fresh separate review is **PASS, F1–F7 closed** in M5_REVIEW.md. It independently
checked the final rejection/resubmission path, cumulative fingerprints/attempts/
accounting, real Docker chmod/write denial, high/critical flows, actual process
exits and atomic settlement/proof cases. One qualifying named architect report
can satisfy model and architect gates together while meeting cross-family/tier
floors, preserving native tier-4 cap one and the lifetime reviewer cap two.

Scoped BasedPyright is explicitly **not green**: four lazy-import-cycle errors
and 1454 warnings remain. Ty passes the changed implementation/tools; no checker
suppression, weakened configuration or global typing migration was introduced.
M5_TYPING.json retains the diagnostic. No new numeric coverage or universal
crash/exhaustive security proof is claimed.

The pre-final full run was intentionally stopped at 27 progress dots after the
rejection report projection defect was discovered; it has no completed suite
result. Its actual partial output and subsequent checks are retained in
M5_PRE_FINAL_VERIFICATION.json. Development fixtures also exposed descending
timestamps, an incorrect unknown-cost assertion and fake/real image-environment
ordering; those were corrected before the final run. Review findings and earlier
reviewer-only harness errors are retained honestly in M5_REVIEW.md.

## Preservation and operational limits

Both protected HEADs, indexes, complete statuses and all 331 files match the
entry inventories, including the original staged plan deletion and all eight
donor untracked entries. All 31 canonical files and 14 archive files match.
Seventeen M3 files remain byte-identical. Removing exactly the additive versioned
feedback hook reproduces the original eighteenth file's raw hash; the audit
does not refresh or weaken the old baseline. All M4 entry files except the three
explicit M5 baseline modifications remain byte-identical. All refs survive.

The ACTIVE receipt SHA256 remains
33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f,
with fingerprint
8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481.
Canonical project:workflow-migration remains sequence 2, head
5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7.
Default resources/harness stay disabled; all real API budgets remain USD 0.

Hardware/manual ingestion is disabled. Required manual gates remain UNVERIFIED
and block acceptance. No live provider/usage transport, paid worker, credentials,
connector, output apply, integration candidate or deployment was enabled. Actor
and model identities remain coordinator declarations. The host coordinator,
Docker/image/kernel and filesystem remain trusted. Approval-file replacement is
separate from SQLite; missing/ambiguous runtime manifests require explicit
inspection and never authorize implicit restart. M5_OPERATIONS.md records the
supported API and recovery path.

## Dated Git delivery record

Entry retained branch/head: feature/workflow-migration at
755ae2907a493b2d4bec42b1d44f02048c01372d, initially clean. Fetch used --no-prune;
origin/main at 7979303869b81fcd1611c8de7b76ff43942b3fb6 was already normally
integrated. A fresh pre-delivery fetch and normal merge again reported already
up to date. No reset, force-push, prune, branch deletion or protected-checkout
write occurred.

Implementation/evidence commit:
8799300ed483a333c7e8c0dc54c98a626cf24e71, pushed non-force to the permanently
retained feature branch. This closeout is a following documentation-only record.
At this record's preparation, the actual delivery PR is open and draft:
[PR #6: Implement M5 independent Docker acceptance](https://github.com/henslewm/ai-template-oop/pull/6).
It must be made ready, checked against the exact final pushed head, manually
merged under the owner's current authorization and normally synchronized back
into the retained branch. The linked PR and final coordinator comment record
the authoritative delivered head, merge SHA, synchronized feature tip and final
preservation checks; this dated pre-merge snapshot does not claim those future
actions have already occurred.

GitHub reports branch deletion on merge disabled. Main has no branch protection
or required checks configured, and no repository test workflow; the two dynamic
Copilot/Dependency Graph workflows are not represented as required test passes.
Inspect actual live checks and deletion policy again immediately before merge.
The protected local main checkout stays at f624e207276372d9386b669bf087a66b44aba714;
updating origin/main must not update that checkout or its staged work.

The next-session prompt is M6_HANDOFF.md. Stop before M6.
