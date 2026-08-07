# Authorized fork testing

v0.6 adds a fail-closed path for testing against a fixed EVM snapshot without sending transactions to a live network.

## Safety boundary

Fork testing is allowed only for:

- contracts you own;
- client systems where the testing scope is explicitly authorized;
- public bug-bounty assets that are in scope under published safe-harbor rules.

A public contract address alone is **not** authorization.

The default repository CI never opens an external fork. Fork execution lives in the separate `fork` Foundry profile and the manual `Authorized fork smoke` workflow.

## Required scope evidence

Every fork run requires:

- `scope_id` — an auditable engagement or bounty identifier;
- `authorization_reference` — signed SOW, issue, bounty scope URL/reference, or equivalent evidence;
- `chain_id` — expected chain;
- `block_number` — fixed historical snapshot;
- `target` — exact authorized contract address;
- confirmation equal to `YES`;
- `CGQA_FORK_RPC_URL` — secret RPC endpoint.

Both the Python preflight and Solidity harness fail closed when required authorization metadata is missing.

## GitHub setup

Before the first real fork run:

1. Create a GitHub environment named `authorized-fork`.
2. Add required reviewers to that environment when available.
3. Add `CGQA_FORK_RPC_URL` as an environment or repository secret.
4. Never commit RPC credentials, private keys, seed phrases, or client secrets.
5. Keep the authorization reference non-sensitive because workflow inputs may be visible in GitHub metadata/logs.

## Manual workflow

Run **Actions → Authorized fork smoke → Run workflow** and provide the exact authorized target details.

The workflow performs:

```text
workflow inputs
      ↓
Python authorization preflight
      ↓
RPC secret presence check
      ↓
Foundry fork profile
      ↓
Solidity authorization validation
      ↓
createSelectFork(fixed block)
      ↓
chain/block/target-code checks
      ↓
read-only snapshot fingerprint
```

The v0.6 smoke test does not call a target function and does not broadcast a transaction. It verifies that the declared target exists at the declared fixed snapshot and produces a deterministic read-only fingerprint.

## Local authorized run

Set the environment variables only for a target you are authorized to test:

```bash
export CGQA_FORK_RPC_URL='<secret RPC URL>'
export CGQA_SCOPE_ID='client-scope-001'
export CGQA_AUTHORIZATION_REFERENCE='signed-sow-2026-08-07'
export CGQA_CHAIN_ID='1'
export CGQA_BLOCK_NUMBER='20000000'
export CGQA_TARGET='0x...'
export CGQA_AUTHORIZED='YES'

FOUNDRY_PROFILE=fork forge test -vvv
```

## Snapshot fingerprint

The smoke fingerprint currently includes:

```text
chain id
block number
target address
target code hash
target native-token balance
```

This is provenance evidence only. It is **not** a complete ContractGraph state hash and must not be used for sound deduplication of a real protocol. A client-specific state hash must include all storage, balances, oracle/epoch/time context, actor state, and external dependencies relevant to future behavior.

## Next step

A client-specific fork adapter can extend the read-only context with explicitly authorized actions and invariants, then reuse the existing parameter/time explorer, state deduplication, minimal-path replay, and deterministic finding-report pipeline.
