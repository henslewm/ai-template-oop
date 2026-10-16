# Fresh scoped M4 correctness review

Reviewer: separate `m4_review` agent, 2026-10-14 UTC. Scope: M4 AC-07 only.
**Scoped review status: PASS; F1–F5 closed. No remaining scoped correctness
blocker identified. Complete split verification remains a separate coordinator
gate and must use the final corrected snapshot.**

The reviewer inspected the Docker dispatch adapter, launcher, pure dispatch
transitions, runtime/scope changes, harness schema/defaults and both new test
modules. Governing references included M4_HANDOFF.md, M4_PLAN.md, frozen
ARCHITECTURE.md, workflow-bootstrap.json, M3_OPERATIONS.md,
M3_RESUME_VERIFICATION.json, M3 acceptance/review/closeout records,
M2_OPERATIONS.md, CLAUDE.md, PROMPTS.md and BRANCH_RETENTION.md. Donor harness
and launcher were read using `git show` at exact commit
`d6e582b7edeae24345a175f36639230726dbdead`.

The reviewer changed only this review document in the workspace. Review probes
used external temporary files and disposable Journal/ownership fixtures with
the offline Docker transport double. No real worker, provider, paid operation,
canonical-state write, Git mutation or protected-checkout write was performed
by the reviewer. The coordinator's separate real Docker and full split results
are separate evidence, not substituted for this review's checks.

## Verified findings and corrections

### F1 — P2: ingestion receipt could contradict M3's effective outcome — closed

A disposable probe stopped a valid PASS run at fixture time T+10, then ingested
it at T+700, after the reservation deadline. Before correction, ingestion
returned `INDEPENDENT_ACCEPTANCE_PENDING`, but native feedback replay showed
`IN_PROGRESS`, reason `ATTEMPT_TIMEOUT`, and routing outcome `FAIL`.

The initial receipt used the untrusted report's PASS rather than M3's effective
result. The correction derives RESULT receipt status from the same simulated
native reducer used for accounting. Only `REVIEW_PENDING` maps to
`INDEPENDENT_ACCEPTANCE_PENDING`; other effective statuses remain adverse or
held. Ingestion returns the committed receipt, including on an identical
concurrent duplicate. M3 deadline/lifetime/accounting semantics remain intact.

The reviewer inspected the correction and independently passed
`test_late_ingestion_receipt_matches_m3_timeout_not_worker_pass`.

### F2 — P2: malformed invocation configuration consumed a lifetime attempt — closed

A disposable probe appended a literal `{` to an otherwise valid invocation.
Before correction, `config_valid` passed. Dispatch then reserved and consumed
one attempt before formatting failed; reconciliation abandoned it without a
worker start. Escaped `{{brief}}` also counted as a required placeholder despite
rendering a literal `{brief}` rather than the supplied brief path.

The correction parses argv with `string.Formatter`, refuses malformed braces,
format specs, conversions and unknown fields, and counts actual substitution
fields rather than escaped text. Known invalid configurations now refuse
before reservation. The reviewer inspected the correction and independently
passed all six invocation regression cases.

The seven F1/F2 regression cases passed in 8.76 seconds. Three later behavioral
tests also passed independently: claim committed before manifest-token write,
transient Docker observation failure retaining ownership/pending state, and two
attempts retaining lifetime history without applying output (two selected cases
in 15.30 seconds and the claim-crash case in 1.84 seconds). The product harness
hash was rechecked after these runs and remains the reviewed value below.
### F3 — P2: combined test collection loses the launcher fixture — closed

The independent invocation below completed with **65 passed, 1 deselected and
28 setup errors** in 271.56 seconds:

```powershell
python -B -m pytest -q -rs -p no:cacheprovider -o addopts= tests/test_execution_harness.py tests/test_worker_launcher.py -k 'not real_pinned'
```

Every launcher test reported `fixture 'execution' not found`. Launcher-only
invocations pass because the plugin import exposes the fixture in that
collection shape, but the fixture remains unavailable to the launcher module
when both modules are collected together. The complete regression invocation
must be supported. This run loaded an earlier in-memory product snapshot; the
ten later correction/additional cases above were run against the corrected
product hash.

The correction explicitly aliases the shared fixture objects into each M4
consumer, removing test-module plugin registration and changing no M3 file.
The reviewer inspected both final imports and independently reran the actual
combined-file collection shape:

```powershell
python -B -m pytest -q -p no:cacheprovider -o addopts= tests/test_execution_harness.py tests/test_worker_launcher.py -k 'disabled_default or runtime_direct or crash_after_claim'
```

Result: **3 passed, 101 deselected in 3.28 seconds**. Both test modules and the
claim-crash launcher case now resolve their fixtures in one invocation. Final
raw hashes were reread after this check; the product harness still has the F1/F2
reviewed hash. The complete final split suite remains the coordinator's required
delivery gate; the initial failed broad run is not represented as a green run.

### F4 — P2: startup can pass an exhausted operator timeout — closed

In a further requested read-only probe, the reviewer supplied a one-second
operator timeout and deterministic monotonic time. The runtime computed its
execution deadline at monotonic zero; the repeated launching preflight advanced
time to two seconds. Despite that exhausted operator bound, the launcher made
one Docker worker start and returned `STOPPED`. The probe passed in 3.44 seconds
and used only a disposable offline transport fixture.

`runtime.execute` computes `execution_deadline` before its repeated preflights,
but `seconds_left()` bounds only the original timeout and the reservation's
absolute deadline. Immediately before Docker start it therefore does not account
for time consumed by preflight or ownership locking. An immediately exiting
worker also bypasses the wait-loop's deadline check. This contradicts the
documented operator-shortened bound with startup counted.

Required correction: immediately before the external start, bound remaining
time by both the original monotonic execution deadline and the absolute
reservation deadline, refuse if either is exhausted, and pass that remaining
bound to Docker. Keep the durable consumed-start state final if refusal occurs
after it was committed. Add deterministic preflight/ownership-delay regressions.

The correction adds a remaining-bound calculation after repeated preflight and
immediately after consumed-start preflight, then passes that calculated
remainder to Docker. The reviewer inspected the corrected runtime and
independently passed all three deterministic delay cases in combined-file
collection, alongside two fixture/bypass checks: **5 passed, 102 deselected in
11.49 seconds**. Expiry after consumption retains consumed authority and claimed
ownership until explicit preservation/abandonment; expiry before consumption
never spends startup authority.

A separate independent disposable probe advanced a one-second operator budget
by 0.25 seconds in the first repeated preflight and to 0.6 seconds after
consumption. The actual worker Docker start received only **0.4 seconds**,
confirmed by a passing assertion in 3.04 seconds. Final runtime/test hashes
below were reread after both checks. The final full split gate must use the
corrected runtime snapshot.

### F5 — P2: the F4 change altered legacy runtime timeout semantics — closed

The coordinator's subsequent full regression exposed a failure in the unchanged
M1 case `test_execution_timeout_still_stops_and_preserves`. The first F4 fix
started the monotonic deadline before Docker start for all runtime calls, while
the existing standalone path without an absolute reservation deadline had
always started its execution timeout after Docker start. Its deterministic
`[100, 101]` clock now tripped the new before-start guard.

The correction enables the startup-counted monotonic bound when an explicit
absolute deadline exists. Every M4 dispatch run requires that deadline and its
Journal preflight; direct dispatch execution without them still refuses. The
legacy standalone path retains its post-start execution deadline. No existing
test or M3 file was changed.

The reviewer inspected that branch and independently ran the unchanged failing
M1 case together with all three M4 startup-delay regressions: **4 passed in
9.95 seconds**. The entire existing runtime-startup module then passed:
**43 passed in 2.11 seconds**. `git diff` for that test module remained empty.
Final runtime SHA256 is recorded below. This compatibility regression check
does not close M1's independent acceptance gaps. The coordinator must obtain
fresh complete split evidence on this final corrected snapshot before delivery.

## Review evidence and limits

The inspected path reserves through M3's native atomic task/role/project
controllers, saves the complete context and exact run binding, and repeatedly
revalidates before the existing durable consumed-start boundary. Worker
execution stays inside the Docker volume export with network none, UID/GID
1000, read-only root, dropped capabilities and existing resource bounds.
Report ingestion reads the ownership store's exact preserved stopped archive,
checks immutable inputs and bounded regular paths, derives a replacement bundle
without host extraction, and never applies or independently accepts output.
Recovery retains consumed starts and explicitly abandons interrupted attempts;
unknown metered liability is delegated to the unchanged M3 reducer.

This is a scoped correctness review, not exhaustive proof of all possible
crashes, malicious archives or host failures. Docker Desktop/kernel, pinned
image and coordinator remain trusted. Actors remain coordinator declarations;
live provider transport, enforceable paid token ceilings and trustworthy live
usage remain disabled. Existing M1 AC-02/AC-03 acceptance gaps and M5
independent acceptance are not closed by this review.

## Reviewed raw SHA256 snapshot

| File | SHA256 |
| --- | --- |
| scripts/execution_harness.py | a17d242303d509d3dd874f822a22a2e36f8421d06df1bfcfab154b9be542687e |
| scripts/worker_launcher.py | 7f758e07ab4be07f7aa25db7c291a1cd3e81f34f215dabdfe430748bfdae9757 |
| scripts/dispatch_state.py | 1996ff2df99c45ffc44c9b5d4b4fa0091a4a41b2c452f17879de356cc476b71a |
| scripts/workflow_runtime.py | a7dac529fe2322ba860a724a73492ef838e94e71fd4c5710a83858bd3bb25b4b |
| scripts/workflow_scope.py | 4f2ebc3b92a9323b63be3182b068ce6fdc11cb9112b2e4a5fcb99bf92b6290e2 |
| config/execution-harness.schema.json | 3926dd6fa3b5c2700561f49acb79c0e5ba0807be3c7e0aadf57b2bc5a5ff6e32 |
| config/execution-harness.json | a44473d9edb9e9f1b8c571e955b49b8cee327d9f68111f2a18850ad30ba2c192 |
| tests/test_execution_harness.py | 5cfd1a4ff6932d145b77441cbbbca351d052dba8a5bf0a74d6c84bb63d496479 |
| tests/test_worker_launcher.py | 1d5c81ef6f07de4a6f5ddd16fcff7cde85683d44db38e1768656faf964c5f88e |
