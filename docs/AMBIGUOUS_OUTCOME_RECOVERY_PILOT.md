# Ambiguous Outcome Recovery Pilot

**One financial operation. One ambiguous result. One bounded proof of whether retry is safe.**

This pilot turns a single retry/reconciliation boundary into an executable, evidence-backed verification fixture.

It is designed for agent payments, programmable wallets, card or bank payouts, payment orchestration, on/off-ramp flows, stablecoin operations, and other systems where a lost or ambiguous response can cause a second monetary action.

## The buyer problem

A local signal can be correct without proving the final economic outcome:

- a policy engine can prove that an action was allowed;
- a credential layer can prove that capacity was reserved;
- an API can prove that a request was accepted;
- a webhook can prove that a provider state changed;
- a ledger can prove that one internal posting exists.

None of those signals alone necessarily proves whether the full economic effect occurred **zero times, once, or remains unresolved across system boundaries**.

The dangerous state is:

```text
request dispatched
→ response lost or ambiguous
→ economic outcome not yet proven
→ another attempt becomes possible
```

## Core proof obligation

For one logical financial operation, the system must classify the outcome before another monetary action is permitted:

| Evidence-backed outcome | Required decision |
|---|---|
| `ZERO` — authoritative evidence proves no economic effect | Retry may be allowed under the original logical operation and policy |
| `ONE` — authoritative evidence proves the intended economic effect | Stop; do not create another monetary action |
| `UNKNOWN` — evidence is incomplete, conflicting, delayed, or non-authoritative | Fail closed; block retry until reconciliation resolves the state |

Core invariants:

```text
one authorized intent → at most one economic effect
```

```text
UNKNOWN outcome → no new financial action
```

```text
retry → same logical operation identity + explicit evidence ancestry
```

## Canonical pilot scenario

```text
intent created
→ authority or policy ALLOW
→ execution attempt dispatched
→ response lost / timeout / ambiguous acknowledgement
→ provider, rail, wallet, or ledger evidence arrives late, duplicated, or out of order
→ system classifies ZERO / ONE / UNKNOWN
→ retry is allowed, stopped, or held
→ deterministic evidence pack records the decision
```

The candidate system may use different names. The pilot preserves the semantic distinctions between:

- logical operation identity;
- concrete execution attempt;
- idempotency or replay identity;
- policy/authority decision;
- provider state;
- external economic evidence;
- internal ledger state;
- reconciliation state;
- retry permission.

## Fixed scope

The pilot covers **one named recovery boundary**, for example:

- agent checkout after an uncertain processor response;
- wallet payment after dispatch timeout;
- payout retry across provider, destination rail, and accounting ledger;
- payment-orchestration fallback from one rail to another;
- fiat debit plus irreversible crypto delivery;
- mint, burn, bridge, or cross-chain operation with delayed off-chain reconciliation.

The engagement includes:

1. map the declared state and evidence contract;
2. identify the authoritative evidence surfaces and their precedence;
3. define the `ZERO / ONE / UNKNOWN` state machine;
4. implement or adapt one synthetic executable fixture;
5. run positive, negative, retry, duplicate, delayed, and out-of-order cases;
6. produce deterministic results and a bounded findings report.

## Minimum test matrix

| Case | Expected result |
|---|---|
| Dispatch never occurred | `ZERO`; retry may be allowed |
| Dispatch occurred; committed evidence arrives | `ONE`; retry blocked |
| Provider reports explicit failure with no economic effect | `ZERO`; retry may be allowed |
| Timeout with no authoritative close-out evidence | `UNKNOWN`; retry blocked |
| Duplicate webhook or event delivery | No duplicate economic side effect |
| Out-of-order evidence | Newer arrival must not override stronger authoritative evidence incorrectly |
| Retry under a new logical operation identity | Reject or classify as a new separately authorized operation |
| Retry with changed idempotency identity where continuity is required | Reject |
| Internal ledger says success but external leg is unresolved | `UNKNOWN` unless the declared contract makes the ledger authoritative |
| External leg succeeds but local state is stale | `ONE`; local recovery must converge without another payment |

## Deliverables

- **Expected-state contract** — the smallest state machine that preserves the recovery guarantees;
- **Executable fixture** — a local or sandbox-backed scenario using the ContractGraph-QA recovery model;
- **Evidence map** — what each status, receipt, webhook, chain event, or ledger record can and cannot prove;
- **Invariant report** — deterministic pass/fail results with violation codes;
- **Counterexample** — minimized trace for any reachable unsafe retry or false finality path;
- **Remediation guidance** — bounded changes to identity, hold, reconciliation, or evidence precedence rules.

## Inputs required

The pilot can begin with public or non-sensitive material:

- API or product documentation;
- state/status definitions;
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

## What the pilot does not claim

The pilot does not prove that an entire payment platform is secure or correct. It does not assume that a webhook, status endpoint, blockchain observation, or ledger record is authoritative without a declared contract or authorized evidence review.

It verifies one recovery boundary and states the remaining uncertainty explicitly.

## Existing executable foundation

This pilot is backed by the vendor-neutral [Agent Payment Recovery Benchmark v0.1](../benchmarks/agent-payment-recovery-v0.1/README.md), including seed cases for:

- committed outcome followed by stop;
- failed outcome followed by retry under the same operation identity;
- retry before reconciliation;
- idempotency drift across retry.

## First technical question

A useful first question for a product or reliability team is:

> After dispatch returns an ambiguous result, which evidence is authoritative before another monetary attempt is permitted: the platform state, the external rail, the wallet or processor receipt, the customer ledger, or an explicit `UNKNOWN` reconciliation hold?

A one-line answer is enough to define the first pilot boundary.
