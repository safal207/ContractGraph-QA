# Contract Lattice Model v0.1

ContractGraph-QA models a contract lifecycle as a discrete causal lattice rather than a bag of functions.

> Unit tests inspect local operations. The Contract Lattice verifies the system those operations can form.

## Coordinates

Each lattice point binds six explicit dimensions:

```text
L = State × Version × Value × Authority × Evidence × TimeWitness
```

- **State** — business lifecycle state such as `Funded` or `Disputed`.
- **Version** — explicit causal state version; a v0.1 transition advances exactly one version.
- **Value** — locked economic value represented as a non-negative integer in the model's declared unit.
- **Authority** — references available at that point for transition authorization.
- **Evidence** — explicit facts/witnesses available at that point.
- **TimeWitness** — recorded time/absence/deadline evidence. Ambient wall-clock reads are not model input.

## Why this exists

A function can be locally correct while its composition creates an unsafe lifecycle.

The canonical example is:

```text
Created@0 → Funded@1 → Disputed@2 → ∅
                         value > 0
```

`raiseDispute()` can be a valid function call while the resulting `Disputed` point has no route to an economic terminal. The function passes; the lifecycle fails.

## v0.1 laws

### `CGQ-LIVE-001` — locked value must retain a safe exit

For every reachable lattice point `L`:

```text
lockedValue(L) > 0  ⇒  exists path(L → safeTerminal)
```

Unreachable synthetic traps do not create a finding.

### `CGQ-LATTICE-VER-001` — causal version continuity

Every modeled transition advances one explicit version:

```text
version(target) = version(source) + 1
```

This prevents a lattice from silently skipping or rewinding causal state.

### `CGQ-LATTICE-BIND-001` — authority/evidence binding

If a transition declares an `authorityRef` or `evidenceRefs`, those references must already be bound at the source lattice point. A transition cannot manufacture authority or evidence while taking the step it is supposed to justify.

### `CGQ-LATTICE-TIME-001` — time must be witnessed

A `timeSensitive` transition must carry one or more explicit `timeWitnessRefs`, and every referenced witness must already be bound at the source point.

This keeps the projection deterministic:

```text
same lattice + same witnesses = same verdict
```

No ambient clock is read by the verifier.

## Runtime invariants remain separate

The lattice is a **possibility model**, so multiple legal outgoing transitions from one point are not automatically an error.

Runtime conflicts are checked by existing engines:

- `CGQ-SAFE-001` — at-most-once economic effect;
- `CGQ-CONS-001` — one committed successor per conflict-domain parent version.

This separation matters: a contract may legally allow either `release` or `refund`; the bug occurs only if incompatible outcomes both commit in one execution history.

## CLI

```bash
cgqa contract-lattice-check \
  --model scenarios/contract-lattice-disputed-dead-end.json
```

The repository fixture intentionally returns a validation failure and emits the minimal reachable counterexample:

```text
Created@0 → Funded@1 → Disputed@2
```

## Evidence boundary

A PASS is exact over the declared lattice and its bound references. It does **not** claim that runtime capture is complete or that arbitrary raw EVM/provider events were normalized correctly.

Those remain explicit adapter/provenance claims.

## Product direction

```text
Solidity / reviewed model ──→ Contract Lattice ──→ lifecycle + binding laws
runtime/provider evidence ──→ Execution Trace ───┬→ economic cardinality
                                                  └→ successor consistency
```

The long-term goal is one auditable pipeline:

```text
contract → lattice → execution evidence → invariants → counterexample → fix verification
```
