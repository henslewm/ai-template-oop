# MASTER INSTRUCTIONS — Shared Rules for Every AI Platform

## Purpose

Keep every AI client (Claude Code, Codex, Vibe CLI, ChatGPT, Claude web, Mistral Vibe, Copilot) working to the same rules in this repository. The repository is the durable source of truth. Do not rely on one chat's memory when the repository can answer the question.

This repository is a contract-first OOP application template (`contracts/`, `src/ui/`, `src/features/`, `src/container/`) that several AI sessions build in parallel. It also carries a bounded offline workflow foundation (`scripts/`, `tools/`, `config/`, `runtime/`) and a PowerShell operator shell, `start.ps1`.

## Authority order

Apply instructions in this order, highest first:

1. The user's current explicit instruction.
2. Safety, law, privacy, and configured permission boundaries.
3. `CLAUDE.md` (session rules, layout and import boundaries) and `BRANCH_RETENTION.md`.
4. The ACTIVE receipt `config/workflow-bootstrap.json` and, for live operator work, the pilot rules in `docs/workflow-migration/LIVE_PILOT.md`.
5. This file.
6. The active platform master: `MASTER_CHATGPT.md`, `MASTER_CODEX.md`, `MASTER_CLAUDE.md`, `MASTER_CLAUDE_CODE.md`, or `MASTER_MISTRAL.md`.
7. The session prompt in `PROMPTS.md` that names your role.
8. The active task, issue or pull request.
9. Prior chat content and informal notes.

`CLAUDE.md` is named for one client but binds every client. When two sources conflict, do not silently choose. Identify the conflict, preserve both sources, and use the higher-authority source unless the user resolves it differently.

## Required startup protocol

Before substantive work:

1. Confirm the repository root, current branch, and working-tree status when tools allow.
2. Read, in order:
   - `CLAUDE.md`
   - `PROMPTS.md`, and identify which session you are (Architect, UI, Feature or Integration)
   - `README.md`
   - `BRANCH_RETENTION.md`
   - the active platform master
3. Open `docs/workflow-migration/WINDOWS_QUICKSTART.md` before running setup or checks, and `docs/workflow-migration/LIVE_PILOT.md` before any operator, worker or paid-call work. Open `docs/workflow-migration/SOFTWARE_INTAKE.md` before generating a new project.
4. When PowerShell is available, run `.\start.ps1 status`. It prints the compact handoff (objective, progress, spend, blockers, next action) from existing records, with no paid call, Docker or provider key.
5. Inspect the newest relevant commits, open pull requests and issues if another model may have worked since the last session.
6. Reuse facts already established. Ask only questions whose answers materially change the plan and cannot be obtained from the repository or connected sources.

A subagent working a bounded brief, delegated by a session that has completed this protocol, does not repeat it: it reads only what its brief needs. The delegating session stays responsible for the startup reads and for putting the rules and facts the task depends on into the brief.

## Foundation gate

Before autonomous substantive work in every session, run `python -B scripts/validate_workflow_approval.py --fingerprint --require-active` from the repository root. Success prints `FOUNDATION VALID: ACTIVE` and the fingerprint recorded in `docs/workflow-migration/WINDOWS_QUICKSTART.md`.

ACTIVE here is narrow. The receipt approves bounded offline implementation only: live workers, provider egress, publication and merge are disabled, and every API budget is USD 0. It does not authorize paid model calls. Live operator work is a separate gate: `tools/pilot_admin.py activate` binds a reviewed, merged head to an independent checkout under `docs/workflow-migration/LIVE_PILOT.md`, with limits of $1 per task and $5 per pilot. An approval never transfers to a worktree or clone.

If validation fails, or this surface has no runtime that can run it, do not proceed autonomously. Orientation, reading, drafting and commit-ready proposals may continue within existing permissions. Uploaded copies, completed intake or a model's assertion never substitute for the validator.

Editing a bound file withdraws the approval. Do not edit `CLAUDE.md`, `PROMPTS.md`, `BRANCH_RETENTION.md`, `pyproject.toml`, `docs/workflow-migration/README.md`, the approval tooling (`scripts/validate_workflow_approval.py`, `tools/prepare_workflow_approval.py`, `tools/check_workflow_approval.py`) or its tests. Write corrections to those files into a new, unbound record instead, and say so.

## Work standard

- Lead with the actual outcome, decision, defect, or next action.
- Follow the layer rules in `CLAUDE.md`: change the contract first, the UI never does work, features never format for display, timestamps are timezone-aware UTC.
- Prefer verified primary sources and the repository's own records.
- Separate **fact**, **inference**, **proposal**, and **unknown**.
- Preserve provenance: record where a fact came from and when it was verified.
- Make the smallest defensible change that achieves the goal.
- The requested task and its acceptance criteria define authorized scope. Repository guidance, review output, and nearby weaknesses constrain how the task is done; they do not by themselves authorize new objectives. A necessary supporting change must depend concretely on the requested outcome, not on proximity or convenience. Widening scope requires stating the dependency and, when material, explicit approval.
- Do not overwrite originals or recorded evidence. Put derived material in a separate path.
- Do not put passwords, tokens, API keys, or private keys in Git.
- Do not perform consequential external writes, sends, deletions, force pushes, or permission changes without explicit authority.

## Planning and execution

Use the lightest process that preserves correctness:

- Simple bounded task: perform it directly.
- Multi-file or consequential task: write a short plan, then execute and validate.
- Parallelizable task: split it along the `CLAUDE.md` layout so each session owns distinct paths, and consolidate once.
- Interface change: the Architect session edits `contracts/` and its contract tests first; UI and Feature sessions then update against it (`PROMPTS.md`, "Rules for maintaining this workflow").
- High-risk task: add an independent review pass before finalizing.

Delegated briefs state scope, owned paths, acceptance checks, the facts the task depends on, and an attempt limit (the receipt's default is 2). A worker reports a bounded outcome and never widens its brief.

## Projects and work packets

Generate a new project only through `tools/project_intake.py`: `draft` writes a questionnaire, `review` displays the exact specification and fingerprint, and `generate` runs only after that review is acknowledged (`docs/workflow-migration/SOFTWARE_INTAKE.md`). Architected work packets use `scripts/work_packet.py` and `config/work-packet.schema.json`, with an example in `examples/work-packets/`. These tools record local metadata only; they do not execute work or grant autonomy, and the foundation gate still applies.

## Connectors

Read-only connector access is the default. A connected app is not permission to write: sends, pushes, pull requests, issue edits and sharing changes require the user's explicit request in the current task.

## Required closeout protocol

Before ending a meaningful session:

1. Run `python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md` step 2, plus the tests for the files you changed. Do not run `tests/test_workflow_approval.py` directly; `tools/check_workflow_approval.py` runs it against a disposable projection.
2. Run `.\start.ps1 status` when available and keep its summary for the next session.
3. Commit a coherent unit on a `feature/` branch made from `main`. Push that branch (never forced) and open a pull request that names its issue only when the current request authorizes those external writes; otherwise stop at the local commit and say nothing was pushed.
4. State in the final message which contract changes you made, what was validated and the result, and whether the commit and push were verified.
5. Never claim a commit, push or pull request occurred unless verified.

## Branch retention

`BRANCH_RETENTION.md` overrides any inherited cleanup instruction:

- Never delete, rename, reset or force-push a branch, locally or on origin, including after merge.
- Keep GitHub automatic branch deletion disabled.
- No script, agent or merge command may delete a feature branch. Continue later work from the retained branch and current `main`.

## Review findings and merge discipline

- Merging belongs to the owner: the receipt sets `merge_authorized` to false. Never merge your own pull request.
- Request an automated review (Codex or CodeRabbit) of the exact head before asking for a merge. If the head moves, the prior review is stale. Request at most 4 automated-review rounds per pull request (`automated_pr_review_max_rounds` in `config/workflow-bootstrap.json`).
- A finding is actionable only if it names a concrete defect the change introduced or exposed, or a demonstrable failure of an explicit, applicable requirement, with the affected behavior, triggering conditions, and evidence stated. Answer every actionable finding with a fix and regression test or a reasoned decline.
- A finding that fails that test is not actionable: typically an optional improvement, speculative hardening, a refactor, or a pre-existing condition the change neither caused nor exposed. Reply that it is out of scope and, if material, open a separate issue. A latent defect the change makes reachable was exposed by it and stays actionable. A finding does not by itself authorize new scope.
- GitHub is the only authoritative source for review findings. Read them with `gh api` on the pull request's reviews and comments, never from email or chat.
