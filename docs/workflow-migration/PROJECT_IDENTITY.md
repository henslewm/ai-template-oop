# Portable project identity and offline approval

This is supporting infrastructure for the reusable OOP template. It does not
complete project generation or the OOP migration. Application features still
implement typed ABCs, receive dependencies through the composition root, and
share behavior tests with mocks. Presentation calls interfaces; business logic
stays in features. Workers still receive scoped context.

## Delivered boundary

`scripts/project_authority.py` owns one project identity format and one project
approval lifecycle. `tools/project_admin.py` is its operator entrypoint.
`workflow_state.active_anchor` selects this authority for initialized projects.
The small controller is procedural infrastructure, not an application framework.

The project identity record is `config/project.json`:

```json
{
  "schema_version": "workflow-project/1",
  "id": "<fresh canonical UUID>",
  "slug": "example-project"
}
```

The UUID is the logical project identity; the lowercase slug is its readable
name. Git worktrees retain that identity and share canonical control storage.
An independent clone of the same project retains its UUID but requires its own
owner approval. A different generated project must receive a fresh UUID.

`config/project-approval.json` is a versioned review package containing the
identity, fixed offline policy and normalized SHA-256 inventory of control
code/configuration. Scripts, tools, contracts, runtime files, configuration,
governing root files and the immutable pilot acceptance checks are covered.
Untracked control inputs also count. Ordinary `src/` implementation changes,
application tests, README edits and other documentation do not require control
plane reapproval. Application interface changes retain the existing separate
contract approval requirements.

The approval decision is **not stored in the project tree**. Registration and
hash-linked owner decisions live under the existing canonical
`LOCALAPPDATA/ai-template-workflow/<Git-common-identity>/project-authority/`
directory. They bind the project, reviewed package and actual Git common
directory. Copying a project, or even copying its host receipt to a different
Git common directory, cannot activate that checkout. These records do not
replace task, budget, ownership or acceptance records.

## Use in a fresh project checkout

Use Windows Python 3.12+ and the existing declared development dependencies.
Run the commands from a checkout containing this implementation. `--root`
must identify the exact Git worktree root; paths containing spaces are supported.
Do not initialize the retained migration worktree or an existing live project
as a fixture.

```powershell
python -B tools/project_admin.py --root '<new-checkout>' status
python -B tools/project_admin.py --root '<new-checkout>' init --slug example-project
python -B tools/project_admin.py --root '<new-checkout>' review
```

Inspect `config/project-approval.json`, its policy and the implementation it
binds. Review emits a fingerprint and prepares the package; it grants no new
authority. After explicit owner approval of that exact package:

```powershell
python -B tools/project_admin.py --root '<new-checkout>' activate --owner '<owner>'
# At the prompt, type: APPROVE <the-reviewed-fingerprint>
python -B tools/project_admin.py --root '<new-checkout>' status
```

`--decision 'APPROVE <fingerprint>'` is available for an explicitly authorized
noninteractive operator. It is never supplied automatically by initialization
or review. Owners and timestamps are declarations from a trusted host operator,
not cryptographically authenticated identities.

Successful activation reports `ACTIVE_OFFLINE`. Paid workers, provider egress,
publication, merge and deployment remain unauthorized; API caps remain zero.
The separate live pilot still requires its original independently reviewed,
checkout-bound authority, exact implementation inventory, objective and gates.
Project approval does not satisfy or generalize pilot approval.

## Change, revoke and recover

Changed control inputs make an existing package stale. Explicit `review`
refreshes that package; approval of an older fingerprint cannot authorize the
new one. Activation appends a decision without dropping earlier decisions.
Use `revoke --owner '<owner>'` and type `REVOKE <current-fingerprint>` to revoke
the current reviewed package. A stale package must first be reviewed. Status
shows a blocker whenever approval is missing, stale, revoked or malformed.

Existing task streams remain bound to their original anchor. Approval changes
do not rebind streams, replenish budgets, reset attempts or authorize implicit
relaunch. Historical reads and permitted outcome recording retain their
existing behavior. There is no automatic journal migration in this package.

Initialization refuses an existing project identity or canonical workflow
state. It never converts the existing migration campaign into a new project.
Mutations use a Git-common-directory lock and complete JSON replacement.
Linked paths, multiply linked inputs, corrupt decisions and interrupted locks
hold authority. After interruption, inspect the process, lock and preserved
records explicitly. A partial initialization keeps its registered UUID and
cannot be retried as a different identity. No cleanup/reset operation is
provided; retain evidence before a separately scoped recovery decision.

## Historical compatibility and limits

The frozen `config/workflow-bootstrap.json`, its validator, receipt and bound
files are unchanged. Without project records/registration, existing campaign
controllers retain their historical foundation path. Its copied ACTIVE receipt
still validates **as the historical offline foundation**, not as new-project
approval. A focused tracked-files export test reproduces that distinction.

Once project identity, project review package or host registration is present,
the runtime adapter uses the project gate and refuses missing/stale approval.
Deleting just the project identity cannot fall back to campaign authority.
This is explicit initialization infrastructure; it does not automatically turn
every old template copy into a generated project. A later generator must call
initialization and must not transfer host approval or canonical runtime state.

This package changes no application ABC, feature, composition root, UI,
branch, historical approval or existing canonical record. Adopting changed
controller code in a live pilot checkout changes its implementation inventory
and requires the pilot's own review process. No live pilot checkout is changed
by this work.

## Focused verification and next package

`tests/test_project_authority.py` covers fresh identity, copied/foreign receipts,
literal decisions, stale code/policy/identity, revoke/reapprove, immutable task
anchors, shared worktrees, concurrent initialization, interrupted writes/locks,
hardlink refusal, read-only status and the historical tracked-export claim.
All approvals in those tests are disposable fixture declarations.

The next architectural deliverable is bounded intake/generation that creates
a small project demonstrating typed contracts, injected real/fake feature
implementations and shared behavior tests. It should consume this lifecycle,
preserve worker scope, and generate inactive software/hardware project records.
More workflow machinery alone is not completion of the reusable OOP template.
