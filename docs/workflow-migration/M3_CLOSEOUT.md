# M3 closeout and current Git state

M3 implementation and AC-04/AC-05/AC-06 verification are complete locally.
Final split checks passed 402 distinct cases: 356 in the full offline suite
(no skips) and 46 frozen approval cases on the disposable projection. All
89 M2 cases and 42 scope/runtime regressions were freshly included. Fresh
scoped review passed 85 cases and closed F1–F6. An additional expert judgment
confirmed the native/source validator repair and exact historical replay.

Ruff lint/format and ty passed. BasedPyright has zero errors and 1219 dynamic
boundary warnings. Diagnostic coverage is 79.53% lines and 72.28% branches
across the three M3 modules, with no exclusions; legacy/error/CLI branches remain
visible. M3_VERIFICATION.json contains exact hashes, counts and uncovered paths.
M3_ACCEPTANCE.md distinguishes earlier skips and tooling retries from the final
green procedure. No earlier M2 result was used as a substitute.

The retained branch is feature/workflow-migration at
ef6ae42bdef7ef32793764400761383fe650bea7, a normal merge with parents
a56743f20517577363bf5affccf3a27f66136c5a and
63b61ff9fcd1dba6676c6fd5dfb7561eaa92aed8. M2 PR #3 was confirmed merged.
The branch is two commits ahead of origin/feature/workflow-migration because
it now includes the M2 main merge and synchronization commit. M3 additions
are new, uncommitted files; the index and every existing tracked file are
unchanged. No M3 commit, push, PR or main merge is claimed.

New implementation files: scripts/model_router.py, scripts/feedback.py,
scripts/workflow_budget.py; config/model-router.schema.json,
config/feedback.schema.json, config/model-router.json, config/feedback.json;
tests/test_model_router.py and tests/test_feedback.py. The accompanying M3
plan/operations/review/verification/preservation/closeout documents and
M4_HANDOFF.md are also new. Session scratch files were removed only after
the durable verification and preservation data were recorded.

Both protected checkouts retain original HEADs, index bytes, complete statuses
and all 331 tracked/untracked file hashes. The original staged plan deletion
and donor's eight untracked entries remain. All retained branch names survive;
no reset, force-push, branch deletion, prune or protected-checkout write occurred.

The actual ACTIVE receipt and its fingerprint remain unchanged, with resources
disabled and all real API caps USD 0. The canonical project journal still has
sequence 2 and head
5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7.
All 31 existing canonical-state/archive/backup files match the preservation
inventory. M3 created no live task or budget account, ownership claim, consumed
start or worker. Existing control state was not reinitialized or replaced.

Remaining boundaries: partial diagnostic coverage and dynamic typing warnings;
coordinator-declared rather than externally authenticated actors; no live
provider transport or trustworthy real usage; separate filesystem approval
replacement; no M4 dispatch/report adapter or M5 independent acceptance.
Remaining M1 AC-02/AC-03 independent export evidence is not closed by M3.
The copy/paste next-session prompt is in M4_HANDOFF.md. Stop before M4.

## Resume and scope correction

The owner reconfirmed M3 only. A stale saved goal naming M4 was mistakenly
followed into partial edits after the original M3 verification. Those edits
and their pinned-source scratch files were preserved in
`C:\Users\hensl\AppData\Local\Temp\m3-scope-correction-b0ee9f7b3e8a4c3b9a43d8e80857cfac`,
with an archive manifest and hashes. Only the known M4 additions were reversed.
All nine M3 implementation/test/config hashes now exactly match the final
reviewed snapshot; all existing tracked and staged diffs are empty. No M4
adapter remains in the active candidate, and no worker or canonical-state
write occurred during that partial work. M4 remains future work.

`M3_RESUME_VERIFICATION.json` records fresh checks, the archive digest,
preservation and current Git state after this correction. It supplements the
dated original M3 evidence. The retained branch and delivery status remain
unchanged; the additional resume record is also uncommitted.

Fresh post-restoration split regression passed **356 cases with no skips** in
115.88 seconds and **46 approval-projection cases** in 2.04 seconds: 402 distinct
cases, including all 85 M3, 89 M2 and 42 scope/runtime regressions. ACTIVE/source,
journal and boundary checks pass. Ruff lint/format and ty pass; BasedPyright
again reports zero errors and 1219 warnings (exit 1 for visible warnings).
No new coverage measurement was made; the unchanged snapshot's original
diagnostic coverage and its limits remain recorded in M3_VERIFICATION.json.
Fresh independent restoration review passed all 17 targeted controller/Journal
checks in 13.42 seconds, verified the nine hashes before and after, and found
no remaining correctness issue. The reviewer corrected a report-only config
hash transcription typo; the config itself was unchanged. All protected and
canonical inventories matched again after the full regression. There are 18
new uncommitted M3 implementation/evidence/handoff files and no tracked changes.
