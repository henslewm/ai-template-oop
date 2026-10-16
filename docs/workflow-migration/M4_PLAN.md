# M4 implementation plan (AC-07 only)

Owner request: implement Docker-only dispatch, launcher preflight and untrusted
report ingestion; stop before M5. The 18 M3 files are preserved byte for byte.
The pinned donor is d6e582b7edeae24345a175f36639230726dbdead, read using
`git -C ../universal-ai-project-template show`, never its working files.

Entry: retained feature/workflow-migration at ef6ae42; fetch --no-prune found
origin/main at 63b61ff and normal merge reported already up to date. Both
protected inventories (331 files), canonical inventory (31 files), ACTIVE
receipt and sequence-2 journal matched M3. M4_PRESERVATION.json captures this
entry, all 18 M3 hashes, existing tracked hashes, refs and the retained archive.

Implementation sequence:

1. Save exact scope/image/config/brief/rules/export and full M3 context in the
   Journal-native reservation; retain its deadline, actor, rates and all heads.
2. Record preparation before Docker side effects, with durable container/volume
   names. Supply bounded immutable instructions through the existing volume
   export. Workers have no host transport or credential environment.
3. Revalidate every binding before consuming the existing startup authority and
   immediately before Docker start. A preparation/launch crash never retries
   implicitly. Preserve stopped session output before ownership release.
4. Validate bounded opaque archives and strict reports. Commit M3 task, role and
   project accounting and the ingestion receipt in one CAS transaction. Exact
   duplicate ingestion is idempotent; changed/stale/conflicting ingestion refuses.
5. Add behavioral, negative, crash, concurrent and replay tests using real
   disposable Journals and offline Docker fixtures. Obtain a separate fresh
   scoped review, repair findings, run the complete handoff split verification
   and scoped static checks, and recheck preservation.
6. Record evidence, limitations and an M5 handoff. Deliver on the retained branch
   under the owner's Git authorization, retaining every branch and leaving both
   protected checkouts untouched. Do not implement M5 or close M1 acceptance.

All default resources stay disabled and API budgets USD 0. Metered launch is
refused. Synthetic usage tests use saved M3 rates; worker cost assertions never
settle metered liability. Frozen approval, contracts and packets stay unchanged.
