import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import {ConformanceReportError, validateConformanceReport, validateConformanceReportJson} from "../src/index.js";

const raw = await readFile(new URL("../../testdata/pass-report.json", import.meta.url), "utf8");
const fixture = () => JSON.parse(raw);

test("accepts the complete pinned non-authorizing report", () => {
  const summary = validateConformanceReportJson(raw);
  assert.equal(summary.valid, true);
  assert.equal(summary.passed, 14);
  assert.equal(summary.mayAuthorizeAction, false);
});

for (const [name, mutate] of [
  ["authority escalation", report => { report.authority.mayAuthorizeAction = true; }],
  ["suite drift", report => { report.suiteSha256 = "0".repeat(64); }],
  ["count mismatch", report => { report.counts.passed = 13; }],
  ["reported side effect", report => { report.results[0].sideEffectExecuted = true; }],
  ["unsafe acceptance", report => { report.results[1].observedSemantics = "UNSAFE_ACCEPTED"; }],
  ["missing case", report => { report.results.pop(); }],
  ["unknown root field", report => { report.authorization = "ALLOW"; }],
]) {
  test(`rejects ${name}`, () => {
    const report = fixture();
    mutate(report);
    assert.throws(() => validateConformanceReport(report), ConformanceReportError);
  });
}

test("rejects duplicate object keys before JSON.parse can collapse them", () => {
  const ambiguous = `{"schema":"duplicate",${raw.trimStart().slice(1)}`;
  assert.throws(() => validateConformanceReportJson(ambiguous), /duplicate object key/);
});
