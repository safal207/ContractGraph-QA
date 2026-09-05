# Time-Space-State-Environment Transition Model v0.1

TSSE is a strict, deterministic ContractGraph-QA model for one explicitly
reviewed finite trace across four primary coordinates:

```text
Time × Space × State × Environment
```

The model also keeps actor, authority, and economic value explicit. It answers
a bounded question:

> Does this supplied trace preserve exact-subject binding, ordered causal
> continuity, declared boundary changes, evidence binding, and the supplied
> forbidden-phase rules?

TSSE does not discover traces, execute a target, infer business invariants, or
prove exhaustive reachability.

## Coordinates

Every node records:

- `time` — block, timestamp, protocol epoch, and causal step;
- `space` — chain, contract, call frame, storage domain, and protocol location;
- `state` — reviewed lifecycle phase, state hash, and modeled values;
- `environment` — oracle state, token model, fee mode, implementation, and an
  external-state hash;
- `actor` — exact identity and role at that point;
- `authority` — authority epoch and current status;
- `value` — declared unit plus locked and moved value.

This makes cross-boundary effects visible. A locally valid state mutation can
no longer silently hide that execution moved into another contract, authority
epoch, external environment, or economic domain.

## Exact subject

`exactSubject` contains the reviewed repository, commit, and adapter identity.
Its canonical SHA-256 is recomputed by the runtime. When
`requireExactSubjectBinding` is enabled, every node and evidence item must carry
that exact digest.

```text
same repository label != same commit
same contract name != same adapter semantics
same trace shape != same subject
```

## Transition continuity

Transitions are evaluated in array order. With causal continuity enabled:

1. `sequence` starts at zero and advances by one;
2. the first `predecessorId` is `null`;
3. every later predecessor is the prior transition id;
4. the prior target is the next source;
5. `causalStep` advances exactly once across every edge.

With monotonic time enabled, block, timestamp, and epoch may stay equal or
advance, but may not regress.

## Boundary classification

For each edge the verifier recomputes changes in canonical order:

```text
time → space → state → environment → actor → authority → value
```

The supplied `crossedBoundaries` list is normalized into that order and must
match the actual node delta exactly. Unknown or duplicate dimensions are
rejected. Results include a classification such as:

```text
time+space+state+environment
```

`time` includes causal sequence time, so an ordinary ordered edge normally
crosses the time boundary even when wall-clock and block values remain equal.

## Forbidden phase transitions

A forbidden rule binds one exact `fromPhase → toPhase` pair to a declared
invariant. Reaching that pair emits `FORBIDDEN_PHASE_TRANSITION` and places the
result on `hold`.

Other deterministic hold reasons include:

- `NON_MONOTONIC_TIME`;
- `CAUSAL_STEP_DISCONTINUITY`;
- `PREDECESSOR_DISCONTINUITY`;
- `PATH_CONTINUITY_BROKEN`;
- `EXACT_SUBJECT_MISMATCH`;
- `EVIDENCE_BINDING_MISSING`;
- `BOUNDARY_DECLARATION_MISMATCH`.

Malformed objects, duplicate JSON keys, unknown fields, unknown references,
duplicate identifiers, and invalid digests fail structural validation.

## CLI

Standalone:

```bash
cgqa-tsse --model scenarios/tsse-payment-lifecycle.json
```

Unified CLI:

```bash
cgqa tsse --model scenarios/tsse-payment-lifecycle.json
```

Write the same stable JSON result to a file:

```bash
cgqa-tsse \
  --model scenarios/tsse-payment-lifecycle.json \
  --output results/generated/tsse-payment-lifecycle.result.json
```

An existing output is refused unless `--force` is explicit. Input aliases are
always rejected, including when `--force` is present.

Standalone `cgqa-tsse` exit codes:

- `0` — `pass` within the declared model;
- `1` — structurally valid model with one or more hold violations;
- `2` — invalid input or output error.

The unified `cgqa tsse` command follows the public ContractGraph-QA contract:
both a bounded hold and structural validation failure return `10`.

The CLI refuses to overwrite its input model with `--output`.

## Demonstration fixture

`scenarios/tsse-payment-lifecycle.json` is a repository-local synthetic payment
lifecycle:

```text
CREATED → AUTHORIZED → SETTLED
```

It demonstrates temporal, spatial, state, actor, authority, and value changes.
It is not evidence about a third-party system.

## Claim and authorization boundary

A TSSE `pass` means only that the supplied finite trace satisfies the enabled
requirements and declared forbidden-phase model. It does not prove:

- that all reachable paths were supplied;
- that state or environment projections are complete;
- that the declared invariants are sufficient;
- that supplied state, environment, or evidence digests match independently
  reopened source bytes (only the canonical `exactSubject` hash is recomputed);
- that an implementation is secure;
- that production execution or mutation is authorized.

Use TSSE only with repository-owned fixtures, contracts you own, explicit
client authorization, or public bug-bounty assets strictly within published
scope. A source repository, address, ABI, RPC endpoint, or trace is not
authorization by itself.
