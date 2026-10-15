# M1 AC-02/AC-03 acceptance campaign

Authority: the owner's explicit acceptance-only request, delivered M5 baseline
5f83ac755369f850af74ee8f17e6b566b871f769, and the unchanged frozen AC-02/AC-03
requirements in config/workflow-bootstrap.json. The migration checkout is the
only destination. M6 implementation, frozen status edits, canonical packet or
approval edits, paid workers and live API calls are excluded.

The evidence gap is a consolidated pair of real Docker exports and an actual
multi-process crash/race campaign. Production adapter code is inspected, rather
than assumed correct from M5 tests. New disposable fixtures bind real Git bases,
packet/interface/candidate hashes, Journals, ownership/startup SQLite and the
pinned image. Synthetic authority and clock are explicitly fixture-only; Docker
transport and observations are real except named fault injection points.

Implementation/verification order:

1. Inspect final M5 delivery, handoff, frozen criteria, current refs/worktrees;
   fetch --no-prune and normally merge origin/main. Preserve existing state.
2. Add paired worker/acceptance adversarial tests with image/inspect evidence,
   allowed scoped candidate production and separate independent acceptance.
3. Exercise separate-process ownership collisions, launch CAS and concurrent
   execute after both created-container observations. Observe one start.
4. Kill the coordinator process before and after actual Docker start, inject
   startup refusal plus logging failure, reopen in a fresh process, refuse retry,
   require stop and nonempty preserved archive before expiry recovery, and refuse
   the old token. Preserve original output bytes after explicit abandonment.
5. Obtain fresh independent scoped judgement; repair substantiated gaps and
   rerun affected checks. Keep the main coordinator responsible for decisions.
6. Run complete split regression, static diagnostics and preservation audits on
   the final source snapshot. Save commands, outputs, hashes and limitations.
7. Record separate supported criterion closure decisions without editing frozen
   requirements/statuses. Update M6 handoff with results and limitations only.
8. Commit, comment, push and deliver remotely under the owner's authorization;
   retain every branch, normally synchronize and repeat preservation checks.

AC-02 evidence: denied direct and link host/sibling/Git/socket/credential/
connector read/write; immutable file/directory writes and candidate chmod/write;
network/socket failures; scoped worker output and independent candidate check;
exact image ID, Docker inspect, separate volumes and unchanged host canaries.

AC-03 evidence: unique branch and workspace claims; one consumed start for both
worker and acceptance launch/execute races; separately committed startup history
after process death/refusal/log failure; fresh-process retry refusal; live-tree
and missing-output recovery refusal; preserved stopped archive; old-token refusal.

Final checks follow the M5 split procedure: full pytest excluding frozen approval
projection, tools/check_workflow_approval.py, ACTIVE/source/fingerprint, Journal,
boundaries, both M4/M5 preservation checks, scoped Ruff lint/format/ty and visible
BasedPyright diagnostics. A new read-only baseline audit will additionally bind
all M5 tracked source/config/tests/tools to delivered 5f83ac7. Existing diagnostics
must remain visible. Hardware stays UNVERIFIED, resources/harness disabled, actual
API budgets USD 0. Docker/image/kernel and the coordinator remain trusted; this
is bounded adversarial evidence, not an exhaustive security or hardware proof.
