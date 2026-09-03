#!/usr/bin/env node
"use strict";

/** Probe the published TypeScript package at the bundle-verifier defect boundary.
 *
 * The caller supplies an extracted npm package directory and the expected
 * version. This probe emits observations only; the replay driver owns the
 * before/after expectations.
 */

const path = require("node:path");

if (process.argv.length !== 4) {
  throw new Error("usage: reference_ts_probe.cjs PACKAGE_DIR EXPECTED_VERSION");
}

const packageDir = path.resolve(process.argv[2]);
const expectedVersion = process.argv[3];
const attenu = require(packageDir);

if (attenu.VERSION !== expectedVersion) {
  throw new Error(
    `loaded attenu-guard ${JSON.stringify(attenu.VERSION)}, ` +
      `expected ${JSON.stringify(expectedVersion)}`,
  );
}

const {
  Authority,
  AuditLog,
  GENESIS,
  Guard,
  HS256TestSigner,
  RowLimit,
  anchorFor,
  exportBundle,
  hashEntry,
  verifyBundle,
} = attenu;

const signer = new HS256TestSigner(Buffer.from("k", "utf8"), "k");
const defectCases = new Set([
  "increased_ttl",
  "loosened_ceiling",
  "unbounded_ttl",
  "dropped_ceiling",
]);

function indexOf(bundle, event) {
  const index = bundle.entries.findIndex((entry) => entry.event === event);
  if (index < 0) throw new Error(`no ${JSON.stringify(event)} entry`);
  return index;
}

function rehashAndReanchor(bundle) {
  let previous = GENESIS;
  for (const entry of bundle.entries) {
    entry.prev_hash = previous;
    const payload = {};
    for (const [key, value] of Object.entries(entry)) {
      if (key !== "hash") payload[key] = value;
    }
    entry.hash = hashEntry(previous, payload);
    previous = entry.hash;
  }
  const anchor = anchorFor(bundle.entries, signer, 0);
  anchor.verified = AuditLog.verifyAnchor(bundle.entries, anchor, signer)[0];
  bundle.anchor = anchor;
}

function makeBundle(granted) {
  const parent = new Authority({
    scopes: ["crm.read", "mail.send"],
    ceilings: [new RowLimit(100)],
    ttl: 3600,
  });
  const root = Guard.issue("orchestrator", parent, {
    chainId: "t",
    schemaVersion: 2,
  });
  const child = root.delegate(
    "summarizer",
    new Authority({ scopes: ["crm.read"], ceilings: [new RowLimit(50)], ttl: 900 }),
    "summarize",
  );
  child.complete();
  root.complete();
  const bundle = exportBundle(root.auditLog(), signer);
  bundle.entries[indexOf(bundle, "spawn")].granted = granted;
  rehashAndReanchor(bundle);
  return bundle;
}

function granted({ scopes = ["crm.read"], maxRows = 50, ttl = 900 } = {}) {
  const constraints = maxRows === null ? [] : [{ key: "max_rows", max: maxRows }];
  return { scopes, constraints, ttl };
}

function observe(name, grantedWire) {
  const report = verifyBundle(makeBundle(grantedWire), signer);
  return {
    name,
    decision: report.ok ? "accept" : "reject",
    checks: {
      anchor: report.checks.anchor,
      containment: report.checks.containment,
      integrity: report.checks.integrity,
      monotonicity: report.checks.monotonicity,
    },
    failure_positions: report.failure_details.map((failure) => ({
      reason: failure.reason,
      seq: failure.seq,
      node: failure.node,
    })),
  };
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

const cases = [
  observe("literal_subset_base", granted()),
  observe("increased_ttl", granted({ ttl: 7200 })),
  observe("loosened_ceiling", granted({ maxRows: 250 })),
  observe("unbounded_ttl", granted({ ttl: null })),
  observe("dropped_ceiling", granted({ maxRows: null })),
  observe("widened_scope_control", granted({ scopes: ["crm.read", "pay.transfer"] })),
];

const report = {
  implementation: "typescript",
  package: "attenu-guard",
  version: attenu.VERSION,
  defect_cases: Array.from(defectCases).sort(),
  cases,
};

process.stdout.write(`${JSON.stringify(stable(report), null, 2)}\n`);
