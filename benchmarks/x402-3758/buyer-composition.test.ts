// Test-only overlay for packages/extensions/test at the exact draft source below.
// Synthetic payments and publicly known deterministic test seeds; no wallet/network I/O.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { x402Client, x402HTTPClient } from "@x402/core/client";
import {
  decodePaymentResponseHeader,
  decodePaymentSignatureHeader,
  encodePaymentRequiredHeader,
  encodePaymentResponseHeader,
} from "@x402/core/http";
import type {
  PaymentRequired,
  PaymentRequirements,
  SchemeNetworkClient,
  SettleResponse,
} from "@x402/core/types";
import { wrapFetchWithPayment } from "../../http/fetch/src";
import {
  DELIVERY_RECEIPT,
  activeKeyEntry,
  buildKeyDirectory,
  createLocalReceiptSigner,
  createReceiptPayload,
  generateReceiptKeyPair,
  getDeliveryReceiptResult,
  sha256Hex,
  signDeliveryReceipt,
  withDeliveryReceipts,
  type KeyDirectory,
  type ReceiptKeyPair,
  type ReceiptSigner,
  type ReceiptVerificationResult,
} from "../src/delivery-receipt";

const SOURCE_SHA = "4d3f2387bd3f2db8007cca324ef8dea23264c248";
const CGQA_BASE_SHA = "f13e586ea9118e026c69438b8c93d0585b8e38ba";
const ISSUER = "https://buyer-composition.example";
const RESOURCE = `${ISSUER}/body`;
const DIRECTORY_URL = `${ISSUER}/.well-known/x402-receipt-keys`;
const NOW = 1_790_473_960;
const BODY = new TextEncoder().encode('{"synthetic":"paid body","unicode":"π"}\r\n');
const CONTENT_TYPE = "application/json";
const requirements: PaymentRequirements = {
  scheme: "exact",
  network: "eip155:8453",
  asset: `0x${"2".repeat(40)}`,
  payTo: `0x${"3".repeat(40)}`,
  amount: "10",
  maxTimeoutSeconds: 60,
  extra: {},
};
const paymentRequired: PaymentRequired = {
  x402Version: 2,
  resource: { url: RESOURCE, mimeType: CONTENT_TYPE },
  accepts: [requirements],
  extensions: {
    [DELIVERY_RECEIPT]: {
      info: {
        version: 1,
        issuer: ISSUER,
        keyDirectory: DIRECTORY_URL,
        algorithms: ["ed25519", "ml-dsa-65"],
        deliveryMode: "body",
      },
    },
  },
};

let governanceEd: ReceiptKeyPair;
let directory: KeyDirectory;
let signers: ReceiptSigner[];
const evidence: unknown[] = [];
let deniedNetwork: ReturnType<typeof vi.fn>;

beforeAll(async () => {
  // These public seeds are test vectors, never operational credentials.
  const seed = (n: number) => new Uint8Array(32).fill(n);
  governanceEd = await generateReceiptKeyPair("ed25519", seed(1));
  const governancePq = await generateReceiptKeyPair("ml-dsa-65", seed(1));
  const receiptEd = await generateReceiptKeyPair("ed25519", seed(2));
  const receiptPq = await generateReceiptKeyPair("ml-dsa-65", seed(2));
  signers = [createLocalReceiptSigner(receiptEd), createLocalReceiptSigner(receiptPq)];
  directory = await buildKeyDirectory({
    issuer: ISSUER,
    publishedAt: NOW - 86_400,
    governance: [governanceEd, governancePq],
    keys: [activeKeyEntry(receiptEd, NOW - 86_400), activeKeyEntry(receiptPq, NOW - 86_400)],
  });
});

beforeEach(() => {
  vi.useFakeTimers({ now: NOW * 1000, toFake: ["Date"] });
  deniedNetwork = vi.fn(async () => {
    throw new Error("Real fetch is forbidden in this synthetic buyer-composition fixture");
  });
  vi.stubGlobal("fetch", deniedNetwork);
});

afterEach(() => {
  expect(deniedNetwork).not.toHaveBeenCalled();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

afterAll(() => {
  const output = process.env.CGQA_EVIDENCE_OUTPUT;
  if (!output) return;
  expect(evidence).toHaveLength(3);
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(
    output,
    JSON.stringify(
      {
        schema: "x402-3758-body-buyer-composition/1",
        source_repository: "johnInarti/x402",
        source_sha: SOURCE_SHA,
        cgqa_base_sha: CGQA_BASE_SHA,
        overlay_sha256: createHash("sha256")
          .update(readFileSync(fileURLToPath(import.meta.url)))
          .digest("hex"),
        node: process.version,
        synthetic_receipt_clock_seconds: NOW,
        public_test_seeds: {
          governance: 1,
          receipt: 2,
          bytes: 32,
          generation: "fill",
        },
        body_hex: Buffer.from(BODY).toString("hex"),
        live_network: "DENIED",
        cases: evidence,
        pass_count: evidence.length,
        negative_control: "DETECTED_UNSAFE_OUTER_REINVOCATION; not internal SDK retry",
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
});

/**
 * Composes the native buyer with an independently counted synthetic transport.
 *
 * @param validReceipt - Whether the adapter returns a signed body receipt
 * @returns Native buyer and its retained observations
 */
function fixture(validReceipt: boolean) {
  const counts = {
    buyer: 0,
    unpaid: 0,
    payload: 0,
    paid: 0,
    syntheticSettlement: 0,
    receiptResult: 0,
    responseHook: 0,
    directory: 0,
  };
  const trace: Array<Record<string, unknown>> = [];
  const transactions: string[] = [];
  const captures: Array<{
    receipt: ReceiptVerificationResult;
    settle: SettleResponse;
    rawSettlementHeader: string;
    response: Response;
  }> = [];
  const record = (event: string, data: Record<string, unknown> = {}) => {
    trace.push({
      sequence: trace.length + 1,
      event,
      counts: { ...counts },
      ...data,
    });
  };
  const scheme: SchemeNetworkClient = {
    scheme: "exact",
    async createPaymentPayload(version, selected) {
      expect(version).toBe(2);
      expect(selected).toEqual(requirements);
      counts.payload++;
      record("synthetic_payload_created", { payloadAttempt: counts.payload });
      return {
        x402Version: version,
        payload: { syntheticAttempt: counts.payload },
      };
    },
  };
  const client = new x402Client().register(requirements.network, scheme).setSpendControls(false);
  client.onPaymentResponse(async context => {
    counts.responseHook++;
    record("native_payment_response_hook", { settle: context.settleResponse });
  });
  const httpClient = new x402HTTPClient(client);
  // Observe calls without replacing native processPaymentResult behavior.
  const paymentResultCalls = vi.spyOn(httpClient, "processPaymentResult");
  const syntheticFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    if (request.url === DIRECTORY_URL) {
      counts.directory++;
      record("synthetic_directory_read");
      return new Response(JSON.stringify(directory), {
        headers: { "content-type": CONTENT_TYPE },
      });
    }
    expect(request.url).toBe(RESOURCE);
    expect(request.method).toBe("GET");
    const header = request.headers.get("PAYMENT-SIGNATURE");
    if (!header) {
      counts.unpaid++;
      record("unpaid_dispatch_402");
      return new Response(null, {
        status: 402,
        headers: {
          "PAYMENT-REQUIRED": encodePaymentRequiredHeader(paymentRequired),
        },
      });
    }
    const payment = decodePaymentSignatureHeader(header);
    expect(payment.accepted).toEqual(requirements);
    expect(payment.payload.syntheticAttempt).toBe(counts.payload);
    expect(payment.extensions?.[DELIVERY_RECEIPT]).toEqual(
      paymentRequired.extensions?.[DELIVERY_RECEIPT],
    );
    counts.paid++;
    record("paid_dispatch", {
      payloadAttempt: payment.payload.syntheticAttempt,
    });
    // Independent adapter counter: not inferred from receipt/settlement-header validity.
    counts.syntheticSettlement++;
    const transaction = `0x${"a".repeat(62)}${counts.syntheticSettlement.toString(16).padStart(2, "0")}`;
    transactions.push(transaction);
    record("synthetic_settlement_applied", { transaction });
    const settle: SettleResponse = {
      success: true,
      transaction,
      network: requirements.network,
      payer: `0x${"1".repeat(40)}`,
    };
    if (validReceipt) {
      const payload = createReceiptPayload({
        issuer: ISSUER,
        resourceUrl: request.url,
        method: request.method,
        requirements,
        settle,
        paymentPayload: payment,
        responseStatus: 200,
        responseContentType: CONTENT_TYPE,
        delivery: { mode: "body", sha256: await sha256Hex(BODY) },
        directory,
        issuedAt: NOW,
      });
      expect(payload).not.toBeNull();
      const { receipt } = await signDeliveryReceipt(payload!, signers);
      settle.extensions = { [DELIVERY_RECEIPT]: { info: { receipt } } };
    }
    record("paid_response_returned", {
      transaction,
      receiptIncluded: validReceipt,
    });
    return new Response(BODY, {
      status: 200,
      headers: {
        "content-type": CONTENT_TYPE,
        "PAYMENT-RESPONSE": encodePaymentResponseHeader(settle),
      },
    });
  }) as typeof fetch;
  const fetchWithReceipt = withDeliveryReceipts(syntheticFetch, {
    pinnedGovernanceKeys: [governanceEd.publicKeyB64],
    requireValidReceipt: true,
    onResult(result, context) {
      // Native callback is synchronous: clone now, consume only after the caller settles.
      const rawSettlementHeader = context.response.headers.get("PAYMENT-RESPONSE")!;
      captures.push({
        receipt: structuredClone(result),
        settle: decodePaymentResponseHeader(rawSettlementHeader),
        rawSettlementHeader,
        response: context.response.clone(),
      });
      counts.receiptResult++;
      record("receipt_onResult", {
        receipt: structuredClone(result),
        reportedSettlement: captures.at(-1)!.settle,
      });
    },
  });
  const nativeBuyer = wrapFetchWithPayment(fetchWithReceipt, httpClient);
  /**
   * Records one complete outer invocation, including the unpaid 402 exchange.
   *
   * @returns Native buyer response, or its unchanged receipt error
   */
  async function buyer() {
    counts.buyer++;
    record("outer_buyer_invoked");
    return nativeBuyer(RESOURCE);
  }
  return {
    buyer,
    counts,
    trace,
    transactions,
    captures,
    record,
    paymentResultCalls,
  };
}

/**
 * Reopens the clones captured synchronously before strict receipt rejection.
 *
 * @param f - Completed fixture
 * @returns Receipt verdicts, reported settlements and exact body bytes
 */
async function preserveBodies(f: ReturnType<typeof fixture>) {
  const retained = [];
  for (const capture of f.captures) {
    const body = new Uint8Array(await capture.response.arrayBuffer());
    expect(body).toEqual(BODY);
    expect(capture.settle.success).toBe(true); // Adapter statement, not authoritative chain proof.
    expect(decodePaymentResponseHeader(capture.rawSettlementHeader)).toEqual(capture.settle);
    retained.push({
      receipt: capture.receipt,
      reportedSettlement: capture.settle,
      rawSettlementHeader: capture.rawSettlementHeader,
      bodyHex: Buffer.from(body).toString("hex"),
    });
  }
  return retained;
}

/**
 * Checks missing-receipt evidence separately from the adapter settlement witness.
 *
 * @param f - Current fixture state
 * @param attempts - Literal expected complete buyer invocation count
 */
function assertMissing(f: ReturnType<typeof fixture>, attempts: number) {
  expect(f.counts).toEqual({
    buyer: attempts,
    unpaid: attempts,
    payload: attempts,
    paid: attempts,
    syntheticSettlement: attempts,
    receiptResult: attempts,
    responseHook: 0,
    directory: 0,
  });
  expect(f.paymentResultCalls).not.toHaveBeenCalled();
  expect(f.captures).toHaveLength(attempts);
  for (const capture of f.captures) {
    expect(capture.receipt).toMatchObject({
      valid: false,
      levels: {
        integrity: false,
        authentic: null,
        trusted: null,
        settlement: null,
        delivery: null,
      },
      reasons: [{ level: "integrity", code: "RECEIPT_MISSING" }],
    });
    expect(capture.settle.success).toBe(true);
  }
  expect(new Set(f.transactions).size).toBe(attempts);
}

describe("#3758: body-mode buyer composition on exact draft source", () => {
  it("valid receipt returns exact body after one payment and normal response hook", async () => {
    const f = fixture(true);
    const response = await f.buyer();
    f.record("outer_return");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(BODY);
    expect(getDeliveryReceiptResult(response)).toMatchObject({
      valid: true,
      levels: {
        integrity: true,
        authentic: true,
        trusted: true,
        settlement: true,
        delivery: true,
      },
    });
    expect(f.counts).toEqual({
      buyer: 1,
      unpaid: 1,
      payload: 1,
      paid: 1,
      syntheticSettlement: 1,
      receiptResult: 1,
      responseHook: 1,
      directory: 1,
    });
    expect(f.paymentResultCalls).toHaveBeenCalledOnce();
    expect(f.trace.map(t => t.event)).toEqual([
      "outer_buyer_invoked",
      "unpaid_dispatch_402",
      "synthetic_payload_created",
      "paid_dispatch",
      "synthetic_settlement_applied",
      "paid_response_returned",
      "synthetic_directory_read",
      "receipt_onResult",
      "native_payment_response_hook",
      "outer_return",
    ]);
    evidence.push({
      case: "valid-receipt-positive",
      outcome: "RETURN",
      counts: f.counts,
      transactions: f.transactions,
      captures: await preserveBodies(f),
      trace: f.trace,
      assertions: "PASS_WITHIN_BOUND",
    });
  });

  it("strict missing receipt preserves settlement/body through onResult and an outer HOLD", async () => {
    const f = fixture(false);
    let error: Error | undefined;
    try {
      await f.buyer();
      throw new Error("Expected strict receipt failure");
    } catch (caught) {
      error = caught as Error;
      f.record("outer_catch", {
        error: { name: error.name, message: error.message },
      });
    }
    expect(error?.message).toContain("invalid receipt (RECEIPT_MISSING)");
    expect(error?.message).toContain(f.transactions[0]);
    assertMissing(f, 1);
    f.record("outer_HOLD_no_reinvocation");
    expect(f.trace.map(t => t.event)).toEqual([
      "outer_buyer_invoked",
      "unpaid_dispatch_402",
      "synthetic_payload_created",
      "paid_dispatch",
      "synthetic_settlement_applied",
      "paid_response_returned",
      "receipt_onResult",
      "outer_catch",
      "outer_HOLD_no_reinvocation",
    ]);
    evidence.push({
      case: "missing-receipt-evidence-aware-HOLD",
      outcome: "HOLD",
      counts: f.counts,
      transactions: f.transactions,
      error: { name: error!.name, message: error!.message },
      captures: await preserveBodies(f),
      trace: f.trace,
      assertions: "PASS_WITHIN_BOUND",
    });
  });

  it("detects two synthetic settlements when an unsafe outer catch reinvokes the whole buyer once", async () => {
    const f = fixture(false);
    const errors: Array<{ name: string; message: string }> = [];
    try {
      await f.buyer();
    } catch (caught) {
      const error = caught as Error;
      expect(error.message).toContain("invalid receipt (RECEIPT_MISSING)");
      errors.push({ name: error.name, message: error.message });
      f.record("unsafe_outer_catch", { error: errors[0] });
      assertMissing(f, 1);
      f.record("unsafe_outer_reinvoke_once");
      try {
        await f.buyer();
      } catch (retryCaught) {
        const retryError = retryCaught as Error;
        expect(retryError.message).toContain("invalid receipt (RECEIPT_MISSING)");
        errors.push({ name: retryError.name, message: retryError.message });
        f.record("unsafe_outer_second_catch", { error: errors[1] });
      }
    }
    expect(errors).toHaveLength(2);
    assertMissing(f, 2);
    expect(f.transactions[0]).not.toBe(f.transactions[1]);
    const paidPath = [
      "outer_buyer_invoked",
      "unpaid_dispatch_402",
      "synthetic_payload_created",
      "paid_dispatch",
      "synthetic_settlement_applied",
      "paid_response_returned",
      "receipt_onResult",
    ];
    expect(f.trace.map(t => t.event)).toEqual([
      ...paidPath,
      "unsafe_outer_catch",
      "unsafe_outer_reinvoke_once",
      ...paidPath,
      "unsafe_outer_second_catch",
    ]);
    f.record("unsafe_control_detected");
    evidence.push({
      case: "unsafe-outer-reinvocation-negative",
      outcome: "DETECTED_UNSAFE_CONTROL",
      counts: f.counts,
      transactions: f.transactions,
      errors,
      captures: await preserveBodies(f),
      trace: f.trace,
      assertions: "PASS_WITHIN_BOUND; expected unsafe application control detected",
    });
  });
});
