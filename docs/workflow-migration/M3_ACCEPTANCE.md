# M3 implementation verification

Scope: routing, cumulative feedback and budget policy, AC-04/AC-05/AC-06 only.
The implementation is locally complete and reviewed. This is implementation
verification, not independent acceptance of M1/M5 or authorization to launch,
publish, merge or deploy. Frozen criterion statuses remain unchanged.

## Entry and preserved authority

Live PR #3 was confirmed MERGED: head a56743f20517577363bf5affccf3a27f66136c5a,
merge 63b61ff9fcd1dba6676c6fd5dfb7561eaa92aed8, merged 2026-10-14T20:18:24Z.
Fetch used --no-prune. Its tree matched the supplied clean retained HEAD.
Current origin/main was then normally merged into feature/workflow-migration.
Synchronization HEAD: ef6ae42bdef7ef32793764400761383fe650bea7; parents are
the retained M2 head and M2 merge above. No history was rewritten.

The actual ACTIVE receipt remains Winston's 2026-10-14T02:07:06Z receipt with
fingerprint 8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481.
Raw manifest SHA256 remains
33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f.
The canonical project:workflow-migration journal remains sequence 2, head
5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7.
No control, ownership or consumed-start state was initialized, replaced,
deleted or scheduled during M3. Existing archived evidence is retained.

## Requirement evidence

| Criterion | Verified behavior |
| --- | --- |
| AC-04 | Pinned donor economic scoring, priors/observations, risk/complexity/role floors, declared tier path, provider outages, context capacity and exact saved-decision replay are ported. Native validator and CLI enforce the destination bounds; source validation remains explicit for historical replay. Actual rendered context and output headroom are counted. Reviewer actor/family/tier and cross-family floors are enforced before reservation and at outcome. |
| AC-05 | Worker and reviewer lifetime caps are 2, with packet/task/policy tier minima 3/3/2/2/1. Repairs, resumptions and resubmissions retain history and spend. Failure normalization, tier repetition, one repair, three blocker resumptions, five diagnoses, 600-second deadlines, five recent entries and 40000 characters are tested. Pending, stale, duplicate and mismatched operations refuse. Historical donor cap 8 remains historical and cannot confer destination scheduling. |
| AC-06 | One real SQLite append_many transaction reserves task/role/project, comparing every head. Same-task and cross-task contention produce one whole winner. Each cap independently refuses without partial writes. Settled spend, pending ceilings and unknown liability survive replay and revision. Null/zero/positive unmeasured costs and abandoned possibly charged runs remain held. Measured usage binds dispatch, saved rates and coordinator evidence; cache pricing is conservative and rounds upward. Token or monetary overruns record truthful spend and hold. Defaults remain disabled and USD 0. |

## Final fresh checks

```powershell
$env:WORKFLOW_TEST_IMAGE = 'sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e'
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_approval.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B scripts/workflow_state.py verify
python -B tools/validate_boundaries.py
ruff check scripts/model_router.py scripts/feedback.py scripts/workflow_budget.py tests/test_model_router.py tests/test_feedback.py
ruff format --check scripts/model_router.py scripts/feedback.py scripts/workflow_budget.py tests/test_model_router.py tests/test_feedback.py
uvx --offline ty check scripts/model_router.py scripts/feedback.py scripts/workflow_budget.py
```

- Final full suite: **356 passed, no skips**, 158.00 seconds. This freshly
  includes all 89 M2 cases, all 42 scope/runtime regressions with the pinned
  offline image, existing application/packet tests and 85 M3 cases.
- Final frozen approval projection: **46 passed**, 4.16 seconds; actual ACTIVE
  manifest bytes unchanged. Thus **402 distinct cases passed** across the split
  final procedure. The earlier M2 number was not substituted for fresh results.
- ACTIVE/source/fingerprint, existing journal/evidence and application boundary
  checks passed. Ruff lint/format and ty passed. BasedPyright reports **zero
  errors and 1219 warnings**, chiefly untyped donor/frozen APIs, dynamic JSON,
  argparse and SQLite adapters. No checker suppression or configuration weakening
  was introduced; repository-wide typing migration remains separate.
- Earlier pre-final full run: 350 passed and one Tk smoke test skipped in
  123.82 seconds, reporting unavailable Tk/ttk spinbox.tcl. That case passed
  alone in 0.09 seconds. The final full invocation above had no skips.
- Initial router CLI fixtures hit sandbox temporary-file restrictions; authorized
  reruns passed. An optional coverage environment pin was unavailable offline;
  cached tooling was used instead. Module-name coverage initially missed the
  router's donor import alias; final measurement uses filesystem paths.

Fresh review is recorded in M3_REVIEW.md. Four initial findings were repaired:
terminal repair history, cross-family eligibility, default durable deadline and
raw cost shape. A further expert judgment requested the strict native validator
split; an actor-name probe also led to whitespace/case-independent identity
comparison. Their regressions are included in the final 85 M3 cases. Pinned
source lifecycle/import/export probes preserve original hashes, bytes, cap,
attempts, repair counts, source approval and settled spend. Those historical
ACCEPTED records are not new destination acceptance.

## Preservation and limitations

M3_PRESERVATION.json records both protected HEADs/statuses/index hashes, all
331 tracked/untracked file hashes, retained refs and the existing canonical-state
inventory. Both complete protected inventories matched; the staged original
plan deletion and donor's eight untracked entries remain. All 31 existing control,
ownership/startup, archive and backup files matched the recorded inventory.
Existing tracked files, frozen approval material, contracts and canonical packet
files have no diff. Only new M3 files and the requested normal merge were added.

No provider transport, measured live rates/usage, paid worker, credential delivery,
M4 dispatch/report adapter, M5 independent acceptance or deployment was enabled.
Actor identities are coordinator declarations, not external authentication.
SQLite approval replacement is still a separate filesystem boundary; M4 launch
must revalidate approval and every saved binding. Semantic replay requires the
controller reducer, and incompatible source imports are held for new scheduling.
Independent M1 AC-02/AC-03 export evidence and M5 remain outstanding.

Coverage and the final reviewed snapshot hashes are recorded in
M3_VERIFICATION.json. Coverage is diagnostic, with remaining legacy/error/CLI
branches visible; the repository has no global coverage gate. These tests and
reviews do not assert every possible historical ledger or live runtime outcome.

## Resume verification

The owner reconfirmed M3 only after a stale saved M4 goal led to partial edits.
Those edits were archived and reversed without deleting work; the nine M3
implementation/config/test files exactly match the reviewed hashes above.
No M4 adapter remains in this candidate. The fresh restoration review and
regression results are recorded in M3_REVIEW.md and M3_RESUME_VERIFICATION.json;
the original dated measurements above remain historical evidence. See
M3_CLOSEOUT.md for the archive location and current delivery status.

The fresh split run passed 356 cases with no skips in 115.88 seconds, followed
by 46 approval cases in 2.04 seconds. All 402 distinct cases passed. It freshly
includes the 85 M3, 89 M2 and 42 scope/runtime cases. ACTIVE/source/fingerprint,
journal/evidence and boundary checks also passed. Scoped Ruff lint/format and
ty passed; BasedPyright again had zero errors and 1219 visible warnings.
