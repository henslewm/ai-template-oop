# Fresh M3 correctness review

Review date: 2026-10-14 UTC. Reviewer: separate `m3_review` agent.

**Current status: PASS for the scoped M3 correctness re-review. F1–F6 are
closed. No remaining correctness blocker was identified in the reviewed
snapshot.**
This status supersedes the initial findings below, which remain as audit
records. The final stable-snapshot evidence and limits appear at the end.

Scope: `scripts/model_router.py`, `scripts/feedback.py`,
`scripts/workflow_budget.py`, both controller schemas and default configs,
`tests/test_model_router.py`, and `tests/test_feedback.py`. Governing references:
`M3_HANDOFF.md`, `M3_PLAN.md`, frozen `ARCHITECTURE.md`,
`config/workflow-bootstrap.json`, `M2_OPERATIONS.md`, and the pinned donor
`d6e582b7edeae24345a175f36639230726dbdead`.

No worker/provider calls, M4 work, canonical-state writes, protected-checkout
writes, application/foundation changes, or Git mutations were performed.
Checks used pure reducers and disposable test state. Only this review document
was edited by the reviewer.

## Initial verified findings

### F1 — P2: an approved repair retains a terminal routing outcome

The initial native plan sends lifetime attempts to the router, including an
earlier revision's `BLOCKED` outcome caused by unknown scope. `REPAIR_CONTRACT`
creates the approved next revision but does not provide a routing resolution
for that terminal outcome. The router therefore returns `TASK_BLOCKED`, although
the controller is READY and has one lifetime attempt remaining.

The first scoped run independently failed
`test_repair_preserves_lifetime_spend_and_nondescending_tiers`: the second
reservation's selected resource was null. Result: **62 passed, 1 failed**.
Required correction: derive the explicitly repaired outcome for native routing
while preserving the original result, attempts, spend, tier history, and stored
donor semantics.

### F2 — P1: reviewer selection can reserve an unusable same-family resource

A pure native-controller probe created a high-risk task, a tier-3 lmstudio
worker, and eligible tier-3 reviewer resources from lmstudio (latency 1) and
mistral (latency 10). After worker PASS, `plan(..., role="reviewer")` returned
DISPATCH selecting lmstudio. Both candidates had empty exclusion reasons.
The later result check refuses that family, after the attempt and budget have
already been consumed. At a tier with one allowed attempt this can strand the
task despite an eligible independent resource.

Required correction: apply the risk and packet cross-family gate to native
reviewer eligibility before economic selection. Bind result declarations to
the selected resource's saved family, tier, and reviewer identity. Keep pinned
source decisions reproducible.

### F3 — P2: the default returned deadline differs from the durable deadline

With `timestamp=None`, `reserve` simulates the task using `wp.now()` but passes
None to every `Append`. Journal subsequently chooses its event time. The
returned deadline is from the simulation, rather than the committed attempt.

A deterministic delayed Journal stand-in used the actual reserve/apply/budget
reducers with simulation time T+1 and commit time T+20. It returned
`2026-10-14T22:10:01+00:00`, while the stored task deadline was
`2026-10-14T22:10:20+00:00`; all three batch timestamps were None.
Existing tests supply timestamps and miss this production default path.

Required correction: capture one effective UTC timestamp for simulation and
all batch appends, and verify the returned deadline equals durable replay.

### F4 — P2: raw result cost types are validated only after replacement

For an explicitly unmetered native result, a pure probe supplied
`api_cost_usd="0"` as a string. The event was accepted and saved that string in
`raw_result`. `budget.money` accepts strings; replacing the claim with numeric
zero before `shape("result")` masks the invalid input type.

Required correction: validate the raw result against its schema before
substituting measured or unmetered accounting, after separately extracting the
coordinator usage field.

## Additional advisory checks

- The public single-stream `append` helper originally accepted accounting
  events. A subsequent disposable Journal probe confirmed the repaired helper
  now refuses DISPATCH with `Accounting events require atomic task/role/project
  controllers`.
- Initial usage measurement lacked reservation-overrun holds and saved token
  ceilings. The implementer was advised to retain truthful measured cost while
  holding any monetary or token-ceiling overrun, including cases where total
  caps still have room.
- The initial source import test generated INIT/DISPATCH with the current
  implementation. A stronger independent check loaded reducer functions and
  schema directly from the exact pinned donor commit into memory. Ten events
  (INIT, DISPATCH, scope-unknown RESULT, REPAIR_CONTRACT DIAGNOSIS, DISPATCH,
  PASS RESULT, legacy bounded-rejection REVIEW, DISPATCH, PASS RESULT, legacy
  APPROVE REVIEW) reproduced the pinned canonical state after every event.
  Final state was ACCEPTED with three attempts, one repair, and original cap
  eight. This verifies historical semantics; it does not authorize destination
  scheduling or M5 acceptance.

## Initial snapshot evidence

The first scoped test started from an in-progress snapshot; feedback and tests
were edited while review continued. Those results are retained only as initial
evidence. Initial SHA256 readings before repair:

| File | SHA256 |
| --- | --- |
| scripts/model_router.py | 7357caf3d83af7ee58992346855e79c17922511c15913e80e35c3ba2ef289489 |
| scripts/feedback.py | a3186acc6ee47487c3ac60689c32fd0b97329dd122395bd6159b10a6bef61835 |
| scripts/workflow_budget.py | 83cd49df0f11b75734ec7939d51ff834439d728a63bd9342acc18ec2ab9ebe75 |
| config/model-router.schema.json | 1170f18f3e450491b7954f56512c13d0dcfd4094667de136bac3f64625966f17 |
| config/feedback.schema.json | 909c475e2646721aaa578024dfcd66612b2c4ef74f238b3809f5bed441bd4178 |
| config/model-router.json | 3a9d29898d30bd0fec5bb1dcd1c1a4f0d14133d20ae1c7727d9dcb086ca1028f |
| config/feedback.json | 93dd79b8ff9722613d812b3b587163890856e44e93c0707406095f4a4da42973 |
| tests/test_model_router.py | ecc97d5473a961f9d769892aa3bf0231a978743bbeb59fb57a9950deaae9009c |
| tests/test_feedback.py | 80a9b79c41fecaf5f642104f34f49a478e9ad2c7db27317edd403a033de1f595 |

## First stable-snapshot re-review and closure

Completed at `2026-10-14T21:14:59Z`. The implementer froze the scoped files for
this re-review. All nine SHA256 readings matched before and after independent
checks. This snapshot is retained for audit and superseded by the final
validator/identity snapshot below.

| File | SHA256 |
| --- | --- |
| scripts/model_router.py | 385ac29687122940f6a8c1235be4515c96027f869b77caee951ab16d380d0758 |
| scripts/feedback.py | 5126ff2ac3bc186faa60e2acfcded5dc630207527089e8c06cc09a1af08f155e |
| scripts/workflow_budget.py | b0c9233dcd04388cb67b6f31577cf347cf5d121ee26a5e5c5cf2f81d800add29 |
| config/model-router.schema.json | 2000779025d25f450931191d74ef8fe28b2a13e3cabbc7f1c83a8f91ce1a8620 |
| config/feedback.schema.json | 7c2094aefab362dca9a28e1b40047ecb6bd044892994a9943466e694ecb06a99 |
| config/model-router.json | 3a9d29898d30bd0fec5bb1dcd1c1a4f0d14133d20ae1c7727d9dcb086ca1028f |
| config/feedback.json | 93dd79b8ff9722613d812b3b587163890856e44e93c0707406095f4a4da42973 |
| tests/test_model_router.py | 886ff4a814bcf745d280f588c3f197e61d34b1143e2e31253749ff3dcdc1874f |
| tests/test_feedback.py | 7db371fe676dc8ee5330b3d4b2b52fb61c292e796043261b5f8a9345e241afea |

The reviewer independently ran:

```powershell
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_model_router.py tests/test_feedback.py
```

Result: **80 passed in 36.46 seconds**, exit 0. The real disposable SQLite
cases include one whole-batch winner for concurrent same-task reservations,
contending project/role caps, stale-head rollback, and each task/role/project
cap's atomic refusal. The expanded suite also covers lifetime resubmissions,
reviewer timeout/abandonment, diagnosis/resumption bounds, disabled resources,
zero budgets, duplicate task identity, context accounting, and raw cost types.

### Finding closure

- **F1 closed:** native routing derives a resolved outcome only for an older
  repaired revision. An independent pure-controller probe compared the complete
  original attempt before/after repair: it remained unchanged, with unknown
  liability preserved. With a cheap lower-tier replacement available, the next
  selection remained at tier 2. The formerly failing regression passed.
- **F2 closed:** native reviewer eligibility filters actual model families
  before selecting and reserving. An independent low-risk packet with an added
  cross-family gate rejected a different-provider/same-family resource and
  selected a same-provider/different-family resource. Substituting the actor,
  tier, or family in the review result was refused. The high/critical regressions
  also passed; economic selection remains within the eligible set.
- **F3 closed:** reserve and finish capture one effective timestamp. Repeating
  the delayed-Journal probe returned and stored exactly
  `2026-10-14T22:10:01+00:00`; every reservation append carried
  `2026-10-14T22:00:01Z`. The real Journal default-timestamp regression passed.
- **F4 closed:** raw result shape validation precedes cost normalization. The
  independent reducer probe refused string `"0"`, boolean true, negative one,
  and NaN. The real Journal regressions verify no heads change on refusal.

The additional bookkeeping/overrun observations are also closed for this scope.
The public single-stream helper refuses accounting events, while result and
reconciliation adapters use atomic task/role/project batches. Saved input and
output ceilings detect token overrun independently of monetary overrun. A fresh
probe exceeded only the output ceiling: measured cost was USD 0.00501, below
the monetary reservation, yet truthful spend was retained and status became
NEEDS_DECISION. Metered unknown liability remains held; unmetered results settle
at zero without discarding the original claim. An independent Unicode-context
probe counted 11,584 input tokens from actual rendered UTF-8 bytes plus harness
overhead and refused a 10,000-token resource.

### Exact pinned history through real Journal import/export

The exact-donor comparison was repeated with a positive historical cost of USD
0.125. The ten original donor-style events were hashed and serialized, then
imported into the actual Journal in a disposable repository. Destination stored
semantics matched the pinned reducer after every event. Replay retained original
cap 8, all three attempts, one repair, original source anchor, original cost,
and historical ACCEPTED status. The imported head was:

`4d73c24c39f32f89290a765ad3d5589c564ddbc7bcedc61db9c3f1d0044973c2`

Export reproduced every original event byte exactly. Attempting a new reservation
against that imported source stream was refused with the source-history relabel
guard. This does not create a destination acceptance or scheduling authority.

The first custom import probe was refused by the filesystem sandbox; the
authorized rerun passed. Disposable successful state and the two directories
left by refused probes were removed after exact target-path checks. No canonical
journal or runtime ownership/startup state was touched.

### Verdict limits

No unresolved M3 correctness finding remains in these nine files. The exact
pinned lifecycle probe provides independent legacy replay evidence beyond the
narrow checked-in source-import fixture. It is one historical lifecycle, not an
exhaustive statement about every possible source ledger.

This reviewer independently certifies the focused tests and probes above.
Full existing/M2 regressions, frozen approval projection, ACTIVE validation,
boundary gates, static tooling, preservation, and milestone closeout remain the
coordinator's separate evidence. This review does not assert provider access,
live worker execution, M1/M5 acceptance, M4 completion, Git publication, or
deployment. The reviewed default resource remains disabled and all destination
live API budget defaults remain USD 0.

## Final validator/identity re-review

Completed at `2026-10-14T21:30:19Z`. This final snapshot supersedes the nine
hashes above. All nine final readings again matched before and after checks.

### F5 — P3: public configuration validation did not identify native bounds

The follow-up read-only audit independently demonstrated that the former
`validate_config` and CLI `validate-config` accepted `max_review_attempts=3`
and `failures_per_tier=3`, with CLI exit 0. Native route refused both, so this
was a validation/CLI clarity mismatch, not a reservation bypass. Preserving
generic validation was necessary for historical source replay, but its public
name and CLI success did not distinguish that narrower meaning.

**F5 closed:** `source_validate_config` retains donor generic bounds explicitly;
source input validation and feedback planning/INIT use it. Public
`validate_config` checks destination shape and approved floors, and the CLI
uses that native validator. Independent probes now refuse both weakened limits
through the public function and CLI (exit 1), while `source_record` followed by
`verify_source` still reproduces each legacy configuration. A lowered high-risk
floor is likewise refused by native validation and accepted by the historical
shape validator. The added native-validator and CLI regressions passed.

### F6 — P2: padding a declared actor name bypassed independence comparison

The same audit used implementer `"Implementer"`, reviewer reservation actor
`" Implementer "`, and the identical padded actor in the review result. Both
reservation and bounded review were accepted because raw strings differed.
The exact saved-result binding did not close this earlier identity comparison.

**F6 closed:** new native actor identities reject outer whitespace and compare
collapsed, case-folded names before reviewer reservation. Exact actor spelling
remains frozen in the reservation and result binding. Independent probes refuse
padded/blank implementer identities, padded reviewer identities, case variants
of the implementer, and `"FIRST   LAST"` against implementer `"First Last"`.
A result changing saved actor `"Independent"` to `"independent"` is still
refused by the exact binding. These are conservative checks on coordinator
declarations; they do not claim authentication of a real person. Stored donor
INIT and review semantics remain unchanged. The three added actor regressions
passed.

The additional reviewer-cap audit found no gap: both policy tier 4 cap 1 and
packet-lowered tier 1 cap 1 permit one review, then return NEEDS_ARCHITECT /
NO_ELIGIBLE_RESOURCE despite the overall reviewer ceiling of 2. The overall
ceiling never replenishes an exhausted tier.

### Final actual checks and hashes

The reviewer reran the same focused command. Result: **85 passed in 78.09
seconds**, exit 0. This includes the F1–F4 regressions and the five new cases.
The independent raw-cost refusal probe was repeated and passed.

The exact pinned ten-event lifecycle was also rehashed, imported, replayed and
exported through the actual disposable Journal after the validator split.
The in-memory pinned adapter explicitly maps the original donor validator to
`source_validate_config`. It retained the same head
`4d73c24c39f32f89290a765ad3d5589c564ddbc7bcedc61db9c3f1d0044973c2`,
all original event bytes, three attempts, cap 8, one repair and USD 0.125
historical cost. New scheduling against the imported source history was again
refused. Disposable state was cleaned. No implementation or frozen files were
edited by the reviewer.

| File | Final SHA256 |
| --- | --- |
| scripts/model_router.py | ca206455f10c7314c7dd80a323e7a69253f6b62d9eaaf08033cefbdc55573d2f |
| scripts/feedback.py | 2d42c83c1009425f32c4aa541ba8e56b0d1cdd039ef8da50e0790a07491d27cd |
| scripts/workflow_budget.py | b0c9233dcd04388cb67b6f31577cf347cf5d121ee26a5e5c5cf2f81d800add29 |
| config/model-router.schema.json | 2000779025d25f450931191d74ef8fe28b2a13e3cabbc7f1c83a8f91ce1a8620 |
| config/feedback.schema.json | 7c2094aefab362dca9a28e1b40047ecb6bd044892994a9943466e694ecb06a99 |
| config/model-router.json | 3a9d29898d30bd0fec5bb1dcd1c1a4f0d14133d20ae1c7727d9dcb086ca1028f |
| config/feedback.json | 93dd79b8ff9722613d812b3b587163890856e44e93c0707406095f4a4da42973 |
| tests/test_model_router.py | 6d95caf2ab98e5b82dca85d40ab6af53e4a74f26c86f7cb00a3739d0fd417675 |
| tests/test_feedback.py | e639253c86edcf1e124bc40c314484bc7c0845b7dcbfb818d426acc1b10db2a9 |

**Final scoped verdict: PASS. F1–F6 are closed; no remaining correctness blocker
was identified.** The scope and verification limits recorded above continue
to apply.

## M3-only restoration audit

Recorded `2026-10-14T21:58:27Z` after the owner reconfirmed M3 only, stopping
before M4. The coordinator archived mistaken partial M4 drafts at
`C:\Users\hensl\AppData\Local\Temp\m3-scope-correction-b0ee9f7b3e8a4c3b9a43d8e80857cfac`
and removed their implementation/hooks from the active workspace. This audit
checks the restored state; it does not authorize the archived work.

The reviewer independently recalculated all nine M3 SHA256 values before and
after targeted checks: **9/9 exactly match `M3_VERIFICATION.json` and the final
measured snapshot above**. The review tables had a transcription error in the
`config/model-router.json` hash (one extra `c`); those three literals are now
corrected. The actual config hash has remained
`3a9d29898d30bd0fec5bb1dcd1c1a4f0d14133d20ae1c7727d9dcb086ca1028f`.
No configuration or implementation changed during this correction.

HEAD remains `ef6ae42bdef7ef32793764400761383fe650bea7` on
`feature/workflow-migration`. Tracked and staged diffs are empty. The workspace
inventory contains the expected uncommitted M3 files and future `M4_HANDOFF.md`;
`execution_harness.py`, `worker_launcher.py`, their tests, the execution-harness
schema, and `.m4-reference` are absent. No M4 execution hooks were found in the
tracked state/runtime/scope modules. Historical source comments naming the
donor harness remain comments. Every default resource remains disabled;
task/role/project live caps and the router role budget remain USD 0.

Fresh targeted verification used the existing feedback cases for atomic append
refusal, default deadline, actor normalization, cross-family eligibility,
repair/lifetime preservation, raw cost types, disabled/zero policy, each budget
cap, and concurrent same-task reservations. Result: **17 passed, 31 deselected
in 13.42 seconds**, exit 0. The coordinator's renewed full split regression and
static checks are separate closeout evidence.

**Restoration verdict: PASS for the exact restored M3 snapshot and M3-only
scope; no remaining correctness issue identified.** The reviewer edited only
this report and did not alter implementation, frozen material, canonical
control/ownership/startup state, Git, or protected checkouts, and launched no
workers.
