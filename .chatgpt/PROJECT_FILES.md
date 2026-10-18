# ChatGPT Project Files and Sources

`python scripts/web_setup.py --client chatgpt` packs exactly the numbered files below into a zip in `.web-setup/` and prints its path. Upload the files inside it to the ChatGPT Project:

1. `MASTER_INSTRUCTIONS.md`
2. `MASTER_CHATGPT.md`
3. `CLAUDE.md`
4. `PROMPTS.md`
5. `README.md`
6. `BRANCH_RETENTION.md`
7. `docs/workflow-migration/WINDOWS_QUICKSTART.md`
8. `docs/workflow-migration/LIVE_PILOT.md`
9. `docs/workflow-migration/SOFTWARE_INTAKE.md`
10. `contracts/__init__.py`
11. `contracts/auth.py`
12. `contracts/data.py`
13. `contracts/errors.py`
14. `contracts/operator.py`
15. `docs/PLATFORM_SUPPORT.md`

Then connect GitHub so the chat can verify the latest repository versions.

The contracts are the interfaces every proposed change must respect. Open other source files and the `docs/workflow-migration/` records through GitHub when a task needs them rather than uploading them all. Rerun the script and re-upload after a material change to a listed file.

- `docs/SESSION_COORDINATION.md`
