# ContractGraph-QA Astra-6 roadmap

`Astra-6` is the internal name for this architecture target. It is not a claim
that ContractGraph-QA is an official OpenAI model or already has laboratory-grade
security capability.

## Small architecture

1. **Evidence intake** validates saved tool output, hashes, and exact subject.
2. **Graph engine** compares idea, plan, and fact across time, space, state,
   environment, actor, authority, and value.
3. **Verdict gate** emits only `PASS_WITHIN_BOUND`, `HOLD`, or
   `COUNTEREXAMPLE` with an explicit claim boundary.
4. **Evidence pack** preserves the minimized test, inputs, hashes, limitations,
   and verification debt.

The public core is read-only. It starts no scanner or contract process and opens
no network connection. Execution is a separate security boundary.

## Delivery sequence

### P0 — Safe core

- keep execution out of the public CLI;
- maintain portable fixtures and deterministic tests;
- keep scan evidence separate from bounty and security verdicts.

### P1 — Subject truth

- bind evidence to a repository tree, commit, chain, block, and deployment;
- reject missing or contradictory subject identity;
- make every conclusion name its exact evidence boundary.

### P2 — Tool evidence

- normalize Foundry, Slither, Echidna, Medusa, and Soroban output into TSSE;
- preserve raw evidence hashes and unsupported fields;
- measure parser accuracy with known fixtures.

### P3 — Stateful search

- express invariants and action sequences as graph transitions;
- explore time, space, state, and environment without claiming proof from one
  test path;
- minimize reproducible counterexamples.

### P4 — Isolated runner

- build it as a separate process or service with least privilege and no network
  by default;
- require authenticated approval and a replay ledger outside target control;
- verify actual executable, working directory, writes, and network effects;
- keep it disabled until containment tests pass.

### P5 — Independent witness

- use a separately authenticated observer and failure domain;
- sign receipts and bind them to the exact subject and action;
- treat missing witness evidence as `HOLD`, never as success.

### P6 — Lab evaluation

- benchmark known vulnerable and known clean contracts;
- track false positives, false negatives, reproducibility, and time to triage;
- publish evidence packs that another reviewer can replay independently.

## Acceptance gates

- core tests are deterministic and require no network;
- no public-core code path starts a process;
- every verdict carries subject identity, evidence hashes, and limitations;
- a new tool adapter ships with positive, negative, and malformed fixtures;
- isolated execution remains unavailable until containment and replay tests are
  independently reviewed.
