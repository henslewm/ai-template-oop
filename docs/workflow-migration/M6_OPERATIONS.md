# M6 shared handoff and integration readiness

`scripts/workflow_handoff.py` and `scripts/workflow_closeout.py` are coordinator
administration tools. M2-M5 remain the authorities for lifecycle, reservation,
review, accounting, ownership, consumed starts and exact stopped evidence.
M6 adds no worker/model transport, output application, merge or deployment API.
Default resources/harness remain disabled and real API caps remain USD 0.

## Derived views and explicit resume

Use an existing `workflow_state.Journal(root)`. Construction and view operations
do not initialize storage. The canonical Git-common-directory state is shared
across worktrees; no alternate state override is added.

```powershell
python -B scripts/workflow_handoff.py view --audience startup
python -B scripts/workflow_handoff.py view --task task:EXAMPLE --audience coordinator
python -B scripts/workflow_handoff.py resume C:\path\to\saved-view.json
```

A clean task with no M4 scope needs an explicitly supplied `--scope` file for
the named task. Existing dispatches derive scope from their Journal intent;
a view cannot replace that scope. Worker/coordinator/startup audiences share
bounded facts, with host workspace paths and ownership tokens omitted from the
public view. The private authority digest binds those facts. A worker view is
information only and is not an export or an execution capability.

Views include objective, task/revision/contract, owned paths, branch/base/diff/
interface, pending dispatch/check/review, attempts/caps, accounts/spend/liability,
blockers, exact evidence references and the next explicit operator action.
Recent history is capped at five, task lists at sixteen and authority inventories
at 128. Oversized views refuse for decomposition rather than silently dropping
authority. Serialized views are bounded at 40000 bytes. Timestamps are UTC;
views expire after 300 seconds. Context estimates count serialized UTF-8 bytes
conservatively, while measured model context and provider usage remain unknown.
Saved attempt usage, if present, retains its separate coordinator evidence.

`build` observes twice and refuses changes; `verify` regenerates current facts
and rejects changed approval, heads, Git/index/scope/interface, evidence,
ownership/start history or edited content/context labels. These observations
are not a distributed transaction across Git, SQLite, approval and Docker.
No saved view grants authority between observations. Regenerate before action;
the existing controller repeats its own full preflight.

`resume` returns an action and blockers only. A reservation without dispatch
intent requires explicit M4 reconciliation. Prepared runs require explicit
inspection and launch or abandonment. Consumed starts require stop/preservation/
reconciliation and are never restarted. Pending acceptance checks and reviews
use their existing explicit M5 ingest/reconcile/abandon APIs. Failed Docker
observations, missing evidence and ambiguous history hold. Old accepted tasks
whose workspaces advance remain historical facts and require a new packet.
Unknown cost stays held; resume never reserves, retries or replenishes attempts.

## Smallest approved context proposal

Python coordinator APIs are:

```python
proposal = propose_context(journal, view, [
    {"path": "src/features/auth/helper.py", "symbol": "parse", "reason": "Need exact caller signature"}
])
receipt = approve_context(journal, view, proposal["requests"], "Named Architect")
revised_scope = context_scope(journal, receipt, view)
```

The named architect must match the task authority. Paths are exact existing
files within the worker's role ownership; contracts, sibling roles, escapes,
links, duplicate/already supplied paths and path-count/size overflow refuse.
The proposal adds only those read paths and preserves every write path, base,
interface, owner and revision. It resolves the worker root from saved authority
when the coordinator is in another worktree. Added bytes and the original facts
are digest-bound. It never edits a pending run or exports any new bytes.

An explicit approval creates one new conditional `context:<digest>` Journal
receipt. Identical retries, including a lost response or a racing commit,
return that receipt without changing history. Historical receipt replay can
outlive the view; deriving a usable scope separately requires a current view
and unchanged original/added context. Changes require a fresh proposal. The
existing controllers still determine whether a new reservation is permitted.

## Exact integration evidence

M5 acceptance binds an unapplied replacement plus exact feature/UI/base input
commits. M6 requires a separately prepared integration commit whose entire tree
equals that accepted base plus the exact replacement bytes/modes. It creates no
commit and applies no output. It verifies ancestry and all commit objects.
Accepted, integrated, VERIFIED dependency and deployed facts remain separate.

The trusted coordinator prepares a manifest under a new canonical `run-*`
evidence directory, then calls `record_validation`. The manifest contains:

- `binding`: the exact `candidate_tree(...)` result, including candidate commit,
  tree digest, accepted input commits and complete submission digest.
- `checks`: exactly `contract`, `boundary` and `affected-runtime`, each with
  `status: PASSED` and a distinct nonempty `Journal.Evidence` log reference.
- `review`: independent named actor, exact candidate `head`, `verdict: APPROVE`
  and a nonempty digest-bound report reference.
- `interface_change`: null for an internal change; otherwise named owner and
  architect, exact accepted `ui_commit`, `mocks_path: src/ui/mocks.py`, exact
  `linked_paths` and an approval Evidence reference.

The interface approval document binds candidate, interface revision, changed
contract paths, owner/architect, UI commit, mocks path and the same linked paths.
Every linked UI path must match the accepted UI commit; mocks must exist and
match. Interface changes require linked UI work. The whole live-main diff is
restricted to accepted replacements plus explicitly approved contract/UI/test
paths; unrelated work carried in an ahead-of-main input base refuses readiness.
No arbitrary command in a manifest is executed. Checks must have been observed
through the approved isolated process; M6 records trusted coordinator evidence
and cannot authenticate a fabricated host-admin observation.

```powershell
python -B scripts/workflow_closeout.py record-validation task:EXAMPLE --candidate <exact-commit> --manifest run-integration/manifest.json
python -B scripts/workflow_closeout.py ready task:EXAMPLE --candidate <exact-commit> --receipt C:\path\receipt.json --pr 9 --retained C:\path\retained-refs.json
```

The retained baseline is the `retained_refs` object from an earlier observation:
nonempty `local` and `origin` maps of permanent branch names to exact tips.
Without it readiness reports HOLD/BASELINE_REQUIRED and supplies a current
inventory; an empty or malformed baseline refuses. Old names must survive and
old commits must remain ancestors. No branch cleanup, reset, forced push or
rename operation exists. The disposable two-release scenario tests distinct
main merge commits and normal synchronization back into the retained branch.

## Live hosting gates and limits

Readiness reads destination GitHub repository/PR facts, effective base-branch
protection/rules, paginated statuses/check runs/reviews/comments/threads and
current origin branch tips. Origin/PR/local candidate tips must agree. The PR
base must equal observed origin main. Automatic branch deletion must be false.
All configured required checks must succeed for the exact head and required app;
missing, pending, failed, skipped or unavailable checks cannot count as green.
No configured required checks is reported as NONE_CONFIGURED. Unsupported required
workflow/deployment/code-scanning rules hold for explicit inspection.

The exact candidate requires independent scoped review. Outstanding decisive
CHANGES_REQUESTED reviews survive later pushes/comments until superseded or
dismissed. Unresolved/unobserved review threads hold. Visible immutable automated
review rounds are capped at four; a recognized mutable bot summary or edited
round marker makes the historical count unknown and holds readiness. It cannot
be treated as zero rounds or an independent approval. No bot review
is triggered by this tool. Live facts are observed again at the end; changes
require regeneration. A READY observation grants no merge or deployment authority.

Hardware/manual ingestion remains disabled and hardware stays UNVERIFIED.
Coordinator/actor/model declarations, Docker/image/kernel and host filesystem
retain the existing trust boundary. M6 has no provider, credential, connector,
unrestricted network export or host execution of untrusted commands.

The final evidence is M6_SOURCE.json, M6_REVIEW.md and M6_VERIFICATION.json.
`tools/check_m6_preservation.py` supplements every unchanged historical audit
with all 131 M6 entry files. These raw-byte audits apply to this original retained
environment, not to a portable fresh clone; no frozen baseline is refreshed.
