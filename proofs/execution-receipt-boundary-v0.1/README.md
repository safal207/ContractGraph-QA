# Execution receipt boundary v0.1

**System case:** \`EXECUTION-RECEIPT-001\`

This framework-neutral executable contract separates four states that are often collapsed:

\`\`\`text
AUTHORIZED
  -> PENDING receipt
  -> provider return / throw
  -> TERMINAL receipt
  -> authoritative external readback (separate)
\`\`\`

The contract deliberately does **not** treat authorization as proof that execution occurred and does **not** treat a local provider return/exception as authoritative truth about an external side effect.

## Receipt phases

### PENDING

Created at the authorization boundary before provider dispatch.

Required semantics:

\`\`\`text
phase = PENDING
local_outcome = NOT_OBSERVED
external_effect_status = UNKNOWN
\`\`\`

A PENDING receipt means:

> this exact logical action was authorized for this exact target/payload/correlation, but terminal execution evidence is not available yet.

If no terminal receipt arrives, continuity is:

\`\`\`text
UNKNOWN -> REVALIDATE
\`\`\`

Never \`NO_EFFECT\` and never automatic retry authority.

### TERMINAL / local success

After the provider call returns:

\`\`\`text
local_outcome = RETURNED_SUCCESS
external_effect_status = UNVERIFIED
\`\`\`

The local return is useful execution evidence, but it is not authoritative external readback.

### TERMINAL / local throw

After the provider call throws:

\`\`\`text
local_outcome = THREW
external_effect_status = UNKNOWN
\`\`\`

A thrown exception does **not** prove that the downstream system performed no external effect.

## Required binding

PENDING and TERMINAL must retain the same:

- \`action_id\`
- target
- payload digest
- \`trace_id\`
- \`decision_id\`
- \`execution_id\`
- \`evidence_id\`

Receipts form an append-only SHA-256 chain.

## Contract cases

| Case | Expected state |
|---|---|
| blocked / not authorized | no execution receipt |
| success + usage | PENDING -> RETURNED_SUCCESS / UNVERIFIED |
| success without usage | PENDING -> RETURNED_SUCCESS / UNVERIFIED |
| provider throws | PENDING -> THREW / UNKNOWN |
| terminal lost | PENDING remains UNKNOWN / REVALIDATE |

Usage is intentionally not part of receipt completeness.

## Unsafe mutants

The harness must reject:

1. \`THREW\` promoted to evidence that the external effect did not occur;
2. TERMINAL receipt without a prior PENDING authorization receipt;
3. target rebinding between PENDING and TERMINAL.

## Runtime experiment

The stacked Aegisora experiment tests the same contract against:

\`aegisora-ai/aegisora@2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`

Expected shape:

\`\`\`text
native Aegisora
  success + usage   -> terminal evidence
  success - usage   -> missing terminal
  provider throws   -> missing terminal
  verdict           -> RED

minimal external adapter
  success + usage   -> PENDING + TERMINAL
  success - usage   -> PENDING + TERMINAL
  provider throws   -> PENDING + TERMINAL
  verdict           -> GREEN
\`\`\`

The external adapter does not modify Aegisora source. It uses the enterprise audit callback to capture the exact ALLOW correlation IDs before provider dispatch, then appends terminal local-return/throw evidence after the gateway call completes.

## Claim ceiling

This contract does not prove:

- crash-atomic receipt durability;
- authoritative downstream effect truth;
- exactly-once execution;
- recipient identity;
- payment or settlement binding;
- distributed consensus;
- production provider behavior.

The next boundary after this proof is durable PENDING persistence across process interruption and authoritative readback reconciliation.
