# Migration handoff

Prepared 2026-10-12 UTC on the owner's Windows machine.
Role: migration coordinator and implementer; no additional agents launched.

## Objective and preserved state

Implement only packet-linked scope and ownership controls after proving a
Windows-hosted runtime boundary. Do not push, open PRs, merge or deploy.

Original checkout:
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop
Local main remains f624e207276372d9386b669bf087a66b44aba714.
The plan deletion remains staged; original local work was not reset, stashed,
cleaned, reconciled or committed. The Downloads plan was not copied here.

Source checkout:
C:\Users\hensl\Documents\GitHub\ai-template\universal-ai-project-template
Branch claude/layered-code-pattern, HEAD d6e582b7edeae24345a175f36639230726dbdead.
No source writes occurred; its eight previously listed untracked entries remain.

## Destination and diff

New separate worktree:
C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration
Retained branch: feature/workflow-migration.
Verified/fetched base and current branch tip:
a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4.
All pre-existing local and cached remote branch tips remained unchanged.
The fetch refreshed FETCH_HEAD and creating the worktree wrote shared Git
administrative metadata as authorized; original checkout/index content was preserved.

Added: the eight source files listed in SOURCES.md, workflow_scope.py,
workflow_runtime.py, scoped behavioral tests, runtime Dockerfile/probe and
this documentation/evidence.
Modified: pyproject.toml dev dependencies add source-pinned jsonschema==4.26.0.
Application contracts, feature implementations, UI, wiring and governing root
instructions are unchanged.

Migration edits are uncommitted. Intent-to-add entries in this worktree make
the exact added-file diff reviewable; the original checkout's index is untouched.
A delivery patch and file inventory are recorded in the host-only evidence
directory linked by evidence.json. Do not treat this patch as approval to apply it.

## Implementation and evidence

- Verified Docker Desktop 4.94.0, Linux Engine 29.8.2, WSL2 backend.
- Isolated image:
  sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e.
- Linux Python 3.12.15; Cline 3.0.70 startup/help; POSIX shell.
- Offline probe completed with every assertion passing, container
  workflow-isolation-probe-20261012, exited 0.
- Real exported feature/UI workspaces denied unrelated host/repository/sibling
  reads, immutable/unowned writes and shell escape attempts while completing
  allowed writes. No host repository or Git objects were mounted.
- Eight-thread and four-process collision checks; branch and workspace
  uniqueness; canonical state across worktrees; alternate-state refusal.
- Expired live-worker recovery refused; stopped output preserved; old ownership
  cannot restart. Real timeout stops the container and preserves output.
- Stale base/packet/interface/context and escaped/duplicate/linked output rejected.
- Final full suite: 139 passed, 0 skipped in 37.75s; boundary checker: Boundaries OK.
- Added CLI roundtrip/recovery test: 1 passed in 6.11s. It exercised
  state-directory, prepare, heartbeat, execute, bundle, check-output and recover.
- Focused Windows host symlink check: 1 passed. Linux runtime symlink escape
  denial also passed. An earlier suite had one transient Tk-dependent skip;
  the final suite had no skips. Full interactive UI readiness is not asserted.

Windows Docker cp normalized file UIDs despite archive ownership. A fixed
offline initializer now assigns owned-file UIDs before worker creation.
Local log rotation requires two files with compression; the adapter enforces
that supported bounded configuration. These failures were corrected and checked.

The packet parser's 42 original tests pass unchanged, and source/destination
blob hashes match. New checks are execution evidence, not independent acceptance.

## Commands versus procedures

See README.md for exact implemented commands and side effects.
Scope/output checking and packet validation are read-only.
Prepare, execute, heartbeat, bundle and recover write coordinator run state.
No command applies a candidate or accepts/integrates/promotes it.
Handoff, intake, approval, missing-context handling and linked UI scheduling
remain procedures. No slash commands were added.

## Remaining decisions and limits

The verified path is offline and local to one coordinator account/host.
Before live AI workers, the owner must approve provider-only egress and
credential delivery; the source routing/budget/attempt and acceptance controllers
must be integrated. No paid model or autonomous AI worker was launched.
Native Windows CLIs and hardware/runtime deployment remain unverified.

Repository-common-directory ownership covers its worktrees, not independent
clones on other machines/accounts. Distributed ownership needs a later design.
Scope allows direct writes to declared files, not atomic editor renames or
directory creation/deletions. Runtime package transitive dependencies are not
fully locked; the measured immutable local image is the tested artifact.
Runtime volumes, containers and evidence remain retained pending a retention
decision. Trusted host/daemon/kernel compromise is outside this boundary.

The owner retains application contract changes, scope exceptions and
integration approval. No exceptions were created. Approved future I/O changes
require linked UI work. No headless exception, approval workflow, closeout merge,
UI migration or live GitHub gate enforcement was implemented.

## Exact next action

Review the uncommitted diff and this bounded implementation. Do not widen the
worker network, copy governance indiscriminately, commit/push/merge, or modify
either protected checkout without further authority. Obtain owner decisions
before online worker integration or scope/contract exceptions.
Context utilization: unknown; no savings measurement claimed.

Resume prompt:

> Continue as migration coordinator in ai-template-oop-workflow-migration.
> Read docs/workflow-migration/HANDOFF.md, README.md, SOURCES.md and evidence.json.
> Preserve the original f624e20 checkout and its staged plan deletion and all source
> untracked work. Verify branch/base, current diff, source provenance and retained
> runtime evidence before acting. The offline controls are implemented and locally
> tested, but unaccepted/unintegrated/undeployed. No push, PR, merge, paid worker,
> contract change, scope exception or network expansion is authorized by this handoff.

## Authorized startup cleanup follow-up

The owner subsequently authorized only the bounded startup cleanup fix and
offline regression tests. Execute now guards the Docker start attempt as well
as execution: a startup timeout, refusal or interrupt triggers stop confirmation,
log capture and output preservation before ownership release. A refused ownership
check does not trigger cleanup. Cleanup failures retain the claim for explicit
recovery, and additional interrupts wait for cleanup to finish. CLI exit codes
and application/packet contracts remain unchanged.

Changed in this follow-up: scripts/workflow_runtime.py, the command reference
and this handoff. Added: tests/test_workflow_runtime_startup.py (untracked,
not staged). Its 23 fault-injection tests use simulated Docker operations and
real temporary SQLite ownership/output files; no containers or agents start.

Validation: 23 new regression cases passed; 120 tests passed in 11.03s when
running pytest with --ignore=tests/test_workflow_scope.py. The existing scope
suite was excluded to avoid its Git-commit fixtures and Docker launches during
this bounded fix. Boundary and diff-whitespace checks passed. No real Docker
startup fault test was run. Original/source checkout statuses, index hashes and
retained branch refs remain preserved.

The evidence.json and host-only delivery patch/inventory above remain historical
evidence for the preceding implementation; they have not been regenerated to
include this follow-up. All follow-up edits remain uncommitted. The next step
is review of this fix; online workers and further migration remain unauthorized.

## Offline review resume: stage 1, provenance and preserved state

Read this handoff, README.md, SOURCES.md, evidence.json and the destination
session/branch-retention instructions. The active role is migration coordinator
and reviewer; no delegated agents are authorized or launched.

Verified locally: feature/workflow-migration still points to
a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4. All eight imported Git blobs match
source commit d6e582b7edeae24345a175f36639230726dbdead exactly. The original
checkout remains on f624e207276372d9386b669bf087a66b44aba714 with the staged
plan deletion; the source remains on the pinned commit with its eight recorded
untracked entries. Retained local/cached remote branch refs match evidence.json.
There is no application, contract or root-governance diff.

The retained historical delivery patch exists and its SHA256 matches its
manifest: 0c9c8c448cbdb964ef0acc5ec224b2097a46fc97453006bf2bb0ed6c8117a2a7.
Its inventory predates the startup cleanup follow-up and is not current
acceptance evidence. Runtime evidence was read from retained local records;
no network request or live runtime was started.

Environment limitation: sandboxed PowerShell cannot start (CreateProcessAsUserW
error -1073283067). Specifically approved local commands run outside the
sandbox with the profile disabled and the destination working directory set
explicitly. The initial profile-enabled read-only attempt was redirected to
the GitHub parent directory; it made no writes. No restriction was bypassed.

Next stage: review the offline implementation and startup fault tests, then run
only checks that do not launch Docker workers or create Git fixture commits.
Keep all changes uncommitted. Network access, live workers, Git delivery,
contract/schema changes and scope exceptions need specific later authority.

## Offline review resume: stage 2, validation and startup retry blocker

Recorded 2026-10-12 UTC. The implementation was reviewed without changing
runtime code, application contracts, canonical packet schemas or imported
source files. The original startup-fault cases are included in this check:

`python -B -m pytest -q -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_scope.py`

Result: 119 passed, 1 skipped in 11.40s. The scope suite was excluded because
its fixtures create Git commits and some cases launch real Docker workers.
`python -B tools/validate_boundaries.py` reported Boundaries OK; the diff
whitespace check passed. This is a bounded offline check, not independent
acceptance or a new full runtime verification.

Important review blocker: a failed startup attempt is not recorded durably.
In scripts/workflow_runtime.py, start_attempted is only a local variable and
runtime.json is updated only after successful cleanup. Ownership.start in
scripts/workflow_scope.py checks the lease but records no consumed-start state.
If Docker start is refused while the container remains created and log capture
then fails, the claim stays claimed and runtime.json stays prepared. Calling
execute again with the same token starts the container without explicit recovery.
That contradicts the documented single-start/recovery requirement.

Reproduced with the existing startup execution fixture: simulated Docker and
repository preflight, real temporary SQLite ownership, baseline checks, logs
and output files. First attempt: startup refusal, container created, injected
log failure; events [start, logs], claim claimed, record prepared. After clearing
the injected failures, a second execute with the same token returned exited,
recorded two start attempts and released the claim as finished. No live worker,
Docker command, network request or Git mutation was used by this diagnostic.

The existing tests prove retained ownership prevents a replacement claim, but
do not check reuse of that retained token after failed cleanup. Required follow-up:
durably consume startup authority before calling Docker, refuse repeat/concurrent
starts with that token, and add offline retry/race regressions while preserving
explicit recovery and CLI exit codes. This is a proposed bounded runtime fix,
not authority to alter application contracts or canonical packet schemas.

No fix was applied: the prior handoff authorizes review of the startup fix and
states that further migration is unauthorized. The startup retry finding blocks
acceptance of the single-start/recovery claim. Continue only read-only evidence
and preservation checks until a specific later prompt authorizes the repair.

## Offline review resume: stage 3, preservation and review close

Final checks confirmed both protected checkout statuses exactly match
evidence.json, all retained local/cached remote refs match, and all eight
imported blobs still match the pinned source. Protected index SHA256 values
were unchanged across this review:

- Original: FE7124042405022BF442485CE5E340489D0B292F2BBAA8A8935321B6653EC39B.
- Source: AC3C6BEB7FE41745EDE3543CAC4F368AA310F6FD83A5DACCEAEF15042F5F4E25.

There is no staged delivery diff; the pre-existing intent-to-add entries and
untracked startup tests remain. This review changed only this handoff. Runtime
code, packet schemas, application contracts/implementations and root governance
were not edited. No delegated agents, network, live workers, commit, push, PR,
merge, branch deletion or source-governance import occurred.

The review is complete; acceptance remains blocked by the stage 2 startup-token
retry defect. The next implementation action requires a specific later prompt
authorizing the bounded offline repair and its retry/concurrency tests. Do not
treat the passing existing tests or historical runtime evidence as resolving it.

## Architecture approval package preparation

The owner authorized preparation of the destination architecture and bootstrap
approval package only, without activation. See ARCHITECTURE.md,
BOOTSTRAP_REVIEW.md and config/workflow-bootstrap.json. The read-only validator
is scripts/validate_workflow_approval.py; the inactive-only preparer is
tools/prepare_workflow_approval.py. Approval binds source/destination identity,
file digests, Docker isolation, split ownership/journal state, cumulative caps,
dispatch and independent acceptance, shared continuity and permanent branches.

Package preparation grants no approval and no runtime authority. The recorded
startup-token retry blocker remains unrepaired. Later owner approval would
cover bounded offline implementation only; paid models, provider access,
credentials, delegation, publication and merge remain outside this foundation.
The fingerprint is printed by the validator after verifying the bound files;
do not paste a stale fingerprint from historical runtime evidence.

No imported controller or source governance is activated. Runtime/application
code and packet schemas are unchanged by this preparation. Offline validator
integrity/refusal checks are separate from the package's pending implementation
acceptance criteria. Preserve both protected checkouts and all retained refs;
validate with --check-source --check-preserved --check-baseline before requesting
later approval. Foundation hashes and the inspected implementation baseline are
separate: routine candidate edits do not revoke the foundation, while initial
review can still prove exactly which implementation was inspected.

Validation for this preparation: the bounded offline suite (excluding
tests/test_workflow_scope.py, whose fixtures can commit or launch Docker) passed
165 tests with 1 skip, including all 46 new approval integrity/refusal cases.
The destination boundary checker and diff-whitespace check passed. Full package
validation checked pinned source blobs, protected checkout statuses/indexes,
retained local/cached refs and the inspected destination baseline.
--require-active refused this package as intended. No runtime/controller
acceptance, live Docker verification, network or Git publication was performed.
