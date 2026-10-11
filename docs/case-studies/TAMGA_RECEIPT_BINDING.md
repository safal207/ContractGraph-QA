# Two receipt-binding gaps found through independent review: the Tamga case

**Historical case · 11 October 2026 · attribution and technical scope confirmed by goun7**

Independent review by **Alexey Safonov (`safal207`)** identified two missing consistency checks in Tamga's pairing-fixture verifier. **Tamga author `goun7` implemented the checks and added two tamper-negative regression controls.** A fresh comparison of the historical versions reproduces the difference.

## What changed

The verifier already recomputed a record hash and checked an input commitment. Two links were missing:

- The computed record hash needed to match both the envelope's `receiptHash` and the record's own `charge.h`.
- The actual input hash needed to match both the fixture commitment and `charge.input_sha256`.

Without these links, updating one side of a relationship could hide a stale value on the other.

The [implementation commit](https://github.com/goun7/tamga-protocol/commit/c62d4a822d7e3546931197905e137d0eb6fb490e) explicitly attributes the two gaps to `safal207`. In the [author's reply](https://github.com/x402-foundation/x402/issues/3379#issuecomment-5562472232), `goun7` connects the changes to the review and adopts its bounded claim.

## Reproduced result

The same committed fixture was checked using the actual upstream verifier at parent [`7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b`](https://github.com/goun7/tamga-protocol/commit/7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b) and fix [`c62d4a822d7e3546931197905e137d0eb6fb490e`](https://github.com/goun7/tamga-protocol/commit/c62d4a822d7e3546931197905e137d0eb6fb490e).

| Fixture scenario | Parent | Fixed version |
|---|---|---|
| Original, unchanged bytes | Accept | Accept |
| Changed record and recomputed receiptHash; stale charge.h | Accept | Reject: `membership` |
| Changed input and updated fixture commitment; stale charge.input_sha256 | Accept | Reject: `input_commitment` |
| Changed input with all corresponding hashes updated consistently | Accept | Accept |

**The original eight verifier invocations matched all eight expected outcomes.** An identical repeat was reported, but its second output was not separately committed. These are four scenarios across two versions, including intentional acceptance controls.

The PR review follow-up records two fresh executions of the revised, stricter reproducer: [first output](../../external-validation/tamga-binding/review-results.json) and [repeat output](../../external-validation/tamga-binding/review-repeat-results.json). Each matched 8/8 expected outcomes; their report bytes match exactly. [The replay record](../../external-validation/tamga-binding/REPLAY_VERIFICATION.json) binds both outputs to the revised harness and records the comparison. This demonstrates fresh repeatability of the historical matrix; it does not recreate the original unrecorded repeat.

The first two mutations reproduce the new AT-007g/h regression shapes. The fourth is counterevidence against a broader authenticity claim: a consistently rewritten fixture can still pass. It retains the old output bytes; acceptance does not verify that the changed input produced those bytes.

## What this establishes

The fixed historical verifier rejects the two selected stale-field mutations. It checks internal record/byte consistency and binding within the supplied fixture.

It **does not independently authenticate the receipt** or establish execution, settlement finality, buyer receipt or acceptance, effect count, or exactly-once. The fixture's settlement side is labeled simulated. Full ledger membership and trusted anchors are outside this comparison.

This is a historical verifier comparison, not an assessment of current Tamga or x402 releases. The full upstream test suite and ContractGraph-QA engine were not run.

## Reproduce and review

The [stdlib-only reproducer](../../external-validation/tamga-binding/reproduce.py) fetches six pinned upstream files, verifies their Git blob identities, and invokes both verifiers on temporary local fixtures:

```bash
python3 external-validation/tamga-binding/reproduce.py --output tamga-results.json
```

It needs Python 3.9+ and network access for the initial source fetch. An optional `--source-packet` reads a UTF-8 JSON packet with a `contents` mapping keyed by the six entries in the script's `FILES` registry; the same Git blob checks apply. Malformed or incomplete supplied packets are rejected before any network fetch or verifier invocation. It does not install Tamga, run its full agent runtime, contact a payment provider, or make a payment. See the [recorded results](../../external-validation/tamga-binding/results.json) and [scope/evidence notes](../../external-validation/tamga-binding/EVIDENCE.md).

**Credits:** independent review and this comparison — Alexey Safonov (`safal207`); Tamga verifier implementation and native regressions — `goun7`. Prepared with AI assistance.

On 11 October 2026, [goun7 confirmed the attribution and technical scope](https://github.com/safal207/ContractGraph-QA/pull/209#issuecomment-6111831002) of the [case submitted for accuracy review at `3a6bcd1`](https://github.com/safal207/ContractGraph-QA/blob/3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6/docs/case-studies/TAMGA_RECEIPT_BINDING.md). He also stated that he is comfortable linking the case from the fixture documentation, provided the historical-commit note remains visible. This is confirmation of this bounded historical case, not formal PR approval, project adoption, or endorsement of ContractGraph-QA. No published upstream documentation link or current-release security guarantee is claimed.

**Reusable review question:** when several artifacts reference the same operation, which exact bytes and fields bind them together, and what remains unverified?

Independent reproduction is welcome: report the Python version and any difference from the recorded outcomes.

