const MAX_REPORT_BYTES = 1_048_576;
const SCHEMA = "org.contractgraph-qa.liminalqa-interop-conformance-result.v0.1";
const SUITE_ID = "cgqa-liminalqa-v0.1";
const SUITE_VERSION = "0.1.0";
const SUITE_SHA256 = "562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac";
const CLAIM_BOUNDARY = "Synthetic conformance verifies adapter behavior only for these pinned fixtures and mutations. It does not verify a production system, prove security or completeness, authorize an action, or replace independent replay against the exact subject.";

const CONTRACT_PINS = new Map([
  ["cgqa-evidence", {
    artifactSchema: "org.contractgraph-qa.liminalqa-evidence.v0.1",
    artifactProfile: "org.contractgraph-qa.bounded-invariant-evidence.v0.1",
    ownerRepository: "safal207/ContractGraph-QA",
    producerCommit: "bdf7ced074e3a7baf57cf89ac68be9674bd76a02",
    schemaSha256: "53b0b4a0b1f4d77de26b8be9dbb90006ea0bd30c5cd3960a2f3e7d44d9664184",
    fixtureSha256: "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce",
  }],
  ["liminal-candidates", {
    artifactSchema: "org.liminalqa.cgqa-candidates.v0.1",
    artifactProfile: "org.liminalqa.non-authoritative-candidate-seeds.v0.1",
    ownerRepository: "safal207/LiminalQAengineer",
    producerCommit: "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3",
    schemaSha256: "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60",
    fixtureSha256: "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3",
  }],
]);

const CASE_PINS = new Map([
  ["cgqa-evidence-golden", ["cgqa-evidence", "golden", "VALID_NON_AUTHORIZING", "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce"]],
  ["cgqa-evidence-authority-escalation", ["cgqa-evidence", "authority_escalation", "INVALID_BLOCKED", "33eb3122738032c3ebc1043f5058bc7a9cc469c6ecff8ad0a602aaa3a80067ce"]],
  ["cgqa-evidence-count-mismatch", ["cgqa-evidence", "semantic_mismatch", "INVALID_BLOCKED", "3f348306ba20fdb780b662ec3aadbdf8d1a805a1d81cb2eb66103824e9f8b95f"]],
  ["cgqa-evidence-temporal-inversion", ["cgqa-evidence", "temporal_inversion", "INVALID_BLOCKED", "dbc7d64eda4aeb497bf360e10335896b3f9b4316973306e37a8a21134cc85ba8"]],
  ["cgqa-evidence-unknown-authority-field", ["cgqa-evidence", "unknown_field", "INVALID_BLOCKED", "49d7eab11be2a4fc5b90776a9822156573ef5753bff25e674629fdb8e742edea"]],
  ["cgqa-evidence-unsafe-causal-parent", ["cgqa-evidence", "unsafe_identifier", "INVALID_BLOCKED", "e50dfe383bbd2577b72dba043bbe129b6370b81ec8226d6fa9ed206bf6bf51af"]],
  ["cgqa-evidence-duplicate-schema-key", ["cgqa-evidence", "ambiguous_json", "INVALID_BLOCKED", "6ff810788c268a93af16daa7a814cfe84616542951de92be8dbe79aabf3d41c9"]],
  ["liminal-candidates-golden", ["liminal-candidates", "golden", "VALID_NON_AUTHORIZING", "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3"]],
  ["liminal-candidates-authority-escalation", ["liminal-candidates", "authority_escalation", "INVALID_BLOCKED", "261570efc9e6c13d46686a6f5941ee7d39db620c4603cf30a64e0f0baae3abff"]],
  ["liminal-candidates-unknown-authority-field", ["liminal-candidates", "unknown_field", "INVALID_BLOCKED", "1a3841322a8dae89e793f92cedcf341c5fafa4a70e308426d76f674434291941"]],
  ["liminal-candidates-missing-independent-replay", ["liminal-candidates", "verification_weakening", "INVALID_BLOCKED", "8030649160511f62065f4ba33d703fb4dcbf96bc25480d8fa9c7d4e85d715423"]],
  ["liminal-candidates-debt-mismatch", ["liminal-candidates", "semantic_mismatch", "INVALID_BLOCKED", "172a1567897dc4a78deaf2c9f50bc6634e59d2d671ab23d414ca8b4a089f8185"]],
  ["liminal-candidates-unsafe-causal-parent", ["liminal-candidates", "unsafe_identifier", "INVALID_BLOCKED", "61b8e74f52248e50fc90e0765b6cc0449ea5b588cb6aa525d148dcb9ac447960"]],
  ["liminal-candidates-duplicate-schema-key", ["liminal-candidates", "ambiguous_json", "INVALID_BLOCKED", "9bf53f54b15a2eb09731c28dfffc5ba39f7c04b0d5fa4d076f300f8107ae2d40"]],
]);

export class ConformanceReportError extends Error {
  constructor(message) {
    super(message);
    this.name = "ConformanceReportError";
  }
}

function fail(path, message) {
  throw new ConformanceReportError(`${path}: ${message}`);
}

function object(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "must be an object");
  }
  return value;
}

function exactKeys(value, expected, path) {
  const actual = Object.keys(object(value, path)).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    fail(path, `fields must be exactly: ${wanted.join(", ")}`);
  }
}

function equal(actual, expected, path) {
  if (actual !== expected) fail(path, `must equal ${JSON.stringify(expected)}`);
}

function nonBlank(value, path) {
  if (typeof value !== "string" || value.trim().length === 0) fail(path, "must be a non-blank string");
}

function safeId(value, path) {
  nonBlank(value, path);
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/.test(value)) fail(path, "must be a safe identifier");
}

function validateContractPins(pins) {
  if (!Array.isArray(pins) || pins.length !== CONTRACT_PINS.size) fail("contractPins", "must contain both pinned contracts");
  const seen = new Set();
  pins.forEach((pin, index) => {
    const path = `contractPins[${index}]`;
    exactKeys(pin, ["id", "artifactSchema", "artifactProfile", "ownerRepository", "producerCommit", "schemaSha256", "fixtureSha256"], path);
    const expected = CONTRACT_PINS.get(pin.id);
    if (!expected || seen.has(pin.id)) fail(`${path}.id`, "must identify one unique pinned contract");
    seen.add(pin.id);
    for (const [key, value] of Object.entries(expected)) equal(pin[key], value, `${path}.${key}`);
  });
}

function validateResults(results) {
  if (!Array.isArray(results) || results.length !== CASE_PINS.size) fail("results", "must contain all 14 pinned case results");
  const seen = new Set();
  results.forEach((result, index) => {
    const path = `results[${index}]`;
    exactKeys(result, ["id", "contract", "category", "status", "expectedSemantics", "observedSemantics", "inputSha256", "diagnostic", "sideEffectExecuted"], path);
    const expected = CASE_PINS.get(result.id);
    if (!expected || seen.has(result.id)) fail(`${path}.id`, "must identify one unique pinned case");
    seen.add(result.id);
    equal(result.contract, expected[0], `${path}.contract`);
    equal(result.category, expected[1], `${path}.category`);
    equal(result.expectedSemantics, expected[2], `${path}.expectedSemantics`);
    equal(result.observedSemantics, expected[2], `${path}.observedSemantics`);
    equal(result.inputSha256, expected[3], `${path}.inputSha256`);
    equal(result.status, "PASS", `${path}.status`);
    equal(result.sideEffectExecuted, false, `${path}.sideEffectExecuted`);
    nonBlank(result.diagnostic, `${path}.diagnostic`);
  });
}

export function validateConformanceReport(report) {
  exactKeys(report, ["schema", "reportId", "suiteId", "suiteVersion", "suiteSha256", "implementation", "status", "counts", "contractPins", "results", "authority", "claimBoundary"], "report");
  equal(report.schema, SCHEMA, "schema");
  safeId(report.reportId, "reportId");
  equal(report.suiteId, SUITE_ID, "suiteId");
  equal(report.suiteVersion, SUITE_VERSION, "suiteVersion");
  equal(report.suiteSha256, SUITE_SHA256, "suiteSha256");
  equal(report.status, "PASS", "status");
  equal(report.claimBoundary, CLAIM_BOUNDARY, "claimBoundary");

  exactKeys(report.implementation, ["name", "version", "language"], "implementation");
  for (const key of ["name", "version", "language"]) nonBlank(report.implementation[key], `implementation.${key}`);

  exactKeys(report.counts, ["total", "passed", "failed"], "counts");
  equal(report.counts.total, 14, "counts.total");
  equal(report.counts.passed, 14, "counts.passed");
  equal(report.counts.failed, 0, "counts.failed");

  exactKeys(report.authority, ["classification", "mayAuthorizeAction"], "authority");
  equal(report.authority.classification, "conformance_evidence_only", "authority.classification");
  equal(report.authority.mayAuthorizeAction, false, "authority.mayAuthorizeAction");
  validateContractPins(report.contractPins);
  validateResults(report.results);

  return Object.freeze({
    valid: true,
    suiteId: SUITE_ID,
    implementation: Object.freeze({...report.implementation}),
    passed: 14,
    mayAuthorizeAction: false,
    claimBoundary: CLAIM_BOUNDARY,
  });
}

function parseWithoutDuplicateKeys(source) {
  let cursor = 0;
  const whitespace = /[\u0020\u000a\u000d\u0009]/;
  const skip = () => { while (cursor < source.length && whitespace.test(source[cursor])) cursor += 1; };
  const syntax = (message) => fail("json", `${message} at character ${cursor}`);

  function parseString() {
    if (source[cursor] !== '"') syntax("expected string");
    const start = cursor++;
    while (cursor < source.length) {
      const char = source[cursor++];
      if (char === '"') {
        try { return JSON.parse(source.slice(start, cursor)); }
        catch { syntax("invalid string"); }
      }
      if (char === "\\") {
        if (cursor >= source.length) syntax("unfinished escape");
        cursor += 1;
      } else if (char.charCodeAt(0) < 0x20) {
        syntax("unescaped control character");
      }
    }
    syntax("unterminated string");
  }

  function parseValue(depth) {
    if (depth > 64) syntax("maximum nesting depth exceeded");
    skip();
    const char = source[cursor];
    if (char === "{") return parseObject(depth + 1);
    if (char === "[") return parseArray(depth + 1);
    if (char === '"') { parseString(); return; }
    for (const literal of ["true", "false", "null"]) {
      if (source.startsWith(literal, cursor)) { cursor += literal.length; return; }
    }
    const number = source.slice(cursor).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (number) { cursor += number[0].length; return; }
    syntax("expected JSON value");
  }

  function parseObject(depth) {
    cursor += 1;
    skip();
    const keys = new Set();
    if (source[cursor] === "}") { cursor += 1; return; }
    while (cursor < source.length) {
      skip();
      const key = parseString();
      if (keys.has(key)) fail("json", `duplicate object key ${JSON.stringify(key)}`);
      keys.add(key);
      skip();
      if (source[cursor++] !== ":") syntax("expected colon");
      parseValue(depth);
      skip();
      const separator = source[cursor++];
      if (separator === "}") return;
      if (separator !== ",") syntax("expected comma or object end");
    }
    syntax("unterminated object");
  }

  function parseArray(depth) {
    cursor += 1;
    skip();
    if (source[cursor] === "]") { cursor += 1; return; }
    while (cursor < source.length) {
      parseValue(depth);
      skip();
      const separator = source[cursor++];
      if (separator === "]") return;
      if (separator !== ",") syntax("expected comma or array end");
    }
    syntax("unterminated array");
  }

  parseValue(0);
  skip();
  if (cursor !== source.length) syntax("unexpected trailing content");
  try { return JSON.parse(source); }
  catch (error) { fail("json", `invalid JSON: ${error.message}`); }
}

export function validateConformanceReportJson(raw) {
  if (typeof raw !== "string") fail("json", "must be a UTF-8 string");
  if (new TextEncoder().encode(raw).length > MAX_REPORT_BYTES) fail("json", `must not exceed ${MAX_REPORT_BYTES} bytes`);
  return validateConformanceReport(parseWithoutDuplicateKeys(raw));
}

export const protocol = Object.freeze({
  schema: SCHEMA,
  suiteId: SUITE_ID,
  suiteVersion: SUITE_VERSION,
  suiteSha256: SUITE_SHA256,
  maxReportBytes: MAX_REPORT_BYTES,
  mayAuthorizeAction: false,
});
