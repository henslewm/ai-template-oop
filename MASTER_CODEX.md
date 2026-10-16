# MASTER CODEX — Repository Execution Instructions

## Native loading

Codex reads `AGENTS.md`. Treat that file as the startup router and this file as the Codex-specific operating layer. `CLAUDE.md` is not Codex-specific: its session rules bind Codex too.

## Foundation gate

Apply `MASTER_INSTRUCTIONS.md` → "Foundation gate" exactly as stated there; it is deliberately not restated here.

## Execution rules

- Work from the repository root unless a task is explicitly scoped to a subdirectory.
- Inspect `git status`, the active branch, and recent relevant commits before editing.
- Use a short plan for multi-file or high-risk changes.
- Stay inside your session's paths from the `CLAUDE.md` layout table. `tools/validate_boundaries.py` enforces the import rules; if a rule is wrong, change the rule, never work around it.
- Prefer repository tools, scripts and tests over manual repetition.
- Use project subagents under `.codex/agents/` for distinct research, review or implementation work, with non-overlapping scopes and file-specific findings.
- Run the narrowest relevant test first, then `python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md`. Do not run `tests/test_workflow_approval.py` directly.
- Do not modify `.git`, credentials, external systems, or recorded evidence under `docs/workflow-migration/` without explicit authority.
- Use `.codex/config.toml` only after the repository is trusted.

## New projects

Use `tools/project_intake.py` for new project generation: `draft`, then `review`, then `generate` after the review is acknowledged. `docs/workflow-migration/SOFTWARE_INTAKE.md` describes the supported shape.

## Output standard

At completion, report:

1. What changed, including any `contracts/` change.
2. What was validated and the result.
3. Remaining risks or unknowns.
4. Exact files updated.
5. Whether changes were committed or pushed, with the verified commit identifier if applicable.
