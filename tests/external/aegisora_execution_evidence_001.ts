import fs from "node:fs";

import { ProviderExecutionGateway } from "../src/providers/provider-execution-gateway";
import { RuntimeContext } from "../src/context/runtime-context";
import { PermissionEngine } from "../src/permissions";
import { ApprovalEngine } from "../src/approval";

const SYSTEM_CASE = "AEGISORA-EXECUTION-EVIDENCE-001";
const UPSTREAM_COMMIT = "2bac618215671f6f0ac8ebddf169830d4fc0f9b3";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(SYSTEM_CASE + " ASSERTION_FAILED: " + message);
  }
}

class UsageProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      provider: "spoofed-response-provider",
      model: "spoofed-response-model",
      output: "usage-bearing-success",
      usage: {
        promptTokens: 5,
        completionTokens: 3,
        totalTokens: 8,
      },
    };
  }
}

class NoUsageProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      provider: "spoofed-no-usage-provider",
      model: "spoofed-no-usage-model",
      output: "success-without-usage",
    };
  }
}

class ThrowingProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown): Promise<never> {
    this.calls += 1;
    throw new Error("synthetic-provider-failure");
  }
}

class IdleProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      provider: "idle",
      model: "idle",
      output: "unexpected",
      usage: {
        promptTokens: 1,
        completionTokens: 1,
        totalTokens: 2,
      },
    };
  }
}

function latestDecision(context: RuntimeContext): any {
  const decisions = context.decisionStore.getAll();
  assert(decisions.length > 0, "expected an enforcement decision");
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

function usageView(event: any) {
  return {
    event_id: event.eventId ?? null,
    workspace_id: event.workspaceId ?? null,
    trace_id: event.traceId ?? null,
    decision_id: event.decisionId ?? null,
    execution_id: event.executionId ?? null,
    evidence_id: event.evidenceId ?? null,
    agent_id: event.agentId ?? null,
    provider_id: event.providerId ?? null,
    model_id: event.modelId ?? null,
    event_type: event.eventType ?? null,
    outcome: event.outcome ?? null,
    usage: event.usage ?? null,
    metadata: event.metadata ?? null,
  };
}

async function main() {
  const evidenceOut = process.env.EVIDENCE_OUT;
  assert(evidenceOut, "EVIDENCE_OUT must be set");

  const context = new RuntimeContext();
  const agentId = "external-execution-evidence-auditor";
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

  const usageEvents: any[] = [];
  gateway.configureEnterpriseUsage({
    workspaceId: "workspace-execution-evidence",
    writer: {
      async create(input: any) {
        const event = JSON.parse(JSON.stringify(input));
        usageEvents.push(event);
        return event;
      },
    },
  });

  const withUsage = new UsageProvider();
  const noUsage = new NoUsageProvider();
  const throwing = new ThrowingProvider();
  const reboundTarget = new IdleProvider();

  const router = (gateway as any).router;
  const token = (gateway as any).providerExecutionToken;

  router.register("openai", withUsage, token);
  router.register("gemini", noUsage, token);
  router.register("groq", throwing, token);
  router.register("anthropic", reboundTarget, token);

  const approvedRequest = {
    prompt: "execution-evidence-approved-path",
    model: "test-model",
  };

  let escalationError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "openai",
      request: approvedRequest,
      metadata: { requiresReview: true },
    });
  } catch (error) {
    escalationError = String(error);
  }

  assert(
    escalationError.includes("[ENFORCEMENT:ESCALATE]"),
    "review-gated request must ESCALATE",
  );
  assert(withUsage.calls === 0, "ESCALATE must not call openai provider");
  assert(usageEvents.length === 0, "ESCALATE must not emit execution usage event");

  const escalation = latestDecision(context);
  const approvalId = escalation.metadata?.approvalId;
  assert(
    typeof approvalId === "string" && approvalId.length > 0,
    "ESCALATE must retain approvalId",
  );

  approvals.approve({
    approvalId,
    actorId: "external-execution-evidence-auditor",
  });

  let rebindError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "anthropic",
      request: approvedRequest,
      metadata: { requiresReview: true, approvalId },
    });
  } catch (error) {
    rebindError = String(error);
  }

  const rebindDecision = latestDecision(context);
  assert(
    rebindError.includes("[ENFORCEMENT:BLOCK]"),
    "rebound provider must BLOCK",
  );
  assert(
    withUsage.calls === 0 && reboundTarget.calls === 0,
    "blocked rebind must have zero provider side effects",
  );
  assert(
    usageEvents.length === 0,
    "blocked rebind must not emit provider.execution usage event",
  );

  const approvedResponse = await gateway.generate({
    agentId,
    provider: "openai",
    request: approvedRequest,
    metadata: { requiresReview: true, approvalId },
  });

  const approvedDecision = latestDecision(context);
  assert(
    String(approvedDecision.decision).toUpperCase() === "ALLOW",
    "exact approved resume must ALLOW",
  );
  assert(withUsage.calls === 1, "approved provider must execute exactly once");
  assert(usageEvents.length === 1, "usage-bearing execution must emit exactly one usage event");

  const approvedUsage = usageEvents[0];
  assert(approvedUsage.eventType === "provider.execution", "wrong usage event type");
  assert(approvedUsage.outcome === "executed", "successful provider event must be executed");
  assert(approvedUsage.providerId === "openai", "usage event must use canonical provider identity");
  assert(approvedUsage.modelId === "test-model", "usage event must use canonical model identity");
  assert(approvedUsage.agentId === agentId, "usage event agent identity drift");
  assert(
    approvedUsage.traceId === approvedDecision.traceId,
    "usage event traceId must bind to ALLOW decision",
  );
  assert(
    approvedUsage.decisionId === approvedDecision.decisionId,
    "usage event decisionId must bind to ALLOW decision",
  );
  assert(
    approvedUsage.executionId === approvedDecision.executionId,
    "usage event executionId must bind to ALLOW decision",
  );
  assert(
    approvedUsage.evidenceId === approvedDecision.evidenceId,
    "usage event evidenceId must bind to ALLOW decision",
  );
  assert(
    approvedUsage.usage?.totalTokens === 8,
    "usage event token propagation drift",
  );
  assert(
    approvedResponse.provider === "spoofed-response-provider",
    "fixture must preserve spoofed response identity control",
  );
  assert(
    approvedUsage.providerId !== approvedResponse.provider,
    "usage event incorrectly trusted provider response identity",
  );
  assert(
    approvedUsage.modelId !== approvedResponse.model,
    "usage event incorrectly trusted provider response model identity",
  );

  const beforeNoUsageEvents = usageEvents.length;
  const noUsageResponse = await gateway.generate({
    agentId,
    provider: "gemini",
    request: {
      prompt: "successful-call-without-usage",
      model: "no-usage-model",
    },
  });
  const noUsageDecision = latestDecision(context);

  assert(
    String(noUsageDecision.decision).toUpperCase() === "ALLOW",
    "no-usage provider call must be authorized",
  );
  assert(noUsage.calls === 1, "no-usage provider must actually execute once");
  assert(
    noUsageResponse.output === "success-without-usage",
    "no-usage provider output drift",
  );
  assert(
    usageEvents.length === beforeNoUsageEvents,
    "success without response.usage unexpectedly emitted usage event",
  );

  const beforeFailureEvents = usageEvents.length;
  let failureError = "";
  try {
    await gateway.generate({
      agentId,
      provider: "groq",
      request: {
        prompt: "throwing-provider-call",
        model: "throw-model",
      },
    });
  } catch (error) {
    failureError = String(error);
  }
  const failureDecision = latestDecision(context);

  assert(
    String(failureDecision.decision).toUpperCase() === "ALLOW",
    "throwing provider must pass pre-execution authorization",
  );
  assert(
    failureError.includes("synthetic-provider-failure"),
    "provider failure must propagate",
  );
  assert(throwing.calls === 1, "throwing provider must be invoked once");
  assert(
    usageEvents.length === beforeFailureEvents,
    "provider failure unexpectedly emitted a failed usage event",
  );

  const report = {
    system_case: SYSTEM_CASE,
    status: "OBSERVED",
    upstream: {
      repository: "aegisora-ai/aegisora",
      commit: UPSTREAM_COMMIT,
    },
    usage_bridge: {
      configured: true,
      workspace_id: "workspace-execution-evidence",
    },
    cases: {
      blocked_rebind: {
        decision: decisionView(rebindDecision),
        error: rebindError,
        approved_provider_calls: withUsage.calls === 1 ? 0 : withUsage.calls,
        rebound_provider_calls: reboundTarget.calls,
        usage_events_after_case: 0,
      },
      success_with_usage: {
        decision: decisionView(approvedDecision),
        provider_calls: withUsage.calls,
        response_provider: approvedResponse.provider,
        response_model: approvedResponse.model,
        usage_event: usageView(approvedUsage),
        correlation_match: {
          trace_id: approvedUsage.traceId === approvedDecision.traceId,
          decision_id: approvedUsage.decisionId === approvedDecision.decisionId,
          execution_id: approvedUsage.executionId === approvedDecision.executionId,
          evidence_id: approvedUsage.evidenceId === approvedDecision.evidenceId,
        },
      },
      success_without_usage: {
        decision: decisionView(noUsageDecision),
        provider_calls: noUsage.calls,
        output: noUsageResponse.output,
        usage_events_before: beforeNoUsageEvents,
        usage_events_after: usageEvents.length,
      },
      provider_failure: {
        decision: decisionView(failureDecision),
        provider_calls: throwing.calls,
        error: failureError,
        usage_events_before: beforeFailureEvents,
        usage_events_after: usageEvents.length,
      },
    },
    findings: {
      usage_bearing_success_has_correlated_post_execution_event: true,
      canonical_provider_and_model_ignore_response_identity_spoof: true,
      success_without_usage_has_no_post_execution_usage_event: true,
      provider_failure_has_no_failed_post_execution_usage_event: true,
    },
    claim_ceiling:
      "Characterizes the optional EnterpriseUsageRuntimeBridge on one pinned Aegisora provider path with inert local providers. It does not establish a general execution receipt for every provider outcome, recipient identity, settlement binding, or production-provider behavior.",
  };

  report.cases.blocked_rebind.approved_provider_calls = 0;

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
