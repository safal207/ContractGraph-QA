# Gonka Verification Runbook — G-001 / G-002

Pinned upstream revision: `f040d0a5b5ef207a0c431894c9f9e2608f9d3073`

This runbook is intentionally limited to a Gonka DevNet/test gateway or another environment where testing is explicitly permitted. Do not point these procedures at mainnet.

## Upstream surfaces used

The current devshard gateway exposes an OpenAI-compatible `POST /v1/chat/completions`, public `GET /v1/status`, and request accounting at `GET /v1/requests/{request_id}`. The gateway binds an inbound `X-Request-Id` into request context and echoes that identity on the response. Request accounting persists request/escrow identity plus execution attempts and can join those attempts to actual inference costs.

A client disconnect is not proof that execution stopped. Gonka documents a meta-drain window that can continue draining host SSE after the client disconnects so protocol completion can finish. Therefore G-002 treats client timeout as an ambiguous outcome.

## Required environment

Set these values only for an explicitly permitted test environment:

```bash
export GONKA_GATEWAY_BASE="https://<permitted-devnet-gateway>"
export GONKA_API_KEY="<test-api-key-if-required>"
export GONKA_MODEL="<advertised-test-model>"
export CGQA_RUN_ID="gonka-$(date -u +%Y%m%dT%H%M%SZ)"
```

Do not store secrets in evidence. Redact Authorization headers and any private/admin material.

## Evidence directory

```bash
mkdir -p "evidence/$CGQA_RUN_ID/G-001" "evidence/$CGQA_RUN_ID/G-002A" "evidence/$CGQA_RUN_ID/G-002B"
```

Each case should record UTC timestamps and the pinned upstream revision.

---

## G-001 — normal inference control

### 1. Capture baseline status

```bash
curl -fsS "$GONKA_GATEWAY_BASE/v1/status" \
  > "evidence/$CGQA_RUN_ID/G-001/gateway_status.before.json"
```

### 2. Choose one explicit request identity

```bash
export G001_REQUEST_ID="cgqa-$CGQA_RUN_ID-g001-a1"
```

### 3. Submit exactly one request, no client retry

```bash
curl -fsS \
  --max-time 120 \
  -D "evidence/$CGQA_RUN_ID/G-001/response.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-001/response.redacted.json" \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GONKA_API_KEY" \
  -H "X-Request-Id: $G001_REQUEST_ID" \
  -d "{\"model\":\"$GONKA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"CGQA control request: reply with a short deterministic acknowledgement.\"}],\"max_tokens\":32,\"stream\":false}"
```

Before preserving `response.headers.txt`, redact Authorization if your HTTP tooling ever records request headers.

### 4. Query request accounting

```bash
curl -fsS "$GONKA_GATEWAY_BASE/v1/requests/$G001_REQUEST_ID" \
  > "evidence/$CGQA_RUN_ID/G-001/request-accounting.json"
```

### 5. Capture final status

```bash
curl -fsS "$GONKA_GATEWAY_BASE/v1/status" \
  > "evidence/$CGQA_RUN_ID/G-001/gateway_status.after.json"
```

### G-001 minimum PASS

- response is terminal and attributable to `$G001_REQUEST_ID`;
- accounting exposes a consistent escrow/request lineage;
- attempt cost arithmetic reconciles;
- no unexplained second billable effect exists.

Do not proceed to G-002 if G-001 cannot be reconciled; fix the baseline first.

---

## G-002A — ambiguous timeout, stable `X-Request-Id`

Purpose: determine what happens when one semantic operation is retried with the same protocol request identity.

### 1. Stable identities

```bash
export G002_LOGICAL_ID="cgqa-$CGQA_RUN_ID-logical-timeout"
export G002A_REQUEST_ID="cgqa-$CGQA_RUN_ID-g002a"
```

Record `G002_LOGICAL_ID` in local evidence only; Gonka's observable request identity is `X-Request-Id`.

### 2. First attempt — intentionally short client timeout

Choose a timeout that is short enough to create a client-side ambiguous outcome but does not attack the server or other users. Start conservatively.

```bash
set +e
curl -sS \
  --max-time 1 \
  -D "evidence/$CGQA_RUN_ID/G-002A/attempt-1.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-002A/attempt-1.response.redacted.json" \
  -w '%{http_code}\n' \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GONKA_API_KEY" \
  -H "X-Request-Id: $G002A_REQUEST_ID" \
  -d "{\"model\":\"$GONKA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"CGQA timeout/retry probe: return a short deterministic acknowledgement.\"}],\"max_tokens\":32,\"stream\":false}" \
  > "evidence/$CGQA_RUN_ID/G-002A/attempt-1.http-code.txt"
export G002A_ATTEMPT1_EXIT=$?
set -e
```

Record the curl exit code and UTC timestamps in `attempt-1.transport-outcome.json`. A timeout is **ambiguous**, not failure-to-execute.

### 3. Observe accounting before retry

```bash
curl -sS "$GONKA_GATEWAY_BASE/v1/requests/$G002A_REQUEST_ID" \
  > "evidence/$CGQA_RUN_ID/G-002A/attempt-1.accounting.json"
```

Possible legitimate observations include: not yet visible, in-progress/partial state, completed accounting, or a terminal response that the client missed.

### 4. Retry once with the same request identity

```bash
curl -sS \
  --max-time 120 \
  -D "evidence/$CGQA_RUN_ID/G-002A/attempt-2.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-002A/attempt-2.response.redacted.json" \
  -w '%{http_code}\n' \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GONKA_API_KEY" \
  -H "X-Request-Id: $G002A_REQUEST_ID" \
  -d "{\"model\":\"$GONKA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"CGQA timeout/retry probe: return a short deterministic acknowledgement.\"}],\"max_tokens\":32,\"stream\":false}" \
  > "evidence/$CGQA_RUN_ID/G-002A/attempt-2.http-code.txt"
```

A `429` while the first request is still in flight is not a duplicate execution; capture it as a concurrency disposition and keep observing the first request.

### 5. Reconcile

```bash
curl -sS "$GONKA_GATEWAY_BASE/v1/requests/$G002A_REQUEST_ID" \
  > "evidence/$CGQA_RUN_ID/G-002A/final.accounting.json"
```

Check:

- all observed attempt nonces;
- winner nonce;
- winner vs non-winner attempts;
- `winner_actual_cost + other_attempts_actual_cost == all_attempts_actual_cost`;
- whether the second transport request was rejected, replayed/cached, or created an additional execution;
- whether every additional execution is explicitly represented and financially reconcilable.

---

## G-002B — ambiguous timeout, fresh transport request identity

Purpose: characterize a common generic-client retry policy where each HTTP attempt receives a new request ID even though the user's semantic intent did not change.

Use:

```bash
export G002B_REQUEST_ID_1="cgqa-$CGQA_RUN_ID-g002b-a1"
export G002B_REQUEST_ID_2="cgqa-$CGQA_RUN_ID-g002b-a2"
```

Repeat the G-002 procedure, but send attempt 1 with `$G002B_REQUEST_ID_1` and retry with `$G002B_REQUEST_ID_2`.

Do **not** expect Gonka to deduplicate two distinct request identities unless the protocol explicitly promises that behavior. The verification target is instead:

1. both executions, if any, are independently observable;
2. both costs, if any, are independently observable;
3. the CGQA evidence layer preserves one `logical_operation_id` across both transport IDs;
4. no execution/cost becomes orphaned or silently hidden.

This distinction matters because `X-Request-Id` is verified as a correlation primitive, not assumed to be an idempotency key.

---

## Reconciliation object

Create one `reconciliation.json` per case with at least:

```json
{
  "case_id": "G-002A",
  "logical_operation_id": "...",
  "transport_request_ids": ["..."],
  "observed_execution_nonces": [],
  "winner_nonce": null,
  "winner_actual_cost": 0,
  "other_attempts_actual_cost": 0,
  "all_attempts_actual_cost": 0,
  "transport_dispositions": [],
  "unexplained_effects": [],
  "verdict": "PASS|FAIL|INCONCLUSIVE"
}
```

## Failure handling

If a test produces an unexplained financial/state effect, stop escalating the fault. Preserve and redact evidence, classify it as a private hypothesis, and do not disclose security-sensitive details publicly until coordinated triage.