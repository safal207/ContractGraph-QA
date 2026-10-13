# x402 #3758: preregistered buyer-composition controls

Recorded before implementation/execution, 2026-10-10 UTC.

Spine ID: x402-3758-body-composition-20261011. Exact subject:
`johnInarti/x402@4d3f2387bd3f2db8007cca324ef8dea23264c248`, draft
delivery-receipt v0.2.1. Host base:
`safal207/ContractGraph-QA@f13e586ea9118e026c69438b8c93d0585b8e38ba`.
Publication authorization: this conversation's request to continue repository
outreach and subsequent “Го”, 2026-10-11 Moscow; own evidence branch/draft and
one relevant issue contribution. No upstream production changes or merges.

Purpose: exercise the existing draft §8.4 rule at the real composition
`wrapFetchWithPayment(withDeliveryReceipts(fakeFetch, options), client)`.
This is a test/example proposal, not a newly discovered x402 protocol defect.
Adjacent #3260 already discusses a paid-response validator; do not duplicate
that hook/API proposal. Current #3758 source already tests strict missing
receipts directly, but those tests start from an already-paid request.

Included: native draft payment/receipt wrappers, deterministic public test
signers, synthetic HTTP response/directory adapter, client payload creation,
paid dispatch and synthetic settlement counters, complete body observations,
onResult and payment-response-hook order. Excluded: live HTTP/providers,
wallets, real money, SSE, distributed idempotency, crash recovery and runtime
patches. Any accidental real fetch is rejected. Stop on source movement,
equivalent composition coverage, unsupported native APIs, or new sensitive
finding requiring a separate disclosure route.

Three finite paths, fresh client/adapter/counters per case:

1. Valid receipt: unpaid request → 402 → one payload → paid dispatch → synthetic
   settlement → receipt observation → normal payment-response hook → return.
2. Missing receipt: same successful synthetic settlement and complete body →
   onResult retains decoded SettleResponse and cloned response → strict throw →
   outer evidence-aware hold. No second buyer invocation; normal payment-result
   hook is not reached. Receipt level `settlement=null` remains distinct from
   adapter-supplied `settle.success=true`.
3. Deliberately unsafe outer caller: catch the same receipt failure and invoke
   the entire buyer once more. Require two payloads/paid dispatches/synthetic
   settlements and distinct synthetic transaction identities. This is external
   consumer retry behavior, not automatic repayment inside the SDK.

State vector: sequence ordinal, buyer invocation, unpaid dispatch, payload
creation, paid dispatch, synthetic settlement, retained transaction/body,
receipt levels/reasons, normal response-hook count and final caller outcome.
Counters are recorded at the independent adapter boundary, not inferred from
the receipt verdict. Assert ordering and node state, not only the final error.
Clock: synthetic fixed receipt issuance time matched to fake verifier clock;
collection time and attempt UUID stay separate. Numeric boundaries are the
zero/one/two attempts above; no property search or wall-clock expiry claim.

Acceptance: all three assertions execute on the native source, the unsafe
control is detected, two fresh-process attempts retain raw traces, tracked
native production bytes/lockfile remain unchanged, reviewed test overlay and
closed manifest bind all report/evidence bytes. Manifest integrity is byte
identity, not receipt authority. No financial authorization derives from this
fixture. Native suites/type/lint checks are reported separately from the three
new assertions and from any CI that has not run.

Orientation: BALANCED for local synthetic execution; evidence prior to the run
is source-only. Supporting evidence is §8.4 and current wrappers/tests;
counterevidence is existing missing-receipt unit coverage and #3260 design.
Debt: no human maintainer acceptance, no production settlement witness, no
mainline adoption. Learning decision remains DEFER until execution/review.
