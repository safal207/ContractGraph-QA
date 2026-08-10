# Valta Sandbox Adapter v0.7

This is the first concrete adapter built on top of the reusable Temporal Transition Field v0.6 adapter contract.

## Purpose

Map the agreed Valta Sprint 1 sandbox surface into ContractGraph-QA without guessing undocumented request shapes and without exposing credentials.

## Confirmed scope

The engagement-confirmed sandbox surface includes:

- `POST /sandbox/reset`
- `POST /sandbox/deposit`
- `POST /policies`
- `POST /spend`
- `POST /agents/wallet-guardian/wallet/spend`
- `GET /audit`
- `GET /transactions`

`wallet-guardian` is a platform agent. It does not have its own wallet transaction log; its activity is recorded in the main wallet transaction history. After Valta's fix, `GET /agents/wallet-guardian/wallet/transactions` should return a clear `422` directing the caller to `GET /transactions`. That agent-wallet path is therefore an environment/contract behavior check, not a defect target.

The older `POST /wallet/transfer` is explicitly excluded as a defect target because the test key is expected to receive `403` there. Monthly enforcement is also out of scope.

## Important execution gate

The spend endpoints were named in the Sprint 1 instructions, but the exact JSON request body was not provided. Public documentation reviewed during v0.7 preparation did not establish that body either.

Therefore:

- `spend_payload_confirmed = false`
- `live_execution_enabled = false`
- the adapter refuses to guess a `/spend` payload;
- no authenticated target request is executed by this v0.7 scaffold.

This is intentional fail-closed behavior, not an implementation gap to bypass.

## Credentials

The repository contains no Valta API key. A future explicitly enabled sandbox execution may read the test key only from:

`VALTA_TEST_API_KEY`

Request-plan rendering always replaces the credential value with a placeholder.

## Offline validation

Run:

```bash
cd adapters/valta
python -m unittest -v test_valta_sandbox_adapter.py
python valta_sandbox_adapter.py
```

The second command prints a sanitized request plan for the confirmed reset/deposit/policy/audit/main-wallet transaction-history surface. It performs no network request.

## Next gate

Before enabling any spend execution, confirm the exact request body for `POST /spend` (and whether the agent-wallet spend endpoint uses the same shape). Then update `endpoint_map.valta.sandbox.json`, add request-shape regression tests, and only after review switch the execution gate in a separate commit.
