# M5 evidence and retained M1 boundaries

M5 implements independent acceptance. Its scoped review and final verification
are recorded separately in M5_REVIEW.md and M5_VERIFICATION.json. The frozen
foundation criteria are unchanged. Neither the M5 implementation nor its passing
tests automatically closes remaining M1 AC-02 or AC-03.

| Criterion | Evidence M5 adds | Evidence/decision still missing |
| --- | --- | --- |
| AC-02: Docker isolation for both worker and acceptance exports | A fresh acceptance volume contains the exact stopped M4 replacement and enumerated immutable inputs. The pinned real image verifies candidate bytes, root ownership, read-only session, denied chmod/write, network connection failure, no exported Git directory or Docker socket, and unchanged host source. Runtime inspection enforces no host binds, network none, UID/GID1000, exact image/environment and resource limits. Exact stopped-output negative tests reject links, escapes, missing/extra/changed files, command-written reports and secret-like content. The complete split run also reruns M4's real worker export/report round trip and existing scope isolation cases. | There is no new criterion-level independent acceptance decision for the original M1 candidate or a consolidated paired worker/acceptance adversarial evidence bundle covering every required host/sibling/credential/link/connector read/write path. M5's focused real acceptance fixture is additional evidence, not that complete decision. No physical hardware or live provider/credential transport was exercised. |
| AC-03: exclusive ownership, one consumed start and safe crash/race recovery | Acceptance uses the existing shared ownership and separately committed consumed-start stores. Its tests exercise one winning concurrent check launch, refused repeat after ambiguous consumed start, explicit stopped-output abandonment, preparation/claim interruption, missing native-review opening after reservation, and idempotent concurrent check/review/feedback outcomes. Actual child-process exit at both synchronization inserts and faults at all four reviewer settlement inserts preserve pre-transaction heads. Existing M1/M4 ownership/startup/expiry/timeout/crash/replay tests rerun in the complete split procedure. | The new acceptance start-race/ambiguous-start cases use real SQLite/ownership with an offline Docker transport double; they do not establish a dedicated actual-Docker multi-process acceptance startup/crash race campaign. No separate exact-candidate AC-03 acceptance decision is recorded for the historical M1 startup repair. Original retained runtime/ownership evidence has been preserved, not silently reclassified as accepted. |

No M5 operation upgrades a missing hardware/manual gate. Attestation ingestion
is disabled, those gates remain UNVERIFIED and block acceptance. Unit or
simulation results do not verify physical devices. Actor and model-family
identities are coordinator declarations. The coordinator, Docker daemon/image,
kernel and host filesystem remain trusted.

The final split results must be read with their actual skips and limitations.
Focused independent review probes and old milestone totals do not substitute
for that run. M6 remains future work; it must keep accepted, integrated, VERIFIED
dependency and deployed facts separate.
