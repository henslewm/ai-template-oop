# M2 host state and next-session starting point

Recorded 2026-10-14 UTC after final regression, review and preservation checks.
This is a derived handoff note; verify current journal heads before continuing.

M2 is implemented, reviewed and locally verified. At the final-regression
snapshot, the new source/test/tool/docs files were uncommitted. HEAD was
`3fba5742044abcce7a664e3030e15a5db33f7b2b`, and every pre-existing local/cached
remote ref and both protected checkout statuses/indexes were preserved.
M3 has not started. Read `M2_ACCEPTANCE.md`, `M2_REVIEW.md`, `M2_OPERATIONS.md`
and `M3_HANDOFF.md` before implementation.

## Canonical control state

```text
Directory:
C:\Users\hensl\AppData\Local\ai-template-workflow\305e980a31665052aeec61623e4baeb216a6867cda0cf51297253375180a8247

Database: control.sqlite3
Stream: project:workflow-migration
Sequence: 2
Head: 5e1f221812eaabd3666f40d4c003a046840ee01e4a51cba0e1881a19e1546bf7
Evidence: run-m2-20261014T182435Z
```

The stream contains one project INIT followed by MILESTONE_VERIFIED for M2.
The latter references eight digest-checked copies of the implementation,
regressions, approval-test runner, plan, operations, review, acceptance record
and M3 handoff. It records the fresh reviewer, AC-01/AC-09 verification, 271
full-suite tests, 46 frozen approval tests, 89 M2 cases and branch-enabled 99%
coverage. Verification of the actual host journal and registered evidence passed.
No task dispatch, ownership claim, worker launch or M3 controller was created.

A real host control backup also completed and passed journal verification:

```text
Backup directory:
C:\Users\hensl\AppData\Local\ai-template-workflow\305e980a31665052aeec61623e4baeb216a6867cda0cf51297253375180a8247\backup-m2-20261014T182435Z

Manifest SHA256:
7cc78178fc07472e6347f685a7eb4916fc283e47410fa1885df8146334faf2b0
```

The control backup is not a replacement for retaining ownership/startup databases
and other historical evidence. Do not overwrite, delete or reinitialize existing
control state to begin M3. Imported task histories must retain their own INIT,
IDs, anchors, hashes, counts, pending dispatches and costs.

## Startup checks

```powershell
python -B scripts/workflow_state.py foundation
python -B scripts/workflow_state.py directory
python -B scripts/workflow_state.py verify
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
git status --short --branch
```

Use explicit `recover` only if an interrupted SQLite write needs rollback
recovery. Every actual scheduling/launch preflight must freshly check approval;
the completed M2 record is not a worker execution permit.

The ACTIVE foundation fingerprint and manifest bytes are unchanged. All live
resources remain disabled and workflow API budgets remain USD 0. The next scoped
work is M3 router/feedback/budget policy (AC-04/AC-05/AC-06), with the copy/paste
prompt in `M3_HANDOFF.md`. Full M1/M5 runtime acceptance and publication remain
separate from this verified storage milestone.

## Owner-authorized Git delivery

After verification, the owner explicitly requested commit, push and an M2 PR,
with the owner performing the PR merge before a new M3 session. This manual Git
delivery does not change the frozen foundation's worker/publication settings or
authorize any controller or paid worker execution.

The retained branch was synchronized by a normal, non-rewriting merge of
`origin/main` at `517a770dd7346fc5d6c530781719365fc9ff409e`. The synchronization
commit is `051a3a6b3c534eff232b604a87a7d5bb096a792a`, with parents
`3fba5742044abcce7a664e3030e15a5db33f7b2b` and the main commit above. Its tree
is unchanged from the reviewed M1 baseline. This avoids repeating squash-merged
M1 changes in the M2 PR; no retained history was reset or force-pushed.

The M2 delivery consists of exactly these nine files:

- `scripts/workflow_state.py`
- `tests/test_workflow_state.py`
- `tools/check_workflow_approval.py`
- `docs/workflow-migration/M2_PLAN.md`
- `docs/workflow-migration/M2_OPERATIONS.md`
- `docs/workflow-migration/M2_REVIEW.md`
- `docs/workflow-migration/M2_ACCEPTANCE.md`
- `docs/workflow-migration/M2_CLOSEOUT.md`
- `docs/workflow-migration/M3_HANDOFF.md`

The three reviewed implementation/test/tool hashes still match `M2_ACCEPTANCE.md`.
Only derived delivery/handoff notes were clarified after the 317-test regression;
the archived `run-m2-20261014T182435Z` evidence copies and journal head remain
unchanged. Actual ACTIVE validation and host journal verification passed again
after branch synchronization.

Post-synchronization delivery refresh: the full offline suite completed with
270 passed and one existing UI smoke test skipped in 86.69 seconds. The skip was
`tests/test_ui.py::test_bad_login_stays_on_login_screen`, reporting
`Tk unavailable: invalid command name "tcl_findLibrary"`. That same test then
passed in a fresh isolated invocation (one passed, 0.08 seconds). All 89 M2
cases and all 42 scope/runtime cases passed in the full run with the pinned
offline Docker image. The frozen approval projection was also rerun: 46 passed,
with the actual ACTIVE receipt bytes unchanged. Thus all 317 distinct cases
passed across the delivery invocations; the full invocation itself had a skip.
Boundary, Ruff lint/format and ty checks passed again. The recorded 99%
branch-enabled coverage is from the unchanged, reviewed implementation snapshot,
not a new delivery coverage run. Both protected indexes, statuses and HEADs,
plus all 331 tracked/untracked file hashes, matched the pre-delivery snapshot.

Fetching main refreshes the shared cached `origin/main` ref and can change the
original checkout's derived ahead/behind display. Its local `main` HEAD, staged
plan deletion, index bytes and file contents remain protected, as do the donor's
HEAD, index and eight untracked entries. Other retained branch refs are untouched.
GitHub automatic branch deletion remains disabled.

Use the live M2 PR and Git history for its delivery head and eventual merge SHA;
this document cannot contain its own commit's identifier. M3 must not start
until the owner merges that PR, its merge is verified, and the retained branch
is deliberately synchronized with current main while preserving local work.
