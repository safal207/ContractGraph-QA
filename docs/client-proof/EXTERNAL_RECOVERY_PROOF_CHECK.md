# External Recovery Proof Check

**One financial operation. One ambiguous result. One evidence-backed retry decision.**

Payment, wallet, payout, ledger, and agentic-commerce systems often have several locally correct signals:

- a policy decision says the action was allowed;
- an API says the request was accepted;
- a receipt or chain event says value may have moved;
- a webhook says a provider state changed;
- an internal ledger shows a posting.

Those signals do not automatically answer the consequential recovery question:

> **Before another monetary action is permitted, can the earlier logical operation be classified as `ZERO`, `ONE`, or `UNKNOWN` economic effects using declared authoritative evidence?**

```text
intent / mandate
→ policy or authorization
→ execution attempt
→ timeout, lost response, delayed event, or conflicting status
→ external evidence
→ ledger and reconciliation state
→ ZERO / ONE / UNKNOWN
→ retry, stop, or hold
```

## Decision contract

| Classification | Evidence meaning | Permitted decision |
|---|---|---|
| `ZERO` | Authoritative evidence proves no economic effect | A controlled retry may be allowed under the same logical operation and policy |
| `ONE` | Authoritative evidence proves the intended economic effect | Stop; do not create another monetary action |
| `UNKNOWN` | Evidence is missing, delayed, stale, conflicting, or non-authoritative | Fail closed; hold the retry until reconciliation resolves the state |

Core invariants:

```text
one authorized intent → at most one intended economic effect
UNKNOWN outcome → no blind retry
retry → same logical operation identity + explicit evidence ancestry
```

## What the client receives

For one named recovery boundary:

1. A confirmed one-page [Recovery Boundary Brief](BOUNDARY_BRIEF.md).
2. An evidence map stating what each status, event, receipt, webhook, or ledger record can and cannot prove.
3. A local or sandbox-backed executable fixture.
4. Positive, negative, duplicate, delayed, out-of-order, retry, and identity-drift cases.
5. A deterministic `PASS`, `FAIL`, or `BLOCKED` result with replay instructions.
6. A minimized counterexample when an unsafe path is reachable.
7. Bounded remediation guidance.
8. One exact-path retest for an in-scope fix delivered within 14 calendar days.

`BLOCKED` is not converted into `PASS`. Missing evidence remains explicit verification debt.

## Public proof signals

These are public engineering signals, not client endorsements or full-platform audit claims.

### 1. External review changed a public evidence design

In [x402 Foundation issue #3379](https://github.com/x402-foundation/x402/issues/3379), a bounded review requested exact record membership, algorithm-specific hash handling, honest source labels, cross-purchase substitution controls, and explicit non-claims.

The external project then published a pairing fixture, separated SHA-256 from Keccak-256, labeled fields as simulated, observed, or derived, added tamper-negative controls, and reported a 20/20 aggregate control suite. A later independent replay confirmed the published positive checks and tamper rejections while retaining the limits: record/byte integrity and binding do not independently establish settlement finality, buyer acceptance, effect count, or exactly-once execution.

### 2. A neighboring review surfaced a real read-path defect

The same public discussion asked whether an append-only claim ledger reverified signatures when reading records. The adjacent `capacity-attest` project reported that its read path had checked the shape of `claimId` and `signature`, but not signature validity, so a directly inserted ledger record could be returned as genuine. The project reported the defect fixed in version 0.4.0 by re-verifying every claim on read.

This was not an x402 core defect. It is evidence that a narrow external question can reveal a concrete verification gap without inflating the claim boundary.

### 3. Bounded live wallet-watch recovery evidence

[resonance-arbitrage-graph PR #85](https://github.com/safal207/resonance-arbitrage-graph/pull/85) records bounded live checks against existing public Ethereum USDC transfers. Separate transaction and block-scan paths observed one event and one local notification; ordinary restart and replay added zero events and zero notifications. A second recent-block scenario resumed from a durable checkpoint, advanced one block, and replayed the original transfer without adding another event.

The published limits remain explicit: one RPC provider, no independent consensus or completeness proof, no continuous-watch certification, and no exactly-once delivery claim.

### 4. Reusable recovery benchmark and evidence bundles

[ContractGraph-QA](../../README.md) ships a vendor-neutral agent-payment recovery benchmark, deterministic evidence bundles, negative controls, provenance binding, and independent bundle verification. Its central distinction is:

```text
logical operation identity
≠ concrete attempt
≠ idempotency identity
≠ policy decision
≠ provider state
≠ external economic evidence
≠ internal ledger state
≠ reconciliation decision
```

## Commercial terms

| Item | Term |
|---|---|
| Scope | One named ambiguous-outcome recovery boundary |
| Fixed price | **$1,000** |
| Payment | **$500 upfront** after written scope agreement; **$500 within 3 business days after acceptance** of the initial evidence pack |
| Delivery | Five business days after written scope agreement, required non-sensitive inputs or authorized sandbox/test access, and upfront payment |
| Effort cap | Up to 12 hours: 10 hours for the initial package and 2 hours for one bounded retest |
| Communication | Email-only and asynchronous |
| Production access | Not required for the initial public-documentation, synthetic, local, or sandbox-backed fixture |

A second provider, rail, wallet, ledger, or independently modeled business operation requires a separate scope.

## Explicit exclusions

The pilot does not include:

- active testing against production without separate written authorization;
- real-money transfers or use of customer data;
- a full-platform security, compliance, legal, or financial certification;
- implementation of the product fix;
- a new production connector;
- public disclosure of client material;
- a claim that bounded testing proves the wider system secure.

## Start with one sentence

Reply by email with one boundary in this shape:

> When `[action]` returns an ambiguous result, which evidence must close logical operation `[O]` before `[retry, fallback, release, replacement credential, or other monetary action]` is permitted?

Public documentation, synthetic traces, status definitions, webhook schemas, and a declared authority rule are enough to begin the Boundary Brief. No production credentials or real-value transaction are required for the initial fixture.

---

> **Each external proof lowers the cost of the next trust decision — only when every proof is bound to the same logical operation and its claim boundary remains explicit.**
