# Workflow foundation approval review

The reviewable package is `config/workflow-bootstrap.json`, with its bound
architecture, validator, tests, destination files and pinned source inventory.
It is inert: `AWAITING_APPROVAL`, autonomy off, approval false with null receipt
metadata. No startup instruction imports it and no activation command is shipped.

Run from the destination root:

```powershell
python -B scripts/validate_workflow_approval.py --fingerprint --check-source --check-preserved --check-baseline
python -B scripts/validate_workflow_approval.py --require-active
```

The first command is read-only and prints a SHA256 fingerprint only after all
checks succeed. The second must exit 1 for this package. Exit 0 means package
validity only; it is not runtime acceptance or approval. JSON is parsed strictly,
duplicate keys/nonfinite numbers refused, and linked/escaped bound files refused.
The validator starts no containers, makes no network requests, creates no state,
and exposes no activate or write operation. `--check-source` reads pinned Git
objects; `--check-preserved` checks recorded refs, protected statuses and indexes.
`--check-baseline` verifies the destination branch/base and pre-implementation
file inventory. Use all three checks when reviewing this initial package.

`python -B tools/prepare_workflow_approval.py` prepares or refreshes an **inactive**
manifest from local pinned Git objects and current destination files. It writes
only `config/workflow-bootstrap.json` through an exclusive temporary file and
refuses an ACTIVE or malformed receipt. Refresh changes the reviewed package;
run validation and review its new fingerprint again. It cannot approve or activate.
The manifest includes 8 preserved imports, 12 controller/schema adaptations and
13 reference/test inputs; only the first two groups form the runtime dependency
closure. Reference inputs are not installed or executed by this preparation.

The fingerprint is SHA256 of compact, sorted-key, UTF-8 canonical JSON of all
package fields except `state`, `autonomy_enabled` and `approval`. Those excluded
receipt fields have separate strict consistency checks. Each bound text file is
hashed after CRLF/CR -> LF normalization without stripping text or changing BOMs.
`bound_files` are the stable foundation: destination rules, architecture/review,
approval tooling/tests, dependency declaration and frozen packet imports.
`baseline_files` captures the remaining inspected code/evidence for initial
review and is checked only with `--check-baseline`. Routine task edits do not
revoke the foundation; candidate/scope/acceptance checks bind those edits.
The recorded baseline hashes remain fingerprint material, so rewriting that
snapshot requires a new review. The bootstrap JSON is the manifest itself and
is not recursively file-bound.
Changes to scope, caps, source pin, foundation-bound content, authority or criteria change
the fingerprint and require a fresh review. Do not edit a hash to conceal drift.

A future receipt must identify the actual approving owner, UTC approval time,
exact fingerprint and literal `APPROVE <fingerprint>` decision, recorded by a
trusted coordinator after explicit owner direction. The validator cannot prove
the human provenance of a hand-edited receipt. No receipt is recorded today.
Even a future ACTIVE receipt for this foundation authorizes only bounded offline
implementation; it cannot enable paid workers, egress, credentials or publication.
Controllers and their integration are not shipped by approving the design.

Review these decisions together:

- Preserve the existing Docker isolation boundary and canonical packet schema.
- Separate process ownership from the durable task/review/project journal.
- Consume startup authority durably before Docker; the known retry defect blocks
  launch readiness until fixed and independently checked.
- Preserve cumulative attempts and unknown-cost holds; initial live API caps are
  zero and all provider resources remain disabled.
- Require independent, exact-candidate acceptance before deliberate integration.
- Retain feature branches locally and on origin permanently; donor cleanup and
  automatic merge authority are excluded.

The machine package lists AC-01 through AC-12 with required evidence. Their
implementation verification remains pending. This review's offline validator
tests establish package integrity/refusal behavior only. Historical runtime
evidence predates the package and does not satisfy these criteria by itself.

Known operational prerequisites are recorded in `blockers`: startup repair,
controller implementation, independent acceptance and runtime crash/concurrency
evidence. These are work to do after approval, not gaps hidden by an ACTIVE flag.
External worker/network/publication enablement is outside this foundation and
requires a new reviewed package. The original checkout's staged plan deletion,
source untracked work and every recorded local/cached branch tip stay preserved.
