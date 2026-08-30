# Recovery Design Partner Lab

**One financial operation. One ambiguous result. One bounded evidence pack for the retry decision.**

The Lab accepts at most **five design partners**. Each partner brings one real recovery boundary; together we confirm its business promise, evidence contract, and consequential decision before ContractGraph-QA builds the fixture. The result is a deterministic classification within the agreed model and evidence, not a blanket claim about the full platform.

## Design-partner terms

| Item | Terms |
|---|---|
| Lab capacity | Maximum **5 design partners** |
| Price | **$750 fixed per one-boundary pilot** |
| Scope | One named ambiguous-outcome recovery boundary |
| Delivery target | Five business days after the Boundary Brief and required inputs are accepted |
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

## How the Lab works

```text
question
→ mirror boundary
→ confirm Boundary Brief
→ paid fixture
→ evidence pack
→ bounded retest
→ product learning
```

The first answer starts the conversation; it does not silently define the scope. ContractGraph-QA mirrors the boundary in the [one-page Recovery Boundary Brief](docs/client-proof/BOUNDARY_BRIEF.md), and the client confirms three async checkpoints:

| Checkpoint | Client confirms | ContractGraph-QA freezes |
|---|---|---|
| **Promise** | Business promise, ambiguous action, duplicate-risk retry, identity, and scope | One named boundary and explicit exclusions |
| **Evidence** | Evidence surfaces, freshness, authority, precedence, and what remains unresolved | Evidence map, assumptions, counterevidence, and `UNKNOWN` conditions |
| **Decision** | What `ZERO`, `ONE`, and `UNKNOWN` permit or block, and the impact of a wrong or delayed decision | Expected-state contract and fixture acceptance cases |

`TBD`, conflicting evidence, or silence does not pass a checkpoint. It remains explicit verification debt or `UNKNOWN` until resolved.

## Included

1. Mirror and confirm the one-page Boundary Brief.
2. Map the declared states, identities, and evidence contract.
3. Identify authoritative evidence surfaces and their precedence.
4. Define the `ZERO / ONE / UNKNOWN` recovery state machine.
5. Implement or adapt one local or sandbox-backed executable fixture.
6. Run positive, negative, duplicate, delayed, out-of-order, retry, and identity-drift cases.
7. Produce deterministic results and a bounded findings report.
8. Provide one in-scope retest when a fix is supplied within the retest window.

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
| Authoritative evidence proves the external leg succeeded while local state remains stale | `ONE`; local state must converge without another payment |

## Deliverables

- **Confirmed Boundary Brief** — the shared Promise, Evidence, and Decision contract for one boundary;
- **Expected-state contract** — the smallest state machine preserving the recovery guarantee;
- **Evidence map** — what each status, webhook, receipt, chain event, or ledger record can and cannot prove;
- **Executable fixture** — one local or sandbox-backed scenario;
- **Invariant report** — deterministic outcomes and violation codes;
- **Counterexample** — minimized trace for a reachable unsafe retry or false-finality path;
- **Remediation guidance** — bounded changes to identity, hold, reconciliation, or evidence precedence rules;
- **Retest evidence** — exact-path replay plus alternate-path review for one in-scope fix.

## Product learning after the retest

The close-out asks:

1. Did the mirrored boundary match the real business promise and duplicate-risk decision?
2. Which evidence surface or authority assumption changed during the fixture review?
3. Which `ZERO / ONE / UNKNOWN` case changed or clarified an operational decision?
4. Which exact trace should remain a client regression?
5. What remains client-specific, unresolved, or outside the verified scope?
6. Did a vendor-neutral invariant, evidence shape, or scenario repeat strongly enough to be considered for a reusable product pack?

Learning does not automatically publish client material or move a client adapter into the open-source core. Repeated patterns must pass the [product-pack promotion rules](docs/PRODUCT_POSITIONING.md#from-client-pattern-to-product-pack).

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
- the fixture deterministically detects any modeled path that permits a second economic effect while the operation is unresolved;
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

A one-line answer is enough to begin the mirror. Scope starts only after the Boundary Brief and required inputs are confirmed.

[Open the Boundary Brief](docs/client-proof/BOUNDARY_BRIEF.md) · [Discuss one bounded Lab pilot](mailto:safal0645@gmail.com?subject=Recovery%20Design%20Partner%20Lab) · [View the engine](README.md)

## Scope and assurance boundary

This pilot does not certify an entire payment platform and does not assume that any status, webhook, receipt, ledger record, or chain observation is authoritative without a declared contract or authorized evidence review.

Results remain bounded to the supplied model, evidence, adapter, environment, and executed test scope.
