import fs from "node:fs";
import { createHash } from "node:crypto";

import { ProviderExecutionGateway } from "../src/providers/provider-execution-gateway";
import { RuntimeContext } from "../src/context/runtime-context";
import { PermissionEngine } from "../src/permissions";
import { ApprovalEngine } from "../src/approval";

const SYSTEM_CASE = "EXECUTION-RECEIPT-AEGISORA-001";
const UPSTREAM_COMMIT = "2bac618215671f6f0ac8ebddf169830d4fc0f9b3";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(SYSTEM_CASE + " ASSERTION_FAILED: " + message);
  }
}

function canonicalize(value: unknown): unknown {
  if (value === null) return null;
  if (Array.isArray(value)) return value.map(canonicalize);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

function digest(value: unknown): string {
  return createHash("sha256")
    .update(JSON.stringify(canonicalize(value)))
    .digest("hex");
}

class SuccessWithUsageProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      provider: "response-spoof",
      model: "response-spoof-model",
      output: "success-with-usage",
      usage: {
        promptTokens: 4,
        completionTokens: 2,
        totalTokens: 6,
      },
    };
  }
}

class SuccessWithoutUsageProvider {
  calls = 0;

  async generate(_request: unknown, _context: unknown) {
    this.calls += 1;
    return {
      provider: "response-spoof-no-usage",
      model: "response-spoof-no-usage-model",
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

type ReceiptPhase = "PENDING" | "TERMINAL";
type LocalOutcome = "NOT_OBSERVED" | "RETURNED_SUCCESS" | "THREW";
type ExternalEffectStatus = "UNKNOWN" | "UNVERIFIED";

interface ReceiptBinding {
  actionId: string;
  adapterCallId: string;
  target: string;
  payloadDigest: string;
  traceId: string;
  decisionId: string;
  executionId: string;
  evidenceId: string;
}

interface ExecutionReceipt {
  schema: "contractgraph.execution-receipt.v0.1";
  action_id: string;
  adapter_call_id: string;
  target: string;
  payload_digest: string;
  trace_id: string;
  decision_id: string;
  execution_id: string;
  evidence_id: string;
  phase: ReceiptPhase;
  local_outcome: LocalOutcome;
  external_effect_status: ExternalEffectStatus;
  error_digest: string | null;
  usage_present: boolean | null;
  previous_receipt_sha256: string | null;
  receipt_sha256: string;
}

class ExecutionReceiptLedger {
  readonly receipts: ExecutionReceipt[] = [];

  append(
    binding: ReceiptBinding,
    phase: ReceiptPhase,
    localOutcome: LocalOutcome,
    externalEffectStatus: ExternalEffectStatus,
    options: {
      errorDigest?: string | null;
      usagePresent?: boolean | null;
    } = {},
  ): ExecutionReceipt {
    const prior = this.receipts.filter(
      (item) => item.action_id === binding.actionId,
    );

    if (phase === "PENDING") {
      assert(prior.length === 0, "duplicate PENDING receipt");
      assert(localOutcome === "NOT_OBSERVED", "PENDING cannot claim terminal outcome");
      assert(externalEffectStatus === "UNKNOWN", "PENDING must stay UNKNOWN");
    } else {
      assert(
        prior.length === 1 && prior[0]?.phase === "PENDING",
        "TERMINAL requires one prior PENDING",
      );
      const pending = prior[0]!;
      assert(pending.target === binding.target, "terminal target mismatch");
      assert(pending.payload_digest === binding.payloadDigest, "terminal payload mismatch");
      assert(pending.trace_id === binding.traceId, "terminal trace mismatch");
      assert(pending.decision_id === binding.decisionId, "terminal decision mismatch");
      assert(pending.execution_id === binding.executionId, "terminal execution mismatch");
      assert(pending.evidence_id === binding.evidenceId, "terminal evidence mismatch");

      if (localOutcome === "THREW") {
        assert(
          externalEffectStatus === "UNKNOWN",
          "THREW must not become external absence proof",
        );
      }
      if (localOutcome === "RETURNED_SUCCESS") {
        assert(
          externalEffectStatus === "UNVERIFIED",
          "local success must remain externally unverified",
        );
      }
    }

    const unsigned = {
      schema: "contractgraph.execution-receipt.v0.1" as const,
      action_id: binding.actionId,
      adapter_call_id: binding.adapterCallId,
      target: binding.target,
      payload_digest: binding.payloadDigest,
      trace_id: binding.traceId,
      decision_id: binding.decisionId,
      execution_id: binding.executionId,
      evidence_id: binding.evidenceId,
      phase,
      local_outcome: localOutcome,
      external_effect_status: externalEffectStatus,
      error_digest: options.errorDigest ?? null,
      usage_present: options.usagePresent ?? null,
      previous_receipt_sha256:
        this.receipts.length > 0
          ? this.receipts[this.receipts.length - 1]!.receipt_sha256
          : null,
    };

    const receipt: ExecutionReceipt = {
      ...unsigned,
      receipt_sha256: digest(unsigned),
    };

    this.receipts.push(receipt);
    return receipt;
  }

  forAction(actionId: string): ExecutionReceipt[] {
    return this.receipts.filter((item) => item.action_id === actionId);
  }
}

class ExecutionReceiptAdapter {
  readonly ledger = new ExecutionReceiptLedger();
  readonly auditRecords: any[] = [];

  private readonly pendingByCallId = new Map<string, ReceiptBinding>();

  constructor(
    private readonly gateway: ProviderExecutionGateway,
  ) {
    gateway.configureEnterpriseAudit({
      workspaceId: "execution-receipt-adapter",
      writer: {
        create: (input: any) => {
          const record = JSON.parse(JSON.stringify(input));
          this.auditRecords.push(record);

          const metadata = input.metadata ?? {};
          const callId = metadata.executionReceiptAdapterCallId;
          const actionId = metadata.executionReceiptActionId;
          const payloadDigest = metadata.executionReceiptPayloadDigest;

          if (
            input.decision === "ALLOW" &&
            typeof callId === "string" &&
            typeof actionId === "string" &&
            typeof payloadDigest === "string"
          ) {
            const binding: ReceiptBinding = {
              actionId,
              adapterCallId: callId,
              target: input.resource,
              payloadDigest,
              traceId: input.traceId,
              decisionId: input.decisionId,
              executionId: input.executionId,
              evidenceId: input.evidenceId,
            };

            assert(
              !this.pendingByCallId.has(callId),
              "duplicate adapter authorization for call",
            );

            this.pendingByCallId.set(callId, binding);
            this.ledger.append(
              binding,
              "PENDING",
              "NOT_OBSERVED",
              "UNKNOWN",
            );
          }

          return record;
        },
      },
    });
  }

  async generate(input: {
    actionId: string;
    agentId: string;
    provider: "openai" | "gemini" | "groq";
    request: {
      prompt: string;
      model: string;
    };
  }) {
    const adapterCallId = "call-" + input.actionId;
    const payloadDigest = digest({
      target: "provider:" + input.provider,
      action: "provider.generate",
      request: input.request,
    });

    const metadata = {
      executionReceiptAdapterCallId: adapterCallId,
      executionReceiptActionId: input.actionId,
      executionReceiptPayloadDigest: payloadDigest,
    };

    try {
      const response = await this.gateway.generate({
        agentId: input.agentId,
        provider: input.provider,
        request: input.request,
        metadata,
      });

      const binding = this.pendingByCallId.get(adapterCallId);
      assert(binding, "ALLOW path returned without PENDING receipt");

      this.ledger.append(
        binding,
        "TERMINAL",
        "RETURNED_SUCCESS",
        "UNVERIFIED",
        {
          usagePresent: response.usage !== undefined,
        },
      );

      return response;
    } catch (error) {
      const binding = this.pendingByCallId.get(adapterCallId);

      if (binding) {
        this.ledger.append(
          binding,
          "TERMINAL",
          "THREW",
          "UNKNOWN",
          {
            errorDigest: digest({ error: String(error) }),
            usagePresent: false,
          },
        );
      }

      throw error;
    }
  }
}

function makeGateway() {
  const context = new RuntimeContext();
  const agentId = "execution-receipt-auditor";
  context.agentRegistry.register({ id: agentId, name: agentId });

  const gateway = new ProviderExecutionGateway(
    context,
    undefined,
    undefined,
    new PermissionEngine(),
    undefined,
    new ApprovalEngine(),
  );

  const withUsage = new SuccessWithUsageProvider();
  const noUsage = new SuccessWithoutUsageProvider();
  const throwing = new ThrowingProvider();

  const router = (gateway as any).router;
  const token = (gateway as any).providerExecutionToken;
  router.register("openai", withUsage, token);
  router.register("gemini", noUsage, token);
  router.register("groq", throwing, token);

  return {
    context,
    agentId,
    gateway,
    withUsage,
    noUsage,
    throwing,
  };
}

async function runNativeRed() {
  const subject = makeGateway();
  const auditEvents: any[] = [];
  const usageEvents: any[] = [];

  subject.gateway.configureEnterpriseAudit({
    workspaceId: "native-red",
    writer: {
      create(input: any) {
        const event = JSON.parse(JSON.stringify(input));
        auditEvents.push(event);
        return event;
      },
    },
  });

  subject.gateway.configureEnterpriseUsage({
    workspaceId: "native-red",
    writer: {
      async create(input: any) {
        const event = JSON.parse(JSON.stringify(input));
        usageEvents.push(event);
        return event;
      },
    },
  });

  const cases: Record<string, any> = {};

  await subject.gateway.generate({
    agentId: subject.agentId,
    provider: "openai",
    request: { prompt: "native-usage", model: "native-usage-model" },
  });

  const allowUsage = auditEvents[auditEvents.length - 1];
  const usageTerminal = usageEvents.find(
    (event) => event.executionId === allowUsage.executionId,
  );

  cases.success_with_usage = {
    allow_audit: Boolean(allowUsage && allowUsage.decision === "ALLOW"),
    terminal_execution_evidence: Boolean(usageTerminal),
    local_provider_calls: subject.withUsage.calls,
  };

  const usageCountBeforeNoUsage = usageEvents.length;
  await subject.gateway.generate({
    agentId: subject.agentId,
    provider: "gemini",
    request: { prompt: "native-no-usage", model: "native-no-usage-model" },
  });
  const allowNoUsage = auditEvents[auditEvents.length - 1];
  const noUsageTerminal = usageEvents.find(
    (event) => event.executionId === allowNoUsage.executionId,
  );

  cases.success_without_usage = {
    allow_audit: Boolean(allowNoUsage && allowNoUsage.decision === "ALLOW"),
    terminal_execution_evidence: Boolean(noUsageTerminal),
    usage_event_count_delta: usageEvents.length - usageCountBeforeNoUsage,
    local_provider_calls: subject.noUsage.calls,
  };

  const usageCountBeforeThrow = usageEvents.length;
  let throwError = "";
  try {
    await subject.gateway.generate({
      agentId: subject.agentId,
      provider: "groq",
      request: { prompt: "native-throw", model: "native-throw-model" },
    });
  } catch (error) {
    throwError = String(error);
  }
  const allowThrow = auditEvents[auditEvents.length - 1];
  const throwTerminal = usageEvents.find(
    (event) => event.executionId === allowThrow.executionId,
  );

  cases.provider_throws = {
    allow_audit: Boolean(allowThrow && allowThrow.decision === "ALLOW"),
    terminal_execution_evidence: Boolean(throwTerminal),
    usage_event_count_delta: usageEvents.length - usageCountBeforeThrow,
    local_provider_calls: subject.throwing.calls,
    error: throwError,
  };

  const terminalCoverage = Object.values(cases).filter(
    (item: any) => item.terminal_execution_evidence === true,
  ).length;

  assert(terminalCoverage === 1, "native coverage changed; expected 1/3");
  assert(
    cases.success_without_usage.terminal_execution_evidence === false,
    "native no-usage unexpectedly has terminal execution evidence",
  );
  assert(
    cases.provider_throws.terminal_execution_evidence === false,
    "native throw unexpectedly has terminal execution evidence",
  );

  return {
    verdict: "RED",
    expected_red: true,
    terminal_coverage: terminalCoverage,
    total_allowed_cases: 3,
    cases,
  };
}

async function runAdapterGreen() {
  const subject = makeGateway();
  const adapter = new ExecutionReceiptAdapter(subject.gateway);

  const cases: Record<string, any> = {};

  const usageAction = "act-adapter-success-usage";
  await adapter.generate({
    actionId: usageAction,
    agentId: subject.agentId,
    provider: "openai",
    request: { prompt: "adapter-usage", model: "adapter-usage-model" },
  });
  cases.success_with_usage = {
    provider_calls: subject.withUsage.calls,
    receipts: adapter.ledger.forAction(usageAction),
  };

  const noUsageAction = "act-adapter-success-no-usage";
  await adapter.generate({
    actionId: noUsageAction,
    agentId: subject.agentId,
    provider: "gemini",
    request: { prompt: "adapter-no-usage", model: "adapter-no-usage-model" },
  });
  cases.success_without_usage = {
    provider_calls: subject.noUsage.calls,
    receipts: adapter.ledger.forAction(noUsageAction),
  };

  const throwAction = "act-adapter-throw";
  let throwError = "";
  try {
    await adapter.generate({
      actionId: throwAction,
      agentId: subject.agentId,
      provider: "groq",
      request: { prompt: "adapter-throw", model: "adapter-throw-model" },
    });
  } catch (error) {
    throwError = String(error);
  }
  cases.provider_throws = {
    provider_calls: subject.throwing.calls,
    error: throwError,
    receipts: adapter.ledger.forAction(throwAction),
  };

  for (const name of ["success_with_usage", "success_without_usage"]) {
    const receipts = cases[name].receipts as ExecutionReceipt[];
    assert(receipts.length === 2, name + " must have PENDING + TERMINAL");
    assert(receipts[0]?.phase === "PENDING", name + " first receipt must be PENDING");
    assert(
      receipts[0]?.local_outcome === "NOT_OBSERVED" &&
      receipts[0]?.external_effect_status === "UNKNOWN",
      name + " PENDING must stay epistemically unknown",
    );
    assert(receipts[1]?.phase === "TERMINAL", name + " terminal missing");
    assert(
      receipts[1]?.local_outcome === "RETURNED_SUCCESS",
      name + " terminal outcome drift",
    );
    assert(
      receipts[1]?.external_effect_status === "UNVERIFIED",
      name + " local success was promoted to external truth",
    );
    assert(
      receipts[0]?.trace_id === receipts[1]?.trace_id &&
      receipts[0]?.decision_id === receipts[1]?.decision_id &&
      receipts[0]?.execution_id === receipts[1]?.execution_id &&
      receipts[0]?.evidence_id === receipts[1]?.evidence_id,
      name + " terminal correlation IDs drifted",
    );
  }

  const throwReceipts = cases.provider_throws.receipts as ExecutionReceipt[];
  assert(throwReceipts.length === 2, "throw must have PENDING + TERMINAL");
  assert(throwReceipts[0]?.phase === "PENDING", "throw first receipt must be PENDING");
  assert(
    throwReceipts[1]?.phase === "TERMINAL" &&
    throwReceipts[1]?.local_outcome === "THREW",
    "throw terminal outcome drift",
  );
  assert(
    throwReceipts[1]?.external_effect_status === "UNKNOWN",
    "provider throw must not prove external absence",
  );
  assert(
    typeof throwReceipts[1]?.error_digest === "string",
    "throw receipt must retain error digest",
  );

  assert(subject.withUsage.calls === 1, "adapter usage provider calls drift");
  assert(subject.noUsage.calls === 1, "adapter no-usage provider calls drift");
  assert(subject.throwing.calls === 1, "adapter throwing provider calls drift");

  return {
    verdict: "GREEN",
    expected_green: true,
    terminal_coverage: 3,
    total_allowed_cases: 3,
    receipt_count: adapter.ledger.receipts.length,
    cases,
  };
}

async function main() {
  const evidenceOut = process.env.EVIDENCE_OUT;
  assert(evidenceOut, "EVIDENCE_OUT must be set");

  const native = await runNativeRed();
  const adapter = await runAdapterGreen();

  assert(native.verdict === "RED", "native subject must reproduce expected RED");
  assert(adapter.verdict === "GREEN", "adapter must satisfy GREEN contract");

  const report = {
    system_case: SYSTEM_CASE,
    status: "PASS",
    upstream: {
      repository: "aegisora-ai/aegisora",
      commit: UPSTREAM_COMMIT,
    },
    contract: {
      pending_semantics:
        "Authorization creates PENDING/UNKNOWN evidence, not proof that provider execution occurred.",
      terminal_success_semantics:
        "RETURNED_SUCCESS records local provider return only; external effect remains UNVERIFIED.",
      terminal_throw_semantics:
        "THREW records local exception only; external effect remains UNKNOWN and requires reconciliation.",
      usage_independence:
        "Terminal receipt is required regardless of response.usage presence.",
    },
    native,
    adapter,
    red_green:
      "RED(native current execution evidence coverage) -> GREEN(minimal external receipt adapter)",
    claim_ceiling:
      "The adapter is an external bounded proof over one pinned provider gateway. It does not patch Aegisora, prove crash-atomic receipt durability, authoritative external effects, recipient identity, or settlement binding.",
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
