# Ambiguous Outcome Recovery Pilot

**One financial operation. One ambiguous result. One bounded proof of whether retry is safe.**

This fixed-scope pilot is for payment, wallet, payout, stablecoin, on/off-ramp, ledger, and agentic-commerce teams that need a deterministic answer after a timeout, lost response, delayed webhook, conflicting state, or fallback.

## Design-partner terms

| Item | Terms |
|---|---|
| Price | **$750 fixed** |
| Scope | One named recovery boundary |
| Delivery target | Five business days after accepted scope and inputs |
| Communication | Async by default |
| Retest | One bounded retest for an in-scope fix delivered within 14 calendar days |
| Production access | Not required for the initial synthetic or sandbox-backed fixture |

The price applies only to the bounded scope below. A second provider, rail, wallet, ledger, or independently modeled business operation requires a separate scope.

## The decision the pilot verifies

Before another monetary attempt is permitted, can the system classify the earlier logical operation as:

| Outcome | Required action |
|---|---|
| `ZERO` — authoritative evidence proves no economic effect | Retry may be allowed under the same logical operation and policy |
| `ONE` — authoritative evidence proves the intended economic effect | Stop; do not create another monetary action |
| `UNKNOWN` — evidence is delayed, incomplete, conflicting, or non-authoritative | Fail closed; block retry until reconciliation resolves the state |

Core invariants:

```text
one authorized intent → at most one economic effect
UNKNOWN outcome → no new financial action
retry → same logical operation identity + explicit evidence ancestry
```

## Typical pilot boundary

```text
intent / mandate
→ policy or authorization ALLOW
→ execution dispatched
→ timeout or ambiguous acknowledgement
→ provider / rail / wallet / chain / ledger evidence arrives
→ classify ZERO / ONE / UNKNOWN
→ retry, stop, or hold
→ deterministic evidence pack
```

The pilot covers **one named recovery boundary**, not the whole platform.

Examples:

- AI-agent checkout after an uncertain processor response;
- wallet payment after dispatch timeout;
- payout retry across provider, destination rail, and accounting ledger;
- payment-orchestration fallback from one rail to another;
- fiat debit plus irreversible crypto delivery;
- mint, burn, bridge, or cross-chain execution with delayed off-chain reconciliation.

## Included

1. Map the declared states, identities, and evidence contract.
2. Identify authoritative evidence surfaces and their precedence.
3. Define the `ZERO / ONE / UNKNOWN` recovery state machine.
4. Implement or adapt one local or sandbox-backed executable fixture.
5. Run positive, negative, duplicate, delayed, out-of-order, retry, and identity-drift cases.
6. Produce deterministic results and a bounded findings report.
7. Provide one in-scope retest when a fix is supplied within the retest window.

## Minimum test matrix

| Case | Expected result |
|---|---|
| Dispatch never occurred | `ZERO`; retry may be allowed |
| Dispatch occurred; committed evidence arrives | `ONE`; retry blocked |
| Provider proves explicit failure with no economic effect | `ZERO`; retry may be allowed |
| Timeout with no authoritative close-out evidence | `UNKNOWN`; retry blocked |
| Duplicate webhook or event delivery | No duplicate economic side effect |
| Out-of-order evidence | Arrival order must not incorrectly override evidence authority |
| Retry under a new logical operation identity | Reject or classify as a separately authorized operation |
| Retry with changed idempotency identity where continuity is required | Reject |
| Internal ledger says success while the external leg remains unresolved | `UNKNOWN` unless the declared contract makes the ledger authoritative |
| External leg succeeds while local state remains stale | `ONE`; local state must converge without another payment |

## Deliverables

- **Expected-state contract** — the smallest state machine preserving the recovery guarantee;
- **Evidence map** — what each status, webhook, receipt, chain event, or ledger record can and cannot prove;
- **Executable fixture** — one local or sandbox-backed scenario;
- **Invariant report** — deterministic outcomes and violation codes;
- **Counterexample** — minimized trace for a reachable unsafe retry or false-finality path;
- **Remediation guidance** — bounded changes to identity, hold, reconciliation, or evidence precedence rules;
- **Retest evidence** — exact-path replay plus alternate-path review for one in-scope fix.

## Inputs required

The pilot can begin with public or non-sensitive material:

- API or product documentation;
- state and status definitions;
- webhook or event schemas;
- idempotency and retry contract;
- synthetic traces or sandbox examples;
- a short statement of which system is intended to be authoritative.

Production credentials, customer data, and real-value transactions are not required for the initial fixture.

## Acceptance criteria

The pilot is complete when:

- every retry decision maps to explicit evidence;
- `UNKNOWN` is represented as a first-class state rather than inferred from silence;
- the same trace produces the same classification and verdict on replay;
- one logical operation cannot create a second economic effect through an unresolved retry path;
- identity continuity and authority ancestry are preserved across attempts;
- all claims remain bounded to the supplied model, evidence, adapter, and environment.

## Good fit

- The team can name one disputed retry, fallback, wallet, payout, settlement, or reconciliation boundary.
- At least one public, synthetic, sandbox, or authorized evidence surface is available.
- The desired result is a reproducible fixture and bounded evidence, not a blanket certification.

## Not a fit

- The request is for an unbounded audit of the entire platform.
- No explicit testing authorization exists for active production access.
- The goal is live exploitation, fund movement, or collection of customer data.
- The team expects a webhook or internal status to be treated as authoritative without declaring why.

## Existing executable foundation

The pilot is backed by the vendor-neutral [Agent Payment Recovery Benchmark v0.1](benchmarks/agent-payment-recovery-v0.1/README.md), including seed cases for:

- committed outcome followed by stop;
- failed outcome followed by retry under the same logical operation identity;
- retry before reconciliation;
- idempotency drift across retry.

See the [synthetic buyer-readable case study](docs/case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md).

## Start with one question

> After dispatch returns an ambiguous result, which evidence is authoritative before another monetary attempt is permitted: platform state, external rail, processor or wallet receipt, customer ledger, or an explicit `UNKNOWN` reconciliation hold?

A one-line answer is enough to define the first boundary.

[Discuss one bounded pilot](mailto:safal0645@gmail.com?subject=Ambiguous%20Outcome%20Recovery%20Pilot) · [View the engine](README.md)

## Scope and assurance boundary

This pilot does not certify an entire payment platform and does not assume that any status, webhook, receipt, ledger record, or chain observation is authoritative without a declared contract or authorized evidence review.

Results remain bounded to the supplied model, evidence, adapter, environment, and executed test scope.
