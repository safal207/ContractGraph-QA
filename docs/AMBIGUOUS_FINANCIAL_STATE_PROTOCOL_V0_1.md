# Ambiguous Financial State Protocol (AFSP) v0.1

AFSP is a provider-neutral continuation contract for autonomous systems that can move money.

Its purpose is narrow: when an external effect may already have happened but the caller cannot yet prove the outcome, **ambiguity must not become permission for another monetary action**.

## Core path

```text
INTENT
  ↓
ACTION ATTEMPT
  ↓
AMBIGUOUS OUTCOME
  ↓
DISCOVERY
  ↓
CANONICAL STATE
  ↓
SETTLEMENT / FAILURE EVIDENCE
  ↓
CONTINUATION AUTHORIZATION
```

The last transition is the important one. Evidence that a prior action failed, succeeded, or remains unresolved is not itself authority to perform a new action.

## Invariants

### AFSP-1 — Preserve logical identity

A transport failure must not silently create a second logical financial operation.

```text
response lost != operation did not happen
```

Retry/discovery mechanisms that preserve a provider idempotency identity belong to the original logical operation unless the provider contract explicitly says otherwise.

### AFSP-2 — Ambiguity blocks new money

If the prior monetary outcome is not canonically reconciled, another monetary action is forbidden.

```text
payment.reconciliationStatus != final
→ monetaryActionAllowed = false
```

### AFSP-3 — Notification is not canonical state

Webhook/event delivery may trigger reconciliation but must not automatically outrank the provider's canonical state surface.

At-least-once delivery also requires event deduplication independently of financial-operation deduplication.

### AFSP-4 — Settlement evidence is not discovery authority

An on-chain transaction identifier, ledger receipt, or settlement record can prove an observed effect after it exists. Its absence before publication/broadcast does not prove that no operation was created.

### AFSP-5 — Final failure does not imply retry authority

A canonical `failed` outcome settles the status of the prior attempt. It does not automatically authorize a fresh spend.

```text
final / failed
+ retry semantics unresolved
→ HOLD
→ monetaryActionAllowed = false
```

### AFSP-6 — Authority is independent of provider state

Provider evidence answers what happened. Authority evidence answers whether the actor may act.

```text
provider state != actor authority
```

Revoked, expired, or unknown authority remains fail-closed even if the provider reports success/failure cleanly.

### AFSP-7 — Provenance cannot gain authority by composition

AFSP distinguishes:

```text
DOCUMENTED GUARANTEE
VENDOR CLARIFICATION
DERIVED INTEGRATION RULE
LOCAL POLICY
```

A derived rule may be safe and useful, but it must not be relabeled as a provider guarantee.

## Decision mapping

AFSP reuses the Unified Agent Payment Decision Gate rather than creating a second decision engine.

| State | Decision | New monetary action |
|---|---|---|
| authorized + not started | `ALLOW` | yes |
| pending / unknown / nonfinal | `RECONCILE` | no |
| committed | `STOP` | no |
| failed + retry authority unresolved | `HOLD` | no |
| failed + explicit documented retry authority | `ALLOW` | yes |
| authority revoked / expired | `STOP` | no |
| authority unknown | `HOLD` | no |

## Crossmint profile — first external instantiation

Crossmint provides the first reviewed AFSP profile in this repository:

```text
create with x-idempotency-key
→ timeout
→ preserve same logical operation
→ same-key replay for discovery
→ GET transaction for canonical state
→ poll until terminal
→ webhook only triggers reconciliation
→ onChain.txId is settlement evidence after broadcast
→ new monetary action still requires separate retry authority
```

The reviewed profile records:

- same-key replay: documented;
- GET transaction: authoritative for finality;
- webhook: non-authoritative notification evidence;
- complete timeout precedence: not published as a normative standalone rule;
- new-operation retry authority after terminal failure: unresolved.

Therefore Crossmint timeout recovery can be modeled without treating the derived composition as a provider guarantee.

## Negative cases

AFSP must reject at least these shortcuts:

```text
timeout → assume failed → create a fresh payment
missing webhook → assume no payment happened
onChain.txId == null → assume transaction does not exist
webhook succeeded → skip canonical reconciliation
terminal failed → infer permission to spend again
provider success → infer actor authority
```

## Scope

AFSP is an integration-verification contract. It does not authorize production execution, establish compliance, certify a provider, or claim a vulnerability.

The same contract can be instantiated for card payments, wallets, stablecoin rails, escrow, payouts, bridges, x402 flows, and other systems where autonomous software can create financial side effects.
