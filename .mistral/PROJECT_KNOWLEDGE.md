# Mistral Vibe Project Knowledge Setup

Preferred: connect the **GitHub App** connector and let chats read the repository directly.

When that is unavailable, run `python scripts/web_setup.py --client mistral`. It packs exactly the files below into a zip in `.web-setup/` and prints its path; upload the files inside it to the Project (or a Library attached to it):

- `MASTER_INSTRUCTIONS.md`
- `MASTER_MISTRAL.md`
- `AGENTS.md`
- `CLAUDE.md`
- `PROMPTS.md`
- `README.md`
- `BRANCH_RETENTION.md`
- `docs/workflow-migration/WINDOWS_QUICKSTART.md`
- `docs/workflow-migration/LIVE_PILOT.md`
- `docs/workflow-migration/SOFTWARE_INTAKE.md`
- `contracts/__init__.py`
- `contracts/auth.py`
- `contracts/data.py`
- `contracts/errors.py`
- `contracts/operator.py`

`AGENTS.md` is included because the Vibe CLI reads it; a chat should know what the CLI session will follow. Libraries accept Markdown, code, PDF, and Office files (up to 100 files per upload, 100 MB per file). Re-upload changed files after material repository updates, or rely on the GitHub connector so chats never read stale copies. Do not rely on chat-to-chat continuity or Memories: if it matters, it belongs in the repository.
