# Codex and Vibe Startup Router

This repository is a contract-first OOP template built by several AI sessions in parallel. `CLAUDE.md` holds the binding session rules for every client; this file routes Codex and the Mistral Vibe CLI to them.

## Read before substantive work

Read, in order: `MASTER_INSTRUCTIONS.md`, `MASTER_CODEX.md`, `CLAUDE.md`, `PROMPTS.md`, `README.md` and `BRANCH_RETENTION.md`. Open `docs/workflow-migration/WINDOWS_QUICKSTART.md` before running checks and `docs/workflow-migration/LIVE_PILOT.md` before any operator or worker work.

Then inspect `git status`, the current branch, and the newest relevant commits. Run `.\start.ps1 status` when PowerShell is available; it prints the compact handoff without paid calls.

Before editing, name your session from `PROMPTS.md` (Architect, UI, Feature or Integration). The layout table in `CLAUDE.md` says which paths it owns and what it may import.

A subagent working a bounded brief follows the bounded-subagent exception in the startup protocol of `MASTER_INSTRUCTIONS.md` instead of repeating these reads.

## Foundation gate

Apply `MASTER_INSTRUCTIONS.md` → "Foundation gate" exactly as stated there; it is deliberately not restated here.

## Core behavior

- Treat the repository, not prior chat memory, as the durable state.
- Ask only questions that cannot be answered from the repo or approved connectors and that materially change execution.
- Change `contracts/` first when an interface must change, and say so in your final message.
- Use `tools/project_intake.py` (`draft`, `review`, `generate`) for a new generated project.
- Use `.codex/agents/` for parallel, non-overlapping subagent work.
- Run `python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md` before completing material changes. Never run `tests/test_workflow_approval.py` directly.
- Apply the closeout protocol in `MASTER_INSTRUCTIONS.md`.

## Safety

Do not force-push, delete, rename or reset branches, delete evidence, expose secrets, send external communications, change permissions, or perform consequential external writes without explicit user authority. Do not edit the approval-frozen files named in `MASTER_INSTRUCTIONS.md`; editing one withdraws the ACTIVE approval. The shipped receipt sets every API budget to USD 0: a paid worker run needs the separate pilot activation in `docs/workflow-migration/LIVE_PILOT.md`.

## Review guidelines

- Report only findings that pass the actionable test in `MASTER_INSTRUCTIONS.md` → "Review findings and merge discipline": a concrete defect, with the input that triggers it. No improvements, hardening, refactors or style.
- Approval-frozen files take no edits; report a defect in one as an issue rather than a patch.
