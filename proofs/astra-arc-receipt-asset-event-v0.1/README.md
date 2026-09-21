# Astra Arc receipt asset-event acquisition v0.1

**Status: ACQUISITION / EVIDENCE_INCOMPLETE until the exact receipt artifact is captured and pinned.**

Tracks [issue #206](https://github.com/safal207/ContractGraph-QA/issues/206).

## Subject

Read-only acquisition for Arc mainnet transaction:

`0xf38fb9962dbee2fc35bd156140bd623d3ce74b92efdcf6a50c5869126c0b6273`

Public motivation:

- x402 discussion: https://github.com/x402-foundation/x402/issues/3504
- buyer-side report: https://github.com/x402-foundation/x402/issues/3504#issuecomment-5748043533
- mirror-event confirmation: https://github.com/x402-foundation/x402/issues/3504#issuecomment-5726132323

The public report says this paid call settled `0.007 USDC`, returned HTTP 200, and its receipt contains both the expected USDC transfer event and an Arc native-balance mirror transfer event that appears first with the amount scaled by `10^12`.

Those prose reports justify the investigation. They are **not** substituted for the exact receipt bytes.

## Goal

Acquire the immutable transaction/receipt response from a public read-only Arcscan surface and freeze enough provenance to build the #196 row:

`FAIL_RECEIPT_ASSET_EVENT_AMBIGUITY`

The later proof must discriminate:

- a reference verifier that binds the expected payment asset contract and the applicable authorization/party/amount fields;
- an unsafe mutant that accepts the first transfer-like event without constraining `log.address`.

## Acquisition gate

The script fetches:

- `https://api.arc-scan.org/v1/chain`
- `https://api.arc-scan.org/v1/txs/<tx>/raw`

and writes:

- exact raw response bytes;
- canonical JSON copies;
- SHA-256 and byte counts;
- source URLs and capture time;
- all receipt-like log addresses in observed order.

It fails closed if:

- Arc chain id is not `5042`;
- the raw response does not contain the pinned tx hash;
- no receipt-like logs are present.

## Run

```bash
python proofs/astra-arc-receipt-asset-event-v0.1/acquire_receipt.py \
  --out-dir /tmp/astra-arc-receipt
```

This is intentionally **not** yet a deterministic proof run. The acquisition artifact is uploaded by CI for inspection before any fixture is committed.

## Evidence boundary

The acquisition itself establishes only that exact bytes were retrieved from the declared public source at a recorded time.

It does not establish:

- that the first transfer event is or is not the actual payment;
- payer/payTo/amount/nonce binding;
- delivery correctness;
- facilitator correctness;
- protocol-wide safety;
- correctness of Arcscan as an oracle.

## Stop condition

If the exact public receipt cannot be retrieved reproducibly, stop at:

`EVIDENCE_INCOMPLETE`

Do not reconstruct logs from narrative comments.

## Next phase

After a successful acquisition:

1. inspect and pin the exact raw/canonical artifact;
2. independently identify the expected payment event;
3. freeze a minimal receipt fixture with provenance;
4. implement reference and topic-only mutant decoders;
5. require the reference verifier to reject any event from the mirror contract as payment evidence;
6. only then publish a bounded PASS/FAIL report.
