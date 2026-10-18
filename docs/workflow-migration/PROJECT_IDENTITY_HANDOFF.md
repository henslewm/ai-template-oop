# Identity package handoff

Owner: Codex, sole implementation owner. Base: retained
`feature/workflow-migration` at `63b9e5f34d9c1a9e6726014de57607754147123e`.
Status: implemented and locally verified; independent scoped source acceptance
is **APPROVE, no findings**, recorded in [the review report](PROJECT_IDENTITY_REVIEW.json).
The owner subsequently authorized commit, publication and merge; the package PR
and Git history record delivery. No project or pilot activation or paid execution
is authorized by that delivery.

The package adds `scripts/project_authority.py`, `tools/project_admin.py` and
`tests/test_project_authority.py`; the only pre-existing source change is the
project-aware adapter in `workflow_state.active_anchor`. See
[operation and limits](PROJECT_IDENTITY.md). The canonical backlog is
[BACKLOG.md](BACKLOG.md); the next package is **B02: one runnable generated OOP
software project**, not more general workflow infrastructure.

## Behavior and limits

- Fresh project UUID/slug, explicit review, fingerprint-bound owner decision,
  checkout-local approval/revocation and preserved decision history.
- Initialized projects cannot use copied historical foundation approval or
  another checkout's receipt. Worktrees share their Git-common authority.
- Review changes neither task history nor budgets/attempts. Changed approval
  anchors cannot silently authorize old task streams. Routine application work
  does not require control-plane reapproval.
- The historical offline foundation path remains for uninitialized campaign
  checkouts. This is explicit initialization, not general project generation or
  automatic deactivation of every legacy template copy.
- Live-pilot authority and all existing restrictions remain separate. Existing
  application ABCs, implementations, composition root and behavior are unchanged.

## Verification

- Initial lifecycle/journal compatibility run: **113 passed in 98.74s**. This
  included the initial 24 lifecycle cases plus existing journal regressions.
  The subsequent focused run includes the final defensive cases/source.
- Final lifecycle/application/shell/pilot compatibility run: **111 passed,
  2 deselected in 651.33s**. It includes all 29 final lifecycle cases. The two
  real-Docker pilot cases are explicitly excluded; no worker or container is
  launched by this package's verification.
- Non-UI import-denial regression: **2 passed in 3.83s**.
- Frozen approval projection: **46 passed in 1.93s**; actual receipt SHA-256
  remains `33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f`.
- Application boundary validator, scoped Ruff lint/format and scoped ty pass.
  `git diff --check` passes; Git reports the existing Windows line-ending
  conversion notice for the intentionally edited adapter.
- Real-worktree read-only inspection returns the unchanged historical foundation
  fingerprint and project status `UNINITIALIZED`. No real owner receipt was issued.

Focused final command:

```powershell
python -B -m pytest -q -p no:cacheprovider -o addopts= tests/test_project_authority.py tests/test_contract_auth.py tests/test_contract_data.py tests/test_boundaries.py tests/test_operator_cli.py tests/test_live_pilot.py -k 'not real_sandbox_stopped_replay_and_independent_rejection and not consumed_unstarted_check_never_passes_after_abandonment'
```

No full M1–M6 campaign, GUI execution, hardware check or live provider call was run.
Passing checks are verification, not independent acceptance. The separate
fresh-context reviewer inspected the actual candidate and its source hashes;
the reviewer did not rerun tests. Review limitations are explicit in its report.

## Initial implementation candidate

Raw SHA-256 at initial acceptance, before the post-merge corrections below:

| Path | SHA-256 |
| --- | --- |
| `scripts/project_authority.py` | `1208cb1ed87860ca4b82fcfa66593b3213ee89410b9206e210ab108844d1b39d` |
| `scripts/workflow_state.py` | `954214cc6d4be3e9a68e89ab81162e1cac4d85c9f0222307ffedf2f2afeafb08` |
| `tools/project_admin.py` | `37880e974c62e4f5f9e1b250cb665dccea488d4ccc514a0a910857beadd407f8` |
| `tests/test_project_authority.py` | `44c6be3eecb7a9d72f8d16006dd791454ccf103f33b70cd12945353fbc286ae6` |

The reviewer checked copy/foreign-receipt refusal, no fallback for registered
projects, unchanged legacy campaign behavior, offline-only policy and preservation
of task anchors, budgets and independent acceptance. Review only these four files,
the operational note, this handoff and the backlog unless a named gap needs more
context. The report binds the exact working source inventory, including files
that were untracked before delivery; it does not approve the old HEAD alone.

## Preservation

Read-only before/after inventories confirm the protected original and donor
checkouts retain all tracked-file hashes, native indexes, HEADs and statuses.
Existing canonical migration state and historical local reviews are unchanged.
At the implementation-verification checkpoint, the retained index and HEAD were
unchanged; its pre-existing staged/deleted
`Original_plan.md` and untracked reviews remain intact. Only the adapter is changed
among existing tracked working files. No Pro-Se Engine file was accessed or edited.

Before/after inventory evidence is retained outside the repository under the
session's `project-identity-*` temporary directory. Do not refresh historical
preservation baselines or clean up unrelated staged/untracked work for delivery.

## Post-merge review corrections

PR #20 integrated the exact initially accepted tree. Its automated review was
still running at merge; subsequent findings from PRs #19/#20 were verified and
corrected in an isolated delivery checkout rather than editing the shared worktree.

Binary inputs now hash verbatim, while known UTF-8 text retains line-ending
portability. Missing/malformed identity returns a read-only approval blocker.
An interrupted operation lock also selects the project gate, preventing the
pre-registration crash window from restoring legacy authority.

Four binary/status regressions and one pre-registration interruption regression
failed before their corresponding fixes. The complete final lifecycle suite
then passed **35 cases in 37.79s**. Scoped Ruff lint/format, ty and whitespace
checks pass. No broad campaign or live execution was repeated.

[The follow-up independent review](PROJECT_IDENTITY_FIX_REVIEW.json) approved all
three corrections with no findings and binds the four current source hashes.
The original report/hash table remains historical evidence; use the follow-up
report for the corrected candidate. Application sources, contracts, pilot scope
and canonical task/accounting records are unchanged by these corrections.
