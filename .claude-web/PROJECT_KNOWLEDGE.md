# Claude Project Knowledge Setup

Preferred: add the complete repository through Claude's GitHub integration.

When that is unavailable, run `python scripts/web_setup.py --client claude`. It packs exactly the files below into a zip in `.web-setup/` and prints its path; upload the files inside it:

- `MASTER_INSTRUCTIONS.md`
- `MASTER_CLAUDE.md`
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
- `docs/PLATFORM_SUPPORT.md`

Add other source files or `docs/workflow-migration/` records only when the active task needs them. Rerun the script and re-upload after a material change to a listed file. Do not rely on chat-to-chat continuity unless the information is in Project knowledge or the repository.

- `docs/SESSION_COORDINATION.md`
