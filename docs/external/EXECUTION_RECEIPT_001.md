# EXECUTION-RECEIPT-001 — native RED -> adapter GREEN

**Stacked on:** AEGISORA-EXECUTION-EVIDENCE-001 / PR #203  
**Aegisora subject:** \`2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`

## Research question

Can we define one execution-receipt contract that:

1. records authorization before provider dispatch without claiming execution already happened;
2. produces terminal evidence for both successful returns and thrown provider calls;
3. does not depend on billing/token usage;
4. preserves exact action/target/payload/correlation binding;
5. keeps external effect truth explicitly unresolved until authoritative readback exists?

## RED subject

The current pinned Aegisora path has two useful evidence layers:

- enterprise audit/evidence at the pre-execution enforcement boundary;
- enterprise usage evidence after a successful provider response with \`usage\`.

The RED condition is therefore not "Aegisora has no execution evidence."

The narrower condition is:

> native terminal execution evidence is conditional on a successful usage-bearing response.

Frozen expected native coverage:

\`\`\`text
success + usage   -> terminal evidence = yes
success - usage   -> terminal evidence = no
provider throws   -> terminal evidence = no

terminal coverage = 1 / 3
\`\`\`

If future Aegisora changes make native coverage 3/3, this RED probe must stop matching and the experiment should fail rather than preserve a stale conclusion.

## GREEN adapter

The minimal adapter is external to Aegisora source.

At the enterprise audit callback for an ALLOW decision it appends:

\`\`\`text
PENDING
local_outcome = NOT_OBSERVED
external_effect_status = UNKNOWN
\`\`\`

with the exact:

\`\`\`text
action_id
target
payload_digest
trace_id
decision_id
execution_id
evidence_id
\`\`\`

Then:

### provider returns

\`\`\`text
TERMINAL
local_outcome = RETURNED_SUCCESS
external_effect_status = UNVERIFIED
\`\`\`

This applies whether \`response.usage\` exists or not.

### provider throws

\`\`\`text
TERMINAL
local_outcome = THREW
external_effect_status = UNKNOWN
error_digest = sha256(error)
\`\`\`

The throw is deliberately not mapped to \`NO_EFFECT\`.

## Why PENDING matters

A wrapper that only writes after \`gateway.generate()\` returns or throws has a blind interval:

\`\`\`text
ALLOW
  -> provider side effect
  -> process interruption
  -> wrapper never writes receipt
\`\`\`

The adapter therefore records PENDING from the pre-dispatch ALLOW audit callback.

This still does **not** prove crash-atomic durability because the proof store is only an in-memory bounded fixture. It freezes the semantics needed for a future durable implementation:

\`\`\`text
PENDING without terminal
  -> UNKNOWN
  -> REVALIDATE
\`\`\`

## RED -> GREEN acceptance

Hosted CI passes only when both are true:

\`\`\`text
native subject = RED
  terminal coverage 1/3

external adapter = GREEN
  terminal coverage 3/3
\`\`\`

The adapter's six receipts (PENDING + TERMINAL for three allowed calls) must form one valid SHA-256 chain.

## What this proof does not claim

- no Aegisora source patch is proposed;
- no crash-atomic durable receipt store is proven;
- no authoritative external provider readback exists;
- RETURNED_SUCCESS is not external-effect confirmation;
- THREW is not external no-effect evidence;
- no recipient or settlement binding is tested.

## Next boundary

The next useful experiment is no longer another in-process adapter.

It is:

\`\`\`text
durable PENDING
  -> real/fresh-process interruption
  -> authoritative readback
  -> terminal reconciliation
\`\`\`

That would connect the receipt contract back into the LiminalDB \`UNKNOWN / REVALIDATE\` continuity semantics and the Evidence Plane.
