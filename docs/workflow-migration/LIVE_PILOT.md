# Bounded live onboarding pilot

The historical ACTIVE receipt is unchanged. The live path is separately
disabled until `tools/pilot_admin.py activate` binds the exact reviewed, merged
bootstrap implementation to an independent checkout and host-local approval.
An approval never transfers to a worktree or clone. Workers cannot read the
receipt, API key, journals, Git objects, host files or Docker socket.

The trusted operator contract is `contracts/operator.py`; the compact factory
is `scripts/operator_service.py`. The onboarding worker owns only `start.ps1`,
`scripts/operator_cli.py`, `tests/test_operator_cli.py` and `README.md`.
`config/pilot-onboarding.json` binds its packet and immutable checks. This is
one maintenance preset, not a project generator. High/critical risk work must
use the existing stronger review path and is ineligible for this pilot.

The pilot extends the existing journal, dispatch reducer, budget reducer,
scope verifier, Docker runtime, independent acceptance exports, handoff and
hosting inspections. Its own versioned lifecycle cannot reset task identities,
attempts, consumed request authority or project spending. Existing offline
controllers retain their original restrictions. No application ABC changed;
the new operator ABC is the shell/controller boundary.

## Bootstrap and operation

Use Python 3.12+, the declared development dependencies, Git, GitHub CLI and the
already verified local Docker image:
`sha256:61526e68966dc3330c3801cbed8740c62710376b0b01b15c960b60c66b6cae1e`.
Review and merge the bootstrap PR first. From the independent pilot clone,
check out a fresh retained `feature/` branch at main, then activate the exact
reviewed bootstrap head with its independent JSON review report:

```powershell
python -B tools/pilot_admin.py activate --commit <reviewed-head> --pr <bootstrap-pr> --review-report <review.json>
python -B tools/pilot_admin.py status
python -B tools/pilot_admin.py run
```

The report must bind `head`, a separate `actor`, `verdict: APPROVE` and
`blocking_findings: []`. Activation verifies the merged PR and the complete
executing scripts/contracts/config/runtime/tools inventory against that head.
The explicit user plan authorizes this receipt, the $1 task/$5 project caps,
provider egress, publication and gated merge. It does not change the original
foundation receipt or confer authority on other controllers.

After the worker shell is accepted and delivered, use its documented short
commands. Status and bare resume derive a compact view from canonical records,
without API access, Docker, a key, attempts, or state provisioning. Explicit
`resume --run` continues only existing eligible work. A request consumed before
an interruption is never silently sent again. Missing or malformed usage keeps
the reservation held. Saved complete responses can be consumed without another
paid request. An interrupted sandbox/check requires inspection of its existing
consumed run; it cannot restart implicitly.

For a consumed request with independently obtained complete provider response
evidence, `python -B tools/pilot_admin.py reconcile-provider --dispatch-id <id>
--response-file <response.json>` settles its original reservation without sending
anything. It preserves the attempt and then permits `resume --run` to consume
that saved output. Missing cache/usage fields remain a hold.

Independent checks also resume their original prepared or stopped container.
For incomplete check preparation, `python -B tools/pilot_admin.py reconcile-checks`
stops and preserves the named run and records a failed check. It cannot grant
acceptance, reset an attempt, or silently relaunch a consumed check.

## Spending and evidence

Worker defaults to `gpt-6-luna`, medium reasoning; one bounded repair can use
`gpt-6.1-sol`. Independent review uses Sol in a separate invocation and actor.
Each role has at most two lifetime attempts. These are initial cost-oriented
defaults, not measured quality or savings claims.

Text-only Responses requests use `store=false`, standard processing, no hosted
tools, no redirects or automatic transport retries, and a maximum of 8,192
output tokens including reasoning. Context remains bounded at 40,000 characters.
The host reserves a conservative byte-based input ceiling, maximum output and
cache-write charges in the existing atomic budget ledger. Both task and project
reservations include worker, reviewer, failed attempts and repairs.

Source: [OpenAI Responses documentation](https://developers.openai.com/api/docs/guides/migrate-to-responses),
[reasoning limits](https://developers.openai.com/api/docs/guides/reasoning), and
[standard pricing](https://developers.openai.com/api/docs/pricing), verified
2026-10-15. Saved USD/million rates are Luna input 0.10, cached input 0.01,
cache write 0.125, output 0.50; Sol input 2.00, cached input 0.10, cache write
2.50, output 10.00. Usage accounting rounds upward to a microdollar and records
provider IDs, model identity, usage, request/response digests and saved rates.
These are usage/rate-derived costs, not invoice reconciliation. Unknown costs
are explicit and block further paid scheduling.

Canonical evidence stays under the checkout's Git-common identity in
`LOCALAPPDATA/ai-template-workflow/`. Provider responses, exact candidate bundles,
Docker input archives, inspected boundaries, stopped output and independent
check logs are retained. Generated code executes only in network-disabled
Docker until accepted. Delivery creates Git objects for exactly that bundle,
publishes a separate PR and reobserves hosting facts before an exact-head merge.
The repository uses rebase merges. Activation and delivery verify that the
integrated commit has exactly the reviewed file tree, retain the original PR
head and review evidence, and require the integrated commit in main's ancestry.
Branches are permanent; there is no deletion or force push.

The owner-approved pilot merge policy uses a saved independent approval bound
to the exact candidate, successful hosting checks, and no unresolved findings.
Mutable automated-review summaries do not confer authority or block a reviewed
candidate by their presence alone. Their history remains explicitly unverified;
observed review-round caps and every other hosting gate still apply. This adds
no model call or user-facing review summary. Offline closeout retains its default.

Report total usage-derived API cost, failed-attempt cost, context bytes and
cost per accepted change. No savings comparison with an unmeasured chat baseline
is supported. The detailed [Windows offline proof](WINDOWS_QUICKSTART.md) remains
reference material. Do not restart the broad M1–M6 campaigns.
