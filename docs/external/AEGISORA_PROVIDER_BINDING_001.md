# AEGISORA-PROVIDER-BINDING-001

**Status:** bounded external runtime probe  
**Subject:** \`aegisora-ai/aegisora@2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`  
**Research authorization:** public Aegisora issue #28, "Break the Agent Execution Boundary"

## Question

Can an approval created for one provider/tool identity be rebound after approval to a different provider while keeping the same agent, action, arguments and approval ID?

Bounded transition:

\`\`\`text
agent A
+ provider:openai
+ provider.generate
+ args X
        |
        v
    ESCALATE
        |
    human APPROVE
        |
        +-------------------------------+
        |                               |
        v                               v
provider:anthropic                 provider:openai
same action / args / approval      exact approved resume
        |                               |
 expected BLOCK                    expected ALLOW
 zero provider calls               openai calls = 1
\`\`\`

The probe then replays the consumed exact approval and requires a second BLOCK with no duplicate provider call.

## Why this is the next Evidence Plane boundary

\`EVIDENCE-PLANE-001\` established stable logical action identity, payload/effect relationships, temporal knowledge and explanation projections over the pinned Crashpoint fixture.

Crashpoint does not expose an independently bound target or recipient identity.

Aegisora's runtime exposes a narrower real execution-target dimension:

\`\`\`text
request.tool = provider:<provider-name>
\`\`\`

and includes that tool identity inside the approval request binding.

This experiment therefore tests **provider/tool identity rebinding**, not recipient or settlement identity.

## Subject integrity

CI does not patch Aegisora.

It:

1. clones the public repository;
2. checks out the exact detached commit:
   \`2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`;
3. records SHA-256 digests of the subject files relevant to:
   - approval binding;
   - enforcement;
   - provider execution;
   - permission evaluation;
4. builds the pinned runtime;
5. copies an external probe into the runtime test directory;
6. executes that probe against the unchanged subject code.

## Side-effect oracle

No production provider, credential or network side effect is used.

Two inert local provider implementations are registered:

\`\`\`text
openai spy
anthropic spy
\`\`\`

Each spy increments a call counter only when its \`generate()\` method is actually reached.

The counters are the execution oracle.

A runtime \`BLOCK\` record alone is not sufficient for PASS.

## Required phases

### 1. Approval acquisition

Request:

\`\`\`text
agent = external-binding-auditor
tool = provider:openai
action = provider.generate
prompt/model = X
requiresReview = true
\`\`\`

Required:

\`\`\`text
decision = ESCALATE
approval.status = pending
openai calls = 0
anthropic calls = 0
\`\`\`

The approval is then explicitly approved.

### 2. Provider rebinding negative control

Resume the same approved transition with:

\`\`\`text
tool = provider:anthropic
same agent
same action
same args
same approvalId
\`\`\`

Required:

\`\`\`text
decision = BLOCK
reason includes binding mismatch
approval remains approved
openai calls = 0
anthropic calls = 0
\`\`\`

The "approval remains approved" condition matters: a rejected tampered resume must not destroy the still-valid exact approval.

### 3. Exact resume positive control

Resume with the original provider:

\`\`\`text
provider:openai
same agent
same action
same args
same approvalId
\`\`\`

Required:

\`\`\`text
decision = ALLOW
openai calls = 1
anthropic calls = 0
approval.status = consumed
\`\`\`

### 4. Consumed-approval replay

Replay the exact request again.

Required:

\`\`\`text
decision = BLOCK
openai calls remains 1
anthropic calls remains 0
\`\`\`

## Independent verifier

The subject probe writes a machine-readable JSON observation.

A separate Python verifier in ContractGraph-QA checks:

- exact upstream repository and commit;
- all four decision states;
- approval lifecycle;
- provider call counters;
- rebinding rejection reason;
- exact provider execution cardinality;
- no side effect on rebind;
- no duplicate side effect on replay.

The workflow preserves the subject report, verifier result, console output, subject-source digests and SHA-256 manifest as one evidence artifact.

## PASS means

Within this exact pinned Aegisora runtime and inert local provider fixture:

> an approval created for \`provider:openai\` cannot be rebound to \`provider:anthropic\` using the same approval ID, action and arguments; the alternate provider is not invoked; the still-valid approval can then authorize exactly one execution of the originally bound provider; subsequent replay is blocked.

## PASS does not mean

A green result does **not** establish:

- arbitrary tool/provider binding across every Aegisora execution path;
- recipient identity;
- payment payer/payee identity;
- x402 settlement binding;
- production OpenAI/Anthropic behavior;
- network or provider-side idempotency;
- distributed approval-store durability;
- resistance to all canonicalization attacks;
- universal mandatory mediation.

Those remain separate boundaries.

## Canonical invariant

> **Approval for one execution target is not authority for a different execution target.**
