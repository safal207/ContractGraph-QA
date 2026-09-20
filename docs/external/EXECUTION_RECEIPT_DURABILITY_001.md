# EXECUTION-RECEIPT-DURABILITY-001

**Stacked on:** EXECUTION-RECEIPT-001 / PR #204  
**Runtime subject:** \`aegisora-ai/aegisora@2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`

## Question

Can an execution receipt survive a real process crash in a state that is safe to reconcile without turning persisted PENDING state into execution authority?

## Acceptance matrix

| Case | Receiver truth | First recovery | Required continuity |
|---|---|---|---|
| effect then crash | one matching effect | FULL readback | FINALIZE_EXISTING |
| crash before effect | zero effects | FULL readback | FRESH_AUTHORIZATION_REQUIRED |
| effect then crash, readback unavailable | effect hidden from recovery | UNAVAILABLE | REVALIDATE |

For every case:

\`\`\`text
provider attempt count after recovery = 1
\`\`\`

Recovery itself may not redispatch.

## Process boundary

The subject process is expected to terminate by real \`SIGKILL\`.

The crash occurs after durable PENDING and after provider entry. Depending on the case it occurs either before or after the receiver effect.

Because \`SIGKILL\` bypasses local cleanup and normal exception/finally handling, the local TERMINAL receipt cannot be manufactured by graceful shutdown.

## Why verified NO_EFFECT still does not mean RETRY NOW

The proof uses:

\`\`\`text
FULL + NO_EFFECT
        ↓
FRESH_AUTHORIZATION_REQUIRED
\`\`\`

rather than:

\`\`\`text
FULL + NO_EFFECT
        ↓
automatic redispatch
\`\`\`

Execution authority remains separate from effect truth.

## Why UNAVAILABLE is the key negative control

In the UNAVAILABLE case, the test harness itself knows the receiver DB contains one effect and independently confirmed that effect before the kill.

The recovery process is intentionally not allowed to use that knowledge.

It must return:

\`\`\`text
INDETERMINATE
REVALIDATE
no redispatch
\`\`\`

Only a later FULL readback may resolve the action.

That directly guards against the unsafe inference:

\`\`\`text
cannot currently observe effect
≠
effect did not happen
\`\`\`

## Evidence artifact

The hosted evidence pack contains:

- exact-head report;
- independent verification report;
- subject source digests;
- dependency lock before/resolved/diff;
- all receipt SQLite databases;
- all receiver SQLite databases;
- SHA-256 manifest for preserved artifacts.

## Claim ceiling

Same-host SQLite + process SIGKILL only. No host-power-loss, distributed, production-provider, recipient, or settlement claim.
