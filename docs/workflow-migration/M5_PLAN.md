# M5 independent acceptance plan

Scope: independent acceptance only. Stop before M6. Preserve frozen approval,
contracts, packets, canonical stores, archives, protected checkouts and branches.
All defaults stay disabled and all real API budgets stay USD 0.

Design: a separate Journal stream owns submissions and gate evidence. Each
submission binds the exact M4 stopped archive and replacement bytes/reference,
task/revision/contract, feature/UI/base commits, interface/scope, image and
environment. A fresh volume export overlays the candidate without host writes.
Architect commands run only inside Docker. Exact stopped output is compared to
the candidate; check claims alone cannot establish a gate. Hardware/manual
evidence ingestion is disabled. Such checks remain UNVERIFIED and block required
gates; no attestation or simulated PASS can waive them.

Model/architect reviews reserve through M3 and settle atomically with their
acceptance record. Native M3 records APPROVE reports as NEEDS_EVIDENCE until the
complete acceptance proof is synchronized. A small versioned feedback hook
validates the embedded acceptance chain, native head, candidate and every gate
before applying approval. Ordinary native APPROVE remains refused. The original
M3 source is recoverable byte for byte by removing this additive hook; the
preservation audit checks that exact reconstruction instead of refreshing hashes.

Phases: implement candidate and pure transitions; implement Docker checks and
review accounting; implement explicit acceptance/proof synchronization; add
behavioral, malformed report/archive, crash, concurrency and replay cases; obtain
fresh scoped review and fix findings; run the complete split verification and
static/preservation gates; document evidence and limitations, commit and deliver
with retained branches, then provide an M6 handoff.

Changing any submission binding invalidates prior gates while retaining all
review attempts, native failures, spend and liability. No host commands, provider
transport, output apply, automatic hardware claim or M1 evidence closure is added.
