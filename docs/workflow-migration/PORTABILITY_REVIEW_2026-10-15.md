# Portability review — 2026-10-15

Lane: Claude (intake/generation, fresh project identity, activation handling, headless cleanup).
Reviewed at `feature/workflow-migration` HEAD `63b9e5f`. Read-only: no files, Git state, workers or
regression suites were changed or run. Donor read through Git objects at pinned `d6e582b`.

Companion lane (platform instructions and onboarding) is reviewed separately; the main thread
reconciles both into one backlog.

## Stale-fact correction

`ORIGINAL_GOALS_HANDOFF.md` §4 is out of date: HEAD is `63b9e5f`, not `34b5a31`, and
`M6_VERIFICATION.json` and `M6_CLOSEOUT.md` both exist. Don't reopen M6 completion as a gap from
that document.

## Bottom line

The destination can't create a new project. Its approval receipt is committed as `ACTIVE` and is
tied to this repository by name only, not to the actual checkout, so a clone or copy arrives already
approved — the opposite of the original requirement that a generated project starts unapproved.

## Findings

| # | Original requirement | Current evidence (file:line) | Remaining gap | Type / class | Smallest next action |
|---|---|---|---|---|---|
| 1 | Project intake and generation (headless brief, capability 2) | Destination has no generator, intake schema, charter or interactive gate. Donor has `scripts/bootstrap_project.py`, `bootstrap_gate.py`, `validate_bootstrap.py`, `prompts/BOOTSTRAP_NEW_PROJECT.md`, `.ai-project-template` marker. `bootstrap_project.py` isn't in the approved source closure (`scripts/validate_workflow_approval.py:33-46`). `config/pilot-onboarding.json:9` names "General project generation" a non-goal. | Not implemented; porting is outside the current approval scope. | Missing implementation · unresolved scope conflict | Owner decides whether generation joins the foundation. If yes, a new approval package adds `bootstrap_project.py` and the gate as "adapt" files. Don't port before that decision. |
| 2 | A new project gets its own identity | Approval package requires repository `ai-template-oop`, branch `feature/workflow-migration` and the fixed base commit (`scripts/validate_workflow_approval.py:253-254`). `scripts/pilot_authority.py:147-151,165-171` and `scripts/workflow_closeout.py:27,162` require remote `henslewm/ai-template-oop`. `pyproject.toml:2` and `src/ui/main_window.py:51` carry the template name. Local state is per checkout (`scripts/workflow_runtime.py:121-142`, keyed on the Git common dir), so that layer is fine. | Identity is fixed in the approval and closeout layers. A new project can't hold a valid receipt or closeout target. Donor replacements (slug, `config/project.json`, `template_mode`) are absent. | Missing implementation · incomplete original requirement | Define one per-project identity record read by the approval package, `pilot_authority` and `workflow_closeout` instead of constants. All involved files are approval-bound, so this needs a new foundation fingerprint. |
| 3 | A new project starts unapproved | `config/workflow-bootstrap.json:3-10` committed as `ACTIVE` (first commit `3fba574`, already ACTIVE). `active_anchor` (`scripts/workflow_state.py:168-172`) checks only the fingerprint over file contents and fixed strings, not the real remote, HEAD or checkout. The baseline check is off in this path and can no longer pass (`scripts/validate_workflow_approval.py:256-259` requires HEAD == fixed base). Donor excludes `bootstrap.json` and `BOOTSTRAP_REVIEW.md` from copies (`bootstrap_project.py:25-29`) and refuses re-bootstrap. | A clone, fork or copy inherits ACTIVE; approval isn't tied to the project it was given to. | Missing implementation · incomplete original requirement | Tie the receipt to the checkout (e.g. the identity from #2, checked in `check_receipt`). A generator then writes `AWAITING_APPROVAL` and never copies the receipt. Approval-bound; owner decision. |
| 4 | Explicit owner activation | `tools/prepare_workflow_approval.py:18,69,141` only writes `AWAITING_APPROVAL` and refuses to overwrite an approved one. No tracked tool moves a foundation to `ACTIVE`; `check_receipt` (`scripts/validate_workflow_approval.py:157-179`) only validates; `approved_by` is free text. `tools/pilot_admin.py:17-35,103` `activate` is a separate pilot mechanism needing a merged PR on `henslewm/ai-template-oop`. Donor has interactive `bootstrap_gate.py activate` (identity plus typed `APPROVE <fingerprint>`, lines 179-191). | Nothing in the repo performs or records foundation activation; a new project would need hand-edited JSON. Pilot activation works only for this repository. | Missing implementation (foundation) · missing verification (origin of current receipt unrecorded) | Add a foundation `activate` command modeled on the donor gate (identity, typed decision, UTC timestamp). Separately, record where the current receipt came from. |
| 5 | Set up from a fresh checkout (activation path) | Default `active_anchor` needs no sibling checkouts. `--check-source` / `--check-preserved` need `../universal-ai-project-template` and `../ai-template-oop` (`scripts/validate_workflow_approval.py:315,333-337`); `tools/prepare_workflow_approval.py:19` needs the donor alongside. Hashes normalize line endings (`:93-95`), so `autocrlf=true` doesn't break them. | A lone fresh clone can pass the activation check but can't run deep verification or regenerate a package. Fresh-clone activation not yet demonstrated. | Missing verification (pass path) · usability gap (sibling dependency) | In a disposable clone with no siblings, run `python scripts/validate_workflow_approval.py --require-active` and record the result. Document that deep checks need the sibling checkouts. |
| 6 | Operator can start their own project's work | `scripts/pilot_controller.py:145-148` rejects any objective except `pilot_authority.OBJECTIVE`. Write paths fixed to 4 files (`scripts/pilot_authority.py:14-19`); project fixed to `live-pilot-2026-10`. | A project made from this template couldn't run its own objective through `start.ps1`. | Intentionally restricted live capability · flagged for portability | No code change. Record that a general per-project objective and scope path needs a new authority package. Keep the pilot preset. |
| 7 | Hardware and software-only generation | Destination has packet/domain validation (`scripts/software_hardware.py`, `config/domains/software-hardware.schema.json`) but no hardware intake question or software-only option (donor: `--no-hardware`, `apply_no_hardware`). `templates/software-hardware/PROFILE.md` is referenced at `software-hardware.schema.json:4,67` but exists only in the donor. | Profile choice depends on #1. PROFILE.md link is broken documentation, not a runtime failure. | Missing implementation (depends on #1) · usability gap (dangling link) | Import `templates/software-hardware/PROFILE.md` byte-for-byte (and `MODULES.md` if wanted), or reword the schema descriptions. Check first whether the schema is in the approval baseline. |
| 8 | Headless template ("Drop the UI") | Partly done: `src/ui/__init__.py` loads Tk lazily; `tests/test_headless_imports.py` proves non-UI tests collect and pass without Tk, but ignores `tests/test_ui.py`. `tests/test_ui.py:9` imports Tk unconditionally, so plain `pytest` without Tk still fails collection. `main.py` launches the Tk app; `README.md:39-42` calls it a separate demo. | Original says drop the UI; the foundation deliberately kept `src/ui`, `main.py`, `tests/test_ui.py` as a worked example. Collection failure is a real inherited defect. | Unresolved scope conflict (removal) · inherited defect (collection) | (a) Owner records whether the UI stays as an example or moves out; don't remove it meanwhile. (b) Make `tests/test_ui.py` skip when Tk is missing — check whether it's in the approval baseline first. |
| 9 | Python version consistency on fresh setup | `pyproject.toml:5` says `>=3.11`; `start.ps1:16,38` and `scripts/workflow_state.py:160` require 3.12+. | Declared minimum is wrong for the workflow. `pyproject.toml` is approval-bound (`scripts/validate_workflow_approval.py:47-52`). | Inherited defect · usability gap | Fold into the next approval package; editing now invalidates the ACTIVE fingerprint. |

**Approval-bound files:** rows 2, 3, 4, 8b and 9 touch files that feed the ACTIVE fingerprint
(`CLAUDE.md`, `PROMPTS.md`, `pyproject.toml`, `scripts/validate_workflow_approval.py`, the receipt) or
possibly the baseline list. Bundle them into one new approval package rather than piecemeal edits.

**Other lane:** there is no `.github/` directory. CI is an original requirement but belongs to the
platform/onboarding review.

## Suggested order

1. Owner decisions (no code): generation in scope (#1), the UI's future (#8a), when to open a new
   approval package (#2–#4, #9).
2. Verification only, runnable now: fresh-clone activation check with no siblings (#5); record the
   origin of the current ACTIVE receipt (#4).
3. First code package once approved: per-project identity record, receipt tied to the checkout,
   foundation `activate` command (#2–#4); then the generator port (#1, #7).
