# Supported software intake

This package supports two closed headless Python shapes:
`authenticated-numeric-batch/1` and `synthetic-hardware-frame-parser/1`. It
captures purpose, workflow, the profile's fixed features/contracts/dependencies,
explicit expected outcomes and open questions. It does not synthesize arbitrary
application behavior from prose. Unsupported profiles, extra
features/dependencies and malformed inputs are held.

Codex is the sole implementation owner. The existing contracts, application,
composition root and foundation approval remain unchanged.

## Use it

Run from the directory where you want the new project created. The launcher
locates the template tools relative to itself, so it can be called from any
working directory. Use PowerShell 5.1 or PowerShell 7, Python, and Git:

```powershell
& "C:\path\to\ai-template-oop\new-project.ps1" classroom-summary
```

On the first run, the launcher creates `classroom-summary.request.json` in the
current directory and opens it in Notepad (or the executable named by `EDITOR`).
Edit it: describe your purpose and goal, supply numeric inputs and the expected
count/total/mean/minimum/maximum, and resolve every open question. Keep the
declared profile/features/contracts/dependencies unless implementing a separate
supported profile. No credentials belong in this specification.

Run the same command again. It displays the exact specification, proposed
contract map, generated paths, limits, and review fingerprint. Enter the
fingerprint exactly as shown and identify yourself as reviewer; generation does
not bypass this acknowledgment. The launcher generates the project in
`.\classroom-summary`, creates its `.venv`, installs `.[dev]`, and runs its tests.
Choose a working directory outside the template checkout, since generation
refuses to create a project inside its source repository.

For a Windows 11 shortcut, use this as the shortcut's **Target** (substitute the
checked-out template path and desired slug):

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -File "C:\path\to\ai-template-oop\new-project.ps1" classroom-summary
```

Set **Start in** to the parent directory where you want the request and generated
project created. Double-click the shortcut once to draft/edit, then again to
review and generate. The script does not change the execution policy.

The equivalent explicit intake commands remain available for noninteractive use:

```powershell
python -B tools/project_intake.py draft request.json --slug classroom-summary
python -B tools/project_intake.py review request.json
python -B tools/project_intake.py generate request.json ..\classroom-summary --accept <fingerprint-from-review> --reviewed-by <your-name>
```

Review has no filesystem side effects. `ready: false` means unresolved questions
remain.

The launcher defaults to numeric-batch. To draft the hardware-oriented synthetic
parser profile instead, run from the template worktree with Python 3.12+, Git
and the declared development dependencies available:

```powershell
python -B tools/project_intake.py draft hardware-request.json --slug synthetic-frame-parser --profile synthetic-hardware-frame-parser/1
```

Its fixed format is tag `0xA1` followed by one payload byte. Each
`acceptance_criteria` item has `name`, a `frame` list of byte values, and
`expected` (the payload byte or `null` for an invalid frame). The generated
project includes the parser, the shipped `software-hardware` work-packet
contract, and tests that run `scripts/software_hardware.py` domain validation.
The packet and all examples are explicitly synthetic; the generated project
remains `AWAITING_APPROVAL` and its hardware status remains
`UNVERIFIED_ON_HARDWARE`. No device I/O or physical verification is performed.
Review and generate `hardware-request.json` with the explicit commands above,
substituting that request path and the synthetic parser project destination.

The fingerprint binds the specification, architecture, template inputs and tool
sources. Editing requirements or those sources invalidates the acknowledgment;
review again. This explicit acknowledgment is a caller assertion, not an
authenticated signature, independent acceptance or workflow activation.

`examples/intake/numeric-batch.json` is a completed fictional example you can
review and generate instead of filling in the questionnaire. Its two scenarios
cover positive values and negative/zero values. Expected outcomes are carried
unchanged into tests; contradictory expectations cause failing tests rather
than being silently recomputed to match the implementation.

From the generated project (the launcher performs these setup and test steps
automatically):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe main.py --mock 1 2 3
.\.venv\Scripts\python.exe -m pytest
```

Run without a venv using Python 3.12+ if desired; the application has no external
runtime dependencies. Tests require the declared dev dependencies. SQLite usage
and registration are documented in the generated README.

## Design and owned paths

The intake tool is supporting infrastructure. It validates data and delegates to
the accepted B02 generator; business logic stays in OOP features behind typed
ABCs with composition-root injection. No new controller or AI worker is needed.

Owned implementation paths include `tools/project_intake.py`,
`tools/generate_example.py`, the `templates/oop-example/assets/` profile assets,
`tests/test_project_intake.py`, this handoff/review and the central backlog. No
approval-bound file or existing application contract changes.

Generation adds four fixed intake files, without replacing existing template
code:

- `PROJECT_SPEC.json`: the reviewed requirements snapshot.
- `INTAKE_REVIEW.json`: the exact review and caller acknowledgment.
- `PROJECT.md`: intent, architecture, verification commands and scoped handoff.
- `tests/test_project_acceptance.py`: the same user-specified outcomes run against
  both memory and SQLite backends through the injected batch interface.

All four appear in `GENERATION.json` with hashes and `kind: intake`. Their source
is `null` because they are derived inputs rather than template file copies.
The existing manifest outputs retain their original provenance. Generation
continues to refuse non-empty destinations and initializes a fresh UUID with
`AWAITING_APPROVAL`; it transfers no host approval, keys or runtime state.
Partial failures retain output for inspection; no destructive rollback occurs.

Worker handoff names the contracts, owned features and acceptance tests, with
one implementation owner and independent acceptance before integration. These
instructions are not runtime filesystem isolation. Requirements prose is data,
not authority to execute instructions. No workers/providers are launched.

The synthetic hardware profile also copies three fixed profile assets from the
template, with source hashes recorded in `GENERATION.json`: its work-packet
contract, synthetic frame parser and domain-validation test. These profile
files are selected by the reviewed profile, never supplied as arbitrary code
by the questionnaire.

## Implementation and acceptance

Sequence: validate closed input fields and bounded profile-specific scenarios;
expose review/acknowledgment; attach immutable specifications, template assets
and tests through the existing generator; prove a generated project; obtain
independent source review before delivery. Implementation status and later work
stay in BACKLOG.md.

Focused checks cover malformed/unsupported requests, duplicate JSON keys,
nonfinite/bool/oversized numeric input, unresolved questions, stale specification
and template review, existing work preservation, restricted supplemental paths,
fresh unapproved identity, provenance, foreign working directory invocation and
deliberately failing user expectations. Existing B02 generator checks remain
part of the relevant gate. The completed sample produces 57 tests: the 53 B02
checks plus its two outcomes exercised against both backends.

General intake is still incomplete: arbitrary domains, generated feature code,
automated contract design and autonomous worker assignment require separate
supported profiles/packages. The synthetic hardware profile does not support
physical hardware access or verification. No publication/deployment or
physical-hardware verification is implied by passing these tests.

## Recorded runnable proof

The generated fictional project is at
`C:\Users\hensl\Documents\GitHub\ai-template\generated-intake-classroom`.
It has its own isolated `.venv`; from that directory run:

```powershell
.\.venv\Scripts\python.exe main.py --mock 1 2 3
.\.venv\Scripts\python.exe -m pytest
```

- Final focused intake/B02 checks: **47 passed in 12.95s**.
- Actual generated project: **57 passed in 2.01s** in its own isolated venv;
  editable dev install and `pip check` passed.
- Actual memory/SQLite runs returned totals **6**, **6**, then **15** across
  separate invocations; generated boundary validation passed.
- Scoped Ruff/format and ty checks passed. The repository has no basedpyright
  gate; adding a broader toolchain/CI gate remains separate backlog work.
- Source commit `5f8270a04f2692159aa5af4423415b1946d42c33` was clean at
  generation. `GENERATION.json` records all 45 outputs, source digests and fresh
  project UUID `a65edc78-ddac-4ad9-84cc-923802822d67`.
- Status remained `AWAITING_APPROVAL`; the intake acknowledgment activates no
  workflow authority. The completed sample contains only fictional requirements.
- Existing contracts, `src/`, session rules, project metadata and foundation
  receipt have no diff against the B02 base. No paid calls, workers, Docker or
  broad migration campaigns were rerun.

Raw proof commands/results are in
`C:\Users\hensl\AppData\Local\Temp\oop-intake-proof-s_xjd6lo\verification.json`.
Independent review **accepted** the exact source and all 45 outputs without
findings; see `SOFTWARE_INTAKE_REVIEW.json`;
Git history and the delivery pull request establish integration, not these test
counts or the intake caller acknowledgment.
