# Authorized engagement playbook

This playbook describes the product workflow for a real smart-contract QA / audit-readiness engagement.

It is intentionally conservative: ContractGraph-QA should fail closed when authorization, provenance, adapter mapping, or evidence is ambiguous.

## 1. Establish written scope

Before any fork or target-specific test:

- identify the legal/technical owner of the target;
- record the exact contract address or deployment identifier;
- record chain ID and fixed snapshot block;
- record the written authorization reference or published safe-harbor scope;
- list excluded contracts/functions/actions;
- define whether state-changing fork calls, impersonation, time changes, oracle overrides, or token deal helpers are allowed in the local simulation;
- define data-handling rules for client source code and reports.

Do not infer permission from public source code, a public address, an ABI, or an RPC endpoint.

## 2. Model the system

Create/review the adapter manifest:

- `adapterId` and `scopeId` are unique to the engagement;
- `target` matches the authorized target;
- `authorizationReference` identifies the written scope;
- action IDs map only to in-scope transitions;
- actors reflect role boundaries;
- `stateFields` list all future-relevant modeled state;
- invariants are explicit, testable statements;
- `search.maxDepth` is bounded and justified.

Review the Solidity adapter separately. The executable `_stateHash()` is the source of truth for deduplication; the manifest state-field list is review evidence and must match it conceptually.

## 3. Fix the fork provenance

For an external authorized target use the existing fork preflight and adapter boundary:

- `CGQA_AUTHORIZED=YES`;
- scope ID;
- authorization reference;
- chain ID;
- fixed block number;
- target address;
- secret RPC URL via the Foundry `authorized` alias.

The fork must confirm chain, block, and deployed code before target-specific exploration begins.

## 4. Build the finite search corpus

Define a finite corpus of:

- actions;
- role/actor choices;
- relevant parameter boundaries;
- time jumps;
- expected rejected transitions.

Prefer meaningful equivalence classes and boundaries over an unbounded parameter space.

Examples include:

- `0`, minimum valid, nominal, maximum valid, maximum + 1;
- before/at/after deadline;
- authorized/unauthorized actor;
- first/repeated/terminal call;
- oracle success/failure/stale value when explicitly in scope.

## 5. Execute with a fixed product config

Create an engagement-specific `cgqa.toml` based on `cgqa.example.toml`.

Run:

```bash
cgqa doctor --require-forge
cgqa validate --manifest manifests/client.json
cgqa run --config cgqa.toml --clean
```

A successful `cgqa run` means the capture, result provenance, finding export, report rendering, bundle hashes, and semantic bundle verification all passed.

It does **not** mean that the target is secure or that all vulnerabilities were found.

## 6. Review the finding as a human

Before client delivery, review:

- whether the invariant represents the intended requirement;
- whether the path uses only in-scope actions;
- whether pre/post-state descriptions match observed behavior;
- whether severity is justified by impact and reachability;
- whether the recommendation fixes the cause rather than only the demonstrated symptom;
- whether the replay command is usable in the engagement environment;
- whether any confidential information should be removed from the client-facing Markdown.

## 7. Deliver evidence

Recommended delivery set:

- client-facing Markdown finding;
- deterministic evidence ZIP;
- optional test/adapter patch when contractually allowed.

Give the client the bundle SHA-256 printed by `cgqa run` so they can verify that the file they received is the reviewed file.

They can verify with:

```bash
cgqa verify-bundle <finding>.evidence.zip
```

## 8. Retest

After a fix:

1. pin the new code/snapshot provenance;
2. replay the exact minimal failing path;
3. confirm the original invariant holds;
4. rerun the bounded exploration;
5. keep the path as a regression test;
6. generate a new evidence bundle rather than modifying the old one.

## Client-service boundary

A useful commercial deliverable is an **Audit Readiness / Smart Contract QA** package, not a claim of formal verification or a full independent security audit unless the engagement actually includes those capabilities.

A product-ready engagement can include:

- requirement/invariant review;
- role/state/transition matrix;
- Foundry unit/negative/fuzz/invariant tests;
- bounded causal-temporal path exploration;
- authorized fixed-block fork simulation;
- reproducible findings and evidence bundles;
- retest after fixes.
