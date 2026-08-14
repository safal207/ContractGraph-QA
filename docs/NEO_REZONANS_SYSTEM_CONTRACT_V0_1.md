# NEO REZONANS System Contract v0.1

This document describes the first machine-readable whole-system composition of the NEO REZONANS trust-infrastructure repositories.

It is intentionally **not** a monorepo migration, shared runtime, deployment orchestrator, or authority grant.

The contract answers a narrower question:

> Which exact canonical capabilities are being composed, what may cross each repository boundary, and what must never be inferred merely because data moved from one layer to the next?

## Canonical snapshot

Machine-readable snapshot:

`governance/neo-rezonans-system-snapshot.v0.1.json`

FCRP system case:

`benchmarks/fcrp-v0.2/FCRP-SYSTEM-001-neo-rezonans.json`

Validator:

`contractgraph_qa/system_snapshot.py`

## System chain

```text
RESONANCE
  Idea / claims / questions / uncertainty
        ↓
CML
  causal memory / applicability / information quality
        ↓
FCRP v0.2
  scope / idea / causal navigation / refactor boundary
        ↓
LiminalOSAI
  explicit authorization governance
        ↓
ContractGraph-QA
  state-transition / invariant / replay verification
        ↓
ProofPath
  proof / provenance / observer-bound evidence
        ↓
LiminalDB
  durable verified state / compatibility boundary
        ↓
RINSE
  versioned reinterpretation over immutable traces
        ↓
RESONANCE
  publish / question / learn / re-enter the cycle
```

The feedback edge is informational and reflective. It grants no execution authority.

## One authority edge

Seven edges explicitly use:

```text
authorityMode = NONE
```

and must forbid:

```text
execution_authority
```

The only edge allowed to carry authorization semantics is:

```text
LiminalOSAI
    ↓
ContractGraph-QA
```

Even that edge may carry authority only as:

```text
authorization_ref
+ authorized scope
+ constraints
+ runtime context
+ expiry / epoch
```

with:

```text
authorityMode = EXPLICIT_CONTRACT_ONLY
```

and an explicit prohibition against:

```text
evidence_as_authority
```

This is the system-level continuation of FCRP-SELF-009.

## Snapshot, not eternal truth

The contract is point-in-time.

Each layer records an exact canonical revision observed for the snapshot. Acceptance checks the external repository `main` heads against those revisions.

After later repository evolution, the old snapshot remains historical evidence. It must not silently be presented as a current whole-system state.

Policy:

```text
onHeadDrift = REVALIDATE_SYSTEM_SNAPSHOT
```

This is deliberately different from claiming that a historical Git commit is forever the semantic compatibility key. SELF-007 already showed why those concepts must remain separate.

Future system-contract versions should move from repository-head snapshots toward content-addressed capability identities where the underlying repositories expose sufficiently stable machine-readable capability manifests.

## Self-hosting without a future-SHA paradox

The system snapshot is itself stored in ContractGraph-QA, which is also one of the system layers.

A manifest cannot safely require its own future merge commit as an input identity: updating the manifest would create a new commit and therefore change the identity again.

v0.1 resolves this by pinning:

```text
hostRepository = safal207/ContractGraph-QA
hostBaseCommit = 505041cae23d0527f7d567e1a6bd6d1952dc4960
hostAcceptanceMode = BASE_PLUS_GOVERNANCE_SNAPSHOT
```

The host base is the canonical revision containing FCRP v0.2 and the state-transition verification capability before the system-governance snapshot is added.

The acceptance commit itself is packaging/governance evolution and is explicitly distinguished from later semantic layer drift.

CI must therefore prove:

```text
PR base == hostBaseCommit
AND
hostBaseCommit is an ancestor of the exact PR head
AND
all external pinned main heads match
```

This avoids both future-SHA self-reference and the opposite mistake of treating arbitrary later host changes as automatically compatible.

## FCRP-SYSTEM-001

The first whole-system FCRP case identifies the remaining divergence after SELF-005 through SELF-009:

```text
strong local repository contracts
        ↓
no shared cross-repository transfer contract   ← First Meaningful Divergence
        ↓
composition relies on ambient assumptions
        ↓
authority / compatibility / canonicality ambiguity
```

Refactor point:

```text
canonical system snapshot
+ explicit edge semantics
```

The case uses FCRP v0.2 and intentionally returns:

```text
decision = PASS
mutationAuthorized = false
```

A coherent whole-system model is still not permission to mutate the system.

## Current bounded invariants

The validator enforces:

- all required logical roles exist;
- all default layers are `CANONICAL`;
- branch-only default dependencies are forbidden;
- every layer has an exact lowercase 40-character commit identity;
- the primary chain contains every layer exactly once;
- every primary transition is represented by an explicit edge;
- exactly one feedback edge closes `RINSE → RESONANCE`;
- every edge lists allowed facts and forbidden inferences;
- non-authority edges explicitly forbid execution authority;
- exactly one edge may transfer an explicit authorization contract;
- the authority edge must carry `authorization_ref` and forbid `evidence_as_authority`;
- the snapshot itself grants no mutation authority;
- the self-hosted ContractGraph-QA layers bind the exact pre-acceptance FCRP v0.2 base.

## Not yet claimed

System Contract v0.1 does not prove:

- runtime interoperability among all repositories;
- transactional cross-repository execution;
- production deployment safety;
- availability or freshness after later repository changes;
- semantic compatibility after a pinned capability evolves;
- autonomous system-wide mutation;
- formal completeness of the causal graph;
- third-party replication.

The next meaningful experiment should be an **end-to-end synthetic system receipt** that starts with an intent, travels through memory → FCRP → explicit authorization → state-transition verification → proof → persistence → reinterpretation, and proves that identities and non-transfer boundaries survive the whole round trip.
