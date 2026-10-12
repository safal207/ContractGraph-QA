# Independent packet review

Decision: the bounded reproduction, oracle, result table and maintainer-facing message are ready. No material harness or reproduction-command defect was found. This review did not execute the SDK, runner or packet verifier, and did not post externally. It read the packet source and all sixteen published save/resume observations, then independently compared JSON fields and file hashes.

## Confirmed

- Both subjects contain exactly eight cases, with 6 PASS / 2 FAIL / 0 ERROR. The raw resume files equal the observations embedded in results.json. Every save/resume pair has different PIDs.
- Same-name/reset/single records exactly X/approved-op, then an X-owned record_effect/d2 interruption with no final output. Same-name/reset/sticky records exactly X/approved-op and X/follow-up-op, no interruption, and done-x. The other six cases produce the corresponding Y-owned behavior.
- The continuation really requests a new operation and call ID. This avoids treating a reset ScriptedModel response queue as independent duplicate-effect evidence.
- Save setup asserts Y, record_effect, d1 and approved-op before public approval and serialization. Literal closure-owned effects provide an oracle independent of SDK alias helpers.
- The known-bug exit mode requires the exact X-owned outcomes, successful returns, separate processes, and all six positive controls. It cannot pass merely because two cases fail. FAIL verdicts remain present. Default zero requires all eight owner assertions to pass.
- Collection errors are distinguished from restore/run errors. The packet claims zero runtime errors only for these completed observations, not for arbitrary future executions.
- Recorded import roots separate the installed release from the pinned source checkout. Identity hashes match provenance in every reviewed resume observation; runner and requirements hashes also match provenance.
- The README commands are coherent for the stated Linux/CPython 3.12 environment. Source mode imports the checkout through PYTHONPATH while reusing the installed dependency freeze. A rejection-based fix may need a distinct agreed oracle, which the README already states.
- The current manifest has 122 unique entries. Every listed file exists and matches size/hash; all packet files except manifest.json itself are listed. Static review of verify_packet.py finds no defect for this declared relative-manifest integrity check. It does not establish authenticity or guard against replacement of both manifest and artifacts, and the documentation says so.
- Attribution, engine NOT_RUN, upstream CI NOT_RUN, absence of a runtime fix, synthetic effects, process reconstruction versus crash recovery, and the narrow status of unique-name controls are accurately separated.

## Small wording/provenance corrections

1. README: “The captured runs contain no such attempts” overstates what the audit hook logs. The hook raises on selected events but does not record an attempt counter; a dependency could catch the exception. All captured stdout/stderr files are empty. Prefer “No blocked network attempt surfaced in the captured outputs,” or omit the sentence. This requires no runtime rerun.
2. provenance.json calls portable commands `invocation`, while the observed environment is rooted in `venv/` rather than the documented `.venv/`. If those strings are normalized reproduction commands rather than the literal executed argv, name them `reproduction_command`, or retain actual argv separately. Do not claim literal command capture if it was reconstructed. The subject/import/hash evidence itself is consistent.

## Publication completion checks

- Root is completing the verifier run and byte-tamper negative control. Retain “Durable Evidence Reopen / Integrity: RUN” only after those actions actually complete; my independent hash comparison does not substitute for executing the advertised verifier/tamper control.
- The MESSAGE URL is an intended branch location, not an independently verified published artifact in this review. Ensure the packet exists there before using the message. A commit permalink is preferable when available.
- Finalize wording before regenerating the manifest. No broad SDK tests, added matrix axes, new claims or additional approval flow are warranted by this review.

The capability table is defensible because its opening explicitly labels RUN as manual/native packet activity rather than corresponding ContractGraph-QA modules. The message credits the original reporter and offers concrete regression coverage without claiming discovery, adoption, a fix or general SDK safety.
