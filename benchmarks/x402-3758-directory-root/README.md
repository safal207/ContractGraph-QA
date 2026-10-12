# x402 #3758: frozen production-directory root experiment

The published epoch-1 directory's root **independently recomputes** from the
exact seven-field projection required by §7.2. This fixture does not reproduce a
producer root-generation defect. The five alternative preimages reported in
comment 6103479775 omit the normative projection or retain the root being
computed. Their failure is therefore consistent with the normative algorithm.

This is a separate offline commitment experiment, not the three synthetic
repayment/client-wrapper checks associated with the earlier
`benchmarks/x402-3758` evidence and [CGQA PR #211](https://github.com/safal207/ContractGraph-QA/pull/211).
The two evidence sets answer different questions and do not inherit each
other's verdicts. At the CGQA base used here, that older benchmark was not
present on main; this change does not copy, alter, or merge it.

## Reproduce without network or installed packages

Requirements: Node 22 or 24 and Python 3.12. Only built-in modules are used.

```sh
node --test benchmarks/x402-3758-directory-root/directory-root.test.mjs
python3 benchmarks/x402-3758-directory-root/oracle.py
python3 benchmarks/x402-3758-directory-root/oracle.py --preimage > /tmp/x402-directory-preimage.json
```

The Node suite executes the Python witness and compares preimage bytes, rather
than accepting only agreement on a copied published root. Override `PYTHON`
with the desired Python executable when necessary. Commands read frozen
fixtures; they do not call the paid route, a key-directory URL or a Polygon RPC.
The ordinary Python command exits nonzero on a root mismatch; `--preimage`
is a byte-producing calculator used to compare both positive and mutated inputs.
CI uses Node 22 and 24 with pinned action revisions in the focused
[workflow](../../.github/workflows/x402-directory-root.yml). Local execution is
not a claim that remote CI has completed.

## Exact normative input

Source: [johnInarti/x402 §7.2 at commit 4d3f238](https://github.com/johnInarti/x402/blob/4d3f2387bd3f2db8007cca324ef8dea23264c248/specs/extensions/delivery-receipt.md#72-format).

```text
root = lowercase_hex(SHA-256(JCS({
  spec, issuer, epoch, prevRoot, publishedAt, governanceKeys, keys
})))
```

Before serialization, `governanceKeys` is sorted by `alg`, `keys` by `kid`.
JCS sorts object member names recursively; it does not itself sort array
elements. All members of each selected nested key object remain committed.
The top-level `root` and `signatures` are absent from the preimage.

`computeDirectoryRoot` in the producer source at that commit selects the same
seven members and sorts those two arrays before invoking `canonicalJson`.
This static source mapping does not independently identify which build was
deployed at the HTTP endpoint.

| Value | Independent result |
|---|---|
| Preimage byte length | 5906 |
| SHA-256 preimage | `9daec3d9df75826056ba182b0c176e6684b85aab723a59efbd4d75f4c999e538` |
| Published `directory.root` | Equals independently recomputed value |
| Receipt's `keyDirectoryDigest` | Equals independently recomputed value |
| Receipt's directory epoch | 1, same as frozen directory |
| Independent Python preimage | Byte-identical to Node preimage |

## Five alternative projections, reproduced

The external comment published digest prefixes. The suite independently
computes and freezes their full digests for the same raw directory.

| Preimage | SHA-256 |
|---|---|
| Whole document except `signatures`, still including `root` | `8e1a7c87d6cd1bf355b8abdf980cfba00dcfa8b3b7f26f1c4ffc797f6f0682d9` |
| Whole document | `eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f` |
| `keys` only | `35c3b77cba0189961d74694ab5769dc935345ca5ff781b443125c095b77b7e93` |
| `governanceKeys` only | `f7d6db30c01f3d00617595794dc27a34e4ba3b03832c1ede9222c2f561c1b309` |
| `{epoch,keys,governanceKeys}` | `6cb9ae03d3f459e9ddc4b7f7c642ebc75b907c01e9e4e90405178f1e8572e016` |

Neither a failed alternative projection nor equality with the published
`root` independently answers the normative recomputation question. The exact
projection does answer it for this frozen epoch.

## Frozen observation provenance

Public data, saved byte-for-byte from the two URLs on 2026-10-11 by the parent
investigation; see [REPORT.md](REPORT.md) for capture context and capability
classification.

| Fixture | Public source | Raw-byte SHA-256 |
|---|---|---|
| `fixtures/directory.json`, 10563 bytes | [Published directory](https://fractalai.net.co/.well-known/x402-receipt-keys) | `eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f` |
| `fixtures/receipt.json` | [Published receipt](https://fractalai.net.co/x402/receipts/77795afae30c36075ed22e6593e28d0b4d7ae24c23acebfdcf8e0c0dc494b5fb) | `91c153cb2bd6e8789209f896783d669e7c3a4f14230af911a370c380418fb654` |

Source discussion:
[x402 #3758](https://github.com/x402-foundation/x402/issues/3758),
[independent comment 6103479775](https://github.com/x402-foundation/x402/issues/3758#issuecomment-6103479775).
Fixtures are public response data; no upstream implementation is imported or
executed. The independent witnesses share the same frozen observation: their
serialization independence does not add a second collection provenance.

## Test coverage and boundaries

The finite suite covers exact snapshot hashes, projection membership,
recursive object order, every combination of the two array reversals,
nonmutation, repeated calculation, every committed top-level member, all 20
existing nested governance/key members, absent-versus-null values, all five
alternative preimages, and false published-root rejection. Separate Ed25519
checks verify the receipt and directory signatures and reject one-bit
message/signature changes. A changed signature may leave the root unchanged;
the signature check still rejects it.

Both serializers deliberately support a guarded RFC 8785-compatible domain:
ASCII strings and member names, ECMAScript safe integers excluding negative
zero, booleans, null, arrays and plain JSON objects. Node rejects unsupported
runtime values; Python additionally rejects duplicate JSON members and
noninteger number tokens during parse. This is enough for these captured
bytes and all declared mutations. It is **not** a general JCS library,
strict Node JSON parser, full schema validator or whole-protocol conformance
test. A missing nested lifecycle field can still be hashed as changed data;
that does not declare the modified directory well-formed.

- Ed25519 verification does not authenticate ML-DSA-65. ML-DSA cryptographic
  verification is explicitly `NOT_RUN`, despite fields being present.
- A valid hash or signature does not establish out-of-band governance-key
  trust, issuer authorization, full directory-chain validity, rollback
  protection, or temporal key authorization.
- The receiptId is independently reproduced; the raw receipt digest is a
  fixture-integrity check, not validation of a missing transport reference.
- No delivered response body was captured. `delivery.sha256` and actual
  content delivery remain unverified; a receipt alone does not prove delivery.
- No Polygon RPC is called. This suite does not independently repeat the
  external researcher's on-chain claims or establish payment finality.
- No paid call, retry, duplicate settlement, crash/recovery or future epoch is
  exercised here. The result is historical and snapshot-specific.

Learning decision: **PROMOTE** this narrowly scoped regression fixture and
mutation controls, supported by independent byte agreement and rejecting
negative controls. **DEFER** broader trust, lifecycle, chain, post-quantum,
delivery and payment claims. See [PLAN.md](PLAN.md) and [REPORT.md](REPORT.md).
