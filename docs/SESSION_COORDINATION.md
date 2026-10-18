# Sessions on this Windows computer

Interactive project Git operations have standing owner authorization under
`MASTER_INSTRUCTIONS.md` → Standing Git authorization and session ownership.
There is no per-push, PR or merge confirmation. Independent review and checks
still gate integration. No application ABC, frozen receipt, client permission,
hook configuration or paid-workflow activation changes.

## Start and own work

Before coding, inspect status/worktrees, fetch without pruning, and compare
`origin/main` with `git ls-remote origin refs/heads/main`. Start an isolated
retained `feature/*` checkout at that verified main, or deliberately integrate
main into your owned branch after preserving existing edits.

From each checkout use its Python environment:

```powershell
python tools/session_coordination.py status
python tools/session_coordination.py init
python tools/session_coordination.py register --name feature-worker --role worker
# One designated session instead registers --role integrator.
# Retain the returned token locally; never publish tokens or local paths.
python tools/session_coordination.py watch --token <token> --once
python tools/session_coordination.py watch --token <token>
```

`status` does not initialize state. `init` is idempotent and binds the GitHub
numeric repository identity and policy. All independent clones/worktrees under
this Windows account use `%LOCALAPPDATA%/ai-template-sessions/<repository-id>/`.
Do not override LOCALAPPDATA per session or copy/delete the database. Other
Windows accounts and machines are deferred to the cross-machine follow-up issue.
Track that work in [issue #51](https://github.com/henslewm/ai-template-oop/issues/51).
GitHub permissions and protection rules are unchanged: cooperating agents obey
the lock; direct Git/GitHub commands can bypass it.

One active session owns each branch and checkout; one owns the integrator role.
Workers cannot change role in place. Run `watch` in an explicitly owned process
while active; it renews ownership and polls remote changes every 60 seconds.
It prints notices, including changes from outside the coordination tool. On
startup, resume and before integration also use `watch --once`. No process is
started silently, and no other terminal or checkout is controlled.

## Synchronize and integrate

```powershell
python tools/session_coordination.py sync --token <token>
python tools/session_coordination.py ack --token <token> --notice <id> --state deferred --detail "Saving current edits"
python tools/session_coordination.py sync --token <token> --apply
python tools/session_coordination.py submit --token <token> --pr <number> --head <40-char-sha> --review-file <review.json>
python tools/session_coordination.py integrate --token <integrator-token> --request <request-id>
python tools/session_coordination.py close --token <token>
```

`sync` inspects by default. `--apply` merges observed target commits into this
session's own clean checkout only. Dirty/conflicted work refuses; nothing is
stashed, reset or force-pushed. A merge conflict remains available for deliberate
resolution. Acknowledgments are seen, deferred, blocked or synchronized; the last
requires real ancestry. Unrelated work can continue deferred. Submission requires
current base ancestry, fresh checks and independent exact-head approval.

Review JSON is trusted coordinator-observed evidence, matching the existing live
pilot review model: `head`, separate nonempty `actor` and `implementer`,
`verdict: "APPROVE"`, `blocking_findings: []`. Keep the full report as evidence;
the CLI binds its SHA256 and saves the declaration in the registry. Obtain this
from a real independent review, never invent an approval. Hosting checks,
reviews and unresolved threads are independently reobserved through GitHub.
Review approvals under standing permission must obey hosting restrictions;
self-approval cannot satisfy the independent review gate.

Integration rechecks source/base and ownership immediately before a rebase merge
with an exact-head guard. A changed base requires sync, validation and resubmission.
It records durable intent before the call; crashes/timeouts retain an uncertain
intent rather than retry. Confirmed merges generate idempotent notices with
target SHA, paths, diff link and contract impact. Offline workers catch up later.
Feature branches and all registry history remain retained.

## Recovery and pilot

After 300 seconds without heartbeat, ownership is stale, never auto-transferred.
Verify the old session and merge subprocesses are stopped; then record the
evidence using the old token:

```powershell
python tools/session_coordination.py recover --token <old-token> --stopped-evidence "Observed old process exited; checked PR and remote outcome at ..."
```

Recovery reconciles confirmed merges/notices. A verified-stopped unmerged intent
is abandoned, requiring fresh submission; it is never silently replayed. Register
a new session after recovery. SQLite holds the writer transaction throughout a
merge call, so concurrent recovery cannot replace ownership during that call.
Clock rollback, unavailable hosting, lock contention and changed policy fail closed.

The separately activated pilot checkout must register as the integrator and set
`AI_TEMPLATE_INTEGRATION_TOKEN` to its token while its watch process maintains the
lease. Its existing checks still run; its merge then uses the same lock. This
does not activate the pilot, authorize paid calls or change offline controllers.

If coordination is unavailable, preserve work and stop shared-target integration.
Use explicit owner-directed recovery; never bypass the lock as a fallback.
