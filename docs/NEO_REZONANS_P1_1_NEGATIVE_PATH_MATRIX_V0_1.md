# Neo Resonance P1-1 — Standard Negative-Path Matrix v0.1

P1-1 makes the negative-path contract addressable across the ProofPath
authority boundary and the ContractGraph-QA independent verifier. The matrix is
provider-neutral and deterministic. It evaluates proposals only; it never
invokes a provider, executor, wallet, network destination or real secret.

## Required result shape

Every case records:

- case ID, surface, threat and trigger;
- expected and observed decision (`ACCEPT` for the safe control, `BLOCK` for
  negative paths);
- expected and observed reason;
- `side_effect_executed=false` and `executor_invoked=false` in dry-run mode;
- a canonical input digest, decision digest and replayable evidence reference;
- an independent replay result equal to the first result.

## Matrix coverage

| Case | Expected decision | Guarded boundary |
|---|---|---|
| `safe_reversible_control` | `ACCEPT` | complete bounded control case |
| `missing_intent` | `BLOCK` | declared intent |
| `missing_causal_parent` | `BLOCK` | causal binding |
| `missing_nonce` | `BLOCK` | replay identity |
| `nonce_replay` | `BLOCK` | consumed nonce |
| `expired_authority` | `BLOCK` | expiry |
| `scope_violation` | `BLOCK` | scope allow-list |
| `secret_egress_unknown_destination` | `BLOCK` | secret destination |
| `changed_arguments_digest` | `BLOCK` | argument integrity |
| `fanout_exhaustion` | `BLOCK` | resource budget |
| `tampered_evidence` | `BLOCK` | evidence digest |
| `untrusted_memory_or_tool_output` | `BLOCK` | context trust |
| `forged_delegation` | `BLOCK` | delegated identity |
| `changed_tool_origin` | `BLOCK` | tool provenance |
| `nonce_race` | `BLOCK` | atomic commit boundary |
| `bundle_path_traversal` | `BLOCK` | evidence namespace |

## Run and replay

```bash
python tools/negative_path_matrix.py run \
  --output-dir evidence/p1-1 \
  --checked-subject <exact-contractgraph-qa-head> \
  --proofpath-head 4a05ee31d7497979c2505dd55bfef08823302e24

python tools/negative_path_matrix.py verify \
  --inputs evidence/p1-1/matrix-inputs.json \
  --result evidence/p1-1/matrix-result.json \
  --checked-subject <exact-contractgraph-qa-head> \
  --proofpath-head 4a05ee31d7497979c2505dd55bfef08823302e24
```

The workflow also binds the matrix to the exact PR subject and records a
SHA-256 manifest for the input, result and run-context artifacts.

## Authority and claim boundary

`ACCEPT` means only that the bounded proposal is policy-eligible in the matrix;
it is not an execution authorization. All cases run in deterministic dry-run
mode with no side effect. A passing matrix proves the listed synthetic guards
and replay contract at the exact revisions recorded in its evidence bundle. It
does not certify ProofPath, ContractGraph-QA, an external provider, production
security, or universal negative-path coverage.
