## Canonical task and work packet

- Task issue:
- Canonical packet at a specific commit or durable version:
- `task_id` / latest revision / complete contract SHA-256:

## Objective and scope

Describe the outcome, changed paths, and relevant packet scope, exclusions, and architecture boundaries.

## Dependencies and records

Link prerequisite task packets and verified outcomes. Identify workflow or handoff records that need updating; state none where applicable.

## Validation

Record exact commands and results for the reviewed commit. Distinguish executed checks from pending checks.

- [ ] Active foundation validation: `python -B scripts/validate_workflow_approval.py --fingerprint --require-active`
- [ ] Boundary validation: `python -B tools/validate_boundaries.py`
- [ ] Focused non-Docker, non-Tk tests from `docs/workflow-migration/WINDOWS_QUICKSTART.md`
- [ ] Approval regression through `python -B tools/check_workflow_approval.py` (disposable projection only)
- [ ] No secrets or unintended sensitive files added

## Independent review and acceptance

- Reviewer and exact-commit review evidence:
- Unresolved findings or evidence gaps:
- Acceptance decision and evidence, or pending:

Passing checks and opening this PR do not establish acceptance, authorize merge, or imply deployment.

## Risks and next action

- Known limits or rollback concerns:
- Next action and owner:

Feature branches are retained permanently. Do not enable automatic branch deletion, reset, or force-push them.
