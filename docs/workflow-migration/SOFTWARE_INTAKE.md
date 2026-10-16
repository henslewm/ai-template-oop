# Supported software intake

This package adds requirements intake for one headless Python shape:
`authenticated-numeric-batch/1`. It captures purpose, one workflow, the existing
features/contracts/dependencies, explicit expected outcomes and open questions.
It does not synthesize arbitrary application behavior from prose. Unsupported
profiles, extra features/dependencies and malformed inputs are held.

Codex is the sole implementation owner. The existing contracts, application,
composition root, template assets and foundation approval remain unchanged.

## Use it

Run from the template worktree with Python 3.12+ and Git available:

```powershell
python -B tools/project_intake.py draft request.json --slug classroom-summary
```

Edit `request.json`: describe your purpose and goal, supply numeric inputs and
the expected count/total/mean/minimum/maximum, and record unanswered questions.
The draft contains a question deliberately; resolve it before generation.
Keep the declared profile/features/contracts/dependencies unless implementing
a separate supported profile. No credentials belong in this specification.

Review the exact specification, proposed contract map, generated paths and limits:

```powershell
python -B tools/project_intake.py review request.json
```

Review has no filesystem side effects. `ready: false` means unresolved questions
remain. After reviewing the report, copy its fingerprint into generation:

```powershell
python -B tools/project_intake.py generate request.json ..\classroom-summary --accept <fingerprint-from-review> --reviewed-by <your-name>
```

The fingerprint binds the specification, architecture, template inputs and tool
sources. Editing requirements or those sources invalidates the acknowledgment;
review again. This explicit acknowledgment is a caller assertion, not an
authenticated signature, independent acceptance or workflow activation.

`examples/intake/numeric-batch.json` is a completed fictional example you can
review and generate instead of filling in the questionnaire. Its two scenarios
cover positive values and negative/zero values. Expected outcomes are carried
unchanged into tests; contradictory expectations cause failing tests rather
than being silently recomputed to match the implementation.

From the generated project:

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

Owned implementation paths: `tools/project_intake.py`, the narrow supplemental
input hook in `tools/generate_example.py`, `tests/test_project_intake.py`,
`examples/intake/numeric-batch.json`, this handoff/review and the central backlog.
No approval-bound file or existing application contract changes.

Generation adds four fixed files, without replacing existing template code:

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

## Implementation and acceptance

Sequence: validate closed input fields and bounded numeric scenarios; expose
review/acknowledgment; attach immutable specification and scenario tests through
the existing generator; prove a generated project; obtain independent source
review before delivery. Implementation status and later work stay in BACKLOG.md.

Focused checks cover malformed/unsupported requests, duplicate JSON keys,
nonfinite/bool/oversized numeric input, unresolved questions, stale specification
and template review, existing work preservation, restricted supplemental paths,
fresh unapproved identity, provenance, foreign working directory invocation and
deliberately failing user expectations. Existing B02 generator checks remain
part of the relevant gate. The completed sample produces 57 tests: the 53 B02
checks plus its two outcomes exercised against both backends.

General intake is still incomplete: arbitrary domains, generated feature code,
hardware projects, automated contract design and autonomous worker assignment
require separate supported profiles/packages. No publication/deployment or
physical-hardware verification is implied by passing these tests.
