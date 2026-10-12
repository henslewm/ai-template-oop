# Revised workflow plan and Codex quickstart

Prepared: 2026-10-12 00:11 UTC / 2026-10-11 20:11 America/New_York.
Status: PLAN ONLY. No code, repository edits, issues, PRs, automation, commits, or merges performed. All proposed defaults below remain provisional.

## 1. Evidence and preserved baseline

Read the complete attached `workflow-transfer-review-2026-10-12(1).md`, including its full branched-chat prompt. Its HartBeat findings remain a targeted reference review, not verified donor implementation. The original donor archive was not supplied or re-audited in this turn.

Read-only GitHub inspection confirmed these main snapshots:

- OOP destination: `henslewm/ai-template-oop` at `a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4`.
- Original infrastructure source: `henslewm/universal-ai-project-template` at `d6e582b7edeae24345a175f36639230726dbdead`.
- Inspected both file trees and selected original startup, work-packet, execution-harness, closeout, README and handoff materials. This was not a fresh full-code audit. Branch tips outside main, local changes, installed CLI versions and live GitHub enforcement remain unknown. No repository commands or test suites were executed.

The baseline remains:

1. Cohesive feature objects own their logic/state and expose typed inputs, outputs, errors and optional progress/events.
2. UI collects inputs and displays outputs. Business decisions and multi-feature business orchestration belong outside UI; dependencies are supplied through declared interfaces.
3. Feature and UI branches are permanent and separate. Never delete, force-push or rename them for cleanup. One writer per branch/workspace. No worker automatically changes another branch.
4. Approved feature I/O changes require linked UI PR work, mocks and compatibility validation. Internal changes preserving I/O need no UI PR.
5. Feature sessions receive only their feature, relevant contracts/tests, task and bounded handoff. UI sessions receive relevant UI, contracts, mocks and UI tests, without feature implementation.
6. A separate integrator assembles explicitly selected commits, owns wiring and verifies the affected combination before gated promotion to main.
7. Keep the template headless. UI rules govern generated applications/consumers; they do not authorize building a template dashboard.
8. Preserve intake, durable decisions/state/handoffs, multi-platform support, routing, budgets/retries, worker launching/monitoring, hardware evidence, CI and safe closeout.

## 2. Keep / change / add / defer

| Action | Current plan or infrastructure | Revised treatment |
|---|---|---|
| Keep | Feature objects, typed contracts, UI separation | Make these the non-negotiable architecture acceptance criteria. Avoid a single oversized public object becoming a dumping ground; private helpers remain internal. |
| Keep | Permanent branches and deliberate integration | Branch ownership and promotion remain explicit. A feature is a scoped set of files; its branch is not itself a source visibility boundary. |
| Keep | Existing task, decision, routing and evidence records | Preserve identifiers/history; migrate with provenance. Do not create a competing task ledger or budget controller. |
| Change | General startup reads and existing bounded-worker exception | Extend the bounded model to ordinary feature/UI CLI sessions. Thin platform routers select shared minimum rules plus one role packet; full governance stays with coordinator/integrator. |
| Change | Work packet and harness | Extend their existing schemas with session role, feature ID, base commit, branch/workspace, owner, separate read/write scope, interface revision, dependencies and acceptance evidence. Keep packet contract revision distinct from application I/O revision. |
| Change | Launcher provides bounded briefs, but deployment isolation remains external | Add prepared file scope and an actual process/filesystem/tool access boundary. No source-repository mount, shared Git object store or broad repository connector for workers. Working directory and read-only brief alone do not enforce read isolation. |
| Change | Shared test registry and project-wide document updates | Feature-owned test discovery/fixtures; integrator owns common wiring. Coordinator alone updates shared state from scoped reports. |
| Change | Existing boundary checker | Extend to sibling-feature imports and transitive dependency paths; pair structural checks with behavioral contract/UI tests. A grep result is not proof of architecture. |
| Change | Existing closeout script | Preserve readiness/review checks, remove branch deletion and implicit cross-branch synchronization. Separate report, publish and promotion operations with explicit authority. Do not run the original merge command unchanged. |
| Add | Ownership and blocked-by checks | Atomic claim per branch/workspace, owner/run ID, expiry/heartbeat and controlled recovery. Independent features can proceed concurrently. |
| Add | Approved contract-change workflow | Record proposal/approval, old/new interface hashes, impacted consumers and linked UI work. Do not let a worker silently edit contracts. |
| Add | Portable lifecycle vocabulary | Preflight, intake, handoff and gate operations reuse current schemas. Optional CLI aliases are adapters; no assumption that slash commands already exist. |
| Add | Focused reporting | One CI failure summary per commit/run; task → interface → diff → check → accepted evidence traceability; coordinator-run drift review. |
| Add | Capability truth and integration decisions | Separate planned, implemented, tested, integrated and deployed with evidence date/environment/commit. Extend existing records instead of maintaining parallel truth. |
| Defer | General recipes, advanced reporting, release dashboards | Add only after isolation and contract gates pass. No dashboard is needed for this headless template. |
| Defer | Broad deployment automation and arbitrary extra adapters | Preserve existing capabilities; expand only for an approved task. Do not import donor stack, hosting or retention policy. |

Rejected donor rules: whole-codebase/root-doc startup for every worker; one personal branch; branch deletion; replacing durable handoffs with machine memory; workers rewriting shared planning documents; donor identities/credentials/paths; configured checks treated as enforced checks. Preserve existing safeguards while removing conflicting behavior. Existing frozen-work policies must be explicitly reconciled for the migration scope, not silently bypassed or erased.

## 3. Reuse map

Paths below are verified present in the original snapshot, not claimed installed in OOP.

| Existing component | Adaptation |
|---|---|
| `config/work-packet.schema.json`, `scripts/work_packet.py`, `WORK_PACKET_PROTOCOL.md` | Extend scope/ownership/interface references; preserve revisions, dependencies and role transitions. |
| `scripts/execution_harness.py`, `scripts/worker_launcher.py`, `EXECUTION_HARNESS_PROTOCOL.md` | Add scoped preparation and enforceable worker launch environment, retaining dispatch/launch/report/ingest separation. |
| `scripts/model_router.py`, `scripts/feedback.py` and their schemas | Retain routing, retry/cost reservations and unknown-cost handling; include measurement evidence without a second budget ledger. |
| `scripts/acceptance.py`, `config/acceptance.schema.json` | Add boundary, compatibility and candidate-integration gates to existing risk floors; do not weaken review requirements. |
| `AGENTS.md`, platform instructions, `prompts/END_SESSION.md`, `HANDOFF_CURRENT.md` | Thin role routing and scoped worker handoffs; coordinator maintains shared summaries. |
| `scripts/validate_project.py`, `scripts/closeout.py` | Reuse validation and readiness after correcting conflicting closeout behavior. |
| `scripts/software_hardware.py`, software/hardware profile | Preserve real hardware evidence requirements; unavailable hardware means blocked/unverified, not simulated success. |
| OOP `contracts/`, `src/features/`, `src/container/`, `tools/validate_boundaries.py` | Architectural destination and focused boundary enhancement; resolve existing UI demo as an explicitly planned headless migration item. |

The original harness documentation explicitly says a worker running as the operator can reach the ledger; deployment isolation is the control. It also contains differing usage/log descriptions. Resolve those against executable source during migration rather than copying inconsistent prose into new instructions.

## 4. Phased adoption

| Phase | Owner and trigger | Context and work | Acceptance evidence | Fallback |
|---|---|---|---|---|
| 0 — Pin migration scope | Coordinator; when implementation is authorized | Destination identity/local status; source SHAs; existing migration branches/PRs; governing decisions; named infrastructure only. Map each capability to keep/adapt/defer and assign owned paths. | Approved migration packet and capability map; no overlapping writer; identified conflicting rules; existing work preserved. | Stay read-only on a disputed scope/base; retain current branches and records. |
| 1 — Scope and ownership first | Workflow feature owner; phase 0 ready | Existing packet, harness, launcher and startup routes plus focused tests. Prepare allowlisted workspace before worker launch; immutable contract inputs; coordinator applies scoped output to its assigned branch. | Negative access tests; collision/recovery tests; normal feature/UI startup traces; no unintended branch ref changes. | Refuse worker launch if isolation cannot be established; coordinator may inspect the gap but cannot label an unrestricted session isolated. |
| 2 — Contracts and boundaries | Contract owner plus scoped feature/UI owners; phase 1 accepted | Relevant interfaces, owned implementations or UI/mocks; integrator alone sees affected combination. Add proposal/approval/linking, compatibility checks and dependency boundaries. | Internal fix passes without UI change; approved interface change creates linked UI work; unapproved change blocked; incompatible combination cannot promote. | Keep previous compatible interface/application candidate. Return proposal for revision without changing another worker's scope. |
| 3 — Lifecycle and continuity | Coordinator and acceptance owner; phase 2 accepted | Extend existing intake/handoff/gates, review/routing/hardware/closeout components in bounded tasks. Preserve IDs and record migrations. | Fresh-session resume; restart after interruption; budget/retry limits; exact candidate gates; permanent branches survive closeout. | Record blocked state and preserve evidence. Do not infer completion or unknown costs. |
| 4 — Reporting and pilot | Coordinator/reviewer; representative workflow available | CI summaries, affected-record drift audit, capability views, redaction/retention; paired feature/UI/integration trials. | Commit/run-bound reports; secrets excluded; token/retry/outcome measurements including integration; quickstart exercised from clean setup. | Keep manual evidence-backed review if reporting is unavailable; withhold efficiency claims. |

No phase is permission to merge automatically. An accepted implementation, an integrated candidate and a deployed release are distinct states. Hardware/runtime validation is required when relevant, with the actual environment recorded.

## 5. Enforcement and acceptance criteria

Provisional enforcement design: the trusted coordinator prepares an allowlisted export for an unprivileged worker in an isolated runtime. Contracts/rules are immutable inputs, owned paths writable, unrelated repository source and Git history inaccessible. Network/tools are constrained so the worker cannot retrieve unrelated source through GitHub or another connector. A worker submits a scoped patch/report; trusted branch-side tooling validates and applies it only to that feature's branch at the recorded base. This preserves branches while avoiding Git worktrees as a false read barrier. Exact Windows runtime remains a decision.

1. **Read isolation:** feature A cannot read feature B through relative/absolute paths, symlinks, Git history, parent directory, inherited state or repository tools. UI cannot read feature implementation. An allowed contract remains readable. Capture denied attempts and a successful normal task.
2. **Write isolation:** unrelated paths, contracts and governance reject worker writes. Returned patches are rejected for path escape, unexpected files or stale base. Feature work leaves other branch tips unchanged; only explicit integration changes its destination.
3. **Ownership:** a second writer is refused atomically. Expiry does not permit takeover until the previous process is confirmed stopped and its changes preserved. Crash recovery records owner and evidence.
4. **Context expansion:** worker requests exact missing path/symbol or question with reason. Coordinator returns the smallest approved addition in a new scope revision. Unrelated discovery becomes a separate proposal.
5. **Architecture:** sibling implementation imports, including indirect paths through shared helpers, fail; interface injection passes. UI tests demonstrate rendering/input behavior while feature tests own business decisions. Shared helpers have a named owner and cannot hide feature coupling.
6. **Interface changes:** changed schemas/types/errors/events and changed semantics are assessed. Approved change produces linked UI PR work against the approved revision, updated mocks and compatibility tests. Internal-only change requires neither UI edits nor UI PR. Headless-only interfaces need the explicit consumer-policy decision below.
7. **Integration:** candidate records exact feature/UI/base SHAs and contract versions. Any candidate change invalidates stale evidence. Affected real execution path passes; failing or missing required checks prevent promotion. Verify live required-check behavior, not merely workflow YAML presence.
8. **Continuity:** a fresh session can identify objective, scope, last base/diff, interface changes, commands/results, pending reservation, blockers and next action from its bounded handoff. The coordinator retains shared decisions. Context usage is measured, estimated or unknown; never an invented percentage. Prepare a handoff near the user's 50% target where telemetry permits and before continuity is at risk.
9. **Preservation:** migrated intake/routing/budgets/launching/acceptance/hardware/closeout behavior is traced to original records and tested at relevant boundaries. Retained branches survive two successive releases from the same feature branch without duplicate changes or history loss.
10. **Truth:** status separates implementation, testing, integration and deployment. Evidence claims identify environment/date/commit and reviewer. Machine reports do not self-approve.

## 6. Contract-change sequence

Feature worker submits bounded proposal → contract owner approves a specific interface revision → coordinator schedules linked feature/UI work and draft UI PR → each owner implements in its own branch using the same contract/mocks → reviewer checks both → integrator tests exact combined candidate → explicit gated promotion.

PR creation is authorized workflow orchestration following approval, not permission for a feature worker to modify the UI branch. Breaking changes require either an explicit compatibility bridge or a coordinated candidate that keeps main runnable. Merge ordering and compatibility duration remain provisional. For a template interface with no UI consumer, do not invent UI code merely to satisfy a link; resolve the documented exception policy before shipping that trigger.

## 7. Decisions still required

| Material decision | Provisional default | Needed before |
|---|---|---|
| Feature boundaries and shared ownership | Cohesive capabilities: session scope/ownership, contract lifecycle, intake/state/handoff, routing/budgets, execution, acceptance/integration; confirm boundaries against existing infrastructure before splitting files. | Phase 0 packet approval |
| Windows read/write enforcement | Isolated export plus restricted process runtime; coordinator owns Git. A worktree alone is insufficient. Select container/VM/OS policy based on actual CLI/tool support. | Phase 1 implementation |
| Contract authority/versioning | Named coordinator/architect approves; immutable revisions plus explicit compatibility classification. Breaking change needs coordinated candidate; compatibility window set per consumer. | Phase 2 |
| Permanent-branch integration mechanics | Merge commits provisionally, deliberate main-to-feature synchronization by its owner; never cleanup deletion or force-push. Check hosting rules and repeat-release behavior first. | First integration |
| Ownership recovery | Heartbeat/lease with coordinator recovery only after process-stop confirmation and preserved diff. Set duration from expected task length. | Phase 1 |
| Headless/no-UI consumers | Linked consumer-impact record instead of an artificial UI PR only if owner explicitly approves this exception. Baseline UI-facing changes always retain linked UI work. | Contract trigger rollout |
| Authority and gates | Worker cannot approve own work or promote; coordinator prepares; independent reviewer accepts; integrator promotes under recorded authority and inherited risk floors. Name actors and required checks. | Phase 2/3 |
| Completion and release | Accepted ≠ integrated ≠ deployed; record environments and hardware requirements. Define risk-waiver owner/expiry/fallback without allowing waiver of baseline isolation. | Phase 3 |

## 8. Measure efficiency

Use matched tasks: internal feature fix, UI-only change, and interface change with linked integration. Provisional pilot: at least three tasks of each type where practical. Pin model/effort, acceptance criteria and comparable starting snapshots; account for caching and task difficulty.

Record startup context tokens (or clearly labeled estimate), unrelated file reads, repeated reads, input/output/cache tokens, attempts, wall time, accepted outcome and defects/rework. Include coordinator, reviewer, handoff and integration effort in totals. Unknown usage stays unknown, not zero. Compare total tokens per accepted change and acceptance rate against the previous workflow; report sample size and variability. Isolation target is zero successful unrelated source reads. No token-saving percentage or performance threshold is established yet.

## 9. Where to start Codex for implementation

Start the **migration coordinator** in your local **ai-template-oop repository**, the intended destination. Keep universal-ai-project-template as the pinned reference source. First inspect local status, current branch, existing migration work and current remote base so an earlier migration is not overwritten or duplicated. Do not start implementation on main or assume the local checkout matches the snapshots above.

After implementation scope is approved, use a dedicated retained migration branch/workspace (provisional name: `feature/workflow-migration`). This coordinator workspace may inspect the named infrastructure across both repositories. It is not the normal feature-worker environment. Subsequent feature/UI sessions start only in prepared scoped workspaces after phase 1 is verified.

No shell execution is required for this plan. Because your local path and installed commands are unknown, use the following prompt in Codex opened through your existing workflow; it performs read-only preparation before coding authorization.

### Copy/paste: migration-session start

```text
Act as migration coordinator for ai-template-oop. Read the attached revised-plan-and-quickstart-2026-10-12-0011Z.md and its source review. This first step is read-only preflight, not permission to code, commit, push, merge, open PRs/issues, run paid workers or change branches.
Confirm destination repository, local status, current branch/base and any existing migration work. Preserve all uncommitted changes. Compare current source/destination revisions to the plan snapshots. Read applicable governing instructions and only the named migration infrastructure; report conflicts with the approved baseline rather than importing them.
Inventory existing packet, harness, launcher, routing/budget, acceptance, state/handoff and closeout interfaces. Distinguish present/documented/tested from absent. Identify exact supported local preflight/handoff commands and their side effects; do not invent slash commands.
Prepare the phase-0 migration packet, ownership/path map, phase-1 task and recommended retained branch/workspace. Prioritize enforceable context isolation and ownership. Keep all defaults provisional. Report readiness, blockers and the next bounded implementation task. Do not run the original closeout merge: it deletes branches in the inspected snapshot.
```

### Can you run preflights and handoffs now?

Yes as **session procedures**, with limits. The original repo has a startup validator and durable handoff prompt. The inspected OOP main tree does not yet include the original lifecycle scripts. There is no verified universal `/preflight` or `/handoff` command in these materials. A prompt is usable today; a portable executable operation remains planned.

- Original startup documents specify `python scripts/validate_project.py`; the work-packet parser supports `python scripts/work_packet.py validate <packet-path>`. These are source-verified invocations, not executed here. Packet validation proves structure/history, not execution authorization or filesystem isolation. Confirm dependencies and local version before use.
- Original `prompts/END_SESSION.md` instructs updates to shared records. In the revised model, the coordinator uses that shared closeout; workers produce only scoped handoffs. Do not give the original broad update instruction unchanged to a feature worker.
- Original `scripts/closeout.py merge` deletes merged branches. Do not reuse it until corrected and branch retention is verified, including repository auto-delete settings. A pending fix elsewhere is not proof that your checked-out version is safe.

### Copy/paste: preflight in a prepared feature/UI workspace

```text
Run the supported preflight for this packet. Confirm role, task/feature ID, owner, workspace, branch/base, interface revision, allowed reads/writes, dependencies, budget and acceptance checks. Read only the supplied startup view and packet context. Verify isolation and ownership evidence; if unavailable, report NOT READY without searching unrelated source or widening access. List the next bounded action. This request does not authorize changes to another branch or automatic Git publication.
```

### Copy/paste: handoff

```text
Prepare a bounded handoff for this task in its authorized handoff destination; if none is writable, return it in chat. Record objective, scope, repository/base and actual branch, changed files/uncommitted work, interface revisions and linked consumer work, commands actually run and results, evidence paths, remaining budget/pending run, blockers and exact next action. Distinguish completed, failed and unverified. State context utilization as measured, estimated or unknown; invent no percentage. Include a ready-to-paste resume prompt. Do not edit shared project records from a worker session, and do not commit/push/merge/delete branches as part of this request.
```

## 10. Post-merge daily quickstart — target behavior, not shipped commands

| Step | What you do | Required system response |
|---|---|---|
| 1. Request | Open coordinator at project root and state one capability/change. | Intake finds or prepares its packet, feature owner and retained branch; new scope needs a separate proposal. |
| 2. Prepare | Ask for the feature/UI session. | Coordinator creates the scoped workspace, supplies contract/tests/handoff, checks ownership and prints the actual supported launch action. |
| 3. Preflight | Use the preflight prompt above or the verified operation documented after migration. | READY only with correct base, interface, scope, dependencies and access enforcement. |
| 4. Work | Ask for the single packet task. | Worker edits owned files and runs declared checks. It escalates missing context/I/O changes instead of expanding scope. |
| 5. Pause/resume | Use the handoff prompt; start the next worker in the prepared workspace. | Resume verifies current base/contract/ownership against handoff before continuing; expired/stale work is reconciled. |
| 6. Review | Submit bounded output for acceptance. | Independent review checks actual diff/evidence, not worker claims alone. |
| 7. Integrate | Coordinator requests the approved integration candidate. | Separate integrator validates exact commits and affected real paths; main promotion follows authority and required checks. |
| 8. Continue | Request more work on that same feature later. | Reuse retained branch after deliberate base/scope reconciliation. No automatic branch deletion or unrelated updates. |

Before calling the merge usable, require an implementation-produced command reference and one consolidated Windows PowerShell quickstart using the actual installed interfaces, tested in a clean checkout and a resume scenario. It must distinguish inspection from writes, refuse wrong/dirty targets safely, preserve branches, and report failures accurately. Inventing those executable commands now would misrepresent planned functionality as shipped.

## 11. Sources and continuity record

- Attachment: `workflow-transfer-review-2026-10-12(1).md`, full review and prompt.
- [OOP snapshot](https://github.com/henslewm/ai-template-oop/tree/a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4)
- [Original startup router](https://github.com/henslewm/universal-ai-project-template/blob/d6e582b7edeae24345a175f36639230726dbdead/AGENTS.md)
- [Existing execution harness protocol](https://github.com/henslewm/universal-ai-project-template/blob/d6e582b7edeae24345a175f36639230726dbdead/EXECUTION_HARNESS_PROTOCOL.md)
- [Work packet implementation](https://github.com/henslewm/universal-ai-project-template/blob/d6e582b7edeae24345a175f36639230726dbdead/scripts/work_packet.py)
- [Original closeout implementation](https://github.com/henslewm/universal-ai-project-template/blob/d6e582b7edeae24345a175f36639230726dbdead/scripts/closeout.py)
- [Original end-session prompt](https://github.com/henslewm/universal-ai-project-template/blob/d6e582b7edeae24345a175f36639230726dbdead/prompts/END_SESSION.md)

Completed: review/prompt reconciliation, focused source inspection, revised plan, acceptance criteria, unresolved decisions and procedural quickstart. Not performed: implementation, repository writes, live tool/CI execution, preflight on your machine, merge, or measurement of savings. No failed repository operation was encountered; local readiness remains unverified. Context utilization for this planning session is unknown.

Next action: open the migration coordinator in ai-template-oop, supply this document and the source review, and use the read-only migration-session prompt. Phase-0 findings establish the exact implementation scope and commands before coding begins.
