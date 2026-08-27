# ContractGraph-QA Outreach

## Operating rule

The first contact is **one buyer-specific technical question**, not a product pitch.

```text
public signal
→ one bounded failure scenario
→ one question about authoritative evidence or invariant
→ wait for a substantive reply
```

Keep the first message under roughly 80 words. Do not attach a deck, ask for a call, or explain the whole engine.

Use one active thread per company. A second route is justified only by a hard bounce or an explicit instruction to contact another team.

## Payment / wallet / ledger first question

```text
Hi [Name / Team],

In [talk, product, or documentation], you described [specific public signal].

One recovery-boundary question:

If [concrete dispatch / timeout / retry scenario], which evidence is authoritative before another monetary attempt is permitted: platform state, the external rail, a processor or wallet receipt, the customer ledger, or an explicit UNKNOWN reconciliation hold?

A one-line answer is enough.

Best,
Alexey Safonov
```

## Policy-controlled agent payment

```text
If an agent receives a valid policy ALLOW, the payment request times out after dispatch, and the agent retries under the same policy, can the system prove whether zero, one, or two economic effects occurred — not merely that both attempts were policy-compliant?
```

## Wallet / credential allowance

```text
If an allowance creates a single-use payment credential, checkout is dispatched, and the processor result is ambiguous, can the system prove both whether the authority was consumed and whether the payment actually happened before permitting another credential or retry?
```

## Payout / vendor transfer

```text
If a vendor transfer is dispatched, the response is lost, and the workflow retries, what evidence proves ZERO, ONE, or UNKNOWN vendor credits across the provider, destination rail, and accounting ledger before another transfer is released?
```

## Smart-contract state-machine question

```text
After [specific terminal or value-moving transition], what invariant prevents [duplicate settlement, trapped funds, terminal resurrection, stale authority, or order-dependent outcome] across the next allowed sequence of calls?
```

## After a substantive answer

Reflect the boundary before offering anything:

```text
Thanks — that clarifies the boundary.

So the platform can prove [A], while [B] remains unresolved until [C]. That makes the critical state:

dispatch accepted
→ external outcome unresolved
→ retry held
→ reconciliation closes ZERO / ONE / UNKNOWN
```

Do not ask three more architecture questions. Convert the answer into one proposed fixture.

## Ask permission to map one fixture

```text
I have a vendor-neutral executable recovery model for exactly this boundary.

Would it be useful if I mapped one synthetic or sandbox flow against:

- ZERO → retry may proceed;
- ONE → stop;
- UNKNOWN → retry remains blocked?

I can send the one-page expected-state contract first.
```

## Paid pilot offer

Use only after the team confirms the boundary or asks what the work would involve.

```text
I can turn this into a fixed-scope design-partner pilot:

- one named recovery boundary;
- one executable local or sandbox-backed fixture;
- duplicate, delayed, out-of-order, retry, and identity-drift cases;
- evidence-precedence map;
- deterministic findings and one in-scope retest.

Price: $750 fixed.
Target: five business days after accepted scope and inputs.
Communication can remain fully async.
```

## Smart-contract pilot offer

```text
For one authorized contract or state-machine slice, I can model up to five prioritized invariants, run bounded sequence exploration, return minimal replayable counterexamples, and include one retest.

Design-partner price: $750 fixed.
```

## Qualification discipline

Prioritize a lead only when:

- the company owns a payment, wallet, ledger, payout, or contract-state boundary;
- a public signal identifies a concrete reliability or control problem;
- one bounded scenario can be written before contact;
- a technical, product, reliability, or developer-relations route exists;
- the company has not already received a recent active-thread outreach.

Stop after one bot escalation request. Do not keep debating an automated support agent.

## Positioning

ContractGraph-QA is an **independent bounded-verification layer for stateful financial systems**.

The primary commercial wedge is:

> prove `ZERO / ONE / UNKNOWN` before retry.

The smart-contract route remains:

> turn business rules into stateful invariants, minimal counterexamples, reproducible evidence, and exact retests.

## Safety boundary

Do not pitch or perform unauthorized active testing. Public documentation may support non-invasive modeling and synthetic fixture design, but a public endpoint, repository, ABI, or contract address is not production-testing authorization.
