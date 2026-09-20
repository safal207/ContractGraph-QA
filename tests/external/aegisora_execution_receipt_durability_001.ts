import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";

import { ProviderExecutionGateway } from "../src/providers/provider-execution-gateway";
import { RuntimeContext } from "../src/context/runtime-context";
import { PermissionEngine } from "../src/permissions";
import { ApprovalEngine } from "../src/approval";

type CaseName =
  | "effect_then_crash"
  | "crash_before_effect"
  | "unavailable_readback";

const SYSTEM_CASE = "EXECUTION-RECEIPT-DURABILITY-001";

const CASE_CONFIG: Record<
  CaseName,
  {
    provider: "openai" | "gemini" | "groq";
    target: string;
    request: {
      prompt: string;
      model: string;
    };
  }
> = {
  effect_then_crash: {
    provider: "openai",
    target: "provider:openai",
    request: {
      prompt: "durable-effect-then-crash",
      model: "durable-model-a",
    },
  },
  crash_before_effect: {
    provider: "gemini",
    target: "provider:gemini",
    request: {
      prompt: "durable-crash-before-effect",
      model: "durable-model-b",
    },
  },
  unavailable_readback: {
    provider: "groq",
    target: "provider:groq",
    request: {
      prompt: "durable-unavailable-readback",
      model: "durable-model-c",
    },
  },
};

function assert(
  condition: unknown,
  message: string,
): asserts condition {
  if (!condition) {
    throw new Error(
      SYSTEM_CASE + " ASSERTION_FAILED: " + message,
    );
  }
}

function parseArgs(): Record<string, string> {
  const out: Record<string, string> = {};
  const argv = process.argv.slice(2);

  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];

    assert(
      typeof key === "string" &&
      key.startsWith("--") &&
      typeof value === "string",
      "arguments must be --key value pairs",
    );

    out[key.slice(2)] = value;
  }

  return out;
}

function canonicalize(value: unknown): unknown {
  if (value === null) {
    return null;
  }

  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }

  if (typeof value === "object") {
    const object =
      value as Record<string, unknown>;

    return Object.fromEntries(
      Object.keys(object)
        .sort()
        .map(
          (key) => [
            key,
            canonicalize(object[key]),
          ],
        ),
    );
  }

  return value;
}

function digest(value: unknown): string {
  return createHash("sha256")
    .update(
      JSON.stringify(
        canonicalize(value),
      ),
    )
    .digest("hex");
}

function runHelper(
  helper: string,
  args: string[],
): string {
  const proc = spawnSync(
    "python3",
    [helper, ...args],
    {
      encoding: "utf8",
      stdio: [
        "ignore",
        "pipe",
        "pipe",
      ],
    },
  );

  if (proc.status !== 0) {
    throw new Error(
      [
        "durability helper failed",
        "argv=" + [helper, ...args].join(" "),
        "status=" + String(proc.status),
        "stdout=" + (proc.stdout?.trim() || "<empty>"),
        "stderr=" + (proc.stderr?.trim() || "<empty>"),
      ].join("\n"),
    );
  }

  return proc.stdout.trim();
}

class CrashProvider {
  calls = 0;

  constructor(
    private readonly caseName: CaseName,
    private readonly actionId: string,
    private readonly target: string,
    private readonly payloadDigest: string,
    private readonly effectDb: string,
    private readonly helper: string,
  ) {}

  async generate(
    _request: unknown,
    _context: unknown,
  ): Promise<never> {
    this.calls += 1;

    runHelper(
      this.helper,
      [
        "attempt-write",
        "--effect-db",
        this.effectDb,
        "--action-id",
        this.actionId,
        "--case",
        this.caseName,
        "--target",
        this.target,
        "--payload-digest",
        this.payloadDigest,
      ],
    );

    if (
      this.caseName ===
      "crash_before_effect"
    ) {
      process.kill(
        process.pid,
        "SIGKILL",
      );

      return await new Promise<never>(
        () => {},
      );
    }

    runHelper(
      this.helper,
      [
        "effect-write",
        "--effect-db",
        this.effectDb,
        "--action-id",
        this.actionId,
        "--case",
        this.caseName,
        "--target",
        this.target,
        "--payload-digest",
        this.payloadDigest,
      ],
    );

    runHelper(
      this.helper,
      [
        "effect-verify",
        "--effect-db",
        this.effectDb,
        "--action-id",
        this.actionId,
        "--expected-count",
        "1",
        "--target",
        this.target,
        "--payload-digest",
        this.payloadDigest,
      ],
    );

    process.kill(
      process.pid,
      "SIGKILL",
    );

    return await new Promise<never>(
      () => {},
    );
  }
}

async function main() {
  const args = parseArgs();

  const caseName =
    args["case"] as CaseName;

  assert(
    caseName in CASE_CONFIG,
    "unknown case",
  );

  const actionId =
    args["action-id"];

  const receiptDb =
    args["receipt-db"];

  const effectDb =
    args["effect-db"];

  const helper =
    args["helper"];

  const suppliedPayloadDigest =
    args["payload-digest"];

  assert(actionId, "missing action-id");
  assert(receiptDb, "missing receipt-db");
  assert(effectDb, "missing effect-db");
  assert(helper, "missing helper");
  assert(
    suppliedPayloadDigest,
    "missing payload-digest",
  );

  const cfg =
    CASE_CONFIG[caseName];

  const computedPayloadDigest =
    digest({
      target: cfg.target,
      action: "provider.generate",
      request: cfg.request,
    });

  assert(
    computedPayloadDigest ===
      suppliedPayloadDigest,
    "payload digest does not match canonical request",
  );

  const context =
    new RuntimeContext();

  const agentId =
    "durability-auditor";

  context.agentRegistry.register({
    id: agentId,
    name: agentId,
  });

  const gateway =
    new ProviderExecutionGateway(
      context,
      undefined,
      undefined,
      new PermissionEngine(),
      undefined,
      new ApprovalEngine(),
    );

  const provider =
    new CrashProvider(
      caseName,
      actionId,
      cfg.target,
      computedPayloadDigest,
      effectDb,
      helper,
    );

  const router =
    (gateway as any).router;

  const token =
    (gateway as any)
      .providerExecutionToken;

  router.register(
    cfg.provider,
    provider,
    token,
  );

  gateway.configureEnterpriseAudit({
    workspaceId:
      "execution-receipt-durability",
    writer: {
      create(input: any) {
        if (
          input.decision ===
          "ALLOW"
        ) {
          assert(
            input.resource ===
              cfg.target,
            "ALLOW audit target drift",
          );

          assert(
            input.action ===
              "provider.generate",
            "ALLOW audit action drift",
          );

          runHelper(
            helper,
            [
              "pending-write",
              "--receipt-db",
              receiptDb,
              "--action-id",
              actionId,
              "--case",
              caseName,
              "--target",
              cfg.target,
              "--payload-digest",
              computedPayloadDigest,
              "--trace-id",
              String(
                input.traceId,
              ),
              "--decision-id",
              String(
                input.decisionId,
              ),
              "--execution-id",
              String(
                input.executionId,
              ),
              "--evidence-id",
              String(
                input.evidenceId,
              ),
            ],
          );

          runHelper(
            helper,
            [
              "pending-verify",
              "--receipt-db",
              receiptDb,
              "--action-id",
              actionId,
            ],
          );
        }

        return JSON.parse(
          JSON.stringify(input),
        );
      },
    },
  });

  await gateway.generate({
    agentId,
    provider:
      cfg.provider,
    request:
      cfg.request,
    metadata: {
      executionReceiptDurabilityCase:
        caseName,
      executionReceiptActionId:
        actionId,
    },
  });

  throw new Error(
    "provider returned unexpectedly; SIGKILL boundary was not reached",
  );
}

main().catch(
  (error: unknown) => {
    console.error(error);
    process.exit(1);
  },
);
