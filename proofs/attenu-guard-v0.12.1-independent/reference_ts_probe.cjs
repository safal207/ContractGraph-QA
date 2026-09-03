#!/usr/bin/env node
"use strict";

/** Score exact official v1.2 cases with one extracted TypeScript release.
 *
 * The replay driver verifies and freezes the fixture and package bytes before
 * sending selected official case objects over stdin. This probe records only
 * observations; the driver owns the before/after expectations.
 */

const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");

if (process.argv.length !== 4) {
  throw new Error("usage: reference_ts_probe.cjs PACKAGE_DIR EXPECTED_VERSION");
}

const vectorContract = "bundle_vectors_v1";
const vectorRevision = "bundle_vectors_v1.2";
const caseCanonicalization = "sorted-key compact JSON UTF-8";
const packageDir = path.resolve(process.argv[2]);
const expectedVersion = process.argv[3];
const attenu = require(packageDir);

if (attenu.VERSION !== expectedVersion) {
  throw new Error(
    `loaded attenu-guard ${JSON.stringify(attenu.VERSION)}, ` +
      `expected ${JSON.stringify(expectedVersion)}`,
  );
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, stable(value[key])]),
    );
  }
  return value;
}

function canonicalSha256(value) {
  return createHash("sha256")
    .update(JSON.stringify(stable(value)), "utf8")
    .digest("hex");
}

function observe(caseRecord) {
  const signerConfig = caseRecord.signer;
  if (
    signerConfig === null ||
    typeof signerConfig !== "object" ||
    signerConfig.alg !== "HS256"
  ) {
    throw new Error(`${JSON.stringify(caseRecord.name)}: unsupported signer`);
  }
  const signer = new attenu.HS256TestSigner(
    Buffer.from(signerConfig.secret_hex, "hex"),
    signerConfig.kid,
  );
  const report = attenu.verifyBundle(caseRecord.bundle, signer);
  return {
    name: caseRecord.name,
    case_sha256: canonicalSha256(caseRecord),
    bundle_sha256: canonicalSha256(caseRecord.bundle),
    decision: report.ok ? "accept" : "reject",
    checks: {
      anchor: report.checks.anchor,
      containment: report.checks.containment,
      integrity: report.checks.integrity,
      monotonicity: report.checks.monotonicity,
    },
    failure_details: report.failure_details,
    failure_positions: report.failure_details.map((failure) => ({
      reason: failure.reason,
      seq: failure.seq,
      node: failure.node,
    })),
  };
}

const document = JSON.parse(fs.readFileSync(0, "utf8"));
if (document.version !== vectorContract) throw new Error("vector contract mismatch");
if (document.revision !== vectorRevision) throw new Error("vector revision mismatch");
if (!Array.isArray(document.cases)) throw new Error("stdin has no case list");

const output = {
  implementation: "typescript",
  package: "attenu-guard",
  version: attenu.VERSION,
  runtime: {
    node: process.version,
    platform: process.platform,
    arch: process.arch,
  },
  fixture: {
    contract: document.version,
    revision: document.revision,
    sha256: document.fixture_sha256,
  },
  case_canonicalization: caseCanonicalization,
  cases: document.cases.map(observe),
};

process.stdout.write(`${JSON.stringify(stable(output), null, 2)}\n`);
