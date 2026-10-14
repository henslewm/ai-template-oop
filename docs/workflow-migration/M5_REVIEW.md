# Fresh scoped M5 correctness review

Reviewer: separate `m5_review` agent, 2026-10-14 UTC. Scope: M5 independent acceptance only. **Scoped correctness review: PASS; F1-F7 closed. No remaining scoped production correctness blocker identified. The coordinator complete split verification and delivery checks remain separate required gates.**

The reviewer inspected `acceptance.py`, `acceptance_runtime.py`, `acceptance_report.py`, the additive feedback hook, acceptance configuration/schema, acceptance tests, both preservation-audit tools, and the additive immutable-workspace runtime mode required by this review. Governing references included M5_HANDOFF.md, M5_PLAN.md, frozen ARCHITECTURE.md and workflow-bootstrap.json, M3_OPERATIONS.md and M3_RESUME_VERIFICATION.json, M4_HANDOFF.md, M4_PLAN.md, M4_OPERATIONS.md, M4_REVIEW.md, M4_CLOSEOUT.md, the final M4 verification/source/preservation evidence, M2_OPERATIONS.md, CLAUDE.md, PROMPTS.md and BRANCH_RETENTION.md. The pinned donor acceptance controller was inspected with `git show d6e582b7edeae24345a175f36639230726dbdead:scripts/acceptance.py` against the donor object database.

The reviewer changed only this document in the workspace. Probe code and disposable Journal/ownership fixtures lived outside the workspace under the system temporary directory. The reviewer made no Git mutation, protected-checkout write, canonical-store write, model/provider call or paid operation. Real Docker probes used only disposable fixture exports and the required immutable image `sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e`.

## Findings and corrections

### F1 - P2: an accepted proof could outlive a later user rejection - corrected

A production-API disposable probe added the user-decision gate, ran independent checks, recorded Owner approval, accepted, then recorded Owner rejection. Although `satisfied(state)` was false, synchronization still produced native ACCEPTED. The original probe passed, demonstrating the defect.

Accepted gates now permit only resubmission, which invalidates them, or synchronization. The proof verifier also rechecks final gate satisfaction. Controller/user actor comparison uses the existing normalized actor identity. Independent corrected probes confirmed post-ACCEPT rejection is refused without a Journal change and a case-variant controller cannot act as the separate user.

### F2 - P2: malformed check events could fabricate an acceptance proof - corrected

A disposable probe appended an unrelated check command, empty prepared metadata, a stopped exit of 1, and a PASSED report with exit 0 and a fake receipt. Acceptance and synchronization succeeded without any fresh check-container start. This demonstrated insufficient semantic validation in the pure proof reducer.

Check transitions now validate the exact contract command and validation ID, derived acceptance scope, bounded deadline, run identity, immutable prepared inventory/image/argv/scope/runtime mode, stopped runtime/archive fields, observed exit, effective deadline and report/archive/log receipt digest. The reviewer inspected these bindings and independently confirmed an unrelated command is refused before preparation. Actual filesystem/Docker observations remain the trusted coordinator adapter's responsibility; a host administrator with arbitrary database/code access is outside this boundary.

### F3 - P1: candidate ownership allowed transient substitution during checks - corrected

Inspection found that changing only tar mode to 0444 left worker-owned UID 1000 files. The existing trusted initializer also chowned all original write paths to UID 1000. An untrusted check could therefore chmod, substitute candidate bytes for a test, then restore them before stopped-output comparison.

Acceptance now marks candidate workspace files root-owned and explicitly prepares an immutable session. The additive runtime mode omits worker-file chown, mounts the acceptance session read-only and records/checks that mode. M4's default preparation path remains unchanged.

An independent real pinned-Docker probe verified root ownership and exact candidate bytes, then verified both chmod and writing raised OSError inside the acceptance container. Its saved log confirmed both denials and its independent ingestion passed. The host source remained unchanged. This is focused evidence for this correction, not closure of remaining M1 AC-02/AC-03 evidence.

### F4 - P2: replay and synchronization read races needed durable receipts - corrected

Inspection identified that CLOSED check replay recomputed the deadline using the later wall clock, potentially revising a saved PASS. Synchronization could also see unsynchronized state, lose a race to another synchronizer, then fail on a later native/proof read outside its conflict handling.

CLOSED replay now uses the durable effective report while rechecking exact archive/log bytes. Synchronization checks proof-head consistency and resolves identical synchronization across the complete read/commit interval. Independent probes passed both replay after the deadline with no Journal change and a deterministic interleaving that committed synchronization between the outer caller's first two read snapshots.

### F5 - P2: a rerun could leave earlier gate evidence usable - corrected

Inspection found that starting a second check retained the earlier PASS and allowed acceptance while the newer run remained pending. It also allowed check evidence to change after model/user evidence had been recorded without forcing fresh review.

Starting a check now clears that validation's previous result. Check reruns after current-generation reviewer or user evidence require resubmission. This preserves historical attempts while invalidating the gates. An independent production-API probe confirmed a prepared second check cannot accept.

### F6 - P2: claimed manual evidence was not registered proof - conservatively closed

The initial ATTESTATION transition accepted caller-supplied positive size/digest fields without a verified hardware-evidence adapter. It now refuses hardware/manual attestation ingestion explicitly. Required manual or hardware validations therefore remain UNVERIFIED and block acceptance. A future adapter must verify and register actual evidence; this milestone does not claim that support exists.

### F7 - P2: valid bounded rejections could not cross the native report schema - corrected

After the initial scoped review, the coordinator found that donor acceptance failures require a detailed `evidence` field, while frozen native feedback permits only `failed_ref`, `kind`, `what_failed` and `corrective_action`. Copying the detailed records into the native event refused a valid REJECT_BOUNDED report instead of preserving the corrective failure.

`condensed` now projects exactly those four native fields. The complete report retains its detailed evidence in the acceptance stream, and native feedback retains its exact report digest. The native fingerprint inputs remain unchanged. A new permanent scenario rejects once, completes a second M4 worker attempt, resubmits without resetting history, and rejects the same failure again into NEEDS_ARCHITECT.

An independent external probe ran that complete permanent scenario and added stronger assertions: two distinct review IDs retain the same failure fingerprint; both worker and reviewer lifetime counts remain two; all native monetary totals remain zero with an empty unknown-liability list; the full failure evidence and native report digest agree; identical duplicate rejection changes no Journal head or state; changing only detailed failure evidence is a conflicting duplicate and changes no head. Both reviewer-role and project budget settlements remain zero. Result: **1 passed in 41.76 seconds**. An earlier run exposed only the corrected test fixture's descending timestamp, and another reviewer harness assertion expected a boolean instead of M3's empty unknown-ID list; neither was a new product defect.

The final revision also enforces configured artifact-character and workspace-file limits and validates approval/environment digest shapes. These guards were inspected, and the permanent lowered-policy test independently passed: **1 passed in 5.89 seconds**. The coordinator's earlier full-suite run was interrupted to incorporate F7; it is not a final passing split result. Fresh complete verification is still required for delivery.

## Independent checks and limits

Corrected external probes: **5 passed in 43.13 seconds** for accepted-state immutability, normalized user identity, late CLOSED replay, wrong-command refusal and the deterministic synchronization read race. A later pending-rerun probe passed independently: **1 passed in 11.63 seconds**.

The repository's real pinned-Docker independent-check test and unchanged legacy `test_execution_timeout_still_stops_and_preserves` passed together: **2 passed in 11.63 seconds**, with no skips. The separate actual chmod/write-denial probe passed: **1 passed in 12.81 seconds**. Its first external harness run had a reviewer-only missing import after the container assertions had already passed; that harness typo was corrected and the complete probe rerun cleanly.

The reviewer independently ran `python -B tools/check_m4_preservation.py`: PASS. Both protected HEADs, complete statuses/indexes and 331 files matched; 31 canonical files and 14 archived files matched. Seventeen M3 files remained byte-identical, and removing exactly the additive feedback hook reproduced the original eighteenth file. Frozen material and retained refs passed the existing audit. This dated check is separate from the coordinator's final post-delivery preservation evidence.

This is a scoped correctness review, not exhaustive proof of every crash, malicious archive, Windows/Docker/kernel failure or deployment behavior. Coordinator identities remain declarations rather than authentication. Live provider transport, paid workers, trustworthy live usage and hardware/manual evidence ingestion remain disabled. M5 implementation does not close remaining M1 evidence, authorize integration/deployment, or perform M6. The coordinator must obtain fresh complete split-suite, static and preservation results on the final snapshot before delivery.

Against the reviewed pre-F7 snapshot, six additional permanent cases passed independently in **93.02 seconds**: both actual process-exit synchronization crashes, every four-stream reviewer-settlement insertion crash, full high and critical native gate flows, and rehashed malformed-proof refusals. The expanded real Docker test, which now includes root ownership, chmod/write, network, socket and Git negatives, passed independently on that snapshot: **1 passed in 16.49 seconds**, with no skips.

The full critical flow verifies the documented destination rule that one qualifying named architect report satisfies both model and architect gates while meeting cross-family/tier floors. This preserves native tier-4 cap one and the overall cumulative review cap; it does not create another review attempt.

Final `tools/check_m5_preservation.py` also passed independently: all entry tracked files except the exact three intended baseline modifications remain byte-identical, every prior ref remains, and the feature tip retains its entry ancestor. The M4 audit remains nested in that check.

Independent static diagnostics: `uvx --offline ty check` passed all six implementation/tool paths. Scoped BasedPyright over the three new acceptance modules reported **4 reportImportCycles errors and 1454 warnings**. These remain visible; the lazy feedback integration and CLI/runtime imports execute after module initialization, and the final runtime tests passed. This scoped correctness PASS does not represent BasedPyright as a green check or suppress those diagnostics.

## Final source snapshot

Raw SHA256 values reread after the independent F7 checks and final static diagnostics. The acceptance controller/test hashes include F7 and the bounded-policy guards; all other recorded hashes remain unchanged.

| File | SHA256 |
| --- | --- |
| scripts/acceptance.py | 7fd67c6eb39b8c0f4945d9338e659dd8a6e5aab2b5f08966d98c85c410340ef9 |
| scripts/acceptance_runtime.py | d84a1b62f74e415824277d85f01fd1cf545e6234f4995238e8a60e7dd1af27b1 |
| scripts/acceptance_report.py | ca8d6e39e2d7002eeda66db932ea08ece935d10222eabf203096b56513102545 |
| scripts/feedback.py | 81c10c75116146e054d2e8adbdc4c39a49fdc7b9579273249e1663661adc55c1 |
| scripts/workflow_runtime.py | 7e4d7cb2e9e7c4424f9edff883232596d65035c25b334376bbabe23809c3ece6 |
| config/acceptance.json | 5573e7830a055e4ce5dcf96c9ee83c3293679594ac6626ddde48a1e6b916aeea |
| config/acceptance.schema.json | 6f45bbb9f00503189c5888e4d0849b8801c04ef1e755c5625cc285ef3e37030b |
| tests/test_acceptance.py | 4e409958ea6b0b7444a4e63d845699b82223d49695725270f0d94d6a951bb45b |
| tools/check_m4_preservation.py | c5ddb7d25da1a12151e798b1248df05e6cea4b8ab840c66aef3249a4b309f1e5 |
| tools/check_m5_preservation.py | 575ce62bcd10546356ba51e28aed4535213b5e5539d2d886b53181a57d1ed05d |
