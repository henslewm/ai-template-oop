# MASTER CLAUDE — Claude Web Project Instructions

## Role

Use Claude web for synthesis, research, drafting, review, and long-context analysis. The GitHub repository is the durable project record.

## Project setup

- Run `python scripts/web_setup.py --client claude` from the repository root. It writes an upload zip into `.web-setup/` (and prints its path) with the files listed in `.claude-web/PROJECT_KNOWLEDGE.md` and copies `.claude-web/PROJECT_INSTRUCTIONS.md` to your clipboard (or names the file to paste from).
- Paste the instructions into the Project instructions field.
- Add the repository through Claude's GitHub integration when available; otherwise upload the files inside the zip as project knowledge.
- Do not assume one chat's context is available in another unless the information is in project knowledge or the repository.

## Startup

Read `CLAUDE.md`, `PROMPTS.md`, `README.md`, `BRANCH_RETENTION.md` and this file before substantive work, then the contracts and docs the task names. Check the repository for newer versions than any uploaded copies.

## Foundation gate

Claude web has no runtime that can run `python -B scripts/validate_workflow_approval.py --fingerprint --require-active` against the repository, so it never proceeds autonomously. Read, analyse, and draft within existing permissions; leave applying changes, running checks and launching workers to Claude Code or Codex. Uploaded state or a model's assertion cannot replace the validator.

## Work and closeout

Apply `MASTER_INSTRUCTIONS.md`. Keep to the `CLAUDE.md` layout, name the owning session for every proposed change, and propose `contracts/` changes first. Never propose edits to approval-frozen files. When the integration is read-only, produce exact commit-ready files or patches, the checks to run, and a concise handoff.
