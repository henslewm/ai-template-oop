# MASTER CLAUDE CODE — Repository Execution Instructions

## Native loading

Claude Code loads `CLAUDE.md` automatically. That file is approval-frozen and imports nothing, so Claude Code does not load this file or `MASTER_INSTRUCTIONS.md` on its own. Read both at session start, or name them in the first prompt.

## Foundation gate

Apply `MASTER_INSTRUCTIONS.md` → "Foundation gate" exactly as stated there; it is deliberately not restated here.

## Sessions and delegation

`PROMPTS.md` defines the roles. The Architect session owns `contracts/` and the contract tests; it decides interfaces and delegates the rest:

| Session (`PROMPTS.md`) | Owns | Delegate |
|---|---|---|
| Session 0: Architect | `contracts/` | interface changes and contract tests; never implementations |
| Session A: UI | none (template is headless) | no UI layer ships; `src/testing/fakes.py` is kept contract-complete by whoever changes a contract (see `docs/workflow-migration/HEADLESS_TEMPLATE.md`) |
| Session B, C, ...: Feature | `src/features/` | one ABC implementation per brief, registered in `tests/conftest.py` |
| Session D: Integration | `src/container/` | wiring in `src/container/wiring.py` |

Rules: every brief names its session, owned paths, acceptance checks, the facts it depends on, and the attempt limit (default 2). Run non-overlapping briefs in parallel and consolidate once. A subagent inherits `CLAUDE.md`, so the brief carries only what that does not. The delegating session verifies each result rather than trusting it, and on failure re-briefs at most once before handling it itself. User-reserved and consequential external actions are never delegated.

## Execution rules

- Start Claude Code at the repository root so `CLAUDE.md` loads.
- Inspect the branch, working tree, and recent relevant commits before edits.
- Use plan mode for multi-file, destructive, security, migration, or contract changes.
- Never read ignored secret files or weaken permission rules to bypass a task.
- Validate actual behavior, not merely syntax: `python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md`. Do not run `tests/test_workflow_approval.py` directly.
- Preserve recorded evidence under `docs/workflow-migration/`; never refresh a baseline to make a check pass.

## Review findings before merge

Apply `MASTER_INSTRUCTIONS.md` → "Review findings and merge discipline" exactly as stated; it is the single definition and is not restated here. Read reviews and comments with `gh api` on the pull request (`.../pulls/<n>/reviews` and `.../pulls/<n>/comments`), never from email.

## Closeout

Apply the closeout protocol in `MASTER_INSTRUCTIONS.md` and state exactly whether a commit or push succeeded. Keep the `.\start.ps1 status` summary in the pull request or final message so ChatGPT, Codex, or Claude web can continue immediately.
