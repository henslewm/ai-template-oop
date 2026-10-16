# Fresh independent M1 AC-02/AC-03 acceptance review

Reviewer: separate `m1_acceptance_review` agent, 2026-10-15 UTC (2026-10-14 America/New_York). Delivered baseline: `5f83ac755369f850af74ee8f17e6b566b871f769`.

**Scoped review: PASS. No remaining production correctness blocker or uncovered required behavior identified for AC-02/AC-03.** The reviewed campaign supports separate criterion-level acceptance decisions on the exact source snapshot below. The coordinator's complete final regression, static diagnostics and preservation gates remain separate required evidence; this report does not claim they have finished. Frozen requirements/statuses are unchanged, and M6 is not implemented.

## Scope and evidence inspected

The reviewer read CLAUDE.md, PROMPTS.md, BRANCH_RETENTION.md, the frozen AC-02/AC-03 requirements and Docker/ownership policy in config/workflow-bootstrap.json, ARCHITECTURE.md, M5_EVIDENCE.md, M5_REVIEW.md, M5_VERIFICATION.json and M6_HANDOFF.md. Review followed the Short Circuit fresh-judgement instructions in references/ORCHESTRATION.md.

Actual source inspection covered scope/export and Ownership, Docker preparation/boundary/execution/preservation, worker launch/preflight, dispatch/stopped-output/reconciliation, acceptance candidate/export/preflight/check ingestion/reconciliation and relevant acceptance reducer bindings. The two new test files were read in full. Relevant existing scope, startup, launcher, harness and acceptance tests and fixture authorities were inspected directly. The new delivered-baseline audit and verification recorder were also reviewed after their addition. A later refresh independently inspected the qualified test fixture imports, dispatch-ID type assertion, heterogeneous-JSON type annotations and actual-interpreter selection for owned BasedPyright diagnostics; these changes preserve the behavioral assertions and evidence bindings. No conclusion relies only on an implementation summary or old milestone totals.

The reviewer changed only this report in the workspace. Probe glue, evidence and disposable Git/Journal/ownership fixtures were created under the system temporary directory. No migration/protected-checkout Git mutation, protected-checkout write, production canonical-store/archive write, provider/API call or paid operation was performed. All actual containers used the pinned image `sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e`.

## Criterion assessment

**AC-02: PASS** for paired software worker and acceptance export isolation on the delivered M5 production adapters and exact pinned Docker image. **AC-03: PASS** for exclusive ownership, durable one-start authority and explicit stopped-output recovery on those adapters. Both conclusions are limited to the declared trusted coordinator/image/Docker/kernel boundary and the bounded evidence below.

| Requirement | Evidence and assessment |
| --- | --- |
| AC-02 paired read/write isolation | The final real paired test probes 31 targets in each export, with denied direct read/write and symlink read/write: 124 denials per export. Targets cover sibling feature/UI files, Git/control/startup/ownership state, Docker sockets, credential files, connectors and disposable host canaries through Windows names and three Linux host aliases. Host environment canary inheritance is refused. Docker inspection independently verifies the no-bind, network-none, UID/GID, immutable image/environment and resource boundary. |
| Immutable inputs and candidate | Both exports adversarially attempt writing/chmod of the immutable contract/test and all six immutable session metadata/instruction files. Root/workspace directory writes fail. Acceptance checks exact candidate bytes and refuses candidate chmod/write; its session volume is read-only and distinct from the worker's. Stopped-output validation binds the same replacement bundle and rejects changed immutable inputs. |
| Allowed scoped task and image evidence | The worker changes only its declared auth file, produces an exact stopped replacement/report, and independent acceptance checks the unapplied `VALUE = 2` candidate. Native feedback becomes ACCEPTED only after the separate acceptance receipt. Host source stays `VALUE = 1`; all canaries remain unchanged. Both inspected containers use the exact pinned image and have one consumed start and finished ownership. |
| Exclusive branch/workspace ownership | Two fresh processes race distinct scopes against the same ownership database, independently isolating a shared branch with different workspaces and a shared workspace with different branches. Exactly one claim succeeds. Existing canonical-state/worktree and expiry tests add coverage of the shared repository identity and refusal of silent takeover. |
| One consumed start under launch and execute races | Both worker and acceptance are parameterized over launch and direct execute. Execute contenders synchronize their created-container observations before ownership locking, so Journal launch CAS cannot hide a broken startup barrier. Exactly one callback trace and one executed log marker appear; the loser is refused without cleanup of the winning run. Production Ownership commits startup consumption separately under the same lock used by recovery; `start_attempted` prevents a losing executor from cleaning up. |
| Refusal/logging failure and actual process death | Both modes cover injected Docker startup refusal plus logging failure, actual child `os._exit(73)` after the durable consumed commit and before Docker start, and actual child `os._exit(74)` after a real Docker start. The after-start case observes a live long-running container. Consumption survives with a claimed owner; a separate fresh process refuses relaunch, and direct Ownership retry also refuses the consumed token. |
| Expiry, stop, preservation and old authority | Expiry is modeled with an explicit fixture clock without rewriting stored leases/events. Recovery refuses a non-stopped tree and missing output; actual live trees must be killed and observed stopped. Nonempty opaque session archives are then preserved before changing ownership to recovered. Explicit abandonment preserves the same archive bytes, startup remains consumed, and the old token is refused. |

The startup-refusal/logging-failure case is an explicit transport fault seam, not a claim that the daemon naturally failed. Docker, Git, SQLite, container inspection and archive handling otherwise remain real. The exclusive-owner test intentionally uses one real prepared/stopped container and two distinct scopes; it does not claim two container preparations raced.

## Findings resolved during review

F1, evidence gap: the initial probe did not adversarially write/chmod immutable session metadata, and Linux pathlib treated the supplied Windows host strings as relative names. The coordinator added all six immutable metadata files and actual Linux Docker Desktop host aliases to both exports. The final paired recheck passes these additions, including `/host_mnt/` aliases. No production repair was needed.

F2, description accuracy: the original exclusive-owner comment described two independently observed created containers although the code used one stopped container. The coordinator corrected the comment. The branch/workspace collision assertions already exercised the intended database invariant.

No unresolved scoped finding remains.

## Independent executions

All reviewer pytest invocations used `python -B -m pytest -q -rs -p no:cacheprovider -o addopts=`, the pinned WORKFLOW_TEST_IMAGE, a fresh explicit external `--basetemp`, and a separate external M1_EVIDENCE_DIR. They neither shared the coordinator's test artifacts nor ran the full repository suite.

| Run | Actual selected cases | Result |
| --- | --- | --- |
| External stronger probe | Paired isolation, acceptance direct-execute race, worker before-start process death, acceptance after-start process death. An external pytest plugin additionally attempted all immutable session metadata writes/chmod and direct host-canary access through `/run/desktop/mnt/host/` and `/host_mnt/`. | 4 passed, 0 skipped, 80.54 seconds |
| Updated campaign subset | Paired isolation, worker direct-execute race, acceptance startup-refusal plus logging failure, workspace claim collision. | 4 passed, 0 skipped, 43.38 seconds |
| Paired recheck before static amendments | `test_paired_real_exports_and_exact_candidate_acceptance` on test hash `7ef9608955e1ab08a4137480700bc2eaece46ee37f028cb6a660a4fc897bdc5e`, with all three Linux host-alias families. | 1 passed, 0 skipped, 24.06 seconds |
| Final refreshed source recheck | Paired isolation and acceptance direct-execute race on the updated final test/tool hashes below. All four owned hashes were reread and unchanged after execution. The execute contenders returned 0/42 with one start trace and finished ownership. | 2 passed, 0 skipped, 47.50 seconds |

The two preliminary runs overlapped test-only edits. All six reviewed production files remained byte-identical throughout. The refreshed pair/execute recheck binds the final test/tool snapshot exactly. All 13 campaign cases also independently collected after the fixture-import amendments. The coordinator remains responsible for rerunning all 13 campaign cases and the existing regression suite together on this final snapshot; a complete run started before these static amendments is pre-final evidence.

Reviewer scratch directories:

- `C:/Users/hensl/AppData/Local/Temp/m1-independent-f4438c6c53294e64b1f6d2a428d35146`
- `C:/Users/hensl/AppData/Local/Temp/m1-final-review-d63b6665f847411fa96c040f38b60f4a`
- `C:/Users/hensl/AppData/Local/Temp/m1-exact-review-5bbc0c2157734bde8ee19d9eb5146f81`
- `C:/Users/hensl/AppData/Local/Temp/m1-refresh-review-ae99632aa8b748c28027fd34324b6d5d`

Final paired reviewer evidence SHA256: `b84a1b6ed3a1ba2df47cfc054a82755886bd8472cb1768cf2b04d91edcae88d5`. Worker preserved archive: `312f0b4f1a7798bab7945f0a13005a78724d2bdb4fc32427bb8498ef5689e0ec`. Acceptance preserved archive: `cc0d997ee46589a7ba9709fb25d3114ca7ce945fca7e42e30cd680df766f8325`. Each export logged 124 denials, used the pinned image, and finished ownership; worker mount RW was true and acceptance mount RW was false.

## Audit and recorder assessment

The delivered-M5 audit nests the existing M4/M5 preservation checks and permits only the requested M6_HANDOFF.md documentation update among delivered tracked files. Independently, all 115 baseline paths matched the actual delivered Git tree, their raw SHA256 values matched the current files, and non-writing Git clean-filter `hash-object` values matched every committed blob at 5f83ac7. The refresh also independently confirmed all 115 raw files still match that delivered baseline. An initial `cat-file --filters` comparison was unsuitable for this mixed LF/CRLF worktree; clean-filter object identity resolved the representation difference with no product mismatch.

The recorder uses a new UUID evidence directory, records real command exit codes/output, hashes owned and M5 source before/after, requires all 13 case evidence files, and writes a digest-bound consolidated Docker bundle. Missing/skipped Docker evidence cannot produce its passing non-typing-gate field. BasedPyright is intentionally a visible diagnostic rather than included in `non_typing_gates_passed`; its exit codes, errors and warning summaries remain recorded, while Ruff and ty are required gates. A passing non-typing field must not be represented as a clean BasedPyright result. The reviewer independently ran owned-file BasedPyright with `uvx --offline basedpyright --pythonpath <actual Python312 executable> --outputjson` after the static amendments: four files analyzed, 0 errors, 687 warnings, exit code 1. Warnings remain visible and the actual exit code is not presented as green.

Final complete results and retained evidence belong in M1_ACCEPTANCE_FINAL_VERIFICATION.json and its linked M1_ACCEPTANCE_FINAL_VERIFICATION_DOCKER.json bundle. M1_ACCEPTANCE_VERIFICATION.json retains the source-changing pre-final full run explicitly. The reviewer did not replace the coordinator's complete preservation/static/regression procedure with the bounded probes above.

## Exact reviewed raw source snapshot

| Path | SHA256 |
| --- | --- |
| scripts/workflow_scope.py | 4f2ebc3b92a9323b63be3182b068ce6fdc11cb9112b2e4a5fcb99bf92b6290e2 |
| scripts/workflow_runtime.py | 7e4d7cb2e9e7c4424f9edff883232596d65035c25b334376bbabe23809c3ece6 |
| scripts/worker_launcher.py | 7f758e07ab4be07f7aa25db7c291a1cd3e81f34f215dabdfe430748bfdae9757 |
| scripts/execution_harness.py | a17d242303d509d3dd874f822a22a2e36f8421d06df1bfcfab154b9be542687e |
| scripts/acceptance.py | 7fd67c6eb39b8c0f4945d9338e659dd8a6e5aab2b5f08966d98c85c410340ef9 |
| scripts/acceptance_runtime.py | d84a1b62f74e415824277d85f01fd1cf545e6234f4995238e8a60e7dd1af27b1 |
| tests/test_m1_acceptance.py | faa85f6d908e6158ad408ff9bfe3d26ee102a81978b0506bea84b9ca2a3045bd |
| tests/ac02_ac03_process.py | ecbb5d3582ab1b19000ffdbd8936af3397266fd55a9f109f4b0e48ba86ac5404 |
| tools/check_m1_acceptance_preservation.py | a1db4c95ef3cf12feb129a0d5d1b5c320677ecb59e63cee5b19d88a0ff20d396 |
| tools/verify_m1_acceptance.py | 55eb8153509221f64d2a5a3ab8a1caebaa1541cb0bd13dca1d4cc4829fddb81f |
| docs/workflow-migration/M1_ACCEPTANCE_BASELINE.json | b32b20ea6ba536ef21554de6009843d1908e2168ee9793fef06045d1c4c60649 |

This is bounded evidence on Windows/Docker Desktop, not exhaustive proof against every kernel/daemon/filesystem fault or administrator action. The coordinator, image, Docker daemon and kernel remain trusted. Actor identities remain declarations; live providers, credential delivery, connector operations, paid workers and hardware/manual attestation remain disabled. No physical hardware behavior, integration, deployment or M6 result is established here.
