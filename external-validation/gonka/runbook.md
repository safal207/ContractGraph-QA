# Gonka Verification Runbook — G-001 / G-002

Pinned upstream revision: `f040d0a5b5ef207a0c431894c9f9e2608f9d3073`

This runbook is intentionally limited to Gonka's local Docker testenv, a Community DevNet, or another environment where testing is explicitly permitted. Do not point ambiguity/fault procedures at mainnet or an unconsenting public broker.

## Upstream surfaces used

The devshard gateway exposes an OpenAI-compatible `POST /v1/chat/completions`, public `GET /v1/status`, per-request accounting at `GET /v1/requests/{request_id}`, and an escrow-keyed form under `/devshard/{escrow_id}/...`. The gateway binds inbound `X-Request-Id` into request context and echoes that identity on the response. Request accounting exposes execution-attempt and cost lineage.

A client disconnect is not proof that execution stopped. The gateway can continue protocol completion after the client disconnects. G-002 therefore classifies a client timeout as an ambiguous transport outcome until accounting evidence resolves it.

## Required environment

```bash
export GONKA_GATEWAY_BASE="https://<explicitly-permitted-test-gateway>"
export GONKA_API_KEY="<test-api-key-if-required>"
export GONKA_MODEL="<advertised-test-model>"
export GONKA_ESCROW_ID="<selected-test-escrow-id>"
export CGQA_RUN_ID="gonka-$(date -u +%Y%m%dT%H%M%SZ)"
```

Build authentication arguments once. An empty API key must not produce an empty Bearer credential:

```bash
GONKA_AUTH_ARGS=()
if [ -n "${GONKA_API_KEY:-}" ]; then
  GONKA_AUTH_ARGS=(-H "Authorization: Bearer $GONKA_API_KEY")
fi
```

Do not store secrets in evidence. Never persist `GONKA_AUTH_ARGS`, Authorization headers, private keys, or admin material.

## Evidence directory

```bash
mkdir -p \
  "evidence/$CGQA_RUN_ID/G-001" \
  "evidence/$CGQA_RUN_ID/G-002A" \
  "evidence/$CGQA_RUN_ID/G-002B"
```

Every reconciliation bundle records UTC timestamps, the pinned upstream revision, one CGQA `logical_operation_id`, transport request IDs, execution nonces, and cost lineage.

---

## G-001 — normal inference control

### 1. Capture baseline status and selected devshard state

```bash
curl -fsS "${GONKA_AUTH_ARGS[@]}" \
  "$GONKA_GATEWAY_BASE/v1/status" \
  > "evidence/$CGQA_RUN_ID/G-001/gateway_status.before.json"

curl -fsS "${GONKA_AUTH_ARGS[@]}" \
  "$GONKA_GATEWAY_BASE/devshard/$GONKA_ESCROW_ID/v1/state" \
  > "evidence/$CGQA_RUN_ID/G-001/devshard_state.before.json"
```

Confirm the selected test escrow/devshard is funded before dispatch. Funding is a precondition, not something inferred from a successful response.

### 2. Create request metadata and redacted request body

```bash
export G001_REQUEST_ID="cgqa-$CGQA_RUN_ID-g001-a1"

cat > "evidence/$CGQA_RUN_ID/G-001/request.redacted.json" <<EOF
{"model":"$GONKA_MODEL","messages":[{"role":"user","content":"CGQA control request: reply with a short deterministic acknowledgement."}],"max_tokens":32,"stream":false}
EOF
```

Create `run_metadata.json` with at least `case_id`, `run_id`, `logical_operation_id`, pinned upstream revision, environment, model, escrow ID, and UTC start time.

### 3. Submit exactly one request, no client retry

```bash
curl -fsS \
  --max-time 120 \
  -D "evidence/$CGQA_RUN_ID/G-001/response.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-001/response.redacted.json" \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  "${GONKA_AUTH_ARGS[@]}" \
  -H "X-Request-Id: $G001_REQUEST_ID" \
  --data-binary @"evidence/$CGQA_RUN_ID/G-001/request.redacted.json"
```

### 4. Query request accounting

```bash
curl -fsS "${GONKA_AUTH_ARGS[@]}" \
  "$GONKA_GATEWAY_BASE/devshard/$GONKA_ESCROW_ID/v1/requests/$G001_REQUEST_ID" \
  > "evidence/$CGQA_RUN_ID/G-001/accounting.json"
```

### 5. Capture final state

```bash
curl -fsS "${GONKA_AUTH_ARGS[@]}" \
  "$GONKA_GATEWAY_BASE/v1/status" \
  > "evidence/$CGQA_RUN_ID/G-001/gateway_status.after.json"

curl -fsS "${GONKA_AUTH_ARGS[@]}" \
  "$GONKA_GATEWAY_BASE/devshard/$GONKA_ESCROW_ID/v1/state" \
  > "evidence/$CGQA_RUN_ID/G-001/devshard_state.after.json"
```

Create `reconciliation.json` conforming to `evidence.schema.json`.

### G-001 minimum PASS

- every transport request ID has a terminal disposition;
- request accounting exists;
- every execution nonce has known request lineage;
- winner/non-winner totals derived from `attempts[]` match the reported cost fields;
- required source artifacts exist;
- there are zero unexplained effects.

Do not proceed to G-002 if G-001 cannot be reconciled.

---

## G-002A — ambiguous timeout, stable `X-Request-Id`

Purpose: determine what happens when one semantic operation is retried with the same protocol request identity.

### 1. Stable identities and request source

```bash
export G002A_LOGICAL_ID="cgqa-$CGQA_RUN_ID-logical-g002a"
export G002A_REQUEST_ID="cgqa-$CGQA_RUN_ID-g002a"

cat > "evidence/$CGQA_RUN_ID/G-002A/attempt-1.request.redacted.json" <<EOF
{"model":"$GONKA_MODEL","messages":[{"role":"user","content":"CGQA timeout/retry probe: return a short deterministic acknowledgement."}],"max_tokens":32,"stream":false}
EOF
cp "evidence/$CGQA_RUN_ID/G-002A/attempt-1.request.redacted.json" \
   "evidence/$CGQA_RUN_ID/G-002A/attempt-2.request.redacted.json"
```

Capture `gateway_status.before.json`, `devshard_state.before.json`, and `run_metadata.json` before dispatch.

### 2. First attempt — intentionally short client timeout

Use this only on an explicitly permitted test gateway. The local Docker harness uses Gonka's deterministic mock-openai latency hook instead of relying on public-network latency.

```bash
set +e
curl -sS \
  --max-time 1 \
  -D "evidence/$CGQA_RUN_ID/G-002A/attempt-1.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-002A/attempt-1.response.redacted.json" \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  "${GONKA_AUTH_ARGS[@]}" \
  -H "X-Request-Id: $G002A_REQUEST_ID" \
  --data-binary @"evidence/$CGQA_RUN_ID/G-002A/attempt-1.request.redacted.json"
G002A_ATTEMPT1_EXIT=$?
set -e
```

Write `attempt-1.transport-outcome.json` with the request ID, timestamps, client exit code, HTTP status if any, and disposition. A client timeout is `client_timeout_ambiguous`, never `proven_non_execution` by assumption.

### 3. Observe before retry

Capture:

- `attempt-1.accounting.json` — the observed accounting snapshot, or an explicit JSON `observed:false` record;
- `gateway_status.after-attempt-1.json`.

### 4. Retry exactly once with the same request identity

```bash
curl -sS \
  --max-time 120 \
  -D "evidence/$CGQA_RUN_ID/G-002A/attempt-2.headers.txt" \
  -o "evidence/$CGQA_RUN_ID/G-002A/attempt-2.response.redacted.json" \
  -X POST "$GONKA_GATEWAY_BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  "${GONKA_AUTH_ARGS[@]}" \
  -H "X-Request-Id: $G002A_REQUEST_ID" \
  --data-binary @"evidence/$CGQA_RUN_ID/G-002A/attempt-2.request.redacted.json"
```

A `429` while the first operation is in flight is explicit proof that the retry was rejected at that boundary; do not count it as an execution.

Capture `attempt-2.transport-outcome.json`, `attempt-2.accounting.json`, `gateway_status.after-attempt-2.json`, `devshard_state.after.json`, and final `reconciliation.json`.

---

## G-002B — ambiguous timeout, fresh transport request identity

Purpose: characterize a generic retry policy where each HTTP attempt has a fresh request ID while CGQA preserves one semantic intent.

```bash
export G002B_LOGICAL_ID="cgqa-$CGQA_RUN_ID-logical-g002b"
export G002B_REQUEST_ID_1="cgqa-$CGQA_RUN_ID-g002b-a1"
export G002B_REQUEST_ID_2="cgqa-$CGQA_RUN_ID-g002b-a2"
```

Repeat the G-002 procedure with attempt 1 using `$G002B_REQUEST_ID_1` and attempt 2 using `$G002B_REQUEST_ID_2`.

Do **not** assume Gonka deduplicates distinct request identities. PASS requires instead that:

1. both transport attempts have known dispositions;
2. a successful/ambiguous attempt has accounting lineage or the case is `INCONCLUSIVE`;
3. an explicitly rejected attempt is recorded as non-executing at that boundary;
4. every observed execution nonce and cost is attributable;
5. cached aliases are reconciled back to one source lineage rather than double-counted;
6. no effect is silently orphaned.

---

## Cost reconciliation

For every unique accounting source:

```text
derived_winner_cost = sum(attempt.actual_cost where attempt.winner == true)
derived_other_cost  = sum(attempt.actual_cost where attempt.winner == false)
derived_all_cost    = derived_winner_cost + derived_other_cost
```

Require:

```text
derived_winner_cost == cost.winner_actual_cost
derived_other_cost  == cost.other_attempts_actual_cost
derived_all_cost    == cost.all_attempts_actual_cost
```

A summary whose aggregate fields add up but disagree with `attempts[]` is not valid evidence.

## Verdict handling

- `PASS` — complete source evidence and no unexplained effects.
- `INCONCLUSIVE` — one or more required causal observations cannot be resolved; do not treat as PASS.
- `FAIL` — reconciliation invariant violated. The Docker test must fail on a conclusive `FAIL`.

A `FAIL` is not automatically a vulnerability. Preserve/redact evidence, stop increasing fault intensity, and classify security-sensitive or financial discrepancies as private hypotheses until independently reproduced and responsibly disclosed.
