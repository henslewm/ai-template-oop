# Reusable OOP template — central implementation backlog

Updated 2026-10-16. This is the current backlog; audit tables and milestone
documents remain dated evidence. Do not maintain competing implementation lists.

Sources: the October 10 headless migration brief in the owner's migration ZIP;
`ORIGINAL_GOALS_HANDOFF.md` (historical); `PORTABILITY_REVIEW_2026-10-15.md`;
[Mistral audit #18](https://github.com/henslewm/ai-template-oop/issues/18);
`LIVE_PILOT.md`; and the main-thread reconciliation in this conversation.

The product is a reusable contract-first OOP template, not a workflow controller
demo. Preserve typed ABCs, injection through a composition root, shared real/fake
behavior tests, presentation-only shells and scoped worker context. Existing
application behavior and the working Pro-Se Engine are outside these packages.

## Execution policy

- One implementation owner per package and branch/workspace. An independent
  reviewer evaluates the exact candidate separately; tests do not accept it.
- Finish one concrete deliverable with relevant checks and a concise handoff.
  Reopen audits only for a specific contradiction or failure.
- Add infrastructure only when the next runnable flow needs it. Preserve
  existing controllers, cumulative budgets/attempts and permanent branches.
- Keep implemented, verified, independently accepted, integrated and deployed
  states distinct. No approval here authorizes paid calls, publication or merge.

## Ordered packages

| ID | Requirement / deliverable | Current status and smallest next action | Owner / dependency |
| --- | --- | --- | --- |
| B01 | Portable identity and offline project approval | Initial implementation merged in PR #20. Late automated findings prompted narrow binary-hashing, damaged-status and interrupted-initialization corrections; see `PROJECT_IDENTITY_FIX_REVIEW.json`, `PROJECT_IDENTITY.md`, the handoff and Git history for exact acceptance/delivery evidence. Historical foundation receipt and narrow live pilot stay separate. B02 and the supported intake build on it. | Codex, sole implementation owner; separate read-only source reviewers. |
| **B02 — built** | **One runnable generated OOP software project** | Merged in PR #23 (`4f134b8`). Generator, explicit manifest and headless assets implemented; actual memory/SQLite example runs in its own isolated venv. Generator checks: 18 passed; generated real/mock suite: 53 passed. Fresh UUID and unapproved lifecycle verified. See `GENERATED_OOP_EXAMPLE.md` for commands, evidence and scoped independent acceptance. General intake and hardware output remain separate. | Codex, sole implementation owner; consumes merged B01. Independent reviewer approved exact source/artifact evidence in `GENERATED_OOP_EXAMPLE_REVIEW.json`; Git history and the delivery pull request record integration. |
| **B14 � independently accepted** | **Requirements intake for the supported headless Python shape** | Closed specification, architecture review/fingerprint and explicit acknowledgment precede generation. User-specified outcomes run against memory and SQLite; unresolved questions and unsupported features hold generation. 47 focused checks and the generated 57-test suite passed; independent review accepted all 45 outputs without findings. See `SOFTWARE_INTAKE.md` and `SOFTWARE_INTAKE_REVIEW.json`. Arbitrary domains/code synthesis remain future profiles. | Codex, sole implementation owner; B01/B02. Independent exact-source/artifact acceptance recorded; Git history and delivery pull request establish integration. |
| B03 | Headless reusable template | Owner decision 2026-10-17 on #28: keep the Tk GUI as an optional example. `tests/test_ui.py` skips when Tk is missing, so plain `pytest` collects without Tk. Removal was tried in PR #33 and closed unmerged. Headless output comes from the generator (B02/B14). | Decided; no removal package. |
| B04 | Required AI-platform adapters | Claude Code/manual prompts exist; Codex, ChatGPT Projects, Claude web, Mistral/Vibe and Copilot adapters are missing. Adapt thin entrypoints from common destination rules, including needed web export/setup. These platforms are already named in the original brief. | One owner; use B02's real generated layout and lifecycle. |
| B05 | GitHub validation CI | No tracked `.github` workflow. Add validation-only CI covering applicable OOP/controller tests, required setup and the separate frozen approval projection. Configured checks are not proof of hosting enforcement. | One owner; derive commands from the demonstrated B02 flow. |
| B06 | Coherent setup and operator instructions | Independent clean-clone offline proof already exists. Remaining gaps include image acquisition, named key/`gh` prerequisites, Python metadata versus Windows 3.12 requirements, safe test commands and current-status routing. Do not rewrite frozen historical documents as current facts. | One owner; fix only prerequisites needed by the selected runnable flow first. |
| B07 | Hardware-oriented generation and evidence | Evidence ladder/schema and refusal rules exist; profile/module index/PlatformIO materials and complete hardware intake remain incomplete. Add a generated hardware-oriented project after software generation is concrete. Simulation must not claim physical verification. | One owner; B02, then relevant donor profile reuse. |
| B08 | Durable project governance and continuity | Journal, handoffs, export and recovery exist. B14 adds a requirements snapshot, review acknowledgment and scoped project handoff. Add remaining ordinary charter/state/decisions/sources/risks/open loops only through a concrete intake need, with coordinator-owned updates and no competing ledger. | One owner; B02 identifies the minimum required records. |
| B09 | General task routing and worker lifecycle | Offline controllers are delivered; paid pilot remains one fixed objective/four files. Retain limits and unknown-cost holds. Generalize only for a named project task that needs it; provide runtime acquisition before claiming new-machine worker usability. | One owner; a concrete scoped task and its own authority package. |
| B10 | General guarded closeout and issue mirroring | M6 readiness and narrow pilot delivery exist. Project-neutral targeting and open-loop mirroring remain incomplete. Preserve exact-candidate review, validation and branch retention. | One owner; project identity and a demonstrated integration candidate. |
| B11 | Reusable architecture enforcement | Preserve existing layer checks and isolation. Extend sibling/transitive and shell checks only against actual generated boundaries, with negative fixtures. Static import checks are not filesystem isolation. | One owner; B02. |
| B12 | Accepted-result cost evidence | Accounting fields exist; comparative savings are unmeasured. Measure matched accepted tasks including reviewer/integration overhead, failed attempts and unknown usage. Do not restart deferred broad telemetry work. | One owner when representative tasks exist. |
| B13 | Retained demo defects | Numeric/non-finite/overflow and username behavior, intermittent Tk issues and historical typing diagnostics require separately scoped decisions. They do not justify rebuilding the workflow or changing Pro-Se Engine. | Separate application owner/package if the retained sample needs those changes. |

## B02 acceptance packet

The deliverable is a generated project someone can run, not another architecture
plan or a generalized orchestrator. Keep the first invocation deterministic and
software-only; hardware output follows as B07.

Expected owned paths are the small generator/intake entrypoint, its explicit
copy/template manifest, headless sample assets, focused generation tests and a
short generated-project quickstart. Name exact paths before editing; preserve
root application files, contracts and frozen approval material. Do not launch
an additional implementation owner on those paths.

Acceptance requires:

1. Generation refuses a non-empty destination and produces a fresh project
   identity with no copied host approval, runtime state, keys or historical
   ACTIVE receipt. Two outputs have distinct project UUIDs.
2. The generated project has a thin CLI calling typed interfaces, business
   logic in features and dependencies assembled in a composition root. Retain
   backend behavior and use the same behavioral assertions for real and fake
   implementations.
3. A documented command runs the sample from its own directory; its shared
   behavior tests and relevant boundary checks pass without Tk. No model call,
   hardware connection or unrelated application dependency is required.
4. Any worker sees only the named generator/sample inputs and owned outputs;
   the reviewer receives the exact generated candidate and independent logs.
   Reviewer approval remains separate from successful tests and integration.
5. The handoff records exact source/output identities, commands, results and
   remaining limits. Infrastructure additions must name the acceptance step
   that requires them.

## Reconciled audit claims

M6 is completed; its old in-progress handoff is stale. Foundation receipt
provenance is recorded in `SESSION_HANDOFF_2026-10-13.md`. Independent-clone
setup/ACTIVE validation and an offline Docker lifecycle proof already exist in
`WINDOWS_QUICKSTART_VERIFICATION.md`. Broad campaign reruns are not a next task.

The legacy ACTIVE receipt validates in a tracked export, but that does not
activate an initialized project's new gate or transfer live-pilot authority.
The new lifecycle is explicit; general project generation remains B02/B07.
Windows workflow code requires Python 3.12+, independent of whether collection
can run on 3.11. Lazy Tk loading fixes non-UI collection; it is not full headless
cleanup. Preserve pre-existing staged/untracked review files deliberately rather
than treating them as cleanup defects.
