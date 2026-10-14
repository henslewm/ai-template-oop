# M2 design and implementation plan

Owner request: finish M2 and provide a copy/paste handoff for M3. The current
worktree is the retained `feature/workflow-migration` branch at `3fba5742044abcce7a664e3030e15a5db33f7b2b`.
Its tree matches merged commit `517a770dd7346fc5d6c530781719365fc9ff409e`.

## Design contract

Implement the approved architecture's canonical control journal/bootstrap
adapter and AC-01/AC-09 checks. One `control.sqlite3` belongs to the Git common
directory identity used by the existing runtime. Ownership and startup databases
remain separate. Reads and foundation inspection do not create storage.

Use SQLite FULL synchronous transactions, immutable event rows, explicit
compare-and-swap stream heads (including one atomic transaction across task,
role and project streams), strict JSON, UTC monotonic timestamps, and donor
six-field event envelopes. Preserve original imported bytes and canonical hashes.
An import requires complete structural and semantic replay, cannot replace an
existing stream, and records its provenance and replay state digest atomically.
Every referenced evidence file is bounded, link-free, within the canonical state
root, and checked by size and digest. Broken history/evidence refuses further use.
Backups contain the consistent journal and its evidence; restore verifies the
externally supplied manifest digest, repository identity, heads, and evidence
before installing a journal, and never overwrites existing control state.

New scheduling events require current ACTIVE approval matching the stream's
anchor. Recording a late outcome or hold remains possible after revocation;
this cannot confer new launch authority. The module performs no worker launch.

Decision: keep the frozen validator, approval manifest, tests, and foundation
bindings unchanged; put the adapter in `scripts/workflow_state.py`.
Reason: those files are fingerprint material, while ordinary candidate changes
have separate acceptance evidence. Source: approved package and receipt.
Invalidates if: the owner explicitly approves a replacement foundation.

Application contracts, packet hashes, provider/credential access, paid workers,
M3 controllers, publication, and branch cleanup are outside this implementation.
The earlier M1 review has passing offline checks but retains current Docker
acceptance evidence gaps; M2 does not silently accept those criteria.

## Implementation phases and gates

1. Add the bootstrap adapter, canonical journal, strict append/read/replay and
   evidence validation. Test ACTIVE/inactive/stale/reforged approval, alternate
   state, corruption, stale heads, cross-worktree identity, and atomic append.
2. Add one-time source-chain import and audit export, then verified backup and
   restore. Test byte/hash/ID/counter/spend retention, semantic refusal, gaps,
   malformed JSON, path/link refusal, damaged evidence, and existing-state refusal.
3. Exercise thread/process contention and real child-process kill/restart before
   and after commits on Windows. Run M2 tests, frozen approval tests using an
   inactive disposable projection, existing offline regressions, boundaries, and
   whitespace checks. Review the implementation against every AC-01/AC-09 item.
   Use a fresh reviewer for the journal correctness audit while CLI verification
   and documentation proceed independently, as the Short Circuit skill directs.
4. Record evidence, CLI usage, implementation limits and M3 handoff instructions.

The repository's canonical test tools are pytest and the boundary checker.
It has no configured Ruff/ty/basedpyright/coverage gate. Use available tooling
for the added modules; a repository-wide toolchain migration is deferred because
it would modify bound project configuration and exceed this milestone.

Keep plan/evidence/handoff artifacts in the established migration docs directory;
do not modify `.gitignore` or the frozen approval snapshot for skill defaults.
