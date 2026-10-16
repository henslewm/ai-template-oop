## 1. Purpose and finding

Prepared from read-only inspection at 2026-10-15 01:46 UTC.

The next session should assess the project against its original intended outcome, preserve the work already done, and identify what remains. Do not implement fixes, add features, reorganize the repositories, or restart the migration during this review.

The original destination goal was broader than making the Tk demo usable:

> A reusable, headless, contract-first template for AI-assisted software and hardware projects, combining the OOP repository’s modular architecture with selected capabilities from the universal template.

The current M1–M6 campaign implements a narrower offline workflow foundation. Its completion would be progress toward that product, but would not establish that the whole original migration is complete.

Two distinctions must survive the handoff:

- Preserve the original product goals without treating historical briefs as current execution authority.
- Preserve accepted engineering work without assuming every later mechanism or document is itself an original product requirement.

No files were changed, tests rerun, branches changed, or remote state refreshed during this investigation.

## 2. Recovered sources and original intent

### Repository identities

| Role | Location / identity |
|---|---|
| Destination repository | henslewm/ai-template-oop |
| Protected original checkout | C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop |
| Retained implementation worktree | C:\Users\hensl\Documents\GitHub\ai-template\ai-template-oop-workflow-migration |
| Read-only donor | C:\Users\hensl\Documents\GitHub\ai-template\universal-ai-project-template |
| Pinned donor revision | d6e582b7edeae24345a175f36639230726dbdead |

The two destination checkouts belong to the same repository. The migration worktree is not a third product.

The protected original checkout currently has no docs directory. Relevant records are in historical Git objects, the migration worktree’s documentation, and Downloads.

### Source trail

Universal template, initial commit ef0155c — August 29

Its initial README describes:

- A reusable intake process.
- Compact, decision-relevant questions.
- Repository-backed charter, state, decisions, sources, risks and handoffs.
- Continuity across ChatGPT, Codex, Claude, Claude Code and GitHub.
- Small platform entrypoints using common project information.
- Validation before commit or handoff.

Its central goal was durable continuity across models and sessions, rather than reliance on one chat’s memory.

Universal template, 25806b6 — September 11

The autonomous control-plane objective adds:

- Lowest practical total cost per accepted result.
- A strong architect decomposing work for cheaper workers.
- Bounded packets, attempts, escalation and independent acceptance.
- Routine execution within approved scope without repeated permission requests.
- Human intervention for material architecture changes and separately consequential actions.
- Small reviewer context rather than repeated whole-repository reading.

Universal template, owner requirements recorded in e5d538a — September 28

The charter explicitly records concern about drift, hallucination and cost, plus the intention of “spending money now to save money later.”

Preserve the distinction between the owner’s stated requirements and portions marked inferred or pending ADR.

Subsequent decisions changed some early objectives:

- Legal tracks were archived.
- A combined ledger was not pursued.
- Broad savings telemetry and dry-run work were deferred.
- Local-model support was removed; cheaper cloud workers remained.
- Startup-context reduction and bounded delegation remained goals.

Do not revive superseded objectives merely because they appear in an early commit.

OOP template, substantive initial commit 9683d58 — October 10

Its original purpose was parallel development through:

- Typed ABC contracts, frozen data objects and declared exceptions.
- Presentation-only UI.
- Cohesive feature implementations behind interfaces.
- Dependency injection and a separate integration owner.
- Shared behavioral tests for mocks and production implementations.
- Structural import-boundary checks.
- Sessions receiving only the code relevant to their role.

The login/statistics Tk application was the worked example for this pattern.

Headless migration brief — October 10

The strongest recovered statement of the requested destination product is inside:

Headless-OOP-Migration-Kit.zip (C:/Users/hensl/Downloads/Headless-OOP-Migration-Kit.zip)

Read the archive member:

2026-10-10_1609_Claude-Headless-OOP-Migration.md

It explicitly says “Drop the UI” and names seven capabilities:

1. Durable decisions, state, open loops, source records and handoffs.
2. Project intake and generation.
3. Multiple AI-platform instruction entrypoints.
4. Model routing, budgets and bounded retries.
5. Worker launching and monitoring.
6. Hardware/firmware verification controls.
7. GitHub CI and guarded closeout.

It also specifies:

- Preserve contract-first modularity and shared behavioral tests.
- Retain useful backend examples without treating them as the control plane.
- Reuse donor controllers rather than rewrite everything as classes.
- Keep one authoritative implementation and record format per capability.
- Generate projects with their own identity and unapproved activation state.
- Demonstrate setup from a fresh checkout.
- Supply usable operator instructions and a consolidated Windows setup/check procedure.
- Distinguish deterministic harness tests from paid-model connectivity and real hardware evidence.

The companion code pack is explicitly reference/example material, not a completed migration.

Later migration planning — October 11–12

Read:

- Capability comparison (C:/Users/hensl/Downloads/2026-10-11T2155Z-oop-vs-universal-capability-review.md)
- Workflow transfer review (C:/Users/hensl/Downloads/workflow-transfer-review-2026-10-12.md)
- Revised plan and quickstart (C:/Users/hensl/Downloads/revised-plan-and-quickstart-2026-10-12-0011Z.md)

The revised plan also exists historically at destination commit:

f624e20:revised-plan-and-quickstart-2026-10-12-0011Z.md

These sources preserve:

- A headless template, with presentation-only UI rules for application consumers.
- Permanent feature/UI branches and explicit integration.
- Enforceable scoped access, not merely instructions or Git worktrees.
- One writer per branch/workspace.
- Approved interface changes linked to affected UI/mocks.
- Small missing-context requests.
- Coordinator-owned shared records and worker-owned bounded handoffs.
- Measurement of total cost and accepted outcomes, including integration overhead.

HartBeat material was an unrelated reference design. Its stack, permissions, identities and branch-cleanup rules were not destination requirements.

### Later owner instruction deliberately narrowed execution

The saved migration-session transcript contains an explicit owner instruction to:

- Preserve the original checkout and donor.
- Create the separate retained migration worktree.
- First prove the Windows isolation boundary.
- Then implement only packet scope and ownership controls.
- Preserve permanent branches, contracts, scoped context and gated integration.

Later M1–M6 authorization extends that bounded foundation.

Therefore, the broad headless brief and the narrower implementation campaign must both remain visible. Their difference is not evidence that the original product goal was completed or explicitly abandoned.

### Investigation coverage

Inspected the destination’s 26 reachable commit summaries, the donor’s 420 ancestor commit summaries through the pinned revision, and the original goal documents and relevant changes.

This was an original-goals investigation, not a line-by-line audit of all 420 donor commits or all implementation code.

## 3. Original-goal alignment at this checkpoint

| Original requirement | Evidence currently visible | Remaining release question |
|---|---|---|
| Contract-first modular architecture | Original contracts, application layers, shared tests and boundary checker remain | Does the operator-facing workflow preserve these boundaries in representative use? |
| Headless reusable template | Tk application and import dependency remain | Reconcile the original headless requirement with the later foundation’s deliberate preservation of application files |
| Durable continuity | Canonical Journal and migration handoff/evidence records exist | Is ordinary project creation and cross-platform continuation usable without reconstructing migration history? |
| Intake and project generation | No migrated project generator identified in the destination’s tracked scripts | Demonstrate software-only and hardware-oriented generated projects with fresh identity and inactive approval |
| Multiple AI-platform entrypoints | Destination retains CLAUDE.md and manual role prompts; the broader native adapter set was not found | Establish which requested platforms actually have a usable destination workflow |
| Routing, budgets and retries | M3 implementation and evidence exist | Preserve cumulative limits; distinguish offline verification from live provider operation |
| Worker launching and monitoring | Docker scope/runtime and M4 dispatch/report machinery exist | Demonstrate the documented operator lifecycle; live providers remain disabled |
| Independent acceptance | M5 implementation and subsequent M1 acceptance records exist | Preserve exact-candidate binding and separate acceptance from integration/deployment |
| Hardware verification | Packet/domain support and refusal requirements exist | Determine completeness of the original hardware-track migration; physical behavior remains unverified |
| GitHub CI | No tracked .github directory | CI is an explicit original requirement, not merely a newly suggested enhancement |
| Guarded closeout and branch retention | M6 readiness implementation is present but uncommitted | Confirm final verification and delivery; readiness inspection is not automatic promotion |
| Simple setup and daily operation | Historical quickstarts and milestone-specific operations documents exist | Demonstrate one coherent fresh-checkout setup and ordinary task/resume path |
| Lower total accepted-work cost | Bounded-context and economic controls exist | No measured destination savings established in this investigation |

Do not use “the demo app is close” or “M6 is finished” as a substitute for this matrix.

## 4. Current work and release-report corrections to preserve

### Repository state

At inspection:

- Migration branch: feature/workflow-migration.
- Migration HEAD: 34b5a3103b397bab6ae2e490a87a00aba6d118e3.
- Cached origin/main: the same revision.
- Protected original checkout’s local main: f624e207276372d9386b669bf087a66b44aba714.

The differing protected local main is known preserved state. Do not reset or synchronize it as cleanup.

The original checkout’s staged plan deletion and donor’s recorded untracked work must remain untouched.

### M6 is actively in progress

Untracked work includes:

- Handoff and closeout modules and their tests.
- M6 verification and preservation tools.
- Plan, operations, review, provenance, source snapshots, live-fact and development-verification records.

The independent review reports no unresolved in-scope correctness blocker for its specified snapshot, but explicitly requires complete final verification.

At the checkpoint, these files were absent:

- M6_VERIFICATION.json
- M6_FINAL_VERIFICATION.json
- M6_CLOSEOUT.md

The development-verification record explicitly says its counts do not establish final-source verification.

Refresh these facts before reporting status. Another session may complete work after this handoff.

### Approval tests

The release report is preserved here:

RELEASE_REVIEW_2026-10-15T0135Z.md (C:/Users/hensl/Downloads/RELEASE_REVIEW_2026-10-15T0135Z.md)

Its four approval-test failures need qualification:

- The approval tests intentionally exercise an inactive foundation.
- The actual foundation is now ACTIVE.
- tools/check_workflow_approval.py already runs those frozen tests against a disposable inactive projection while preserving the real receipt.
- The documented verification procedure splits ordinary regression from this approval regression.

Do not rewrite the tests to expect ACTIVE or weaken them merely to make an undifferentiated pytest invocation green.

The discoverability of this split and the ordinary fresh-checkout test experience remain legitimate usability questions.

### Frozen foundation

The approval-bound files include:

- CLAUDE.md and PROMPTS.md.
- pyproject.toml.
- Architecture and approval-review documents.
- Approval tooling/tests and preserved packet/domain material.

Consequently, raising the Python requirement or casually rewriting governing instructions is not an isolated documentation fix. First determine the approval implications.

Historical “proposed” or “AWAITING_APPROVAL” prose in frozen documents does not override the actual ACTIVE receipt. Preserve historical documents and explain current status through appropriate current records.

### Application findings

No diff was found between the initial OOP implementation and current committed HEAD for the inspected application code, original contract/UI tests, and boundary checker. The reported application defects appear inherited rather than introduced by M1–M5.

Retain these findings for a separately scoped defect decision:

- Non-finite numeric input.
- Overflow from otherwise finite inputs.
- Empty usernames.
- Tk imports preventing unrelated tests from collecting without tkinter.
- A Python 3.12-only test API despite the declared Python 3.11 minimum.
- Stale onboarding documentation.

Rejecting nan and inf in UI parsing alone would not address finite-input aggregation overflow or direct service callers.

The Python finding demonstrates a test-suite compatibility problem; it does not, by itself, prove the entire application cannot run on 3.11.

No test results from the supplied release report were rerun here. Its counts, platform limitations and skips must remain attributed to that review.

GitHub PR status, live checks, tags and release claims were not independently refreshed during this investigation.

## 5. Exact next-session assignment

Role: read-only original-goals and release-alignment reviewer.

Objective: produce a source-backed account of what the owner originally requested, what later decisions narrowed or superseded, what has been delivered, and what still prevents ordinary use of that intended product.

Proceed as follows:

1. Refresh repository identity, branch, HEAD and worktree status without changing refs or files. Preserve concurrent M6 work.
2. Read the original source trail above before treating recent migration summaries as the complete specification.
3. Read the current approval package, milestone evidence and latest M6 records. Treat frozen acceptance statuses and historical prose as historical where later evidence explicitly supplies current decisions.
4. Build one requirements matrix. For each requirement record:
   - Original source and date.
   - Whether it is an owner requirement, inferred interpretation, proposal, or superseded decision.
   - Current implementation evidence.
   - Verification environment and limitations.
   - Remaining gap and the smallest separately scoped next action.
5. Assess three release boundaries separately:
   - The original worked-example application.
   - The bounded offline workflow foundation.
   - The originally requested reusable headless software/hardware template.
6. Classify gaps as inherited defects, incomplete original requirements, intentionally restricted live capabilities, usability/documentation gaps, or unresolved scope conflicts.
7. Return a detailed handoff and a concise operator-facing assessment. Do not implement a preferred interpretation of unresolved scope.

### Required safeguards

- Read donor content through pinned Git objects; do not alter its checkout.
- Do not delete, rename, reset, force-push or prune branches.
- Do not modify protected checkouts, original evidence, canonical Journals or frozen approval material.
- Do not launch workers, providers, hardware checks or automation.
- Do not perform GitHub writes, publish or merge.
- Do not rerun expensive suites merely to reconstruct already recorded evidence. Identify the exact missing verification first.
- Keep planned, implemented, tested, independently accepted, integrated and deployed claims separate.
- Treat missing usage and unknown costs as unknown.
- Do not turn optional reference-design suggestions into new requirements.
- Do not treat this historical-goals review as authority to remove the UI or expand the current migration.

### Completion criteria

The review is complete when another engineer can answer, with sources:

1. What product was originally requested?
2. Which later owner decisions changed that request or only narrowed an implementation phase?
3. What can a new user actually do from a clean setup today?
4. Which original requirements remain incomplete?
5. Which reported defects are real, state-dependent, or insufficiently verified?
6. What is the smallest next work package that advances the intended product without discarding existing work?

The next deliverable is that reconciliation and handoff—not another implementation layer.