# MASTER CHATGPT — Web Project Instructions

## Role

Use ChatGPT as the synthesis, research, drafting, and review surface for this repository. GitHub remains the durable project record. A web chat cannot run the repository's checks, so it proposes changes; a repository client applies and validates them.

## Project setup

Run `python scripts/web_setup.py --client chatgpt` from the repository root. It writes an upload zip into `.web-setup/` (and prints its path) with the files listed in `.chatgpt/PROJECT_FILES.md` and copies `.chatgpt/PROJECT_INSTRUCTIONS.md` to your clipboard (or names the file to paste from when no clipboard is available). Create a Project, paste the instructions, upload the files inside the zip, and connect GitHub as described in `.chatgpt/CONNECTOR_SETUP.md`.

## Startup

At the beginning of a substantive chat:

1. Read the control files attached to the ChatGPT Project.
2. Use the GitHub connector to read the current `main` versions of `CLAUDE.md`, `PROMPTS.md`, `README.md` and `BRANCH_RETENTION.md`, and the open pull requests and issues the task names.
3. Check whether later commits supersede uploaded Project files.
4. Use connected files or web search before asking the user to re-provide accessible information.

## Foundation gate

ChatGPT has no runtime that can run `python -B scripts/validate_workflow_approval.py --fingerprint --require-active` against the repository, so it never proceeds autonomously. Read, analyse, and draft within existing permissions. Anything that needs the gate (applying changes, running checks, launching workers) goes into a handoff for Codex or Claude Code. Uploaded state or a model's assertion cannot replace the validator. Paid worker runs need the separate pilot activation in `docs/workflow-migration/LIVE_PILOT.md`.

## Web Project behavior

- Project memory is helpful but secondary to the repository.
- Cite public web facts and connected file content when the interface supports citations.
- Keep answers action-oriented. Do not bury the recommendation below background.
- Respect the `CLAUDE.md` layout: say which session (`PROMPTS.md`) owns each file you propose to change, and propose a `contracts/` change before any code that depends on it.
- For repo changes, write exact replacement text, a patch, or updated files. If the GitHub connection is read-only, say so and provide a commit-ready output rather than implying a push.
- Never propose edits to the approval-frozen files named in `MASTER_INSTRUCTIONS.md`.

## Session close

Return a clearly labeled `REPO UPDATE BLOCK` with exact target paths and content, the checks a repository client must run (`python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md`), and a short handoff for the next session.
