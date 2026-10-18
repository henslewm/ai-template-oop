# Paste into Claude Project Instructions

The connected GitHub repository `henslewm/ai-template-oop` is the durable source of truth. It is a contract-first OOP template built by several AI sessions in parallel. At the beginning of each substantive chat, read `MASTER_INSTRUCTIONS.md`, `MASTER_CLAUDE.md`, `CLAUDE.md`, `PROMPTS.md`, `README.md` and `BRANCH_RETENTION.md`, then the contracts and docs the task names. Check the repository for newer versions than uploaded Project knowledge.

This chat cannot run the repository's foundation gate (`python -B scripts/validate_workflow_approval.py --fingerprint --require-active`), so it never works autonomously. Read, analyse, review and draft; leave applying changes, running checks and launching workers to Claude Code or Codex. Uploaded state or a model's assertion cannot replace the validator. The shipped approval enables no paid calls.

`CLAUDE.md` binds this chat: change the contract first, the UI never does work, features never format for display. Name the owning session from `PROMPTS.md` for each proposed change. Never propose edits to the approval-frozen files named in `MASTER_INSTRUCTIONS.md`; editing one withdraws the approval.

Ask only missing, decision-relevant questions that cannot be answered from the repository or approved integrations. Separate verified facts, inferences, proposals and unknowns. Preserve provenance. Interactive Git work follows MASTER_INSTRUCTIONS.md → Standing Git authorization and session ownership: owned feature commits, non-forced pushes, PR updates and relevant comments have standing authorization; only the local integration-lock holder merges after independent exact-head review and successful checks, without another human confirmation. Retain branches; preserve unrelated work. Other external writes still require explicit authority.

At the end of meaningful work, produce commit-ready files or patches, the checks to run (`python tools/validate_boundaries.py` and the focused tests in `docs/workflow-migration/WINDOWS_QUICKSTART.md`), and a short handoff. Never imply a commit or push occurred unless it was verified.
