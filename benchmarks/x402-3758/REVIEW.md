# Independent review of the x402 #3758 composition packet

Review status: no material blocker in the reviewed native test, replay runner, README, integrity-verifier logic or dedicated CI definition. This is a static source review plus independent inspection of the two retained JSON observations; the reviewer did not execute the native test or create, modify or remove its source overlay.

Reviewed subject: `johnInarti/x402@4d3f2387bd3f2db8007cca324ef8dea23264c248`. Reviewed test SHA-256: `a73f722ddabe3f17aed57052a3334604c643aeff70bfabde24d9243b4bf8336f`.

## Source and oracle

- The test imports the actual delivery-receipt and fetch wrappers and uses real `x402Client` and `x402HTTPClient`. The payment scheme and HTTP boundary are explicitly synthetic. The `processPaymentResult` spy calls through rather than substituting an implementation.
- Reading the real core/fetch path supports the stated seam: an inner strict receipt error exits the paid-fetch await before normal payment-result processing. The synchronous receipt `onResult` callback can retain its result, settlement header and a response clone before the outer catch.
- The positive control reaches the real normal payment-response hook once and returns the exact body. Missing-receipt controls retain `levels.settlement=null` separately from the synthetic header's `success=true`. Neither is represented as external-chain evidence.
- The unsafe control explicitly calls the complete buyer a second time. It does not establish internal SDK auto-retry or a real double charge. The HOLD branch is a test-driver decision, not a claimed reusable production policy.
- Payload creation, paid dispatch and synthetic settlement are separately counted. The full event order is asserted, as are pre-reinvocation and final counts. The same request and payment requirements are used; each synthetic attempt receives a distinct transaction ID.

## Retained observations

Both files have separate attempt IDs, `COMPLETE`, three passed native tests, zero failed and zero skipped. Their outer test hashes and inner overlay hashes match the reviewed test bytes. Both record Node v24.19.0 and pnpm 11.25.0.

| Case | Payload / paid / synthetic settlement | Normal hook | Result and evidence |
|---|---|---|---|
| Valid signed inline receipt | 1 / 1 / 1 | 1 | RETURN; exact body retained; all five verifier levels true |
| Missing receipt, test-driver HOLD | 1 / 1 / 1 | 0 | `onResult` precedes catch and HOLD; one preserved body/header/result |
| Unsafe outer reinvocation | 2 / 2 / 2 | 0 | Two distinct synthetic transaction IDs; two strict errors and preserved bodies; expected unsafe control detected |

The positive verifier result is the native **session** verification path: Ed25519 is verified, `unverifiedAlgorithms` retains `ml-dsa-65`, and `longTermEvidence=false`. The existing README's signed-inline wording is compatible with this result; later REPORT/MESSAGE text should not expand it into hybrid-signature or long-term verification coverage.

## Replay, integrity and CI

- Replay rejects a different HEAD, tracked changes and a pre-existing overlay; rebuilds native core; requires exactly 3/0/0 from the native test report; checks unchanged overlay bytes before removal; rechecks tracked source and uses exclusive creation for retained output. A zero-test green run cannot satisfy the count gate.
- Verifier logic binds bytes, sizes and closed packet membership, rejects traversal and symbolic paths, and binds listed repository sources. It correctly disclaims observation authentication. Manifest assembly and its positive/tamper/unlisted checks were still pending when this review was written.
- The dedicated workflow pins both native subject and action revisions, runs the same replay on Node 22 and 24, and prints its JSON to logs. README accurately distinguishes this planned CI execution from unrelated host CI; no uploaded JSON artifact is promised.
- README commands match the runner and selected native workspace packages. The fetch deny stub is accurately distinguished from an OS network sandbox.
- The existing §8.4 policy and both #3260 and the already-existing #3349 implementation are credited. The contribution is the two-wrapper regression seam, not a new repayment prohibition, competing validator hook or protocol fix.

## Small wording refinement

README says the traces “assert their order and intermediate snapshots.” The implementation retains every intermediate snapshot but directly asserts event order plus pre-reinvocation/final counts. For literal precision, use: “The traces retain count snapshots and assert event order plus pre-reinvocation and final counts.” This is not an oracle blocker.

REPORT.md, MESSAGE.md, final manifest bytes and remote exact-commit CI were not yet available to this reviewer. This review therefore does not certify those subsequent artifacts or claim upstream acceptance. No additional runtime matrix is needed for the present three-case bound.
