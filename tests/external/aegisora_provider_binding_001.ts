import fs from "node:fs";
import { ProviderExecutionGateway } from "../src/providers/provider-execution-gateway";
import { RuntimeContext } from "../src/context/runtime-context";
import { PermissionEngine } from "../src/permissions";
import { ApprovalEngine } from "../src/approval";

const SYSTEM_CASE = "AEGISORA-PROVIDER-BINDING-001";
const UPSTREAM_COMMIT = "2bac618215671f6f0ac8ebddf169830d4fc0f9b3";

class SpyProvider {
  calls = 0;
  constructor(readonly name: string) {}
  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      output: this.name + ":executed",
      usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2 },
    };
  }
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(SYSTEM_CASE + " ASSERTION_FAILED: " + message);
  }
}

function latestDecision(context: RuntimeContext): any {
  const decisions = context.decisionStore.getAll();
  assert(decisions.length > 0, "expected at least one enforcement decision");
  return decisions[decisions.length - 1];
}

function decisionView(decision: any) {
  return {
    decision: String(decision.decision).toUpperCase(),
    reason: String(decision.reason ?? ""),
    trace_id: decision.traceId ?? null,
    decision_id: decision.decisionId ?? decision.id ?? null,
    execution_id: decision.executionId ?? null,
    evidence_id: decision.evidenceId ?? null,
    enforcement_status: decision.enforcementStatus ?? null,
    execution_outcome: decision.executionOutcome ?? null,
    canonical_tool: decision.metadata?.canonicalTool ?? decision.metadata?.tool ?? null,
    approval_id: decision.metadata?.approvalId ?? null,
  };
}

async function main() {
  const evidenceOut = process.env.EVIDENCE_OUT;
  assert(evidenceOut, "EVIDENCE_OUT must be set");

  const context = new RuntimeContext();
  const agentId = "external-binding-auditor";
  context.agentRegistry.register({ id: agentId, name: agentId });

  const approvals = new ApprovalEngine();
  const gateway = new ProviderExecutionGateway(
    context,
    undefined,
    undefined,
    new PermissionEngine(),
    undefined,
    approvals,
  );

  const openai = new SpyProvider("openai");
  const anthropic = new SpyProvider("anthropic");
  const router = (gateway as any).router;
  const token = (gateway as any).providerExecutionToken;
  router.register("openai", openai, token);
  router.register("anthropic", anthropic, token);

  const request = {
    prompt: "bounded provider-binding probe",
    model: "test-model",
  };

  let escalationError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "openai",
      request,
      metadata: { requiresReview: true },
    });
  } catch (error) {
    escalationError = String(error);
  }

  assert(
    escalationError.includes("[ENFORCEMENT:ESCALATE]"),
    "initial openai request must ESCALATE",
  );
  assert(
    openai.calls === 0 && anthropic.calls === 0,
    "ESCALATE must cause zero provider side effects",
  );

  const escalation = latestDecision(context);
  const approvalId = escalation.metadata?.approvalId;
  assert(
    typeof approvalId === "string" && approvalId.length > 0,
    "ESCALATE decision must retain approvalId",
  );

  const pending = approvals.get(approvalId);
  assert(pending?.status === "pending", "new approval must be pending");

  approvals.approve({ approvalId, actorId: "external-auditor" });
  const approved = approvals.get(approvalId);
  assert(approved?.status === "approved", "approval must become approved");

  let rebindError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "anthropic",
      request,
      metadata: { requiresReview: true, approvalId },
    });
  } catch (error) {
    rebindError = String(error);
  }

  const rebindDecision = latestDecision(context);
  assert(
    rebindError.includes("[ENFORCEMENT:BLOCK]"),
    "provider rebinding must BLOCK",
  );
  assert(
    /binding mismatch/i.test(rebindError),
    "provider rebinding must fail on approval binding mismatch",
  );
  assert(
    String(rebindDecision.decision).toUpperCase() === "BLOCK",
    "rebind audit decision must be BLOCK",
  );
  assert(openai.calls === 0, "rebind must not call approved provider");
  assert(anthropic.calls === 0, "rebind must not call alternate provider");

  const afterRebind = approvals.get(approvalId);
  assert(
    afterRebind?.status === "approved",
    "failed rebind must not consume the valid approval",
  );

  const rebindOpenaiCalls = openai.calls;
  const rebindAnthropicCalls = anthropic.calls;

  const exactResult = await gateway.generate({
    agentId,
    provider: "openai",
    request,
    metadata: { requiresReview: true, approvalId },
  });

  const exactDecision = latestDecision(context);
  assert(
    exactResult.output === "openai:executed",
    "exact approved resume must reach openai spy provider",
  );
  assert(
    String(exactDecision.decision).toUpperCase() === "ALLOW",
    "exact resume audit decision must be ALLOW",
  );
  assert(openai.calls === 1, "exact resume must call approved provider once");
  assert(anthropic.calls === 0, "exact resume must not call alternate provider");

  const consumed = approvals.get(approvalId);
  assert(consumed?.status === "consumed", "exact resume must consume approval");

  let replayError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "openai",
      request,
      metadata: { requiresReview: true, approvalId },
    });
  } catch (error) {
    replayError = String(error);
  }

  const replayDecision = latestDecision(context);
  assert(
    replayError.includes("[ENFORCEMENT:BLOCK]"),
    "consumed approval replay must BLOCK",
  );
  assert(
    openai.calls === 1 && anthropic.calls === 0,
    "replay must not cause another provider side effect",
  );

  const report = {
    system_case: SYSTEM_CASE,
    status: "OBSERVED",
    upstream: {
      repository: "aegisora-ai/aegisora",
      commit: UPSTREAM_COMMIT,
    },
    boundary: {
      approved_provider: "openai",
      rebound_provider: "anthropic",
      action: "provider.generate",
      request,
    },
    phases: {
      escalation: {
        ...decisionView(escalation),
        approval_status: pending?.status,
        openai_calls: 0,
        anthropic_calls: 0,
      },
      provider_rebind: {
        ...decisionView(rebindDecision),
        error: rebindError,
        approval_status: afterRebind?.status,
        openai_calls: rebindOpenaiCalls,
        anthropic_calls: rebindAnthropicCalls,
      },
      exact_resume: {
        ...decisionView(exactDecision),
        approval_status: consumed?.status,
        output: exactResult.output,
        openai_calls: 1,
        anthropic_calls: 0,
      },
      replay: {
        ...decisionView(replayDecision),
        error: replayError,
        approval_status: approvals.get(approvalId)?.status,
        openai_calls: openai.calls,
        anthropic_calls: anthropic.calls,
      },
    },
    observed_invariant: {
      provider_rebinding_rejected_before_side_effect: true,
      exact_bound_provider_executes_once: true,
      consumed_approval_replay_blocked: true,
    },
    claim_ceiling:
      "Pinned Aegisora runtime plus inert local spy providers only; no recipient identity, payment/settlement binding, distributed durability, or production-provider claim.",
  };

  fs.writeFileSync(
    evidenceOut,
    JSON.stringify(report, null, 2) + "\n",
    "utf8",
  );
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
