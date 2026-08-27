# Issue draft: Smart Contract Finality Continuity v0.2

## Problem

Bridge v0.1 can bind one observed receipt, block witness, head, and confirmation
count. One RPC observation and a positive confirmation count do not establish
canonical finality. Receipt disappearance, block replacement, transaction
replacement, and reorg recovery need repeated evidence and an explicit policy.

## Proposed scope

- versioned repeated-capture series for one exact transaction/attempt;
- receipt appearance and disappearance;
- block-hash and parent-hash replacement;
- transaction replacement by sender/nonce with payload binding;
- explicit confirmation/finality policy by chain;
- optional multi-RPC corroboration with independent source identity;
- deterministic classification of observed replacement/reorg transitions;
- integration with LTP only after a separate versioned semantic contract is
  reviewed.

## Non-goals

- no silent addition of `MINED`, `CONFIRMING`, `FINALIZED`, `REORGED`, or
  `REPLACED` to LTP v0.1 terminal statuses;
- no claim that majority RPC agreement proves canonical truth;
- no production RPC calls in default CI;
- no automatic retry permission from receipt disappearance alone.

## Acceptance evidence

1. receipt persists across repeated captures and satisfies declared policy;
2. receipt disappears after earlier observation;
3. same height contains a replacement block hash;
4. same sender/nonce resolves to a different transaction hash;
5. providers disagree and the result remains bounded/inconclusive;
6. deterministic replay produces byte-identical transition reports;
7. old v0.1 fixtures remain unchanged.
