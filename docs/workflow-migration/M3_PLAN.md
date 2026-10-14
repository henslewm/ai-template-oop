# M3 design and implementation plan

Scope: AC-04, AC-05 and AC-06 only. Implement offline routing, cumulative
feedback and atomic budget reservations. Stop before M4; no worker, provider,
independent acceptance or Git publication is authorized by this milestone.

Entry evidence: PR #3 is MERGED, head a56743f20517577363bf5affccf3a27f66136c5a,
merge 63b61ff9fcd1dba6676c6fd5dfb7561eaa92aed8. Fetch used --no-prune. The
retained branch was synchronized by a normal merge of current origin/main.
The ACTIVE validator and existing canonical journal both passed before changes.
Protected indexes match M2; a new snapshot covers all 331 protected files.

Use pinned donor d6e582b7edeae24345a175f36639230726dbdead. Keep its stored
event semantics for imports, without rewriting bytes, policies or identities.
New destination events carry a distinct versioned controller binding and use
stricter transitions. An incompatible imported task can be inspected, never
silently relabeled for scheduling. All durable controller writes use Journal;
dispatch and settlement update task, role and project streams with append_many.
CAS compares every relevant head. Unknown costs retain ceilings and block new
metered reservations. Saved config/rates/approval/history reproduce decisions.

Native defaults: disabled resources, task/role/project USD 0, worker/reviewer
caps 2, policy tiers 3/3/2/2/1, repeated failures 2 per tier and 3 total, repair
1, blocker resumes 3, diagnoses 5, deadline 600 seconds, recent history 5 and
context 40000 characters. Packet limits may lower these bounds. Revisions and
resubmissions preserve lifetime attempts, identities, spend and liability.

Phases: adapt router and schemas; adapt pure feedback reducers; add budget
reducers and Journal adapters; port donor behavior and add destination negative,
concurrency and replay tests; obtain fresh scoped review; resolve findings;
run the split approval procedure, full existing/M2 regressions and relevant
static checks; record actual evidence, preservation and M4 handoff.

Keep the frozen manifest, validator/tests, architecture, application contracts,
canonical packet files, ownership/start state and archived evidence unchanged.
Use deterministic disposable fixtures for enabled resources and synthetic costs.
The existing repository has no global Ruff/typing/coverage configuration;
run available scoped tools, reporting gaps rather than migrating the toolchain.
