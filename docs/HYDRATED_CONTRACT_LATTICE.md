# Hydrated Contract Lattice v0.1

The hydrated lattice composes static Solidity possibility evidence with normalized runtime evidence without erasing claim boundaries.

```text
Solidity source + reviewed profile
            ↓
   Contract Lattice template
            │
            ├──────────────┐
            │              │
normalized ExecutionTrace │ reviewed hydration bindings
            │              │
            └──────┬───────┘
                   ↓
          Hydrated assessment
                   ↓
     PASS | FAIL | INCONCLUSIVE
```

## One command

```bash
cgqa-hydrated \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/solidity-lattice-disputed-dead-end-profile.json \
  --trace scenarios/execution-trace-double-settlement-conflict.json \
  --bindings scenarios/hydration-bindings-escrow-race.json \
  --root .
```

## Independent claims

The result keeps four independent proof layers:

1. **Static lifecycle** — Solidity AST + reviewed economic profile; catches reachable value-holding dead ends/traps (`CGQ-LIVE-001`).
2. **Runtime verification** — normalized trace; catches duplicate economic effects (`CGQ-SAFE-001`) and competing committed successors (`CGQ-CONS-001`).
3. **Static/runtime conformance** — every committed runtime transition must exist in the static lattice and advance one version (`CGQ-HYDRATE-001`, `CGQ-LATTICE-VER-001`).
4. **Binding verification** — declared authority-sensitive operations require authority evidence; declared time-sensitive operations require explicit time witnesses; commits need source/binding evidence (`CGQ-LATTICE-BIND-001`, `CGQ-LATTICE-TIME-001`).

## Status contract

- **FAIL**: any proved violation exists in static lifecycle, runtime replay/successor checks, or static/runtime conformance.
- **INCONCLUSIVE**: no proved violation exists, but a required proof leg is absent (for example missing authority, time witness, economic-effect evidence, successor evidence, or no committed transition).
- **PASS**: every required proof leg is present and all applicable invariants pass.

This prevents missing evidence from being upgraded into a synthetic green result.

## Hydrated points

Runtime state commits produce observed lattice points such as:

```text
Funded@7 --release--> Released@8
        \\--raiseDispute--> Disputed@8
```

Each observed transition records:

- commit id;
- source and successor state/version;
- operation;
- normalized source reference;
- authority reference when declared required;
- evidence references;
- explicit time witness references when declared time-sensitive;
- whether the runtime transition matched a static transition template.

## Economic value boundary

Static extraction only knows **value presence**, not the real token/native amount. Hydration v0.1 therefore preserves `valuePresence` and does not fabricate `lockedValue` amounts. Concrete balance/value evidence is a future runtime adapter concern.

## Time boundary

The verifier never reads wall-clock time. A time-sensitive operation can pass its binding leg only when an explicit witness reference is supplied in the hydration bindings.

## Provenance

The result includes an evidence fingerprint over:

- Solidity AST SHA-256;
- reviewed static profile SHA-256;
- normalized execution trace SHA-256;
- hydration bindings SHA-256.

The combined `assessmentSha256` makes the exact assessment inputs replayable and distinguishable.
