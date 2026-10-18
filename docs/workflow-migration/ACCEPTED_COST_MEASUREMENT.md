# Accepted-result cost measurement

Use `python -B tools/accepted_cost_report.py <manifest.json>` to compare a
predeclared, matched set of tasks. The tool prints a JSON report and a SHA-256
of the exact input manifest; redirect it to a new, separately named file when
recording a measurement. Do not overwrite earlier evidence.

Each manifest contains `version: 1`, a cohort name, provenance, and non-empty
task entries. Every task has a unique ID and `baseline` and `pilot` arms. Each
arm records whether the result was accepted and a complete list of cost
activities. An activity has a category (`implementation`, `review`,
`integration`, or `other`), outcome (`accepted`, `failed`, `abandoned`, or
`other`), and `cost_usd` as a non-negative number or `null`. Record all
attempts—including unsuccessful worker and review attempts—and include an
explicit integration activity for every task and arm. Use zero only when
evidence establishes no cost; use `null` when cost is unknown. Input costs must
use the same currency and valuation method in both arms.

The report sums every activity for every task in the cohort, including tasks
that were not accepted. It divides that total by the count of accepted results
in the same arm. It separately reports failed/abandoned attempt costs and
integration costs. Any unknown activity cost makes the arm's total and
cost-per-accepted-result unknown; unknown is never treated as zero. With no
accepted results, cost per accepted result is unknown. Savings are baseline
cost per accepted result minus pilot cost per accepted result; the percentage
is unknown when baseline cost is zero or either arm's result is unknown.
USD amounts are emitted as exact decimal strings; unknown amounts are JSON `null`.

For real evidence, `provenance.kind` must be `real`; fixtures and mixed cohorts
are labeled but never qualify. This declaration is not independently verified.
`evidence_ref` should identify the retained, non-secret source records for the
cohort. The tool reports provenance as `declared_not_verified`: it calculates
from the supplied manifest and does not authenticate the source, prove that
tasks are comparable, or establish that all activities were reported. Preserve
the ledger/provider usage, acceptance, failure, and integration-time/rate
evidence that supports each amount. For human integration effort, record
elapsed effort and the consistently applied loaded rate used to derive USD, or
report the cost as unknown.

There is no qualifying non-fixture pilot cohort recorded in this checkout or
its available local workflow state. The shipped authority disables live workers
and sets API budgets to USD 0. Therefore no real measurement or savings claim is
recorded here; the report must be run against actual, authorized pilot evidence
before that acceptance item can be completed. Do not substitute fixture tests,
the current code change, or estimates for a real pilot measurement.
