<!-- seo-product-intro:start -->
# ContractGraph-QA

## Bounded verification for stateful financial systems

**ContractGraph-QA tests declared failure paths between intent, authorization, execution, external evidence, ledger state, reconciliation, and retry.**

It is built for payment, wallet, payout, stablecoin, agentic-commerce, and smart-contract teams that need reproducible evidence for one high-risk financial promise.

The primary recovery question is:

> After an execution returns an ambiguous result, can the system prove whether the economic effect happened `ZERO` times, `ONE` time, or remains `UNKNOWN` before another monetary action is permitted?

```text
one authorized intent → at most one economic effect

UNKNOWN outcome → no new financial action
```

[Read the Recovery Design Partner Lab](PILOT.md) · [Open the Boundary Brief](docs/client-proof/BOUNDARY_BRIEF.md) · [See the synthetic case study](docs/case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md) · [Run the local demo](#run-a-local-proof)
<!-- seo-product-intro:end -->

---

## Choose the right product route

| Team / trigger | Product route | What gets verified |
|---|---|---|
| Payment, wallet, payout, stablecoin, or agentic-commerce team | **Recovery Design Partner Lab** | timeout, lost response, duplicate or delayed webhook, retry, fallback, reconciliation, policy continuity, ledger divergence |
| Smart-contract or protocol team | **State-Machine Review** | escrow, settlement, release/refund, conservation, authorization, time boundaries, terminal states, ordering, replay |
| Engineering or audit-readiness team | **CGQA evidence pipeline** | reviewed model, bounded search, minimal counterexample, deterministic replay, provenance-bound evidence bundle |

ContractGraph-QA is currently delivered **productized-service first**: the client buys a bounded verification result; the open-source engine produces the fixture, evidence map, verdict, and replay artifacts underneath.

---

## Recovery Design Partner Lab

- **Capacity:** maximum **5 design partners**
- **Design-partner price:** **$750 fixed per one-boundary pilot**
- **Scope:** one named recovery boundary
- **Target delivery window:** five business days after the Boundary Brief and required inputs are accepted
- **Communication:** async by default
- **Retest:** one bounded retest for an in-scope fix delivered within 14 calendar days

A typical boundary looks like:

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

The pilot includes:

- a compact expected-state contract;
- an evidence-precedence map;
- one local or sandbox-backed executable fixture;
- positive, negative, duplicate, delayed, out-of-order, and retry cases;
- deterministic pass/fail output with violation codes;
- a minimized counterexample when an unsafe path is reachable;
- bounded remediation guidance;
- one retest inside the agreed scope.

The initial fixture can start from public documentation, synthetic traces, status definitions, webhook schemas, and a declared authoritative-evidence rule. Production credentials, customer data, and real-value transactions are not required.

[Lab workflow, checkpoints, and acceptance criteria →](PILOT.md) · [One-page Boundary Brief →](docs/client-proof/BOUNDARY_BRIEF.md)

---

## Why ordinary local signals are not enough

A component can be locally correct while the economic result remains unresolved:

- a policy engine can prove that an action was allowed;
- a credential layer can prove that capacity was reserved;
- an API can prove that a request was accepted;
- a webhook can prove that a provider state changed;
- a ledger can prove that one internal posting exists.

None of those signals alone necessarily proves the full cross-system outcome.

ContractGraph-QA therefore preserves the distinctions between:

```text
logical operation identity
≠ concrete execution attempt
≠ idempotency / replay identity
≠ policy decision
≠ provider state
≠ external economic evidence
≠ internal ledger state
≠ reconciliation state
≠ retry permission
```

---

## Run a local proof

The latest verified release is distributed as a GitHub release wheel.

```bash
python -m pip install \
  https://github.com/safal207/ContractGraph-QA/releases/download/v1.9.0/contractgraph_qa-1.9.0-py3-none-any.whl

cgqa demo --output-dir cgqa-demo
cgqa verify-bundle cgqa-demo/CGQA-005.evidence.zip
```

The demo is repository-owned, performs no external financial action, and is not presented as a third-party audit.

From a repository checkout, run the recovery benchmark:

```bash
git clone https://github.com/safal207/ContractGraph-QA.git
cd ContractGraph-QA

cgqa payment-recovery-evaluate \
  --scenario benchmarks/agent-payment-recovery-v0.1/cases/pass_committed_stop.json
```

The vendor-neutral benchmark includes seed cases for:

- committed outcome followed by stop;
- explicit failure followed by retry under the same logical operation;
- retry before reconciliation;
- idempotency drift across retry.

[See Agent Payment Recovery Benchmark v0.1 →](benchmarks/agent-payment-recovery-v0.1/README.md)

---

## Smart-contract quickstart

For an unfamiliar local smart-contract repository:

```bash
cgqa quickstart --target /path/to/project
```

The safe default does not execute project code. It inventories recognized sources and frameworks, computes a source fingerprint, surfaces bounded review prompts, plans the native test command, and writes:

```text
<project>/.cgqa/quickstart/
  quickstart.json
  REPORT.md
```

Native tests remain explicit:

```bash
cgqa quickstart --target /path/to/project --run-native
```

Detected routes include Foundry, Hardhat, Truffle, Ape/Brownie/Vyper, Soroban, Anchor, Move, and Cairo/Scarb.

[Universal quickstart documentation →](docs/UNIVERSAL_QUICKSTART.md)

For end-to-end request, transaction-attempt, receipt/event, indexer, backend,
and API continuity, see the
[Smart Contract Continuity Bridge v0.1](docs/SMART_CONTRACT_CONTINUITY_BRIDGE.md).
ContractGraph-QA produces reviewed evidence envelopes; the existing LTP verifier
remains the only source of continuity verdicts.

For the reciprocal, file-first ContractGraph-QA ↔ LiminalQA adapter, including
bounded-evidence export and non-authoritative candidate import, see
[LiminalQA interop v0.1](docs/LIMINALQA_INTEROP.md).

Run the portable golden and fail-closed vectors before shipping any language adapter:

```bash
cgqa liminalqa-conformance
```

---

## What the engine produces

```text
AUTHORIZED SCOPE / EXACT SUBJECT
      ↓
REVIEWED STATE + ACTION + AUTHORITY MODEL
      ↓
EXPLICIT INVARIANTS / FORBIDDEN STATES
      ↓
BOUNDED SEARCH + NEGATIVE CONTROLS
      ↓
MINIMAL VIOLATING PATH OR BOUNDED NO-FINDING
      ↓
DETERMINISTIC REPLAY
      ↓
OBSERVED PRE/POST EVIDENCE
      ↓
PROVENANCE-BOUND FINDING + REPORT + ZIP
      ↓
INDEPENDENT VERIFICATION
      ↓
FIX → EXACT RETEST
```

Every declared invariant is classified as exactly one of:

```text
violated
not_found_within_bound
inconclusive
```

`not_found_within_bound` is bounded evidence, not a security certification. `inconclusive` remains unresolved and fails closed.

---

## What makes ContractGraph-QA different

- **Stateful, not function-by-function.** It searches sequences of actors, actions, retries, ordering, and time changes.
- **Economic-effect oriented.** It tracks the reachable effect, not only the local return value.
- **Evidence first.** Findings carry minimal paths, observed state, identity, provenance, and replay instructions.
- **Honest assurance language.** Missing coverage does not silently become a clean PASS.
- **Retestable.** The same historical path can be replayed after a fix, followed by alternate-path search.
- **Authorization bounded.** Public code or an address is not treated as permission to test a production target.

---

## Advanced operator workflow

```bash
cgqa doctor --require-forge
cgqa init-engagement acme-financial-flow
# Replace generated TODOs only after explicit scope and authorization review.
cgqa engagement-run --config engagements/acme-financial-flow/cgqa.toml
cgqa verify-engagement-bundle \
  engagements/acme-financial-flow/evidence/engagement.evidence.zip
```

The generated scaffold starts fail-closed until the operator supplies the authorization, target, state hash, action model, invariants, and capture adapter.

Key documents:

- [Recovery Design Partner Lab](PILOT.md)
- [One-page Boundary Brief](docs/client-proof/BOUNDARY_BRIEF.md)
- [Synthetic Recovery Case Study](docs/case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md)
- [Product runtime](docs/PRODUCT.md)
- [CLI reference](docs/CLI.md)
- [Engagement workflow](docs/ENGAGEMENT.md)
- [Adapter manifest](docs/ADAPTER_MANIFEST.md)
- [LiminalQA interop v0.1](docs/LIMINALQA_INTEROP.md)
- [Evidence distribution](docs/DISTRIBUTION.md)
- [Client proof pack](docs/client-proof/README.md)
- [Agent verification protocol](AGENTS.md)

---

## Commercial workflow

```text
question
→ mirror boundary
→ confirm Boundary Brief
→ paid fixture
→ evidence pack
→ bounded retest
→ product learning
```

A good first question is:

> After dispatch returns an ambiguous result, which evidence is authoritative before another monetary attempt is permitted: platform state, external rail, processor or wallet receipt, customer ledger, or an explicit `UNKNOWN` reconciliation hold?

A one-line answer is enough to begin the mirror. The paid scope starts only after the one-page Boundary Brief is confirmed.

---

## Product status

- Python 3.11+
- Apache-2.0
- Installable `cgqa` CLI
- Deterministic evidence bundles
- Independent bundle verification
- Universal smart-contract quickstart
- Agent-payment recovery benchmark
- Current release: `v1.9.0`

Release artifacts, checksums, and release notes are published under [GitHub Releases](https://github.com/safal207/ContractGraph-QA/releases).

---

## Scope and safety

ContractGraph-QA may be used on:

- repositories and fixtures you own;
- client systems with explicit written authorization;
- public bug-bounty assets strictly within their published scope and rules;
- public documentation for non-invasive modeling and synthetic fixture design.

It does not claim that:

- bounded search proves an arbitrary system secure;
- selected invariants are complete;
- a webhook, status endpoint, receipt, ledger record, or chain observation is authoritative without a declared contract;
- a clean bounded result means no vulnerability exists;
- a QA engagement is equivalent to a formal full-platform security audit.

Never commit RPC secrets, private keys, seed phrases, customer data, or client credentials.

See [SECURITY.md](SECURITY.md).

## License

Apache-2.0
