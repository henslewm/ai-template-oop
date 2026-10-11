# Permanent feature-branch retention

Owner direction, 2026-10-11: never delete feature branches.

- Keep feature branches locally and on origin, including after pull-request merge.
- Keep GitHub automatic branch deletion disabled.
- No closeout script, agent, CI workflow, or merge command may delete a feature branch.
- Existing branch names must not be overwritten, renamed, or replaced with archive aliases as cleanup.
- For further work, inspect the retained branch and current main, preserve uncommitted work, and integrate changes deliberately. Do not force-push or reset the retained branch.
- Branch recovery from a recorded PR head preserves that commit; it cannot prove recovery of later unrecorded work.
- This applies to the pending migration: donor auto-closeout branch deletion must not be imported.

Current check: GitHub reports delete_branch_on_merge=false. No deletion setting was changed by this policy addition.
