# Independent post-delivery preservation-audit triage

Reviewer: separate `m1_acceptance_review` agent. Reviewed HEAD: `8c2ce9bf4ed0302d7ef3e558bb43d8f05138a8e2`. Scope: the portability finding supplied from [PR #7](https://github.com/henslewm/ai-template-oop/pull/7#discussion_r4277839470), against the owner's existing-migration-checkout, exact-byte-preservation objective. This is triage only; no implementation, baseline refresh, checkout/ref mutation or M6 work was performed.

**Assessment: the fresh-checkout portability limitation is reproducible. Replacing the existing raw-byte checks with normalization or Git-object checks would weaken the required preservation invariant. I find no in-scope correctness regression in the delivered audit at this HEAD and recommend retaining its raw checks and baseline.** This conclusion does not claim the tool is portable or dismiss the reported observation as false.

## Purpose and authorized boundary

The audit's docstring identifies a delivered-M5 and protected-state audit for AC-02/AC-03 closure. M1_ACCEPTANCE_PLAN.md specifies the migration checkout as the only destination; M1_ACCEPTANCE.md explicitly limits acceptance to the delivered M5 software in the existing migration checkout. The prior review binds exact raw source hashes. The current task requires preserving the original checkouts, indexes, canonical stores, archives and evidence, with no baseline refresh or weakening.

`check_m1_acceptance_preservation.py` adds raw SHA256 comparison of 115 delivered files, permitting only the requested M6_HANDOFF.md documentation update. It calls the existing M5 audit, which calls M4. Those inherited checks independently require the original protected sibling checkouts, exact protected HEADs/statuses/raw index bytes, preserved source bytes, the canonical repository identity and an absolute canonical-state path, plus a retained absolute archive path and raw inventories. A fresh clone cannot establish preservation of that original host state merely by containing equivalent Git source objects. Changing the new 115-file comparison alone would therefore neither satisfy the original objective nor make the complete audit portable.

## Independent read-only evidence

All probes ran in the existing migration checkout. `GIT_OPTIONAL_LOCKS=0` was set for the nested audit to avoid optional index refresh writes. Projection and mutation probes used Git reads and in-memory bytes only; no alternate checkout or projected file was created.

| Probe | Actual result |
| --- | --- |
| `python -B tools/check_m1_acceptance_preservation.py` | Exit 0. The M1→M5→M4 audit passed at 8c2ce9b. All 331 protected files, both protected HEADs/statuses/raw indexes, 31 canonical files, 14 archived files and retained refs matched. Its only delivered-M5 file delta was the authorized M6_HANDOFF.md update. |
| Raw bytes versus M1_ACCEPTANCE_BASELINE.json | Of 115 files, only M6_HANDOFF.md differed. |
| Non-writing Git clean-filter `hash-object --path=<path> --stdin` versus the delivered M5 commit `5f83ac755369f850af74ee8f17e6b566b871f769` | Again, only M6_HANDOFF.md differed. This is useful supplemental source-identity evidence; it proves a different property from raw preservation. |
| Literal current-HEAD Git blobs, representing a checkout with no CRLF conversion | All 115 blobs have LF delimiters. Their raw hashes differ from the recorded worktree baseline for 58 files; excluding the permitted handoff leaves 57 mismatches. This independently reproduces the reported LF-checkout limitation without creating a checkout. |
| In-memory all-CRLF projection of those blobs | Also 58 baseline mismatches, or 57 excluding the handoff. A global line-ending selection cannot reconstruct this historical mixed representation. |
| In-memory line-ending mutation of `scripts/workflow_runtime.py` | Converting its current CRLF bytes to LF changes raw SHA256 while leaving its Git clean-object identity unchanged. Therefore an object-only replacement would accept a byte change that the present raw invariant rejects. No source file was modified. |

Strict current-worktree classification is 58 LF-only files, 56 CRLF-only files and one internally mixed file. The mixed file is `runtime/workflow/Dockerfile`: 18 LF delimiters total, one preceded by CR. Calling all 57 files containing CRLF uniformly CRLF would miss that distinction. The mixed file is unchanged against the delivered baseline.

The mutation counterexample is concrete:

- Recorded/current runtime raw SHA256: `7e4d7cb2e9e7c4424f9edff883232596d65035c25b334376bbabe23809c3ece6`.
- In-memory LF variant SHA256: `8610acffbf53724a430f071731696bcd29ef37f2f506fece1791586f0909c5f9`.
- Git clean-object identity: equal for both variants.

Normalization need not change Python behavior to weaken this gate: the asserted property is that the reviewed and preserved bytes remain unchanged. Source-equivalent bytes are not sufficient evidence for that assertion. The existing output field `m5_production_source_config_tests_tools_byte_identical` would also become inaccurate if raw checks were replaced while that field retained its meaning.

## Recommended action

1. Acknowledge the reproducible portability limitation in the review response and classify the proposed normalization/object-only fix as outside this acceptance task's existing-checkout scope. Retain the current raw hashes and baseline; do not normalize historical files, regenerate snapshots, add line-ending exceptions or reinterpret a raw mismatch as preservation success.
2. Use this new triage report to make the operational precondition explicit: the preservation command audits the retained original environment and its historical bytes. It is not a generic fresh-clone/CI source checker. Earlier M1/M5 review and evidence should remain unchanged.
3. If portable validation becomes an explicitly authorized goal, design a separate source-identity or reproducibility check for fresh checkouts, test its declared LF/CRLF behavior, and label its result separately. It may supplement the raw original-environment audit. It must not claim that an absent original canonical store, protected index or retained archive was preserved, nor replace the current byte-preservation gate.

The portability finding does not, by itself, invalidate the completed AC-02/AC-03 Docker and consumed-start evidence on the retained environment. This report makes no new claim about general cross-platform reproducibility or a future checkout's ability to rerun the historical preservation procedure.

## Exact reviewed raw artifacts

| Path | SHA256 |
| --- | --- |
| tools/check_m1_acceptance_preservation.py | a1db4c95ef3cf12feb129a0d5d1b5c320677ecb59e63cee5b19d88a0ff20d396 |
| tools/check_m4_preservation.py | c5ddb7d25da1a12151e798b1248df05e6cea4b8ab840c66aef3249a4b309f1e5 |
| tools/check_m5_preservation.py | 575ce62bcd10546356ba51e28aed4535213b5e5539d2d886b53181a57d1ed05d |
| docs/workflow-migration/M1_ACCEPTANCE_BASELINE.json | b32b20ea6ba536ef21554de6009843d1908e2168ee9793fef06045d1c4c60649 |
| docs/workflow-migration/M3_PRESERVATION.json | 2af361f9fadcc3f02acd027c6d6c6527f72c5ac5e9ee2283c477b2786480c272 |
| docs/workflow-migration/M4_PRESERVATION.json | cab0649056e611858c38247f022d5b7a9a37ee790b3a0dfe42abdb17bb09bcb1 |
| docs/workflow-migration/M5_PRESERVATION.json | 4727c7a2fe48a2e52a04422e2aaa694e44ed25b3614a210d2086492279d6de0f |
| docs/workflow-migration/M1_ACCEPTANCE_PLAN.md | 23a15776d43c3ddd37140edbe9190c5baf7ecc8432b804aafe3fdcff9a81f143 |
| docs/workflow-migration/M1_ACCEPTANCE.md | d0bbdfc1ba29b004328d69f2f2fe88c4baaa3c92627a73b2f800655b0a34e408 |
| docs/workflow-migration/M1_ACCEPTANCE_REVIEW.md | 31830064d673f5d0a3570270aafdaf70967c37cefa1434e502e89ff6dfc75934 |
| docs/workflow-migration/M6_HANDOFF.md | 3b1106a7fb4b6314fb2983aaa1b513c7433e1385385debde30fb78249bae178e |

Only this new report was written. The remote review's supplied portability claim was evaluated; the remote thread was not fetched independently. No provider/network calls, Docker execution, complete regression rerun, canonical/protected/archive writes, ref changes or baseline refresh occurred. This triage does not implement M6 or alter any prior acceptance decision.
