# Strict delivery receipt errors at the buyer-composition boundary

Three offline native regression controls for [x402 #3758](https://github.com/x402-foundation/x402/issues/3758)
on `johnInarti/x402@4d3f2387bd3f2db8007cca324ef8dea23264c248` (draft v0.2.1).
The real `wrapFetchWithPayment(withDeliveryReceipts(fakeFetch, options), client)`
runs with real `x402Client`/`x402HTTPClient`, a registered synthetic scheme and a
synthetic HTTP adapter. No wrapper is replaced with a mock.

The existing [§8.4](https://github.com/johnInarti/x402/blob/4d3f2387bd3f2db8007cca324ef8dea23264c248/specs/extensions/delivery-receipt.md#84-failure-handling)
already forbids automatic repayment after receipt failure. Existing receipt tests
check strict missing-receipt behavior with already-paid requests. These controls
add the complete 402 → payload → paid-request composition and outer caller path.
[#3260](https://github.com/x402-foundation/x402/issues/3260) and its existing
[#3349](https://github.com/x402-foundation/x402/pull/3349) address a separate
post-payment validator hook; this packet proposes no competing hook or runtime fix.

| Path | Payloads / paid dispatches / synthetic settlements | Normal payment-result hook | Caller |
|---|---|---|---|
| Valid signed inline receipt | 1 / 1 / 1 | 1 | Return exact body |
| Strict missing receipt, evidence-aware test driver | 1 / 1 / 1 | 0 | Preserve evidence; HOLD |
| Strict missing receipt, unsafe outer reinvocation once | 2 / 2 / 2 | 0 | Detect unsafe control |

`onResult` executes before the strict error reaches the outer catch. That error
preempts `processPaymentResult`, so ordinary payment-response hooks are not reached.
The synchronous callback clones the response and retains the decoded settlement
header; body bytes are consumed after the caller settles. The missing receipt's
`levels.settlement=null` remains separate from the adapter's `settle.success=true`.
Neither that header nor the fixture is an authoritative blockchain witness.

Counters come from separate payload, paid-dispatch and synthetic-settlement
transitions. Traces retain intermediate snapshots; tests assert event order,
first-failure counts before reinvocation, and final counts. The unsafe
test explicitly reinvokes the complete buyer once and creates distinct synthetic
transaction IDs. It does not demonstrate automatic retry inside either SDK wrapper.
HOLD is an explicit test-driver choice, not a general production policy implementation.
The positive control uses the session/Ed25519 verification path: ML-DSA-65 remains
explicitly unverified and `longTermEvidence=false`; no archival verification is claimed.

## Reproduce

Node 22+ and pnpm 11.25.0; source and lockfile are pinned. Use a fresh public checkout:

```bash
git clone https://github.com/johnInarti/x402.git x402-draft
git -C x402-draft checkout --detach 4d3f2387bd3f2db8007cca324ef8dea23264c248
pnpm -C x402-draft/typescript install --frozen-lockfile --ignore-scripts --filter @x402/core --filter @x402/extensions --filter @x402/fetch
python3 benchmarks/x402-3758/verify-evidence.py
python3 benchmarks/x402-3758/replay.py x402-draft /tmp/x402-attempt-1.json
python3 benchmarks/x402-3758/replay.py x402-draft /tmp/x402-attempt-2.json
```

The replay script rejects a different/dirty tracked revision and an existing
overlay, rebuilds native core exports, places only the test overlay in the native
extensions package, requires exactly three passing/unskipped tests and removes
the overlay afterwards. It refuses to overwrite retained evidence. Installation
uses the native frozen lockfile with lifecycle scripts disabled. Runtime global
`fetch` is stubbed to reject and its zero-call condition is asserted; the synthetic
adapter handles only the two fixture URLs. This is not an OS network sandbox.

Raw local attempts, baseline checks and capability/debt status are in `evidence/`
and `REPORT.md`. The dedicated workflow runs the same test overlay on Node 22/24;
its status must be checked on the draft's exact commit. An unrelated host CI result
does not prove the native composition assertions ran. CI-generated observations
are printed to the job log; this workflow does not upload a JSON artifact.

## Boundaries

- Synthetic HTTP responses and counters; no live seller, wallet, provider or value transfer.
- Public deterministic receipt test seeds; synthetic payment payloads are not monetary authorizations.
- Signed inline receipt positive control, missing-receipt negative paths, body mode only.
- No SSE, by-reference fetch-failure matrix, unclean crashes, persistence, multiprocess or idempotency guarantee.
- No new protocol defect, real double charge, upstream merge or maintainer acceptance claim.
- A closed manifest binds packet bytes and membership, not semantic truth or issuer authority.

AI-assisted implementation and independent agent review. Native draft production
files and lockfile remain unchanged; all changes are additive host evidence/tests.
