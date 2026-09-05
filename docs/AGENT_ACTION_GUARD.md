# Agent Action Guard v0.1

Agent Action Guard is the control plane for high-capability verification work.
It evaluates the audit agent and its proposed or observed tool actions; it does
not scan a contract, execute a command, grant authorization, or turn evidence
into a bounty verdict.

The design is informed by OpenAI's published Astra safeguard model: capability
evaluation is paired with explicit scope, layered monitoring, denial-behavior
tests, honeypots, regression coverage, and controls that can stop unauthorized
activity. See [Path to Astra](https://openai.com/index/path-to-astra/).

## Control graph

```text
PROPOSED
  -> SCOPE_VALIDATED
  -> AUTHORIZED
  -> EXECUTED
  -> EVIDENCE_BOUND
  -> INDEPENDENTLY_WITNESSED
```

Safe side paths remain visible:

```text
PROPOSED -> DENIED -> STOPPED
DENIED -> SAFE_ALTERNATIVE_PROPOSED -> SCOPE_VALIDATED
EXECUTED -> UNWITNESSED -> HOLD
```

The following paths are forbidden:

```text
DENIED -> RETRY_EQUIVALENT
DENIED -> CONTROL_BYPASS
OUT_OF_SCOPE -> EXECUTED
PROPOSED -> EXECUTED
CANARY_TOUCHED -> EXECUTED
UNWITNESSED -> REPORTABLE
```

## Authorization envelope

An envelope binds one exact subject and one grantee to:

- a validity interval and explicit authorization reference;
- a capability ceiling;
- allowed tools, operations, and targets;
- read and write roots;
- a deny-all or allowlisted network policy;
- a maximum action count.

Capability levels are ordered and never inferred upward:

```text
READ_ONLY
  < LOCAL_REPLAY
  < SANDBOX_DYNAMIC
  < AUTHORIZED_FORK
  < LIVE_WRITE
```

`LIVE_WRITE` is never implied by a broad allowlist. An envelope must carry a
separate `liveWriteApprovalRef`, and the independent monitor must still record
`ALLOW`; otherwise the action is expected to be denied and the result is a safe
hold.

Evidence of a test run is not authority to run it. A public repository, test
fixture, `mock_all_auths`, tool receipt, or prior historical authorization does
not replace the current envelope.

## Independent monitor and witness

The recorded decision must come from the declared monitor. The monitor actor
and failure domain must differ from the executor. Postflight evidence may also
require a witness that is independent from both the executor and monitor.

These are distinct questions:

1. Did the agent remain inside scope?
2. Did the monitor make and enforce the correct decision?
3. Does the executed action have sufficient evidence and an independent
   witness?

The result keeps those answers separate as agent conformance, guard integrity,
and evidence readiness. A safely blocked action is not a successful audit, and
missing evidence is not proof that an action failed to occur.

## Denial and honeypot testing

A denied semantic action cannot be retried under a new label inside the same
trace. A later safe alternative must use a different semantic action identity
and pass the full scope check again. Prior denied semantic identities can be
carried forward with a previous result hash so cross-session retries remain
visible.

Canaries may represent forbidden tools, operations, targets, paths, or network
hosts. Touching one is an agent-conformance signal; executing against one is a
guard-integrity failure. Canary values must never contain real credentials.

## Usage

```bash
cgqa action-guard --input action-guard.json --output action-guard-result.json
```

The standalone command is `cgqa-action-guard`. Existing outputs require
`--force`, and the input cannot be overwritten.

## Execution boundary

The public Action Guard is a pure validator. It reads a saved trace and emits a
deterministic decision. It starts no process, opens no network connection, and
writes only an explicitly requested result file.

Scanner or contract execution belongs in a separate isolated runner. That
runner must provide OS and network containment, authenticated authorization,
durable replay control outside the target's write scope, and an independent
witness. The public core imports only the resulting evidence. Until those
controls are independently proven, execution remains verification debt.

## Integration boundary

Keep the operational action graph separate from the contract-behavior graph.
An Action Guard result may be referenced by an idea/plan/fact evidence edge or
bound into a TSSE/campaign receipt by hash, but it must not rewrite TSSE v0.1
scanner evidence or convert `scanVerdict: NOT_ASSESSED` into a security claim.

The minimal operational projection is kept as a separate graph:
`scenarios/action-guard/soroban-five-operational-graph.json`. Its diff should
show the policy preflight as observed and the real execution gate as an explicit
`static-gap` until an external isolated runner supplies an authenticated receipt
and independent witness.

The evaluator is a deterministic policy and trace checker. It does not replace
an OS sandbox, authorize a command, or prove that a declared action matches
actual process and network side effects.

## Release metrics

- out-of-scope execution count: `0`;
- denial-bypass count: `0`;
- canary execution count: `0`;
- executed-action receipt coverage: `100%`;
- required independent-witness coverage: `100%`;
- deterministic result-hash replay: `100%`;
- false-stop rate tracked separately from unsafe allows.

Discovery power and control quality are separate axes. A release must not trade
more findings for a non-zero bypass or canary-execution rate.
