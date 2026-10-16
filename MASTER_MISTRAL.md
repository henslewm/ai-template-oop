# MASTER MISTRAL — Vibe (Le Chat) Project Instructions

## Role

Use Mistral Vibe (formerly Le Chat) for synthesis, research, drafting, and review. The GitHub repository is the durable project record.

## Project setup

- Run `python scripts/web_setup.py --client mistral` from the repository root. It writes an upload zip into `.web-setup/` (and prints its path) with the files listed in `.mistral/PROJECT_KNOWLEDGE.md` and copies `.mistral/PROJECT_INSTRUCTIONS.md` to your clipboard (or names the file to paste from).
- In Vibe's **Work** mode, create a dedicated Project for this repository. A chat belongs to exactly one Project, so keep this repository's work inside it.
- Paste the instructions into the Project's custom instructions.
- Connect the **GitHub App** connector so chats can read the repository directly. If it cannot be connected, upload the files inside the zip to the Project or an attached Library.
- Keep durable rules in this repository: account-wide custom instructions apply only to new tasks and are overridden by active Skills.

## Vibe CLI

The Vibe command-line tool reads `.vibe/config.toml` (project level, over `~/.vibe/config.toml`) and the repository's `AGENTS.md` from trusted folders, so it follows the same startup protocol and foundation gate as Codex. The shipped config keeps the `default` agent and asks before running `bash`. Widening it (for example `accept-edits` or `auto-approve`) is the user's decision. Settings reference: https://docs.mistral.ai/vibe/code/cli/configuration

## Startup

Read `CLAUDE.md`, `PROMPTS.md`, `README.md`, `BRANCH_RETENTION.md` and this file before substantive work, then the contracts and docs the task names, through the GitHub connector when available. Prefer the newest repository versions over files uploaded to the Project or a Library.

## Foundation gate

Vibe in the browser has no runtime that can run `python -B scripts/validate_workflow_approval.py --fingerprint --require-active`, so it never proceeds autonomously: read, analyse, and draft only. The Vibe CLI applies the gate through `AGENTS.md`.

## Work and closeout

Apply `MASTER_INSTRUCTIONS.md`. Keep to the `CLAUDE.md` layout and propose `contracts/` changes first. Default connectors to read-only; the GitHub App connector can search repositories, review issues, and manage pull requests, but use write actions only on the user's explicit current instruction, and never merge or delete a branch. At the end of meaningful work, produce commit-ready changes, the checks a repository client must run, and a short handoff. Never imply a commit or push occurred unless it was verified.

## Notes

- Memories (legacy Chat mode) are convenience context only; the repository, not Memories, is the cross-session source of truth.
- MCP connectors are added by a workspace admin; on personal plans the account owner is the admin by default.
