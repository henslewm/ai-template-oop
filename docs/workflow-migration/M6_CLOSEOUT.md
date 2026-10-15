# M6 closeout

M6 implements AC-10, the remaining integration/readiness portion of AC-11,
and AC-12. It adds two coordinator modules, two test modules and two verification
tools. All 131 files tracked at entry remain byte-identical. Historical frozen
acceptance statuses and the separate M1 AC-02/AC-03 decisions are unchanged.

`workflow_handoff.py` produces bounded startup, worker and coordinator views
from current Journal, approval, scope, Git, evidence, ownership and start facts.
Explicit resume checks freshness and identifies blockers and the next operator
action. It cannot launch workers, grant retries, restore consumed starts or
replenish budgets. Missing-context proposals name exact paths/symbols/reasons;
only a named architect-approved, digest-bound minimal read-only addition can
derive a new scope. Views and proposals never replace authoritative records.

`workflow_closeout.py` checks the exact accepted replacement against the
integration candidate, linked interface/UI changes, independent validation and
live GitHub PR/check/review/retention facts. Unknown or edited automated-review
history holds readiness. The module has no integration, output-apply, push,
branch-deletion or deployment operation. Acceptance, integration, VERIFIED
dependencies and deployment remain separate facts. See [operations](M6_OPERATIONS.md)
for the supported APIs, limits, required evidence and refusal behavior.

| Requirement | M6 evidence |
| --- | --- |
| AC-10 | Thirty handoff cases exercise bounded role views, explicit interrupted resume, stale/concurrent observation refusal, exact approval/context binding, conditional approval replay, cross-worktree context and retained starts/liability. |
| AC-11, remaining readiness | Forty closeout cases exercise accepted artifact/tree/commit/mode bindings, exact interface and UI approval, independent validation, current PR/base/required-check facts, review history and readiness refusal. M5 acceptance itself is unchanged. |
| AC-12 | Real disposable bare-origin tests perform two distinct main merges, normally synchronize the retained feature branch, and preserve names/history without duplicate changes. Original-checkout preservation passes separately. No actual destination merge is claimed by these tests. |

Fresh independent [scoped review](M6_REVIEW.md) closed eleven findings before
final verification and found no remaining in-scope blocker. Its final report
binds all six frozen source hashes; retained probe/recorder records and their
digests are in [the review evidence manifest](M6_REVIEW_EVIDENCE/manifest.json).
Pre-final runs and snapshots are labeled separately and do not substitute for
final-source verification.

The six source/test/tool files were frozen at 2026-10-15 01:36:02 UTC in
[M6_SOURCE.json](M6_SOURCE.json). The complete final verification ran once,
2026-10-15 01:39:18–02:10:21 UTC. Source hashes matched before and after every
command, including the final command. The aggregate mismatch flag is latched;
a later match cannot erase an earlier mismatch.

| Final check | Actual result |
| --- | --- |
| Complete pytest split excluding the approval module | 614 passed, 1 skipped, 1851.44 seconds |
| Separate approval runner | 46 passed |
| Unchanged skipped Tk case, isolated after the complete run | 1 passed, 0.08 seconds |
| ACTIVE/source/fingerprint, Journal and boundaries | Passed |
| M4, M5, M1 acceptance and M6 preservation | Passed |
| Scoped Ruff lint and format | Passed |
| Scoped ty | Passed |
| Scoped BasedPyright, diagnostic only | Non-green: 26 errors, 1602 warnings, six files |
| Whitespace check | Passed |

[M6_VERIFICATION.json](M6_VERIFICATION.json) retains every command, output,
timing, exit code and source-hash observation. All 70 new M6 cases and existing
real-Docker campaigns are included in the complete run with image
`sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e`.
The complete run retains its Windows Tk skip, tracked in
[issue #4](https://github.com/henslewm/ai-template-oop/issues/4), even though
[the unchanged isolated case passed](M6_UI_RECHECK.json). That issue remains
separate. The required gates passed; this is not a claim that BasedPyright is
green. Its diagnostics include heterogeneous JSON/dictionary inference, pytest
fixture imports and annotations in these additive modules. No type configuration
was weakened and no existing typing diagnostic was suppressed.

Preservation checks retained the protected original checkout at
`f624e207276372d9386b669bf087a66b44aba714`, its staged plan deletion, the donor at
`d6e582b7edeae24345a175f36639230726dbdead` and all eight donor untracked entries.
The protected 331-file inventory, both raw indexes/statuses, 31 canonical files,
14 retained archive files and all 131 entry files are unchanged. These original
checkout raw-byte audits are not portable fresh-checkout gates; see the preserved
[M1 post-delivery review](M1_POST_DELIVERY_REVIEW.md). Baselines were not refreshed.

ACTIVE still has fingerprint
`8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
Canonical `project:workflow-migration` remains sequence 2, head
`5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7`.
All real API caps remain USD 0. Default resources, paid workers, live provider
transport, hardware ingestion and deployment remain disabled; hardware remains
UNVERIFIED. Declared actors and the coordinator/Docker trust boundaries retain
their existing limits.

Immediately before delivery, a fresh `fetch --no-prune` still observed local
feature, origin feature and origin main at
`34b5a3103b397bab6ae2e490a87a00aba6d118e3`. All four remote branches remained.
GitHub reported automatic branch deletion false, main unprotected, rebase merge
enabled and merge commits disabled. The earlier [live adapter observation](M6_LIVE_FACTS.json)
is explicitly a historical PR #8 observation; it does not establish readiness of
the new M6 PR. Delivery facts for the new PR must be read from its current exact
head and checks. No inherited donor automatic-merge authority is used.

The migration checkout also contains unrelated `Original_plan.md` and
`ORIGINAL_GOALS_HANDOFF.md` work. It is preserved and excluded from M6 delivery.
Work stops after M6; no actual task integration or deployment is performed.

Implementation commit `2a3a26bd796847db76c3bbfd956b39772730a578` was pushed normally
to the retained feature branch and delivered in
[PR #9](https://github.com/henslewm/ai-template-oop/pull/9). The subsequent
[dated delivery snapshot](M6_DELIVERY.json) records the exact observed head,
current base, empty required-check rules, preserved branches and passing
post-delivery preservation. CodeRabbit's SUCCESS explicitly means review skipped;
GitHub has no submitted PR review. The following evidence-only commit adds this
snapshot without changing any frozen source. Reobserve the live exact head before
a separate integration decision.
