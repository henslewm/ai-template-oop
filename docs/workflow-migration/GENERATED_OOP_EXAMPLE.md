# B02 — one runnable generated OOP project

Implementation owner: Codex. This package generates one software worked example,
not general intake or hardware projects. The working template application and
Pro-Se Engine are unchanged.

## Run the built example

The local example is at
`C:\Users\hensl\Documents\GitHub\ai-template\generated-oop-example`.
It has its own Git repository, UUID and isolated `.venv` with declared dev
dependencies installed. From that directory:

```powershell
.\.venv\Scripts\python.exe main.py --mock 1 2 3
.\.venv\Scripts\python.exe main.py --db example.db --register 1 2 3
.\.venv\Scripts\python.exe main.py --db example.db 4 5 6
.\.venv\Scripts\python.exe -B -m pytest
```

The memory run returns count 3, total 6 and mean 2. The SQLite commands use the
fictional demo account, store a result and then reuse the account/database.
`--register` is only for a new account. The application also runs with ordinary
Python 3.12+ without installing runtime packages.

## Generate another project

From the migration worktree, choose a new or empty destination outside it:

```powershell
python -B tools/generate_example.py ..\another-oop-example --slug another-oop-example
```

Generation refuses non-empty directories, runtime/approval/secret inputs and
unexpected literal-rewrite drift. It uses only `templates/oop-example/manifest.json`;
it never copies the whole repository, original Git history or ACTIVE receipt.
New projects get a fresh UUID through the existing B01 lifecycle and remain
`AWAITING_APPROVAL`. Deterministic application execution/tests require no workflow
activation. No worker, provider, hardware or publication capability is enabled.

## Architecture demonstrated

- Existing auth/data ABCs, SQLite implementations and their behavior tests are
  copied byte-for-byte. Existing headless-capable fakes move only in the output,
  from the template's UI package to `src/testing/fakes.py`.
- The generated `BatchService` ABC and frozen `BatchRequest` declare the business
  workflow. `AuthenticatedBatchService` receives auth/data interfaces, performs
  registration/authentication/processing and guarantees session cleanup.
- `src/container/wiring.py` assembles memory or SQLite dependencies. Presentation
  parses input, invokes one batch interface method and renders raw results.
- The same auth/data/batch assertions exercise real and mock dependencies. The
  generated boundary checker also rejects presentation importing implementations.
- `AGENTS.md` preserves one writer, named feature/contract/test context and
  independent exact-candidate acceptance. Instructions do not claim runtime
  filesystem isolation; no worker was launched for this example.

No existing application contract was changed. The batch contract exists only in
generated output and its template assets. The numerical behavior remains the
existing demo's behavior, not new scientific processing or numerical hardening.

## Verification and provenance

- **18 generator checks passed in 9.40s** after final generator/asset changes,
  including a complete generated **53-case** suite under a Tk import-denial hook.
- In the actual example's new isolated Python **3.12.10** venv, editable install
  with `.[dev]` succeeded and `pip check` found no broken requirements.
- Actual memory and SQLite commands returned totals **6**, **6**, then **15**;
  SQLite record IDs advanced from **1** to **2** across separate invocations.
- The actual example's complete suite passed **53 cases in 1.92s**. Boundaries,
  scoped Ruff and ty passed. Project status remained `AWAITING_APPROVAL`.
- No M1–M6 campaign, Docker task, paid model or hardware verification was rerun.

`GENERATION.json` in each output records the source commit and dirty-source flag,
manifest/tool digest, project UUID and every source/output hash. It is a historical
generation snapshot, not approval. Local source includes new uncommitted package
files; the dirty flag exposes that instead of claiming a clean published revision.
The concrete example was generated before a lint-only generator import placement
adjustment; its complete app/control output hashes still match the final manifest.
Fresh projects in the final generator regressions use the final generator source.

Raw command results and preservation snapshot are retained at
`C:\Users\hensl\AppData\Local\Temp\oop-example-proof-hy0yvadk\`.
Independent source/artifact review **approved** the exact current source and all
41 generated outputs with no blocking findings; see
[GENERATED_OOP_EXAMPLE_REVIEW.json](GENERATED_OOP_EXAMPLE_REVIEW.json).
Independent acceptance is separate from integration; Git history and the delivery
pull request record integration. Review limits and historical generator provenance
remain explicit.
The central status and next work remain in `BACKLOG.md`; do not start another
infrastructure package merely because this example exposes an optional extension.
