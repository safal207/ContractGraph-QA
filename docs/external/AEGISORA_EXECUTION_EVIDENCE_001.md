# AEGISORA-EXECUTION-EVIDENCE-001

**Status:** bounded external runtime characterization  
**Subject:** \`aegisora-ai/aegisora@2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`  
**Stacked on:** \`AEGISORA-PROVIDER-BINDING-001\`

## Question

After a provider action is correctly authorized and actually reaches the provider, does Aegisora retain post-execution evidence that binds the real execution back to the same authorization identities?

The tested identities are:

\`\`\`text
traceId
decisionId
executionId
evidenceId
agentId
providerId
modelId
\`\`\`

The experiment also asks whether that evidence exists for:

1. a successful provider response with \`usage\`;
2. a successful provider response without \`usage\`;
3. a provider invocation that throws.

## Why this follows the provider-binding proof

\`AEGISORA-PROVIDER-BINDING-001\` showed that an approval for \`provider:openai\` cannot be rebound to \`provider:anthropic\`, and that the exact approved provider executes once.

That same run exposed a separate fact:

\`\`\`text
ALLOW enforcement record
  enforcement_status = not_executed
  execution_outcome  = not_attempted

external spy provider
  calls = 1
\`\`\`

That is coherent if the enforcement record is a pre-execution authorization artifact. It is insufficient by itself as post-execution evidence.

Aegisora also exposes \`EnterpriseUsageRuntimeBridge\`, called by \`ProviderExecutionGateway\` after a successful provider response carrying usage. This experiment characterizes that bridge as an execution-evidence path.

## Subject integrity

CI checks out the exact detached upstream commit and records SHA-256 digests for:

- approval engine;
- enforcement gate;
- enterprise usage bridge;
- provider execution gateway;
- base provider contract.

No Aegisora source file is patched.

The external probe is copied into the subject test directory and executed against the built upstream runtime.

The pinned upstream lockfile is stale relative to the runtime package manifest, so dependency installation uses pnpm \`11.20.0 --no-frozen-lockfile\`. Original lock, resolved lock and lock diff are retained in the artifact.

## Local execution oracle

All providers are inert local spies. No production credentials or provider calls are used.

### Case A — blocked provider rebinding

An approval created for \`provider:openai\` is presented to \`provider:anthropic\`.

Required:

\`\`\`text
decision = BLOCK
openai calls = 0
anthropic calls = 0
usage events = 0
\`\`\`

This confirms blocked authorization does not create execution evidence.

### Case B — successful execution with usage

The exact approved \`provider:openai\` request executes once.

The provider deliberately returns spoofed response identity fields:

\`\`\`text
response.provider = spoofed-response-provider
response.model    = spoofed-response-model
\`\`\`

while also returning usage.

Required post-execution event:

\`\`\`text
eventType  = provider.execution
outcome    = executed
providerId = openai
modelId    = test-model
\`\`\`

The event must preserve the exact \`traceId\`, \`decisionId\`, \`executionId\` and \`evidenceId\` from the ALLOW decision.

This tests whether canonical execution identity comes from the gateway rather than untrusted ProviderResponse identity fields.

### Case C — successful execution without usage

A \`provider:gemini\` spy executes and returns a normal output but no \`response.usage\`.

Required observation:

\`\`\`text
decision = ALLOW
provider calls = 1
new EnterpriseUsage event = 0
\`\`\`

This identifies whether the usage bridge is a general execution receipt or a conditional usage-bearing receipt.

### Case D — provider invocation fails

A \`provider:groq\` spy is authorized and then throws from \`generate()\`.

Required observation:

\`\`\`text
pre-execution decision = ALLOW
provider calls = 1
provider error propagates
new outcome=failed usage event = 0
\`\`\`

The bridge's input type supports \`outcome: "failed"\`, but this experiment tests whether the provider gateway actually emits that event on its failure path.

## Independent verifier

The subject produces a machine-readable observation packet.

A separate Python verifier checks:

- exact upstream commit;
- blocked rebind has zero effects and zero execution event;
- usage-bearing success emits one correlated \`provider.execution\` event;
- all four correlation IDs equal the ALLOW decision;
- provider/model identities ignore spoofed response fields;
- successful execution without usage has no new usage event;
- provider failure has no new failed execution event.

## Expected interpretation

The experiment is designed to produce a coverage result rather than force a single all-or-nothing verdict.

A possible result is:

\`\`\`text
usage-bearing successful execution
  -> correlated post-execution evidence

successful execution without usage
  -> no post-execution usage record

failed provider invocation
  -> no failed post-execution usage record
\`\`\`

If observed, the correct interpretation is:

> \`EnterpriseUsageRuntimeBridge\` can close the authorization-to-execution evidence seam for a successful usage-bearing provider response, but it is not a general execution receipt for every provider outcome on this path.

## Claim ceiling

This experiment does not establish:

- production-provider behavior;
- recipient identity;
- payment or settlement binding;
- provider-side idempotency;
- distributed durability of the usage writer;
- mandatory usage-bridge configuration;
- universal coverage of every Aegisora tool/provider path.

## Canonical invariant

> **A pre-execution ALLOW decision and a post-execution observation are different evidence objects; when both exist, their identities must bind exactly.**
