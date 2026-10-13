# Astra signed derived-field contradiction v0.1

**Result: 2/2 PASS; 1/1 unsafe signature-only mutant detected.**

This proof tracks [issue #196](https://github.com/safal207/ContractGraph-QA/issues/196) and exercises one narrow Astra rule:

> A cryptographically valid record must not be accepted as economic truth when deterministic derived fields contradict the primary evidence.

## Causal spine

- **spineRef:** `contractgraph.astra-crash-retry.issue-196`
- **exact subject:** two frozen synthetic Ed25519-signed economic records
- **verification backend:** OpenSSL `pkeyutl`
- **public-key SHA-256:** `7f10c178864d5d5713a9a98afea8c06ccf684e40f6a9d27b351aba8e5c8974c5`
- **mutation authority:** this proof branch only
- **merge authority:** not granted by this artifact

The proof is deliberately synthetic. It targets semantic verification after cryptographic integrity, not any live payment rail.

## Transition field

The record models this post-decision surface:

`PAYMENT ATTEMPT -> ACTUAL SETTLEMENT/FINALITY -> RECEIPT BINDING -> DELIVERY -> RECONCILIATION`

The verifier derives:

- `settled := finality == FINAL`
- `delivered := delivery == DELIVERED`
- `reconciled := settled && delivered && receipt_binding == BOUND`

A signed record may carry these fields, but the verifier does not trust them. It recomputes them from the primary evidence.

## Frozen cases

| Case | Signature | Primary evidence | Claimed derived state | Expected verdict |
|---|---|---|---|---|
| `control-consistent` | valid Ed25519 | final + bound + delivered | settled/delivered/reconciled = true | `PASS_AUTHENTICATED_SEMANTICALLY_CONSISTENT` |
| `signed-settled-contradiction` | valid Ed25519 | finality = UNKNOWN, receipt = UNKNOWN, delivery = UNKNOWN | `settled=true` | `FAIL_SIGNED_DERIVED_FIELD_CONTRADICTION` |

The negative row is important because the contradiction is itself correctly signed. Re-signing a false derived field does not make the field follow from the evidence.

## Unsafe mutant

The harness includes one intentionally unsafe verifier:

`valid signature -> ACCEPT`

That mutant accepts both records. The reference verifier rejects the contradictory record, so the mutant is detected.

This is the discriminator:

`cryptographic integrity != semantic derivation`

## Reproduce

```bash
python proofs/astra-signed-derived-field-contradiction-v0.1/harness.py \
  --write-report /tmp/astra-signed-derived-report.json

diff -u \
  proofs/astra-signed-derived-field-contradiction-v0.1/report.json \
  /tmp/astra-signed-derived-report.json
```

The hosted workflow requires byte-for-byte equality with the committed report.

## Evidence boundary

Native evidence in this proof is limited to:

- the exact frozen fixture bytes;
- their exact Ed25519 signatures;
- the committed public key;
- deterministic semantic recomputation;
- detection of the signature-only acceptance mutant.

The private signing key used to create the frozen fixtures is not committed.

## Claim ceiling

A PASS does **not** establish:

- correctness or security of Ed25519 or OpenSSL;
- correctness of a live x402, AP2, MPP, wallet, facilitator, merchant, or chain;
- that any real payment settled;
- that any real resource was delivered;
- that all receipt schemas expose enough primary evidence to recompute their derived fields;
- production safety outside these exact two synthetic records.

It proves only that, for this frozen corpus, a valid cryptographic signature is insufficient when `settled` contradicts the primary finality evidence.

## Learning harvest

- **Observation:** authenticated bytes can still encode a false deterministic conclusion.
- **Reusable invariant:** every deterministic derived economic field must be recomputed by the verifier or explicitly treated as an assertion.
- **Negative control:** signature-only acceptance.
- **Risk:** overgeneralizing the synthetic schema to real protocols without a reviewed field mapping.
- **Decision:** `PROMOTE` as a framework-neutral Astra conformance row.
- **Publication authority:** this branch/PR only; no merge or external publication is implied.

## Next boundary

Bind the same rule to a real public receipt/certificate corpus only after the exact source bytes, schema, signer authority, and primary-to-derived field mapping are independently pinned.
