# M2 implementation verification

Recorded 2026-10-14 UTC. Owner objective: finish M2 and provide copy/paste M3
handoff instructions. Role: Codex coordinator and journal implementer. Fresh
reviewer: Goodall, a separate host review session using the Short Circuit
workflow. The reviewer changed only `M2_REVIEW.md` and independently reproduced
and retested its findings using disposable state.

Verdict: M2's scoped implementation and AC-01/AC-09 verification are complete.
The corrected implementation passed fresh review with no remaining correctness
blocker. M3 controllers have not been implemented or started. Full M1/M5 runtime
acceptance, deployment and publication are separate facts and are not inferred.

## Exact implementation and authority (verification snapshot)

At final regression, before the subsequent owner-authorized Git delivery,
the worktree was `feature/workflow-migration` at
`3fba5742044abcce7a664e3030e15a5db33f7b2b`; its base tree matches the GitHub
merge commit `517a770dd7346fc5d6c530781719365fc9ff409e`. M2 adds uncommitted
files in the existing worktree rather than changing any retained branch ref at
that verification checkpoint. See `M2_CLOSEOUT.md` for the later manual delivery.

The frozen ACTIVE receipt identifies Winston at `2026-10-14T02:07:06Z` with
fingerprint `8e75e71b3561eaec4ad5cf71e37a1dec9f2c7dce0d07e0be46346daacfc90481`.
Actual ACTIVE validation with pinned source checks passed. Manifest raw SHA256:
`33761b533bca129aa0d90133d0fb2ce970ba85945c5f381e7f5f9ce6621bc81f`.
The manifest, frozen validator/tests, architecture, original baseline hashes,
application interfaces and eight exact donor imports were not edited.

Fresh-review snapshot, identical to the regression-tested code:

| File | Raw SHA256 |
| --- | --- |
| `scripts/workflow_state.py` | `6c87c02e3c467ec8a3cf2af48720ea59d7ecb7285620d91e0e28be05c7495050` |
| `tests/test_workflow_state.py` | `fda5387e288fee28660e703f9d20dfe356beef9ce90c290aa6275cd3071906e7` |
| `tools/check_workflow_approval.py` | `f25a57337cc7d146c9ea7ec9138150994aa68be3565e7a79d9b302272049eeaa` |

## Requirement evidence

| Requirement | Evidence and outcome |
| --- | --- |
| AC-01: current foundation, exact fingerprint and owner receipt | Actual `--fingerprint --check-source --require-active` validation passed; adapter reuses frozen file/policy/receipt validation. |
| AC-01: inactive/forged/altered-file/altered-policy/changed-anchor refusal | 46 frozen integrity/refusal tests pass on an inactive disposable projection, plus destination adapter tests for these cases and changed valid anchors. |
| AC-01: approval remains current through scheduling validation | Pure paused reducer plus a separate receipt-revocation thread rolls back the complete task/project batch. Scheduling anchors are checked again just before commit. Outcome-only recording remains available after revocation. |
| AC-09: one canonical journal across worktrees | Real disposable Git worktrees resolve to the same Git common-directory identity; alternate state paths refuse. Initialization is explicit and never replaces an existing journal. |
| AC-09: durable append and writer collision | Actual journal write connections use FULL synchronous transactions. Eight-thread and four-process CAS contests have one winner; multi-stream task/role/project updates commit together or roll back together. |
| AC-09: actual kill/restart | Real Windows child-process kills before and after commit preserve exactly the committed history. A 3 MiB uncommitted insert spills SQLite cache; ordinary read refuses its hot journal, explicit public recovery rolls it back, verifies state, and permits the next append. |
| AC-09: gap/digest/stale-head/evidence refusal | Corrupt sequences, row/canonical/original/head/repository/ref-inventory digests, changed or missing evidence, and stale heads refuse reads/new writes without deleting history. |
| AC-09: one-time source-chain import | The actual pinned donor feedback code generated and replayed a four-event chain. Import/export retain exact bytes and hashes, both attempt IDs, two attempts, recorded spend 0.5 and the pending dispatch. Generic cases also preserve lifetime counters/spend, BOM/CRLF bytes, and reject semantic/partial/duplicate imports. |
| AC-09: semantic replay continuity | Replay and semantic append compare the imported prefix against the recorded state digest. A changed reducer's interpretation is held; previous counters/costs cannot silently reset. |
| AC-09: verified backup/restore | Consistent SQLite snapshot, external manifest digest, repository/head/evidence verification, no-overwrite installation and interrupted restore are tested. A source mutation during restore cannot replace the private verified bytes; installed digest and heads match the manifest exactly. |

## Final checks

```powershell
$env:WORKFLOW_TEST_IMAGE = 'sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e'
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= --ignore=tests/test_workflow_approval.py
python -B tools/check_workflow_approval.py
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --require-active
python -B tools/validate_boundaries.py
ruff check scripts/workflow_state.py tools/check_workflow_approval.py tests/test_workflow_state.py
ruff format --check scripts/workflow_state.py tools/check_workflow_approval.py tests/test_workflow_state.py
uvx ty check scripts/workflow_state.py tools/check_workflow_approval.py
```

- Final full suite: **271 passed, no skips**, 90.24 seconds. It includes all
  scope/runtime tests with the pinned network-disabled Docker image.
- Frozen approval suite: **46 passed**, 6.73 seconds, on the disposable inactive
  projection; the actual ACTIVE manifest bytes remained unchanged.
- M2 suite: **89 passed**, 60.21 seconds in the isolated coverage environment.
  Branch-enabled coverage reports **99%** (459 statements, 3 missed; 76 branches,
  4 partial branches). Remaining misses are exceptional/entrypoint/POSIX paths,
  not hidden by exclusions. The host implementation is verified on Windows.
- Boundary, Ruff lint/format and ty checks pass. BasedPyright reports **zero
  errors and 279 warnings**, primarily frozen untyped APIs, dynamic JSON,
  argparse and SQLite boundaries. A global typing/toolchain migration is deferred.
- Fresh review initially found F1–F3; all were repaired and independently
  retested. O1's imported-state digest observation was also strengthened. The
  reviewer reports PASS for scoped M2 correctness in `M2_REVIEW.md`.

Coverage artifact: `C:\Users\hensl\AppData\Local\Temp\m2-coverage-reviewed-e01fc418e19a4c5e81deab634a562294`.
Coverage tooling used an isolated uv environment with Python 3.12.10, pytest-cov,
pytest and jsonschema==4.26.0; project dependencies/configuration were not changed.

## Preservation and remaining boundaries

Read-only snapshot comparison confirms both protected statuses/index hashes match
the approved records, and all local/cached remote refs match the start of M2.
Original index SHA256 remains
`fe7124042405022bf442485ce5e340489d0b292f2bbaa8a8935321b6653ec39b`;
source index SHA256 remains
`ac3c6beb7fe41745ede3543cac4f368aa310f6fd83a5dacceaef15042f5f4e25`.
The staged plan deletion and the source's eight untracked entries remain.
At that verification checkpoint, no application/root-governance/frozen-source
diff, staging, commit, push, merge,
branch deletion, source-controller activation or paid worker launch occurred.

Receipt replacement does not share SQLite's lock. Final checks catch revocation
during validation; later dispatch/launch must freshly validate current approval.
Binary read/verify/recover cannot perform a controller's semantic checks without
its supplied reducer. Windows process kill is tested; power-loss and distributed
coordination are not asserted. Control backups do not replace retention of the
independent ownership/startup stores. Historical M1 evidence and current worker
regressions do not prove full independent acceptance-export coverage.

The canonical host journal is provisioned during final closeout, with a project
continuity record and digest-bound evidence for this verified implementation.
See `M2_OPERATIONS.md` for recovery/backup/API use and `M3_HANDOFF.md` for the
copy/paste next-session instructions. M3 owns routing, feedback and budget policy.
