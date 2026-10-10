@johnInarti, I exercised the existing §8.4 no-repayment rule at the actual
`wrapFetchWithPayment(withDeliveryReceipts(fakeFetch, options), client)` seam on
your draft commit `4d3f2387bd3f2db8007cca324ef8dea23264c248`.

The three offline native controls use real clients/wrappers and a synthetic scheme/HTTP adapter:

| Case | Payloads / paid dispatches / synthetic settlements | Normal payment-result hooks |
|---|---|---:|
| Valid signed inline receipt | 1 / 1 / 1 | 1 |
| Strict missing receipt, outer HOLD | 1 / 1 / 1 | 0 |
| Unsafe outer catch reinvokes the buyer once | 2 / 2 / 2 | 0 |

The useful boundary: strict receipt failure occurs before `processPaymentResult`.
`onResult` still runs before the outer catch, so synchronously cloning the response
there preserves the exact body and decoded `SettleResponse`. The missing receipt's
`levels.settlement=null` remains separate from the adapter's `settle.success=true`.

[Runnable packet and retained traces](https://github.com/safal207/ContractGraph-QA/tree/evidence/x402-3758-composition-20261011/benchmarks/x402-3758).
Two fresh-process local runs each pass all three controls; the unsafe control
detects explicit caller reinvocation, not automatic repayment inside the SDK.

This complements existing already-paid receipt tests. #3260/#3349 already own the
separate paid-response validator proposal; no new hook or protocol fix is proposed.
The positive verification path is session/Ed25519, not archival verification.
All settlement counters are synthetic: no live payments or monetary effects.

Would this small composition regression fit your draft's test suite?

AI-assisted implementation and independent agent review; no upstream patch or adoption claim.
