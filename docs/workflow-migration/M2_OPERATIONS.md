# M2 control journal operations

The coordinator journal is `scripts/workflow_state.py`. It adapts the frozen
destination validator without changing the ACTIVE manifest or its fingerprint.
It performs no worker launch, model call, task acceptance or Git promotion.
The application interfaces and eight exact donor imports remain unchanged.

## Storage and authority

All worktrees sharing a Git common directory resolve to the existing runtime's
canonical host-local state directory. `control.sqlite3` is separate from
`ownership.sqlite3` and `startup.sqlite3`; retain all applicable stores and run
evidence when backing up the complete workflow. M2 control backups contain the
control journal and its registered evidence only, and do not pretend to back up
the independent runtime ownership stores.

Construction, `foundation`, `directory`, `read`, `replay`, and `verify` create no
storage. Initialization is explicit and refuses an existing database. Alternate
state paths, links/junctions, multiply linked files, broken chains, stale heads,
nonfinite/ambiguous JSON, descending or non-UTC timestamps and changed evidence
are refused. Native and imported streams begin with exactly one INIT. History
cannot be reset by reinitializing or reimporting a stream.

Every write uses a FULL synchronous SQLite transaction. `append_many` compares
each expected head and commits up to sixteen distinct streams together; any
refusal rolls back the entire batch. This is the M3 substrate for atomic task,
role and project reservation bookkeeping. The storage layer does not calculate
budget caps or make routing decisions.

New scheduling events require current ACTIVE approval matching the immutable
stream anchor, checked again after reducers/evidence work immediately before
commit. Late RESULT/ABANDON/REVIEW/hold/reconciliation events can be recorded
after revocation to retain liabilities and outcomes. These event names grant no
launch authority. M3/M4 controllers must validate their semantic transitions and
provide exact packet/config/rate/dispatch bindings; direct journal access belongs
to the trusted coordinator, never to workers.

Approval replacement is a separate filesystem operation and does not share the
journal's SQLite lock. The final check closes the slow validation interval; it
does not claim an atomic transaction with arbitrary receipt editors. Future
dispatch and launch preflight must independently validate current approval.

## Commands

Run from the migration worktree using Python 3.12+ on Windows:

```powershell
python -B scripts/workflow_state.py foundation
python -B scripts/workflow_state.py directory
python -B scripts/workflow_state.py verify
```

After a coordinator crash, SQLite may leave a hot rollback journal whose
recovery requires writing existing uncommitted pages back to their committed
state. Read-only `verify`/`replay` can refuse that condition. Recover explicitly:

```powershell
python -B scripts/workflow_state.py recover
python -B scripts/workflow_state.py verify
```

Recovery does not initialize missing state, edit stream history, release
ownership, or launch anything. It verifies repository identity, full event chains
and registered evidence after SQLite's rollback recovery. Corruption still holds.

If control state is absent, initialize it once:

```powershell
python -B scripts/workflow_state.py initialize
```

Export writes numbered JSON as an audit view, preserving source event bytes.
An export is never a second writable ledger. Use a new output directory:

```powershell
python -B scripts/workflow_state.py export --stream project:workflow-migration --out "$env:LOCALAPPDATA\ai-template-workflow-audits\m2-20261014"
python -B scripts/workflow_state.py backup --out "$env:LOCALAPPDATA\ai-template-workflow-backups\m2-20261014"
```

Backup prints its manifest SHA256. Keep that digest outside the backup and use
it for restore. Backup uses a consistent SQLite snapshot and copies every
registered evidence file after digest/size verification. Partial failed backups
are retained for inspection and must not be treated as completed backups.

Restore verifies the externally supplied manifest digest, repository identity,
database content, all stream heads and every evidence reference before installing
control state. Database bytes are captured once and verified in a private copy;
those exact bytes populate the staged installation, whose digest and heads are
checked again. A concurrently changed backup cannot substitute different history.
Restore refuses an existing control database or conflicting evidence.
On Windows it flushes a staged database and atomically renames it without
replacing another writer's database. An interrupted pre-install restore leaves
no partial authoritative database; rerunning with the verified backup is safe.
POSIX uses exclusive hard-link installation; an interruption between linking
and unlinking staging fails closed on the link check and needs explicit operator
inspection. Power-loss durability and distributed coordination are not asserted.

```powershell
python -B scripts/workflow_state.py restore --from "$env:LOCALAPPDATA\ai-template-workflow-backups\m2-20261014" --manifest-sha256 <the-backup-command-digest>
```

Do not delete a live database to make this example run. Restore is for absent
control state during an explicitly chosen recovery procedure. It never changes
existing ownership/startup databases or enables implicit dispatch. Exit codes
are 0 success, 1 refusal and 130 coordinator interrupt.

## Controller adapter API

`Journal(root)` exposes `initialize`, `create`, `read`, `replay`, `recover`, `append`,
`append_many`, `evidence`, `import_chain`, `export`, `verify`, `backup`, and
`restore`. `Head(sequence, hash)` is the mandatory expected head for an append.
An `Append` request has `stream`, `kind`, `data`, `expected`, optional UTC
`timestamp`, `evidence`, and `reducer`. Batches require distinct streams.

`Evidence(path, sha256, size)` references a regular file under a `run-*` directory
inside canonical state. Register every coordinator evidence dependency required
for replay or later dispatch. Evidence references themselves are bound by a
per-event inventory digest. Every write verifies every existing stream and its
references, so a missing/corrupt prerequisite holds use of the whole journal.
The trusted coordinator controls filesystem access; workers never see this root.

Semantic reducers receive copies of the donor six-field event envelope without
`hash`: sequence, previous, kind, timestamp and data. They must be pure with
respect to external state and raise on invalid controller transitions. Imported
events are structurally validated and semantically replayed before one atomic
import. The receipt retains source byte-chain digest, source head/count and
replay state digest. Original bytes, hashes, IDs, attempts, liabilities and spend
are not rewritten. Replay and semantic append verify the imported-prefix state
digest and hold if the reducer's meaning has changed. Imported source
anchors/policies remain historical; M3 must
hold any incompatible history rather than silently replacing INIT or its caps.

For donor compatibility, use `stored=True` when replaying historical events and
the donor's stricter new-transition behavior for a proposed append. A reducer
passed to `append`/`append_many` can distinguish the proposed event using its
sequence relative to the supplied expected head. Do not validate every historical
event as new or label a new event historical to bypass current rules.

Import accepts a trusted Python reducer rather than accepting executable code
or a reducer name from the CLI. Production feedback/acceptance adapters are M3/M5
work; no donor controller is enabled merely by having this storage API.

## Verification

```powershell
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_workflow_state.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B tools/validate_boundaries.py
```

The approval runner uses a disposable inactive projection for the 46 frozen tests
and checks that the actual ACTIVE manifest bytes remain unchanged. Never run the
inactive-only cases directly against the actual ACTIVE package or refresh the
historic foundation/baseline hashes to conceal implementation changes.

The repository does not yet have configured global typing/coverage gates. M2
uses Ruff and ty on the added modules and measures branch coverage in an isolated
tool environment. BasedPyright has zero errors with warnings for the frozen
untyped APIs, dynamic event data, argparse and SQLite boundaries. Those warnings
remain visible; repository-wide typing/toolchain migration is deferred.
