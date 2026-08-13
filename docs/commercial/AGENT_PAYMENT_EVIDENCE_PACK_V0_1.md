# Agent Payment Evidence Pack v0.1

A compact customer-facing proof artifact for one question:

> **May this agent safely make another monetary action now?**

The pack composes the Unified Agent Payment Decision Gate into a deterministic ZIP that can be shared with a client without requiring them to understand the full ContractGraph-QA architecture.

## Pack contents

```text
agent-payment-evidence.zip
├── input.json
├── decision.json
├── customer-summary.md
└── manifest.json
```

- `input.json` — canonical normalized authority / payment / retry / fulfillment state;
- `decision.json` — machine decision from the unified gate;
- `customer-summary.md` — short human explanation, causal chain and next proof;
- `manifest.json` — SHA-256 + byte length for every content artifact.

The ZIP uses fixed entry metadata and canonical JSON, so the same input produces the same bytes and the same pack SHA-256.

## Demo scenario

The bundled demo represents a generic synthetic failure-recovery boundary:

```text
agent authorized
→ payment attempt
→ final response lost / timeout
→ payment independently reconciled as COMMITTED
→ fulfillment remains UNKNOWN
→ new payment is NOT allowed
→ decision = RECONCILE
```

This is intentionally provider-neutral and synthetic. It is not a claim about Crossmint, PayRam, x402, or any production provider.

## Build

```bash
cgqa agent-payment-evidence-pack \
  --input benchmarks/agent-payment-recovery-v0.1/customer-evidence-pack/demo-timeout-settled-fulfillment-unknown.json \
  --output /tmp/agent-payment-evidence.zip
```

Expected decision:

```text
decision = RECONCILE
monetaryActionAllowed = false
```

## Verify independently

```bash
cgqa verify-agent-payment-evidence-pack /tmp/agent-payment-evidence.zip
```

Verification does two things:

1. recomputes each declared content hash and byte length;
2. recomputes the Agent Payment Decision from packed `input.json` and requires it to match `decision.json` and the manifest.

A pack therefore cannot be made to say `ALLOW` by editing the rendered decision while leaving the source state unchanged.

## Customer reading path

The first file a customer needs is `customer-summary.md`. It gives:

- executive verdict;
- whether another monetary action is allowed;
- authority → payment → retry → fulfillment → decision chain;
- exact blocking coordinate;
- the next evidence required to move forward;
- scope boundary.

The JSON files are retained for reproducibility and machine verification.

## Product boundary

This pack is a deterministic evidence/communication artifact, not a wallet, payment executor, security certification, legal opinion or production authorization. It performs no network calls and moves no funds.

The commercial path is:

```text
captured evidence
→ normalized state
→ unified decision gate
→ customer evidence pack
→ client review
→ next discriminating evidence / remediation
```
